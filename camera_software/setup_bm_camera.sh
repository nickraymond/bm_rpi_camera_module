#!/usr/bin/env bash
set -euo pipefail

# ---------- styling ----------
GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; CYAN="\033[36m"; BOLD="\033[1m"; NC="\033[0m"
ok(){ echo -e "${GREEN}✔${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠${NC} $*"; }
err(){ echo -e "${RED}✖${NC} $*"; }
info(){ echo -e "${CYAN}ℹ${NC} $*"; }

# ---------- defaults you can change ----------
REPO_URL_DEFAULT="https://github.com/nickraymond/bm_rpi_camera_module.git"
BRANCH_DEFAULT="main"
SUBDIR_DEFAULT="camera_software"
DEST_DEFAULT="$HOME/bm_camera"
REQS_PATH_DEFAULT="/home/pi/bm_camera/camera_software/requirements.txt"  # per your note
PY_PKGS="git python3 python3-pip python3-venv python3-dev build-essential python3-apt"
CAM_PKGS="libcamera-apps python3-picamera2"
UART_TOOLS="picocom"
MISC_PKGS="raspi-config jq"
REBOOT_REQUIRED=0

# ---------- helpers ----------
ensure_pkg(){
  local pkgs=("$@")
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
}

append_or_replace_kv(){
  # append_or_replace_kv <file> <key> <value>
  local file="$1" key="$2" val="$3"
  sudo mkdir -p "$(dirname "$file")"
  if [ -f "$file" ] && grep -Eq "^${key}=" "$file"; then
	sudo sed -i "s|^${key}=.*|${key}=${val}|" "$file"
  else
	echo "${key}=${val}" | sudo tee -a "$file" >/dev/null
  fi
}

pause(){ read -rp "Press Enter to continue..."; }

# ---------- 0) greet ----------
echo -e "${BOLD}BM Camera one-shot setup${NC}"
info "This script will install packages, fetch your repo subfolder, configure UART & camera, and run quick tests."

# ---------- 1) base packages ----------
info "Installing system packages (Git, Python toolchain, camera, UART tools)..."
ensure_pkg $PY_PKGS $CAM_PKGS $UART_TOOLS $MISC_PKGS
ok "Base packages installed."

# ---------- 2) SSH & Git identity ----------
# Ensure SSH server is running (safe if already enabled)
info "Ensuring SSH server is enabled and running..."
sudo systemctl enable --now ssh >/dev/null 2>&1 || true
ok "SSH server is active."

echo
read -rp "Set git identity? (y/N) " ans || true
if [[ "${ans:-N}" =~ ^[Yy]$ ]]; then
  read -rp "  Git user.name [e.g., Nick Raymond]: " GNAME
  read -rp "  Git user.email [e.g., nick@sofarocean.com]: " GEMAIL
  if [ -n "${GNAME:-}" ]; then git config --global user.name "$GNAME"; fi
  if [ -n "${GEMAIL:-}" ]; then git config --global user.email "$GEMAIL"; fi
  ok "Git identity set: $(git config --global user.name 2>/dev/null) <$(git config --global user.email 2>/dev/null)>"
fi

echo
read -rp "Generate a GitHub SSH key and show the public key? (y/N) " ans || true
if [[ "${ans:-N}" =~ ^[Yy]$ ]]; then
  mkdir -p "$HOME/.ssh"
  if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
	read -rp "  Email for SSH key comment [default: $(git config --global user.email || echo pi@raspberrypi)]: " KEYMAIL
	ssh-keygen -t ed25519 -C "${KEYMAIL:-pi@raspberrypi}" -f "$HOME/.ssh/id_ed25519" -N ""
	ok "SSH key generated."
  else
	warn "SSH key already exists, reusing."
  fi
  info "Add the following PUBLIC key to GitHub → Settings → SSH and GPG keys:"
  echo "----- BEGIN PUBLIC KEY -----"
  cat "$HOME/.ssh/id_ed25519.pub"
  echo "----- END PUBLIC KEY -----"
  read -rp "Test SSH to GitHub now? (y/N) " t || true
  if [[ "${t:-N}" =~ ^[Yy]$ ]]; then
	ssh -T git@github.com || true
  fi
fi

# ---------- 3) repo inputs ----------
echo
read -rp "Repo URL [default: $REPO_URL_DEFAULT]: " REPO_URL
REPO_URL="${REPO_URL:-$REPO_URL_DEFAULT}"

read -rp "Branch name [default: $BRANCH_DEFAULT]: " BRANCH
BRANCH="${BRANCH:-$BRANCH_DEFAULT}"

read -rp "Subfolder to check out [default: $SUBDIR_DEFAULT]: " SUBDIR
SUBDIR="${SUBDIR:-$SUBDIR_DEFAULT}"

read -rp "Destination directory [default: $DEST_DEFAULT]: " DEST
DEST="${DEST:-$DEST_DEFAULT}"

ok "Using: REPO=$REPO_URL  BRANCH=$BRANCH  SUBDIR=$SUBDIR  DEST=$DEST"

# ---------- 4) sparse-checkout the subfolder ----------
info "Fetching only '$SUBDIR' from $BRANCH..."
mkdir -p "$DEST"
cd "$DEST"
if [ ! -d ".git" ]; then
  git init
  git remote add origin "$REPO_URL"
