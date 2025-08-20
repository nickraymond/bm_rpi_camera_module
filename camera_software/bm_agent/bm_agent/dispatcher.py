from .handlers import rtc
from .handlers import clock
from .handlers import test_pi  # <— add

def build_dispatch(cfg):
	topics = cfg.get("topics", {})
	table = {}
	
	# existing rtc/clock mapping (example)
	rtc_topic = topics.get("rtc")
	if rtc_topic:
		def _rtc_and_clock(node, topic, data, ctx):
			rtc.handle(node, topic, data, ctx)
			clock.handle(node, topic, data, ctx)
		table[rtc_topic] = _rtc_and_clock
	
	# NEW mapping for test/pi
	test_topic = topics.get("test_pi")
	if test_topic:
		table[test_topic] = lambda n, t, d, c: test_pi.handle(n, t, d, c)
	
	return {k: v for k, v in table.items() if k}

def init_handlers(cfg):
	ctx = {"cfg": cfg}
	clock.init(ctx)
	test_pi.init(ctx)   # <— add
	return ctx

def cleanup_handlers(ctx):
	test_pi.cleanup(ctx)  # <— add
	clock.cleanup(ctx)