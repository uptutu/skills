#!/usr/bin/env python3
"""从 SKILL.md 生成 cherry-studio.json，避免双份拷贝漂移。

用法: python3 scripts/gen-cherry-studio.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
OUT = ROOT / "cherry-studio.json"

text = SKILL.read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
if not m:
    sys.exit("SKILL.md 缺少 YAML frontmatter")
fm, body = m.groups()

def field(name):
    f = re.search(rf"^{name}: '(.*)'$", fm, re.M)
    return f.group(1) if f else None

desc = field("description")
if desc:
    desc = desc.split("Triggers on")[0].strip()  # cherry-studio 不需要触发词列表

data = {
    "name": field("name") or "ford",
    "emoji": "🧭",
    "description": desc,
    "group": ["uptutu-skills"],
    "prompt": body.strip(),
}
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"written {OUT}")
