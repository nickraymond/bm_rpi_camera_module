#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Settings (override via flags)
# -----------------------------
GIT_URL=""
BRANCH=""           # optional
REPO_DIR_NAME="bm_camera"   # cloned into ~/$REPO_DIR_NAME

# -----------------------------
# Parse flags
# -----------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
	--repo)    GIT_URL="$2"; shift 2 ;;
	--branch)  BRANCH="$2";  shift 2 ;;
	--name)    REPO_DIR_NAME="$2"; shift 2 ;;
	*) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

if [[ -z "${GIT_URL}" ]]; then
  echo "Usage: $0 --repo <GIT_URL> [--branch <branch>] [--name <dir>]"
  exit 2
fi

# -----------------------------
# Resolve paths/users
# -----------------------------
PI_USER="${SUDO_USER:-$USER}"
HOME_DIR="$(eval echo ~${PI_USER})"
BASE_DIR="${HOME_DIR}/${REPO_DIR_NAME}"
AGENT_DIR="${BASE_DIR}/camera_software/bm_agent"
VENV_DIR="${AGENT_DIR}/.venv"
SERVICE_NAME="bm-agent.service"

echo "[*] Running as user: ${PI_USER}"
echo "[*] Target repo dir: ${BASE_DIR}"

# -----------------------------
# Basic prereqs
# -----------------------------
command -v git >/dev/null || { echo "git missing. Installing..."; sudo apt update && sudo apt install -y git; }
command -v python3 >/dev/null || { echo "python3 missing. Please install Raspberry Pi OS with Python3."; exit 1; }

echo "[*] Installing apt packages..."
sudo apt update
sudo apt install -y python3-venv python3-dev lsof

# -----------------------------
# UART sanity checks
# -----------------------------
UART_DEVICE="/dev/serial0"
NEED_REBOOT=0

if [[ ! -e "${UART_DEVICE}" ]]; then
  echo ""
  echo "[WARN] ${UART_DEVICE} is missing. UART likely not enabled."
  echo "       You must run raspi-config to enable the serial hardware and disable the login shell."
  echo "       Steps:"
  echo "         sudo raspi-config"
  echo "           → Interface Options → Serial Port"
  echo "           → 'Login shell over serial?'  → No"
  echo "           → 'Enable serial port hardware?' → Yes"
  echo "         sudo reboot"
  echo ""
  echo "   (Advanced) Check these files:"
  echo "     /boot/firmware/config.txt or /boot/config.txt → ensure 'enable_uart=1'"
  echo "     /boot/firmware/cmdline.txt or /boot/cmdline.txt → must NOT include 'console=serial0,115200'"
  exit 3
fi

# Is serial-getty still grabbing the port?
if systemctl is-active --quiet "serial-getty@ttyAMA0.service" || systemctl is-active --quiet "serial-getty@ttyS0.service"; then
  echo ""
  echo "[WARN] A serial console (serial-getty) appears active and can block ${UART_DEVICE}."
  echo "       Disable it with:"
  echo "         sudo systemctl disable --now serial-getty@ttyAMA0.service || true"
  echo "         sudo systemctl disable --now serial-getty@ttyS0.service || true"
  echo "       Then reboot:"
  echo "         sudo reboot"
  echo ""
  # Don't exit—some images still work with serial0 → ttyAMA0 and getty disabled already. Just warn.
fi

# Dialout group check
if ! id -nG "${PI_USER}" | grep -qw dialout; then
  echo ""
  echo "[WARN] User '${PI_USER}' is not in 'dialout' group. Needed for ${UART_DEVICE}."
  echo "       Add and re-login (or reboot) for it to take effect:"
  echo "         sudo usermod -a -G dialout ${PI_USER}"
  echo "         # then log out/in or: sudo reboot"
  echo ""
fi

# -----------------------------
# Clone/update repo
# -----------------------------
if [[ -d "${BASE_DIR}/.git" ]]; then
  echo "[*] Repo exists. Updating..."
  git -C "${BASE_DIR}" fetch --all
  if [[ -n "${BRANCH}" ]]; then
	git -C "${BASE_DIR}" checkout "${BRANCH}"
	git -C "${BASE_DIR}" pull --ff-only origin "${BRANCH}" || true
  else
	git -C "${BASE_DIR}" pull --ff-only || true
  fi
