#!/bin/bash
set -u

APP_DIR="/home/pi/BM_Devel_Pi"
LOG_DIR="$APP_DIR/cron_logs"

mkdir -p "$LOG_DIR"

RUN_TS="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || echo unknown_time)"
LOG_FILE="$LOG_DIR/capture_cycle_${RUN_TS}.log"

exec >> "$LOG_FILE" 2>&1

echo "============================================================"
echo "[CRON] bmcam002 capture cycle starting"
echo "[CRON] start_utc=$(date -u --iso-8601=seconds 2>/dev/null || date)"
echo "[CRON] user=$(whoami)"
echo "[CRON] pwd=$(pwd)"
echo "[CRON] app_dir=$APP_DIR"
echo "[CRON] log_file=$LOG_FILE"

# Give the Pi, UART, and BM bridge time to settle after boot.
sleep 30

cd "$APP_DIR" || exit 1

echo "[CRON] camera_schedule.yaml:"
sed -n '1,180p' camera_schedule.yaml || true

echo "[CRON] checking Python syntax..."
/usr/bin/python3 -m py_compile main_pi_camera.py process_image_v2.py spotter_time_sync.py bm_serial.py
if [ $? -ne 0 ]; then
    echo "[CRON][ERROR] Python syntax check failed"
    exit 2
fi

echo "[CRON] running production capture/transmit cycle..."
/usr/bin/python3 -u main_pi_camera.py --transmit
EXIT_CODE=$?

echo "[CRON] main_pi_camera.py exit_code=$EXIT_CODE"
echo "[CRON] end_utc=$(date -u --iso-8601=seconds 2>/dev/null || date)"
echo "============================================================"

exit $EXIT_CODE
