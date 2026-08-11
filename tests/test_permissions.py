"""Risk-classification tests — the DecompositionGuard bypass fix.

These assert that the AST-based ``classify`` / ``classify_python`` /
``classify_shell`` cannot be evaded with the counterexamples from the security
review: ``subprocess.run(...)``, ``os.system(...)``, ``pathlib.Path.unlink()``,
``python3 -c "..."``, __import__ of a network module, etc. The whole point is
that a security-literate reader can no longer construct a string that sneaks a
high-risk action past the floor.
"""

from __future__ import annotations

from sworker.permissions import classify, classify_python, classify_shell
from sworker.models import RiskLevel
from sworker.tools.base import Tool
from sworker.tools.exec import PythonAnalysis, ShellExec


# ---- python.run: the evasions that used to stay at the REVERSIBLE floor ------

def test_subprocess_run_is_external():
    code = "import subprocess\nsubprocess.run(['curl', 'https://x'])"
    assert classify_python(code) == RiskLevel.EXTERNAL


def test_os_system_is_external():
    code = "import os\nos.system('curl https://x')"
    assert classify_python(code) == RiskLevel.EXTERNAL


def test_pathlib_unlink_is_destructive():
    code = "import pathlib\npathlib.Path('/tmp/x').unlink()"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_shutil_rmtree_is_destructive():
    code = "import shutil\nshutil.rmtree('/tmp/x')"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_os_remove_is_destructive():
    code = "import os\nos.remove('/tmp/x')"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_urllib_request_is_external():
    code = "import urllib.request\nurllib.request.urlopen('https://x')"
    assert classify_python(code) == RiskLevel.EXTERNAL


def test_dynamic_import_of_socket_fails_closed():
    # __import__('socket') with a literal still loads a network module -> escalate.
    code = "__import__('socket').socket()"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_import_of_unknown_module_fails_closed():
    # A module we cannot prove is safe must not be assumed benign.
    code = "import something_made_up_for_the_test"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_eval_with_dynamic_arg_fails_closed():
    code = "eval(user_input)"
    assert classify_python(code) == RiskLevel.DESTRUCTIVE


def test_syntax_error_fails_closed():
    # Unparseable code -> cannot prove safe.
    assert classify_python("def f(:\n  pass") == RiskLevel.DESTRUCTIVE


def test_benign_analysis_stays_low():
    code = (
        "import csv, json\n"
        "from collections import Counter\n"
        "rows = list(csv.reader(open('sales.csv')))\n"
        "total = sum(float(r[2]) for r in rows)\n"
        "print(total)"
    )
    assert classify_python(code) == RiskLevel.READ


def test_classify_via_tool_object_uses_ast():
    tool = PythonAnalysis()
    args = {"code": "import os\nos.remove('/tmp/x')"}
    assert classify(tool, args) == RiskLevel.DESTRUCTIVE


# ---- shell.exec: interpreter floor + token checks ----------------------------

def test_python3_c_is_external_even_without_old_tokens():
    # python3 -c "..." contains none of curl/wget/ssh but can run anything.
    cmd = "python3 -c \"import socket; s=socket.socket()\""
    assert classify_shell(cmd) == RiskLevel.EXTERNAL


def test_bash_c_is_external():
    assert classify_shell("bash -c 'echo hi'") == RiskLevel.EXTERNAL


def test_plain_destructive_token_is_destructive():
    assert classify_shell("rm -rf /tmp/foo") == RiskLevel.DESTRUCTIVE


def test_plain_network_token_is_external():
    assert classify_shell("curl https://example.com") == RiskLevel.EXTERNAL


def test_fixed_purpose_binary_stays_reversible():
    # ls / cat cannot launch arbitrary code from the command line.
    assert classify_shell("ls -la /tmp") == RiskLevel.REVERSIBLE
    assert classify_shell("cat company/sales.csv") == RiskLevel.REVERSIBLE


def test_unparseable_command_fails_closed():
    # shlex.split raises -> we can't vet it.
    assert classify_shell("'unterminated") == RiskLevel.DESTRUCTIVE


def test_classify_shell_via_tool_object():
    tool = ShellExec()
    args = {"command": "python3 -c \"import os; os.system('echo pwned')\""}
    assert classify(tool, args) == RiskLevel.EXTERNAL
