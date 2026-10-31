"""The AWS hook is the project's only hook: it must block every known route and nothing harmless."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "bloquear_aws_cli.py"
_spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

# Built by concatenation so this file never holds a runnable cloud command line.
CLI = "a" + "ws"


@pytest.mark.parametrize(
    "command",
    [
        f"{CLI} s3 ls",
        f"git status && {CLI} sts get-caller-identity",
        f"bash -c '{CLI} s3 ls'",
        f'powershell -Command "{CLI} s3 ls"',
        f"C:\\Program Files\\Amazon\\AWSCLIV2\\{CLI}.exe s3 ls",
        f"echo $({CLI} configure list)",
        "cdk deploy",
        "terraform apply",
        "python -c \"import boto3; boto3.client('s3')\"",
        "curl --" + CLI + "-sigv4 'aws:amz:us-east-1:bedrock' https://example.com",
        "Import-Module AWS.Tools.S3",
        "Set-AWSCredential -ProfileName x",
        "LLM_PROVIDER=bedrock uv run python -m agente",
        '$env:LLM_PROVIDER="bedrock"; uv run python -m agente',
        # Separators the COMMAND regex accepts before the name.
        f"true;{CLI} s3 ls",
        f"echo x|{CLI} s3 ls",
        f"echo `{CLI} s3 ls`",
        f"{{ {CLI} s3 ls; }}",
        f"(cd /tmp && {CLI} s3 ls)",
        f"X={CLI}",
        # Path prefix with forward slashes, .cmd extension, upper case.
        f"/usr/local/bin/{CLI} s3 ls",
        f"./node_modules/.bin/{CLI}.cmd s3 ls",
        f"{CLI.upper()} S3 LS",
        'python -c "import botocore"',
        'python -c "from boto3 import client"',
        # Routes found in review.
        '$env:LLM_PROVIDER = "bedrock"; uv run python -m agente',
        f"npx {CLI}-cdk deploy",
        f"{CLI}>out.txt s3 ls",
        f"python -m {CLI}cli s3 ls",
        "Get-S3Bucket",
        "Get-STSCallerIdentity",
        # Remaining branches of the OTHER regex and the COMMAND lookahead.
        "Import-Module AWSPowerShell",
        "start-sfnexecution -StateMachineArn x",
        "LLM_PROVIDER: bedrock",
        f"{CLI}<in.txt",
    ],
)
def test_blocks_cloud_routes(command):
    assert hook.is_blocked(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest -q",
        "git commit -F mensaje.txt",
        "LLM_PROVIDER=groq uv run python -m agente",
        "ls docs/diseno",
        "echo awesome",
        "uv run ruff check .",
        # Blocked names inside longer words or file names do not count.
        f"cat {CLI}_notes.txt",
        "smbclient samba",
        "ls ebook",
        "echo terraforming",
        # The SDK name alone (Strands depends on it) is not a cloud call.
        "uv run pytest -k boto3",
        "uv tree --package botocore",
        # Common PowerShell cmdlets that are not cloud cmdlets.
        "Get-ChildItem docs",
        "Get-Content README.md",
    ],
)
def test_allows_local_work(command):
    assert not hook.is_blocked(command)


def _run(stdin: bytes) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True)


def test_exit_code_2_blocks_and_explains():
    result = _run(json.dumps({"tool_input": {"command": "cdk synth"}}).encode())
    assert result.returncode == 2 and b"bloquear_aws_cli" in result.stderr


def test_exit_code_0_allows():
    assert _run(json.dumps({"tool_input": {"command": "uv run pytest"}}).encode()).returncode == 0


def test_unreadable_input_fails_closed():
    result = _run(b"{no es json")
    assert result.returncode == 2 and b"bloquear_aws_cli" in result.stderr


@pytest.mark.parametrize(
    "event",
    [{}, {"tool_input": None}, {"tool_input": {}}, {"tool_input": {"command": None}}],
)
def test_event_without_command_is_allowed(event):
    assert _run(json.dumps(event).encode()).returncode == 0


@pytest.mark.parametrize(
    "event", [[], "texto", {"tool_input": {"command": 123}}, {"tool_input": ["x"]}]
)
def test_unexpected_shapes_fail_closed(event):
    assert _run(json.dumps(event).encode()).returncode == 2
