#!/usr/bin/env bash
set -euo pipefail

# ---------- styling ----------
GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; CYAN="\033[36m"; BOLD="\033[1m"; NC="\033[0m"
ok(){ echo -e "${GREEN}✔${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠${NC} $*"; }
err(){ echo -e "${RED}✖${NC} $*"; }
info(){ echo -e "${CYAN}ℹ${NC} $*"; }

# ---------- defaults ----------
REPO_URL_DEFAULT="https://github.com/nickraymond/bm_rpi_camera_module.git"
BRANCH_DEFAULT="main"
SUBDIR_DEFAULT="camera_software"
DEST_DEFAULT="$HOME/bm_camera"
REQS_PATH_DEFAULT="/home/pi/bm_camera/camera_software/requirements.txt"
PY_PKGS="git python3 python3-pip python3-venv python3-dev build-essential python3-apt"
CAM_PKGS="libcamera-apps python3-picamera2"
UART_TOOLS="picocom"
MISC_PKGS="raspi-config jq"
REBOOT_REQUIRED=0

# ---------- helpers ----------
ensure_pkg(){
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

append_or_replace_kv(){
  local file="$1" key="$2" val="$3"
  sudo mkdir -p "$(dirname "$file")"
  if [ -f "$file" ] && grep -Eq "^${key}=" "$file"; then
	sudo sed -i "s|^${key}=.*|${key}=${val}|" "$file"
  else
	echo "${key}=${val}" | sudo tee -a "$file" >/dev/null
  fi
}

# ---------- greet ----------
echo -e "${BOLD}BM Camera one-shot setup${NC}"
info "Installing packages, fetching repo, setting up UART & camera..."

# ---------- install system packages ----------
ensure_pkg $PY_PKGS $CAM_PKGS $UART_TOOLS $MISC_PKGS
ok "Base packages installed."

# ---------- SSH ----------
sudo systemctl enable --now ssh >/dev/null 2>&1 || true
ok "SSH server is active."

# ---------- git identity ----------
read -rp "Set git identity? (y/N) " ans || true
if [[ "${ans:-N}" =~ ^[Yy]$ ]]; then
  read -rp "  Git user.name: " GNAME
  read -rp "  Git user.email: " GEMAIL
  [ -n "$GNAME" ] && git config --global user.name "$GNAME"
  [ -n "$GEMAIL" ] && git config --global user.email "$GEMAIL"
  ok "Git identity set."
fi

# ---------- repo clone ----------
read -rp "Repo URL [default: $REPO_URL_DEFAULT]: " REPO_URL
REPO_URL="${REPO_URL:-$REPO_URL_DEFAULT}"
read -rp "Branch [default: $BRANCH_DEFAULT]: " BRANCH
BRANCH="${BRANCH:-$BRANCH_DEFAULT}"
read -rp "Subfolder [default: $SUBDIR_DEFAULT]: " SUBDIR
SUBDIR="${SUBDIR:-$SUBDIR_DEFAULT}"
read -rp "Destination dir [default: $DEST_DEFAULT]: " DEST
DEST="${DEST:-$DEST_DEFAULT}"

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
ok "Checked out $SUBDIR from $BRANCH."

# ---------- python venv + requirements ----------
REQS_PATH_INPUT="$REQS_PATH_DEFAULT"
read -rp "Path to requirements.txt [default: $REQS_PATH_DEFAULT]: " RIN || true
REQS_PATH_INPUT="${RIN:-$REQS_PATH_DEFAULT}"

if [ ! -f "$REQS_PATH_INPUT" ]; then
  err "requirements.txt not found at $REQS_PATH_INPUT"
  exit 1
fi

cd "$(dirname "$REQS_PATH_INPUT")"
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
grep -v -E '^\s*python-apt(\s|==|$)' "$(basename "$REQS_PATH_INPUT")" | python -m pip install -r /dev/stdin
ok "Python dependencies installed."

# ---------- UART setup ----------
CONFIG_PATH="/boot/firmware/config.txt"
[ -f "$CONFIG_PATH" ] || CONFIG_PATH="/boot/config.txt"
append_or_replace_kv "$CONFIG_PATH" "enable_uart" "1"

for SVC in serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
  sudo systemctl stop "$SVC" >/dev/null 2>&1 || true
  sudo systemctl disable "$SVC" >/dev/null 2>&1 || true
done

if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_serial 1 || true
fi

sudo usermod -aG dialout,video "$USER" || true
REBOOT_REQUIRED=1
ok "UART configured."

# ---------- camera test ----------
if rpicam-still -o /tmp/test.jpg --timeout 1000 >/dev/null 2>&1; then
  ok "Camera CLI test succeeded (/tmp/test.jpg)."
else
  warn "Camera CLI test failed. Try again after reboot or check cabling."
fi

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
	print("OK: Picamera2 capture /tmp/picam2_test.jpg")
except Exception as e:
	print("WARN: Picamera2 test failed:", e)
PY

# ---------- summary ----------
echo
echo -e "${BOLD}Setup complete.${NC}"
echo -e "Repo:     ${CYAN}$REPO_URL${NC}"
echo -e "Branch:   ${CYAN}$BRANCH${NC}"
echo -e "Subdir:   ${CYAN}$SUBDIR${NC}"
echo -e "Code at:  ${CYAN}$DEST/$SUBDIR${NC}"
echo -e "Venv:     ${CYAN}$(dirname "$REQS_PATH_INPUT")/.venv${NC}"
[ $REBOOT_REQUIRED -eq 1 ] && warn "Reboot recommended for UART/camera changes."
