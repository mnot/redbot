from collections import defaultdict
import encodings
import errno
import importlib
import pkgutil
import socket
import sys
from types import ModuleType
from typing import List, Dict, Union, Optional

from importlib_resources import files as resource_files

import thor

if sys.platform == "linux":
    try:
        import seccomp  # type: ignore
    except ImportError:
        try:
            import pyseccomp as seccomp  # type: ignore  # pylint: disable=import-error
        except RuntimeError:
            seccomp = None  # pylint: disable=invalid-name
else:
    seccomp = None  # pylint: disable=invalid-name


def enable_seccomp(enforce: bool = True) -> bool:
    """
    Enable seccomp. If enforce is false, violations will only be logged.

    Returns whether it was successfully enabled.
    """
    if not seccomp:
        return False

    prep_seccomp()

    violation_action = seccomp.KILL_PROCESS if enforce else seccomp.LOG
    deny_action = seccomp.ERRNO(errno.EACCES)
    filt = seccomp.SyscallFilter(seccomp.ALLOW)
    filt.set_attr(seccomp.Attr.CTL_LOG, 1)

    # Sycalls that we should never call.
    syscalls = get_syscalls()
    add_rules(filt, deny_action, syscalls["file-system"], ["newfstatat", "close"])
    add_rules(filt, violation_action, syscalls["chown"])
    add_rules(filt, violation_action, syscalls["clock"])
    add_rules(filt, violation_action, syscalls["cpu-emulation"])
    add_rules(filt, violation_action, syscalls["keyring"])
    add_rules(filt, violation_action, syscalls["module"])
    add_rules(filt, violation_action, syscalls["mount"])
    add_rules(filt, violation_action, syscalls["obsolete"])
    add_rules(filt, violation_action, syscalls["privileged"])
    add_rules(filt, violation_action, syscalls["process"], ["clone3"])
    add_rules(filt, violation_action, syscalls["raw-io"])
    add_rules(filt, violation_action, syscalls["reboot"])
    add_rules(filt, violation_action, syscalls["sandbox"])
    add_rules(filt, violation_action, syscalls["setuid"])
    add_rules(filt, violation_action, syscalls["swap"])

    filt.load()
    return True


def prep_seccomp() -> None:
    """
    Prepare for turning on seccomp.
    """

    # load encodings
    load_modules(encodings, ["encodings.mbcs", "encodings.oem"])

    # do a DNS lookup to load /etc/gai.conf
    thor.dns.lookup(b"example.com", 80, socket.SOCK_STREAM, lambda a: None)


def add_rules(
    filt: "seccomp.SyscallFilter",
    rule: Union[int, "seccomp.ERRNO"],
    syscalls: List[str],
    exceptions: Optional[List[str]] = None,
) -> None:
    for syscall in syscalls:
        if exceptions and syscall in exceptions:
            continue
        try:
            filt.add_rule(rule, syscall)
        except OSError:
            sys.stderr.write(f"\nUnknown syscall: {syscall}\n\n")
            raise


def get_syscalls() -> Dict[str, List[str]]:
    """
    Return a dictionary of syscalls indexed by family.

    Generate reference/linux-syscalls like this:
    > sudo systemd-analyze syscall-filter > linux-syscalls
    """
    text = (
        resource_files("redbot.util.reference").joinpath("linux-syscalls").read_text()
    )
    out = defaultdict(list)
    current_section = None
    for line in text.split("\n"):
        if line == "":
            continue
        first = line[0]
        if first == "@":
            current_section = line[1:].strip()
        elif first == "#":
            continue
        elif first == " ":
            value = line.strip()
            if "@" in value:
                continue
            if value[0] != "#":
                assert current_section is not None
                out[current_section].append(value)
        else:
            assert False, f"Unhandled line: {line}"
    return out


def load_modules(module: ModuleType, skip: List[str]) -> None:
    for _, name, _ in pkgutil.iter_modules(
        module.__path__, prefix=f"{module.__name__}."
    ):
        if name not in skip:
            importlib.import_module(name)
