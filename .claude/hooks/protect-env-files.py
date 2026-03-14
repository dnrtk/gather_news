import json
import re
import sys

input_data = json.loads(sys.stdin.read())
tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
file_path = tool_input.get("file_path", "")
cmd = tool_input.get("command", "")

# Read・EditツールでのENVファイルアクセスをブロック
if re.search(r'\.env($|\.)', file_path):
    print(".envファイルへのアクセスはブロックされました。", file=sys.stderr)
    sys.exit(2)

# Bashでの.env読み取りやシークレット出力をブロック
SENSITIVE_VARS = [
    "GEMINI_API_KEY",
]

if tool_name == "Bash":
    pattern = r'\.env|echo.*\$[A-Z_]*KEY|echo.*\$[A-Z_]*SECRET|echo.*\$[A-Z_]*TOKEN|echo.*\$[A-Z_]*PASSWORD'
    var_pattern = r'echo.*\$(' + '|'.join(SENSITIVE_VARS) + r')'
    if re.search(pattern, cmd) or re.search(var_pattern, cmd):
        print(".envや秘密情報に関連するコマンドはブロックされました。", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
