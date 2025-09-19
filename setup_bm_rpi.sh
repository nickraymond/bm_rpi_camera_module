#!/usr/bin/env bash

# === BM Camera Setup with Client-First Wi-Fi and AP Fallback ===
# Usage: sudo ./setup_ap_fallback.sh <hostname> <ap-ssid> <ap-pass> [--disable-usb] [--enable-hdmi] [--force-dhcpcd]

set -euo pipefail

NAME="${1:-}"
SSID="${2:-}"
PASSPHRASE="${3:-}"
DISABLE_USB=false
DISABLE_HDMI=true
FORCE_DHCPCD=false

for arg in "$@"; do
  case "$arg" in
    --disable-usb)    DISABLE_USB=true ;;
    --enable-hdmi)    DISABLE_HDMI=false ;;
    --force-dhcpcd)   FORCE_DHCPCD=true ;;
  esac
done

if [[ -z "$NAME" || -z "$SSID" || -z "$PASSPHRASE" ]]; then
  echo "❌ Usage: sudo $0 <hostname> <ap-ssid> <ap-pass> [--disable-usb] [--enable-hdmi] [--force-dhcpcd]"
  exit 1
fi

echo "🔧 Hostname: $NAME"
echo "📶 AP SSID: $SSID"
echo "🔑 AP Pass: $PASSPHRASE"

# ---------- Hostname ----------
echo "$NAME" | tee /etc/hostname >/dev/null
sed -i "s/^\(127\.0\.1\.1\).*/\1\t$NAME/" /etc/hosts
hostnamectl set-hostname "$NAME" || true

# ---------- Networking stack preflight ----------
# If NetworkManager is active (Bookworm default), AP via hostapd/dnsmasq will conflict.
# You can either disable NM and use dhcpcd, or use NM-native hotspot (not covered here).
if systemctl is-active --quiet NetworkManager; then
  if $FORCE_DHCPCD; then
    echo "⚠️ NetworkManager detected. Disabling it and enabling dhcpcd..."
    systemctl disable --now NetworkManager
    apt-get update
    apt-get install -y dhcpcd5
    systemctl enable --now dhcpcd
  else
    echo "❌ NetworkManager is active. Re-run with --force-dhcpcd or disable NM manually:"
    echo "   sudo systemctl disable --now NetworkManager"
    echo "   sudo apt-get install -y dhcpcd5 && sudo systemctl enable --now dhcpcd"
    exit 1
  fi
fi

# ---------- Packages ----------
echo "📦 Installing hostapd and dnsmasq..."
apt-get update
apt-get install -y hostapd dnsmasq

# Ensure AP services are disabled at boot; we only start them on fallback.
systemctl disable --now hostapd || true
systemctl disable --now dnsmasq || true

# ---------- hostapd (AP) ----------
echo "⚙️ Writing /etc/hostapd/hostapd.conf"
install -o root -g root -m 644 /dev/null /etc/hostapd/hostapd.conf
cat >/etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$SSID
country_code=US
hw_mode=g
channel=7
wmm_enabled=1
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSPHRASE
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
EOF

# Point hostapd to the config
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# ---------- dnsmasq (AP DHCP/DNS) ----------
echo "⚙️ Writing /etc/dnsmasq.d/ap.conf"
mkdir -p /etc/dnsmasq.d
install -o root -g root -m 644 /dev/null /etc/dnsmasq.d/ap.conf
cat >/etc/dnsmasq.d/ap.conf <<EOF
interface=wlan0
bind-interfaces
dhcp-range=192.168.50.50,192.168.50.150,12h
domain=$NAME.lan
dhcp-option=6,192.168.50.1
local=/$NAME.lan/
expand-hosts
EOF

# ---------- DO NOT force static IP or block wpa_supplicant in dhcpcd ----------
# If previously added, comment out an old AP block in /etc/dhcpcd.conf to allow client mode.
if grep -q '^interface wlan0$' /etc/dhcpcd.conf 2>/dev/null; then
  echo "🧹 Commenting old AP block in /etc/dhcpcd.conf (if present)"
  awk '
    BEGIN{inblk=0}
    /^interface wlan0$/ {inblk=1}
    inblk==1 {print "#" $0; if ($0 ~ /^$/) inblk=0; next}
    {print}
  ' /etc/dhcpcd.conf > /etc/dhcpcd.conf.tmp && mv /etc/dhcpcd.conf.tmp /etc/dhcpcd.conf
fi

