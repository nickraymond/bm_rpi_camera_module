# from importlib import import_module
# from typing import Dict, Callable
# from bm_daemon.pluginspec.handler import Handler
# 
# # def load_plugin_dispatch_from_config(cfg: dict) -> Dict[str, Callable]:
# # 	specs = cfg.get("plugins", [])
# # 	table: Dict[str, Callable] = {}
# # 	for spec in specs:
# # 		modname, clsname = spec.split(":")
# # 		mod = import_module(modname)
# # 		cls = getattr(mod, clsname)
# # 		inst: Handler = cls()
# # 		for topic in getattr(inst, "topics", []):
# # 			def _make(inst):
# # 				def _fn(node, topic_str, data, ctx):
# # 					inst.handle({"node": node, "topic": topic_str, "data": data}, ctx=ctx)
# # 				return _fn
# # 			table[str(topic)] = _make(inst)
# # 	return table
# from importlib import import_module
# from typing import Dict, Callable, Any
# 
# def _wrap_handle(handle):
# 	def _fn(node, topic_str, data, ctx):
# 		handle({"node": node, "topic": topic_str, "data": data}, ctx=ctx)
# 	return _fn
# 
# def _as_callable_table(obj: Any) -> Dict[str, Callable]:
# 	table: Dict[str, Callable] = {}
# 	topics = getattr(obj, "topics", None)
# 	handle = getattr(obj, "handle", None)
# 	if topics and callable(handle):
# 		for t in topics:
# 			table[str(t)] = _wrap_handle(handle)
# 	return table
# 
# def load_plugin_dispatch_from_config(cfg: dict) -> Dict[str, Callable]:
# 	specs = cfg.get("plugins", [])
# 	dispatch: Dict[str, Callable] = {}
# 	for spec in specs:
# 		if ":" in spec:
# 			modname, clsname = spec.split(":")
# 			obj = getattr(import_module(modname), clsname)
# 			# if it's a class, instantiate it
# 			if isinstance(obj, type):
# 				obj = obj()
# 		else:
# 			# module-style: module exposes topics + handle at top level
# 			obj = import_module(spec)
# 		dispatch.update(_as_callable_table(obj))
# 	return dispatch
from importlib import import_module
from typing import Dict, Callable, Any

def _wrap_handle(handle):
	def _fn(node, topic_str, data, ctx):
		handle({"node": node, "topic": topic_str, "data": data}, ctx=ctx)
	return _fn

def _as_callable_table(obj: Any) -> Dict[str, Callable]:
	table: Dict[str, Callable] = {}
	topics = getattr(obj, "topics", None)
	handle = getattr(obj, "handle", None)
	if topics and callable(handle):
		for t in topics:
			table[str(t)] = _wrap_handle(handle)
	return table

def load_plugin_dispatch_from_config(cfg: dict) -> Dict[str, Callable]:
	specs = cfg.get("plugins", [])
	dispatch: Dict[str, Callable] = {}
	for spec in specs:
		if ":" in spec:
			modname, clsname = spec.split(":")
			obj = getattr(import_module(modname), clsname)
			if isinstance(obj, type):
				obj = obj()  # class -> instance
		else:
			obj = import_module(spec)  # module exposes topics + handle
		dispatch.update(_as_callable_table(obj))
	return dispatch
