import yaml, pathlib

DEFAULTS = {
	"uart_device": "/dev/serial0",
	"baudrate": 115200,
	"topics": {},
	"led": {"pin": 17},
}

def load_config(path="config.yaml"):
	p = pathlib.Path(path)
	if not p.exists():
		return DEFAULTS
	with p.open() as f:
		loaded = yaml.safe_load(f) or {}
	out = DEFAULTS.copy()
	for k, v in loaded.items():
		if isinstance(v, dict) and isinstance(out.get(k), dict):
			out[k].update(v)
		else:
			out[k] = v
	return out