fi
git fetch origin "$BRANCH"
git sparse-checkout init --cone
git sparse-checkout set "$SUBDIR"
git checkout -B "$BRANCH" "origin/$BRANCH"
ok "Subfolder checked out at: $DEST/$SUBDIR"

# ---------- 5) Python venv + requirements ----------
REQS_PATH_INPUT="$REQS_PATH_DEFAULT"
read -rp "Path to requirements.txt [default: $REQS_PATH_DEFAULT]: " RIN || true
REQS_PATH_INPUT="${RIN:-$REQS_PATH_DEFAULT}"

if [ ! -f "$REQS_PATH_INPUT" ]; then
  err "requirements.txt not found at $REQS_PATH_INPUT"
  exit 1
fi

cd "$REQS_PATH_INPUT"
cd "$(dirname "$REQS_PATH_INPUT")"

info "Creating virtual environment (with system site packages so python-apt works)..."
python3 -m venv .venv --system-site-packages
# shellcheck disable=SC1091
source .venv/bin/activate
python -V
ok "Venv active: $(which python)"

info "Installing Python requirements (skipping python-apt if pinned there)..."
python -m pip install --upgrade pip wheel setuptools
# Skip python-apt in pip (installed via apt), install others
grep -v -E '^\s*python-apt(\s|==|$)' "$(basename "$REQS_PATH_INPUT")" | python -m pip install -r /dev/stdin
ok "Python dependencies installed."

# ---------- 6) UART setup ----------
info "Configuring UART (enable port, disable login console/getty, set groups)..."

# Detect config path (Bookworm: /boot/firmware/config.txt, older: /boot/config.txt)
CONFIG_PATH="/boot/firmware/config.txt"
[ -f "$CONFIG_PATH" ] || CONFIG_PATH="/boot/config.txt"

append_or_replace_kv "$CONFIG_PATH" "enable_uart" "1"
ok "Set enable_uart=1 in $CONFIG_PATH"

# Disable serial console on common UART devices
for SVC in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
  sudo systemctl stop "$SVC" >/dev/null 2>&1 || true
  sudo systemctl disable "$SVC" >/dev/null 2>&1 || true
done
ok "Disabled serial-getty on ttyAMA0/ttyS0 (if present)."

# Use raspi-config to ensure 'no login shell' on serial and HW UART enabled
if command -v raspi-config >/dev/null 2>&1; then
  # 0 = disable shell, 1 = enable HW serial
  sudo raspi-config nonint do_serial 1 || true
  ok "raspi-config serial setting applied."
fi

# Add user to groups
sudo usermod -aG dialout,video "$USER" || true
ok "User added to groups: dialout, video"
REBOOT_REQUIRED=1

# Quick device view
ls -l /dev/serial* /dev/ttyAMA* /dev/ttyS* 2>/dev/null || true

# ---------- 7) Camera quick test ----------
info "Testing camera CLI (creates /tmp/test.jpg)..."
if rpicam-still -o /tmp/test.jpg --timeout 1000 >/dev/null 2>&1; then
  ok "Camera CLI test succeeded (/tmp/test.jpg)."
else
  warn "Camera CLI test failed. This can be normal over headless SSH (no display). Try rpicam-still again after reboot or check cabling."
fi

# Minimal Picamera2 still capture test
info "Testing Picamera2 capture (may fail headless, ignore if you don't need preview)..."
python - <<'PY' || true
from time import sleep
try:
	from picamera2 import Picamera2
	picam = Picamera2()
	picam.configure(picam.create_still_configuration())
	picam.start()
	sleep(1)
	picam.capture_file("/tmp/picam2_test.jpg")
	picam.stop()
	print("OK: Captured /tmp/picam2_test.jpg")
except Exception as e:
	print("WARN: Picamera2 quick test failed:", e)
PY

# ---------- 8) UART sanity test ----------
info "UART quick check..."
if [ -e /dev/serial0 ]; then
  ok "/dev/serial0 present."
else
  warn "/dev/serial0 not found. Check config/cabling after reboot."
fi

# Check if something is holding the port
sudo lsof /dev/serial0 /dev/ttyAMA0 /dev/ttyS0 2>/dev/null || true

# ---------- 9) Summary ----------
echo
echo -e "${BOLD}Summary:${NC}"
echo -e "  Repo:     ${CYAN}$REPO_URL${NC}  branch ${CYAN}$BRANCH${NC}  subdir ${CYAN}$SUBDIR${NC}"
echo -e "  Code at:  ${CYAN}$DEST/$SUBDIR${NC}"
echo -e "  Venv:     ${CYAN}$DEST/$SUBDIR/.venv${NC}"
echo -e "  UART:     enable_uart=1; user in groups dialout,video"
echo -e "  Camera:   test file(s) in ${CYAN}/tmp/test.jpg / /tmp/picam2_test.jpg${NC} (if succeeded)"
echo

if [ $REBOOT_REQUIRED -eq 1 ]; then
  warn "A reboot is recommended for UART group changes & config to take effect."
  read -rp "Reboot now? (y/N) " r || true
  if [[ "${r:-N}" =~ ^[Yy]$ ]]; then
	sudo reboot
  fi
fi

ok "Setup complete."
