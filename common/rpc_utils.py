import inspect
import functools
import threading
import traceback

from loguru import logger

_RPC_CONTEXT = threading.local()


def sandbox_api(name=None):
    """Mark a method as an exposed RPC endpoint.

    When called via RPC, only the *outermost* @sandbox_api call wraps the
    response in {"status": "ok", "data": ...}. Nested internal calls
    (e.g. get_render_data -> get_type) pass through raw values so that
    the calling code sees normal Python objects, not wrapped dicts.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            is_rpc = getattr(_RPC_CONTEXT, "active", False)
            depth = getattr(_RPC_CONTEXT, "depth", 0)
            is_outermost = is_rpc and depth == 0
            try:
                _RPC_CONTEXT.depth = depth + 1
                result = func(*args, **kwargs)
                if is_outermost:
                    return {"status": "ok", "data": result}
                return result
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"[RPC ERROR] {func.__name__}: {e}\n{tb}")
                if is_outermost:
                    return {"status": "error", "message": str(e), "traceback": tb}
                raise
            finally:
                _RPC_CONTEXT.depth = depth

        wrapper._sandbox_api = True
        wrapper._sandbox_name = name or func.__name__
        return wrapper
    return decorator


def register_module_api(dispatcher, module_instance, namespace="", visited=None):
    """Recursively register all @sandbox_api methods from *module_instance*
    (and its sub-objects) with the RPC *dispatcher*.

    Uses a lazy path resolver so that dynamic object rebinding (e.g. map
    reload) is automatically picked up at call time.
    """
    if visited is None:
        visited = set()
    if id(module_instance) in visited:
        return
    visited.add(id(module_instance))

    cls_name = module_instance.__class__.__name__
    prefix = f"{namespace}." if namespace else ""

    # Register @sandbox_api methods declared on the class
    for name, func in inspect.getmembers(module_instance.__class__, predicate=inspect.isfunction):
        if not getattr(func, "_sandbox_api", False):
            continue

        rpc_name = f"{prefix}{func._sandbox_name}"

        # Lazy resolver: re-traverses the object tree on every call so that
        # reassigned attributes (e.g. after map.load_map()) are respected.
        def _lazy_caller(*args, __path=rpc_name, **kwargs):
            parts = __path.split(".")
            root = getattr(dispatcher, "root_object", None)
            if root is None:
                raise RuntimeError("dispatcher.root_object is not set")
            for p in parts[:-1]:
                root = getattr(root, p)
            return getattr(root, parts[-1])(*args, **kwargs)

        dispatcher.add_method(_lazy_caller, name=rpc_name)
        logger.info(f"[RPC] Registered {cls_name}.{rpc_name}")

    # Recurse into sub-objects that may contain more @sandbox_api methods
    for attr_name in dir(module_instance):
        if attr_name.startswith("_"):
            continue
        try:
            attr_value = getattr(module_instance, attr_name)
        except Exception:
            continue

        # Skip primitives, callables, types, and modules
        if isinstance(attr_value, (int, float, str, bool, list, tuple, dict, set, type(None))):
            continue
        if inspect.isfunction(attr_value) or inspect.ismethod(attr_value):
            continue
        if inspect.isclass(attr_value) or inspect.ismodule(attr_value):
            continue
        if id(attr_value) in visited:
            continue

        if hasattr(attr_value, "__dict__") or hasattr(attr_value, "__slots__"):
            register_module_api(dispatcher, attr_value, namespace=f"{prefix}{attr_name}", visited=visited)
