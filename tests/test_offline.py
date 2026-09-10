"""Linux kernel-enforced network denial for the complete standalone workflow."""

import subprocess
import sys
import pytest


def test_offline_solve_validate_export(tmp_path):
    if sys.platform != "linux":
        pytest.skip("Linux seccomp test")
    program = r"""
import ctypes, ctypes.util, errno, socket, sys
library = ctypes.util.find_library('seccomp')
if not library:
    sys.exit(77)
sec = ctypes.CDLL(library, use_errno=True)
sec.seccomp_init.argtypes=[ctypes.c_uint32]
sec.seccomp_init.restype=ctypes.c_void_p
sec.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
sec.seccomp_syscall_resolve_name.restype=ctypes.c_int
sec.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
sec.seccomp_load.argtypes=[ctypes.c_void_p]
sec.seccomp_release.argtypes=[ctypes.c_void_p]
context=sec.seccomp_init(0x7fff0000)
assert context
for name in ['socket','connect','sendto','sendmsg','sendmmsg','recvfrom','recvmsg','recvmmsg']:
    number=sec.seccomp_syscall_resolve_name(name.encode())
    if number>=0:
        assert sec.seccomp_rule_add(context,0x00050000|errno.EPERM,number,0)==0
assert sec.seccomp_load(context)==0
sec.seccomp_release(context)
try:
    socket.socket()
    raise AssertionError('Network was not blocked')
except PermissionError:
    pass
from sp5generator.cli import main
assert main(['demo','--days','1','-o','input.json'])==0
assert main(['solve','input.json','--time-limit','5','-o','result.json'])==0
assert main(['validate','input.json','result.json','-o','validation.json'])==0
assert main(['export','input.json','result.json','result.csv'])==0
assert main(['export','input.json','result.json','result.xlsx'])==0
print('kernel-network-denied: solve, independent validation, CSV, XLSX passed')
"""
    outcome = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if outcome.returncode == 77:
        pytest.skip("libseccomp unavailable")
    assert outcome.returncode == 0, outcome.stderr
    assert "kernel-network-denied" in outcome.stdout
