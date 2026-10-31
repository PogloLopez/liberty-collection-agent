"""PreToolUse hook: blocks any shell command that could reach AWS from this machine.

Claude Code sends the tool call as JSON on stdin. Exit code 2 blocks the call and shows
stderr to Claude; any unexpected input or error also exits 2 (fail closed). Pablo runs
every cloud command himself.

Command text is all a hook can see: a script that imports boto3 on its own, or shell
escapes such as a\\ws, are invisible here. The real barrier is that Claude's environment
has no AWS credentials. Known false positives (blocked names in paths or search patterns)
are accepted: they err on the safe side.
"""

import json
import re
import sys

# The AWS CLI, the AWS deploy CLIs that wrap it, and IaC tools that deploy to it.
BLOCKED_COMMANDS = (
    "aws", "awscli", "agentcore", "cdk", "sam", "copilot", "eb", "amplify", "eksctl",
    "terraform", "tofu", "pulumi", "serverless", "sls",
)  # fmt: skip

# A blocked command at the start, after a shell separator, a subshell opener or a quote
# (catches `bash -c 'aws ...'`), with an optional path prefix and Windows extension.
COMMAND = re.compile(
    r"(?:^|[\s;&|(`{'\"=]|\$\()"
    r"(?:[\w./\\:-]*[\\/])?"
    r"(?:" + "|".join(BLOCKED_COMMANDS) + r")"
    r"(?:\.exe|\.cmd)?"
    r"(?=$|[\s;&|)`}'\"<>-])",  # `-` catches npx aws-cdk, `>` catches redirections
    re.IGNORECASE,
)

# Other ways to call AWS from a command line.
OTHER = re.compile(
    r"(?:import|from)\s+boto(?:3|core)\b"  # SDK in inline code: python -c "import boto3"
    r"|aws-sigv4"  # curl --aws-sigv4
    r"|\bAWS\.Tools\b|\bAWSPowerShell\b|-AWS[A-Z]"  # AWS Tools for PowerShell modules
    r"|\b(?:Get|Set|New|Remove|Write|Read|Invoke|Start|Stop|Update)-"
    r"(?:S3|STS|IAM|BDR|BAR|DDB|CFN|EC2|SFN|SNS|SQS|LM|CW|SM)[A-Z]"  # AWS Tools cmdlets
    r"|LLM_PROVIDER[\s=:'\"]*bedrock",  # running the agent against Bedrock
    re.IGNORECASE,
)

MESSAGE = (
    "Bloqueado por .claude/hooks/bloquear_aws_cli.py: en este proyecto Claude no ejecuta nada "
    "contra AWS. Escribe el comando en docs/ y avisa a Pablo para que lo ejecute."
)


def is_blocked(command: str) -> bool:
    return bool(COMMAND.search(command) or OTHER.search(command))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input") or {}
        command = tool_input.get("command") or ""
        if not isinstance(command, str):
            raise TypeError("command is not a string")
        blocked = is_blocked(command)
    except Exception:
        print(MESSAGE + " (entrada inesperada: se bloquea por seguridad)", file=sys.stderr)
        return 2
    if blocked:
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
