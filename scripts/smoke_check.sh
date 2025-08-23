cat > scripts/smoke_check.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

IMDIR="/home/pi/bm_camera/camera_software/images"
VIDDIR="/home/pi/bm_camera/camera_software/videos"

echo "[check] last 1 image:"
ls -lt "$IMDIR" | head -n 2 || true

echo
echo "[check] last 1 video:"
ls -lt "$VIDDIR" | head -n 2 || true

echo
echo "[check] count of videos modified in last 60s:"
find "$VIDDIR" -maxdepth 1 -type f -mmin -1 -name '*.mp4' | wc -l
SH
chmod +x scripts/smoke_check.sh