# ---------- Fallback checker script ----------
echo "📝 Installing /usr/local/bin/wifi_check.sh"
install -o root -g root -m 755 /dev/null /usr/local/bin/wifi_check.sh
cat >/usr/local/bin/wifi_check.sh <<'EOS'
#!/bin/bash
set -euo pipefail
LOG="/var/log/wifi_check.log"
AP_IP="192.168.50.1/24"
AP_GW="192.168.50.1"

echo "[$(date -Is)] Wi-Fi check start" >> "$LOG"

# Give DHCP/client stack time to connect
sleep 30

# If we already have a default route and can ping, stay in client mode
if ip route get 8.8.8.8 >/dev/null 2>&1 && ping -c 2 -W 2 8.8.8.8 >/dev/null 2>&1; then
  echo "[$(date -Is)] Internet OK (client mode); ensuring AP services are stopped" >> "$LOG"
  systemctl stop hostapd 2>>"$LOG" || true
  systemctl stop dnsmasq 2>>"$LOG" || true
  exit 0
fi

echo "[$(date -Is)] Internet NOT available; switching to AP mode" >> "$LOG"

# Stop client stack so it doesn't fight with AP
systemctl stop wpa_supplicant 2>>"$LOG" || true
systemctl stop dhcpcd 2>>"$LOG" || true

# Bring up wlan0 with static IP
ip link set wlan0 down 2>>"$LOG" || true
ip addr flush dev wlan0 2>>"$LOG" || true
ip link set wlan0 up 2>>"$LOG" || true
ip addr add "$AP_IP" dev wlan0 2>>"$LOG" || true

# Start AP services
systemctl start dnsmasq 2>>"$LOG" || true
systemctl start hostapd 2>>"$LOG" || true

# Optional: quick NAT if eth0 is up and you want internet sharing (uncomment below)
# sysctl -w net.ipv4.ip_forward=1
# iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
# iptables -C FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
# iptables -C FORWARD -i wlan0 -o eth0 -j ACCEPT 2>/dev/null || iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

echo "[$(date -Is)] AP mode started on wlan0 ($AP_IP)" >> "$LOG"
EOS

# ---------- systemd oneshot to run checker at boot ----------
echo "⚙️ Creating systemd unit wifi-fallback.service"
cat >/etc/systemd/system/wifi-fallback.service <<'EOF'
[Unit]
Description=Wi-Fi Client->AP Fallback
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/wifi_check.sh
RemainAfterExit=yes
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wifi-fallback.service

# ---------- Low-power & camera tweaks (kept from your original) ----------
CONFIG_TXT="/boot/config.txt"
echo "⚡ Applying low-power & camera settings..."
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' "$CONFIG_TXT" || true
grep -qxF 'core_freq=250' "$CONFIG_TXT" || tee -a "$CONFIG_TXT" > /dev/null <<EOF

# --- Low Power Headless Optimizations ---
core_freq=250
disable_splash=1
boot_delay=0
dtoverlay=disable-bt
# dtoverlay=disable-wifi
enable_tvout=0
dtparam=act_led_trigger=heartbeat
dtparam=pwr_led_trigger=none
gpu_mem=16
EOF

grep -qxF 'start_x=1' "$CONFIG_TXT" || tee -a "$CONFIG_TXT" > /dev/null <<EOF

# Enable camera for libcamera stack
start_x=1
camera_auto_detect=1
dtoverlay=imx708
EOF

# ---------- Optional HDMI/USB toggles ----------
if $DISABLE_HDMI; then
  echo "🔌 Disabling HDMI (if supported)..."
  /usr/bin/tvservice -o || echo "⚠️ tvservice not supported"
else
  echo "ℹ️ HDMI left enabled."
fi

if $DISABLE_USB; then
  echo "❌ Disabling USB ports (unbind usb1)..."
  echo 'usb1' | tee /sys/bus/usb/drivers/usb/unbind || echo "⚠️ USB unbind not available"
else
  echo "✅ USB will remain enabled."
fi

# ---------- Misc ----------
echo "🧠 Disabling swap..."
sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=0/' /etc/dphys-swapfile || true
systemctl stop dphys-swapfile || true
systemctl disable dphys-swapfile || true

echo "💻 Setting CLI boot..."
systemctl set-default multi-user.target || true

echo "🔄 Restarting Avahi..."
systemctl restart avahi-daemon || true

echo "✅ Setup complete."
echo "   • Hostname: $NAME  (mDNS: $NAME.local)"
echo "   • AP SSID:  $SSID"
echo "   • Reboot recommended: sudo reboot"
