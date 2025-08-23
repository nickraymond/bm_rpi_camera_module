mkdir -p scripts
cat > scripts/demo_publish.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# Quick publisher to exercise the agent. Adjust topics if you changed them in config.yaml.
TOPIC_IMAGE=${TOPIC_IMAGE:-camera/capture/image}
TOPIC_VIDEO=${TOPIC_VIDEO:-camera/capture/video}

echo "[demo] sending STILL (defaults)"
bm pub "$TOPIC_IMAGE" 1 text 0
sleep 3

# Use a 6s clip so we can see de-dupe working with your dynamic window
echo "[demo] sending VIDEO (6s @ 720p, 25 fps, 2 Mb/s)"
bm pub "$TOPIC_VIDEO" dur=6s,res=720p,fps=25,br=2M text 0

echo "[demo] done. Watch the agent logs and check camera_software/{images,videos}"
SH
chmod +x scripts/demo_publish.sh
