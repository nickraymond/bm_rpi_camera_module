
# Placeholder camera handlers (text-only)

## 1) Add topics to config.yaml
camera_software/bm_agent/config.yaml:
```yaml
topics:
  camera_capture_image: camera/capture/image
  camera_capture_video: camera/capture/video
```

## 2) Wire into dispatcher.py
In camera_software/bm_agent/bm_agent/dispatcher.py add:

```python
from .handlers import capture_image_cmd, capture_video_cmd

def build_dispatch(cfg):
    topics = cfg.get("topics", {})
    table = {}

    img_topic = topics.get("camera_capture_image")
    if img_topic:
        table[img_topic] = lambda n,t,d,c: capture_image_cmd.handle(n,t,d,c)

    vid_topic = topics.get("camera_capture_video")
    if vid_topic:
        table[vid_topic] = lambda n,t,d,c: capture_video_cmd.handle(n,t,d,c)

    return {k: v for k, v in table.items() if k}

def init_handlers(cfg):
    ctx = {"cfg": cfg}
    capture_image_cmd.init(ctx)
    capture_video_cmd.init(ctx)
    return ctx

def cleanup_handlers(ctx):
    capture_video_cmd.cleanup(ctx)
    capture_image_cmd.cleanup(ctx)
```

(If your dispatcher already has other handlers, keep them; just insert these imports and entries.)

## 3) Run the agent
```bash
python /home/pi/bm_camera/camera_software/bm_agent/run_agent.py
```

## 4) Test from BM CLI (text 0 framing)
Avoid spaces (the CLI splits on spaces). Use underscores/hyphens.

```bash
bm pub camera/capture/image 1 text 0
bm pub camera/capture/image hello_from_nick text 0

bm pub camera/capture/video 1 text 0
bm pub camera/capture/video test_video_placeholder text 0
```

Expected Pi output:
```
[CAM/IMG] placeholder TRIGGER: would call image_capture.py()
[CAM/IMG] placeholder MESSAGE: 'hello_from_nick'
[CAM/VID] placeholder TRIGGER: would call video_capture.py()
[CAM/VID] placeholder MESSAGE: 'test_video_placeholder'
```
