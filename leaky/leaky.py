import builtins
from dataclasses import dataclass, field
import logging
import socket
from threading import Thread
import time
import traceback
from typing import Any
import _io

from leaky.shutdown_listener import should_continue


@dataclass(frozen=True)
class FD:
    subject: Any
    stack: list[str]
    created_at: float = field(default_factory=time.time)


FDS: dict[int, FD] = {}
UNCLOSED_TIMEOUT = 180
INTERVAL = 15


def get_self(args, kwargs):
    if len(args) >= 1:
        return args[0]
    return kwargs["self"]


original_open = builtins.open
original_init = socket.socket.__init__
original_close = socket.socket.close
original_detach = socket.socket.detach

logger = logging.getLogger(__name__)


def print_error(msg: str, stack_trace: list[str]):
    output = [f"\n===== {msg} =====\n"]
    output.extend(stack_trace[:-1])
    logger.error("".join(output))


def patched_open(*args, **kwargs):
    print("patched_open called with:", args, kwargs)  # Debug print
    file_obj = original_open(*args, **kwargs)
    id_ = id(file_obj)
    file_close = file_obj.close
    print("Created file object:", file_obj, "with id:", id_)  # Debug print

    def patched_file_close(*args, **kwargs):
        print("patched_file_close called for id:", id_)  # Debug print
        FDS.pop(id_, None)
        result = file_close(*args, **kwargs)
        return result

    file_obj.close = patched_file_close
    FDS[id_] = FD(file_obj, traceback.format_stack())
    print("Added to FDS:", id_, FDS)  # Debug print
    return file_obj


def patched_init(*args, **kwargs):
    result = original_init(*args, **kwargs)
    self = get_self(args, kwargs)
    id_ = id(self)
    FDS[id_] = FD(self, traceback.format_stack())
    return result


def patched_close(*args, **kwargs):
    self = get_self(args, kwargs)
    id_ = id(self)
    FDS.pop(id_, None)
    result = original_close(*args, **kwargs)
    return result


def patched_detach(*args, **kwargs):
    self = get_self(args, kwargs)
    id_ = id(self)
    FDS.pop(id_, None)
    result = original_detach(*args, **kwargs)
    return result


def run():
    while should_continue():
        time.sleep(INTERVAL)
        threshold = time.time() - UNCLOSED_TIMEOUT
        for id_, fd in list(FDS.items()):
            if fd.created_at < threshold:
                FDS.pop(id_)
                print_error("UNCLOSED", fd.stack)

    for fd in FDS.values():
        print_error("UNCLOSED", fd.stack)


def patch_fds():
    builtins.open = patched_open
    _io.open = patched_open  # Also patch _io.open for tempfile module
    socket.socket.__init__ = patched_init  # type: ignore
    socket.socket.close = patched_close  # type: ignore
    socket.socket.detach = patched_detach  # type: ignore
    Thread(target=run, daemon=True).start()
