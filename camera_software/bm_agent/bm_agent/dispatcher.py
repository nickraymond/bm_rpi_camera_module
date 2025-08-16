from .handlers import rtc
try:
	from .handlers import led
	_HAS_LED = True
except Exception:
	_HAS_LED = False

def build_dispatch(cfg):
	topics = cfg["topics"]
	table = {
		topics.get("rtc"): rtc.handle,
	}
	if _HAS_LED and topics.get("led"):
		table[topics["led"]] = led.handle
	# Clean out None keys (in case a topic wasn’t configured)
	return {k: v for k, v in table.items() if k}

def init_handlers(cfg):
	ctx = {
		"led_pin": cfg["led"]["pin"],
	}
	if _HAS_LED:
		led.init(ctx)
	return ctx

def cleanup_handlers(ctx):
	if _HAS_LED:
		led.cleanup(ctx)