else
  echo "[*] Cloning repo..."
  git clone "${GIT_URL}" "${BASE_DIR}"
  if [[ -n "${BRANCH}" ]]; then
	git -C "${BASE_DIR}" checkout "${BRANCH}"
  fi
fi

# -----------------------------
# Python venv + deps
# -----------------------------
echo "[*] Creating venv and installing Python deps..."
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install pyserial pyyaml RPi.GPIO

# -----------------------------
# Default config (if missing)
# -----------------------------
mkdir -p "${AGENT_DIR}"
if [[ ! -f "${AGENT_DIR}/config.yaml" ]]; then
  echo "[*] Writing default config.yaml..."
  cat > "${AGENT_DIR}/config.yaml" <<'YAML'
uart_device: /dev/serial0
baudrate: 115200

topics:
  rtc: "spotter/utc-time"
  led: "camera/led"

led:
  pin: 17

clock:
  enabled: true
  max_backward_seconds: 0
  apply_if_drift_seconds: 2
  min_apply_interval_seconds: 300
YAML
fi

# -----------------------------
# bm-set-time helper + sudoers
# -----------------------------
echo "[*] Installing bm-set-time helper..."
sudo tee /usr/local/sbin/bm-set-time >/dev/null <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: $0 ISO_8601_UTC_TIME" >&2
  exit 2
fi
IN="$1"
# Normalize to "YYYY-MM-DD HH:MM:SS UTC"
norm="${IN/T/ }"
norm="$(echo "$norm" | sed -E 's/\.[0-9]+//')"
norm="$(echo "$norm" | sed -E 's/Z$/ UTC/; s/\+00:?00$/ UTC/')"
if ! echo "$norm" | grep -Eq ' UTC$'; then
  norm="$norm UTC"
fi
# Toggle NTP if necessary
reenable_ntp=0
if timedatectl show -p NTP --value 2>/dev/null | grep -qi '^yes$'; then
  reenable_ntp=1
  /usr/bin/timedatectl set-ntp false
fi
/usr/bin/timedatectl set-time "$norm"
if [[ "$reenable_ntp" -eq 1 ]]; then
  /usr/bin/timedatectl set-ntp true
fi
echo "Time set to: $norm"
SH
sudo chown root:root /usr/local/sbin/bm-set-time
sudo chmod 0755 /usr/local/sbin/bm-set-time

echo "[*] Configuring sudoers for bm-set-time..."
sudo tee /etc/sudoers.d/bm-set-time >/dev/null <<SUDO
${PI_USER} ALL=(root) NOPASSWD: /usr/local/sbin/bm-set-time
SUDO
sudo chown root:root /etc/sudoers.d/bm-set-time
sudo chmod 0440 /etc/sudoers.d/bm-set-time
sudo visudo -c >/dev/null

# -----------------------------
# systemd unit
# -----------------------------
echo "[*] Installing systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME} >/dev/null <<UNIT
[Unit]
Description=Bristlemouth Agent (dispatcher for RTC/LED/Camera)
After=dev-serial0.device
Requires=dev-serial0.device

[Service]
WorkingDirectory=${AGENT_DIR}
ExecStart=${VENV_DIR}/bin/python ${AGENT_DIR}/run_agent.py
Environment=PYTHONUNBUFFERED=1
User=${PI_USER}
Group=${PI_USER}
SupplementaryGroups=dialout
Restart=always
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT

echo "[*] Enabling + starting service..."
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

echo ""
echo "== Success =="
echo "View logs:    sudo journalctl -u ${SERVICE_NAME} -f"
echo "Check clock:  date -u"
echo ""
echo "If you saw UART warnings, fix them and reboot:"
echo "  sudo raspi-config    # Serial Port: login shell=No, hardware=Yes"
echo "  sudo systemctl disable --now serial-getty@ttyAMA0.service || true"
echo "  sudo systemctl disable --now serial-getty@ttyS0.service || true"
echo "  sudo usermod -a -G dialout ${PI_USER}  # then reboot"
