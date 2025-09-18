#!/usr/bin/env python3
"""
Refactor your Bristlemouth daemon repo to a core+plugin structure (Option B: config-listed modules).

Usage:
  python3 refactor_plugins.py /path/to/bm_rpi_camera_module.zip
  python3 refactor_plugins.py /path/to/bm_rpi_camera_module   (directory)

What it does (idempotent/safe to re-run):
  - Creates a plugin package "bm_camera" with handlers/capture/utils/encode
  - Moves camera-specific files out of bm_daemon into bm_camera (if present):
	  * bm_daemon/agent/handlers/capture_image_cmd.py -> bm_camera/handlers/capture_image_cmd.py
	  * bm_daemon/agent/handlers/capture_video_cmd.py -> bm_camera/handlers/capture_video_cmd.py
	  * bm_daemon/capture/image_capture.py            -> bm_camera/capture/image_capture.py
	  * bm_daemon/capture/video_capture.py            -> bm_camera/capture/video_capture.py
	  * bm_daemon/utils/camera_lock.py                -> bm_camera/utils/camera_lock.py
	  * bm_daemon/encode/file_encoder.py              -> bm_camera/encode/file_encoder.py
  - Adds bm_daemon/pluginspec/handler.py (Handler protocol)
  - Adds bm_daemon/agent/plugin_loader.py (loads handlers from config.yaml)
  - Patches bm_daemon/agent/run.py to merge plugin dispatch
  - Adds bm_daemon/__main__.py so `python -m bm_daemon` works
  - Ensures config.yaml includes:
		plugins:
		  - "bm_camera.handlers.capture_image_cmd:CaptureImageHandler"
		  - "bm_camera.handlers.capture_video_cmd:CaptureVideoHandler"

Output:
  - If input was a ZIP: writes <input>_refactored.zip next to the input file
  - If input was a directory: writes <dirname>_refactored.zip next to that directory

Notes:
  - Make a git branch or backup before running (recommended)
  - Script prints a summary of changes
"""

import argparse, sys, shutil, zipfile, re, tempfile, os
from pathlib import Path
from typing import Dict, List

MOVES = {
	'bm_daemon/agent/handlers/capture_image_cmd.py': 'bm_camera/handlers/capture_image_cmd.py',
	'bm_daemon/agent/handlers/capture_video_cmd.py': 'bm_camera/handlers/capture_video_cmd.py',
	'bm_daemon/capture/image_capture.py':            'bm_camera/capture/image_capture.py',
	'bm_daemon/capture/video_capture.py':            'bm_camera/capture/video_capture.py',
	'bm_daemon/utils/camera_lock.py':                'bm_camera/utils/camera_lock.py',
	'bm_daemon/encode/file_encoder.py':              'bm_camera/encode/file_encoder.py',
}

REPLACEMENTS = [
	(r'from bm_daemon\.capture', 'from bm_camera.capture'),
	(r'from bm_daemon\.encode', 'from bm_camera.encode'),
	(r'from bm_daemon\.utils\.camera_lock', 'from bm_camera.utils.camera_lock'),
]

PLUGIN_SPEC = '''from typing import Protocol, Iterable, Mapping, Any

class BusMessage(Mapping[str, Any], Protocol):
	pass

class Handler(Protocol):
	topics: Iterable[str]
	def handle(self, msg: BusMessage, *, ctx: dict) -> None: ...
'''

PLUGIN_LOADER = '''from importlib import import_module
from typing import Dict, Callable
from bm_daemon.pluginspec.handler import Handler

def load_plugin_dispatch_from_config(cfg: dict) -> Dict[str, Callable]:
	specs = cfg.get("plugins", [])
	table: Dict[str, Callable] = {}
	for spec in specs:
		modname, clsname = spec.split(":")
		mod = import_module(modname)
		cls = getattr(mod, clsname)
		inst: Handler = cls()
		for topic in getattr(inst, "topics", []):
			def _make(inst):
				def _fn(node, topic_str, data, ctx):
					inst.handle({"node": node, "topic": topic_str, "data": data}, ctx=ctx)
				return _fn
			table[str(topic)] = _make(inst)
	return table
'''

MAIN_SHIM = 'from bm_daemon.agent.run import main\nif __name__ == "__main__":\n    raise SystemExit(main())\n'

def read(p: Path) -> str:
	return p.read_text(encoding='utf-8', errors='ignore')

def write(p: Path, text: str):
	p.parent.mkdir(parents=True, exist_ok=True)
	p.write_text(text, encoding='utf-8')

def ensure_init(pkg_dir: Path):
	pkg_dir.mkdir(parents=True, exist_ok=True)
	init = pkg_dir/'__init__.py'
	if not init.exists():
		init.write_text('', encoding='utf-8')

def find_project_root(extracted_dir: Path) -> Path:
	"""Choose the top-level dir that contains bm_daemon or config.yaml."""
	candidates = [extracted_dir] + [p for p in extracted_dir.iterdir() if p.is_dir()]
	for c in candidates:
		if (c/'bm_daemon').is_dir() or (c/'config.yaml').exists():
			return c
	return extracted_dir

