# filename: video_test.py
# description: quick hardware sanity test to record a video clip

from video_capture import save_video

# Record a 3-second 720p clip into ./videos
out = save_video(base_name="TEST", duration_s=10.0, resolution_key="720p", directory_path="./videos")
print("Saved video:", out)
