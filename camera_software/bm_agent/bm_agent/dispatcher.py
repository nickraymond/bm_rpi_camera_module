# from .handlers import rtc
# from .handlers import clock  # NEW
# 
# 
# try:
# 	from .handlers import led
# 	_HAS_LED = True
# except Exception:
# 	_HAS_LED = False
# 
# def build_dispatch(cfg):
# 		topics = cfg["topics"]
# 		table = {
# 			topics.get("rtc"): rtc.handle,
# 		}
# 		# Use the same RTC topic for clock sync; it just decides when to act
# 		if cfg.get("clock", {}).get("enabled", True) and topics.get("rtc"):
# 			table[topics["rtc"]] = lambda node, topic, data, ctx: (
# 				rtc.handle(node, topic, data, ctx),
# 				clock.handle(node, topic, data, ctx),
# 			)
# 		return {k: v for k, v in table.items() if k}
# 	
# 	def init_handlers(cfg):
# 		ctx = {"cfg": cfg}
# 		clock.init(ctx)   # NEW
# 		return ctx
# 	
# 	def cleanup_handlers(ctx):
# 		clock.cleanup(ctx)
from .handlers import rtc
from .handlers import clock

def build_dispatch(cfg):
	topics = cfg["topics"]
	table = {}

	rtc_topic = topics.get("rtc")
	if rtc_topic:
		# fan-out: log RTC AND feed the clock sync
		def _rtc_and_clock(node, topic, data, ctx):
			rtc.handle(node, topic, data, ctx)
			clock.handle(node, topic, data, ctx)
		table[rtc_topic] = _rtc_and_clock

	return {k: v for k, v in table.items() if k}

def init_handlers(cfg):
	ctx = {"cfg": cfg}
	clock.init(ctx)
	return ctx

def cleanup_handlers(ctx):
	clock.cleanup(ctx)