def refactor_dir(root: Path):
	summary = {"moved": [], "created": [], "patched": []}

	# 1) plugin skeleton
	bm_camera = root/'bm_camera'
	for sub in ('', 'handlers', 'capture', 'utils', 'encode'):
		ensure_init(bm_camera/sub if sub else bm_camera)
	summary["created"] += [str((bm_camera/sub if sub else bm_camera)/'__init__.py') for sub in ('', 'handlers', 'capture', 'utils', 'encode')]

	# 2) move files
	for s_rel, d_rel in MOVES.items():
		s = root/s_rel; d = root/d_rel
		if s.exists():
			d.parent.mkdir(parents=True, exist_ok=True)
			shutil.move(str(s), str(d))
			summary["moved"].append(f"{s_rel} -> {d_rel}")
	for maybe in (root/'bm_daemon/capture', root/'bm_daemon/agent/handlers'):
		if maybe.exists() and not any(maybe.iterdir()):
			maybe.rmdir()

	# 3) pluginspec + loader
	pluginspec = root/'bm_daemon'/'pluginspec'/'handler.py'
	if not pluginspec.exists():
		write(pluginspec, PLUGIN_SPEC); summary["created"].append(str(pluginspec))
	plugin_loader = root/'bm_daemon'/'agent'/'plugin_loader.py'
	write(plugin_loader, PLUGIN_LOADER); summary["created"].append(str(plugin_loader))

	# 4) patch run.py
	run_py = root/'bm_daemon'/'agent'/'run.py'
	if run_py.exists():
		txt = read(run_py); changed = False
		if 'load_plugin_dispatch_from_config' not in txt:
			txt = txt.replace(
				'from bm_daemon.agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers',
				'from bm_daemon.agent.dispatcher import build_dispatch, init_handlers, cleanup_handlers\nfrom bm_daemon.agent.plugin_loader import load_plugin_dispatch_from_config'
			); changed = True
		if 'plugin_dispatch = load_plugin_dispatch_from_config(cfg)' not in txt:
			new_txt, n = re.subn(
				r'raw_dispatch\s*=\s*build_dispatch\s*\(\s*cfg\s*\)',
				'raw_dispatch = build_dispatch(cfg)\n\tplugin_dispatch = load_plugin_dispatch_from_config(cfg)\n\traw_dispatch.update(plugin_dispatch)',
				txt, count=1, flags=re.M
			)
			if n == 0:
				new_txt = txt + '\n# [plugins] manual merge example:\n# from bm_daemon.agent.plugin_loader import load_plugin_dispatch_from_config\n# plugin_dispatch = load_plugin_dispatch_from_config(cfg)\n# raw_dispatch.update(plugin_dispatch)\n'
			txt = new_txt; changed = True
		if changed:
			write(run_py, txt); summary["patched"].append(str(run_py))

	# 5) fix imports inside plugin files
	for py in (root/'bm_camera').rglob('*.py'):
		txt = read(py); orig = txt
		for pat, repl in REPLACEMENTS:
			txt = re.sub(pat, repl, txt)
		if txt != orig:
			write(py, txt); summary["patched"].append(str(py))

	# 6) __main__.py shim
	main_py = root/'bm_daemon'/'__main__.py'
	if not main_py.exists():
		write(main_py, MAIN_SHIM); summary["created"].append(str(main_py))

	# 7) config.yaml plugins list
	cfg_path = root/'config.yaml'
	if cfg_path.exists():
		cfg = read(cfg_path)
		if 'plugins:' not in cfg:
			cfg += '\n\nplugins:\n  - "bm_camera.handlers.capture_image_cmd:CaptureImageHandler"\n  - "bm_camera.handlers.capture_video_cmd:CaptureVideoHandler"\n'
			write(cfg_path, cfg); summary["patched"].append(str(cfg_path))
	else:
		write(cfg_path, 'plugins:\n  - "bm_camera.handlers.capture_image_cmd:CaptureImageHandler"\n  - "bm_camera.handlers.capture_video_cmd:CaptureVideoHandler"\n')
		summary["created"].append(str(cfg_path))

	return summary

def zip_dir(dir_path: Path, out_zip: Path):
	if out_zip.exists(): out_zip.unlink()
	with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
		for p in dir_path.rglob('*'):
			if p.is_file():
				z.write(p, p.relative_to(dir_path.parent))

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument('path', help='Path to project directory or zip file')
	args = ap.parse_args()
	target = Path(args.path).expanduser().resolve()
	if not target.exists():
		print(f"[ERR] Path does not exist: {target}", file=sys.stderr); return 2

	# ZIP input
	if target.suffix.lower() == '.zip':
		with tempfile.TemporaryDirectory() as td:
			td = Path(td)
			with zipfile.ZipFile(target, 'r') as z: z.extractall(td)
			root = find_project_root(td)
			summary = refactor_dir(root)
			out_zip = target.with_name(target.stem + '_refactored.zip')
			zip_dir(root, out_zip)
			print(f"[OK] Wrote {out_zip}")
			for k,v in summary.items():
				if v: print(f"[{k}]\n  - " + "\n  - ".join(v))
	else:
		# Directory input
		root = find_project_root(target)
		summary = refactor_dir(root)
		out_zip = target.with_name(target.name + '_refactored.zip')
		zip_dir(root, out_zip)
		print(f"[OK] Wrote {out_zip}")
		for k,v in summary.items():
			if v: print(f"[{k}]\n  - " + "\n  - ".join(v))

if __name__ == '__main__':
	raise SystemExit(main())
