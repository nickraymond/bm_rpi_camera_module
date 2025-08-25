# from .handlers import rtc
# from .handlers import clock
# from .handlers import test_pi  # <— add
# from .handlers import capture_image_cmd, capture_video_cmd
# 
# 
# def build_dispatch(cfg):
# 	topics = cfg.get("topics", {})
# 	table = {}
# 	
# 	# existing rtc/clock mapping (example)
# 	rtc_topic = topics.get("rtc")
# 	if rtc_topic:
# 		def _rtc_and_clock(node, topic, data, ctx):
# 			rtc.handle(node, topic, data, ctx)
# 			clock.handle(node, topic, data, ctx)
# 		table[rtc_topic] = _rtc_and_clock
# 	
# 	# NEW mapping for test/pi
# 	test_topic = topics.get("test_pi")
# 	if test_topic:
# 		table[test_topic] = lambda n, t, d, c: test_pi.handle(n, t, d, c)
# 	
# 	return {k: v for k, v in table.items() if k}
# 	
# 	# NEW mapping for camera still image and video
# 	img_topic = topics.get("camera_capture_image")
# 	if img_topic: table[img_topic] = lambda n,t,d,c: capture_image_cmd.handle(n,t,d,c)
# 	
# 	vid_topic = topics.get("camera_capture_video")
# 	if vid_topic: table[vid_topic] = lambda n,t,d,c: capture_video_cmd.handle(n,t,d,c)
# 
# 
# def init_handlers(cfg):
# 	ctx = {"cfg": cfg}
# 	clock.init(ctx)
# 	test_pi.init(ctx)   # <— add
# 	capture_image_cmd.init(ctx)
# 	capture_video_cmd.init(ctx)
# 
# 	return ctx
# 
# def cleanup_handlers(ctx):
# 	test_pi.cleanup(ctx)  # <— add
# 	clock.cleanup(ctx)
# 	capture_video_cmd.cleanup(ctx)
# 	capture_image_cmd.cleanup(ctx)
# filename: dispatcher.py

from .handlers import rtc, clock
from .handlers import test_pi                      # if you’re using test/pi
from .handlers import capture_image_cmd, capture_video_cmd  # <-- add these

def build_dispatch(cfg):
	topics = cfg.get("topics", {})
	table = {}

	# RTC (optionally chained with clock)
	rtc_topic = topics.get("rtc")
	if rtc_topic:
		if cfg.get("clock", {}).get("enabled", False):
			def _rtc_and_clock(n, t, d, c):
				rtc.handle(n, t, d, c)
				clock.handle(n, t, d, c)
			table[rtc_topic] = _rtc_and_clock
		else:
			table[rtc_topic] = lambda n, t, d, c: rtc.handle(n, t, d, c)

	# test/pi (optional)
	test_topic = topics.get("test_pi")
	if test_topic:
		table[test_topic] = lambda n, t, d, c: test_pi.handle(n, t, d, c)

	# NEW: camera capture topics from your YAML
	img_topic = topics.get("camera_capture_image")     # camera/capture/image
	if img_topic:
		table[img_topic] = lambda n, t, d, c: capture_image_cmd.handle(n, t, d, c)

	vid_topic = topics.get("camera_capture_video")     # camera/capture/video
	if vid_topic:
		table[vid_topic] = lambda n, t, d, c: capture_video_cmd.handle(n, t, d, c)

	# return only valid keys
	return {k: v for k, v in table.items() if k}

def init_handlers(cfg):
	ctx = {"cfg": cfg}
	if cfg.get("clock", {}).get("enabled", False):
		clock.init(ctx)
	# init your handlers (no-op init is fine)
	return ctx

def cleanup_handlers(ctx):
	if ctx.get("cfg", {}).get("clock", {}).get("enabled", False):
		clock.cleanup(ctx)
