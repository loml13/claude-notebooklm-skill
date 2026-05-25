#!/usr/bin/env python3
"""notebooklm skill 执行脚本。

用法: query.py <notebook_id> <question>

行为：
- 向 NotebookLM 提问；答案在 Chrome 中渲染
- 归档目录为空 → 直接新建归档，结束
- 归档目录非空 → 输出 STAGING 信息，由 Claude 决定新建还是合并改写

环境变量（必填）：
- NOTEBOOKLM_STORAGE  notebooklm-py 的 storage_state.json 路径
                      （默认 ~/.notebooklm/profiles/default/storage_state.json）
- NOTEBOOKLM_CLI      notebooklm-py 命令行入口（用于过期自动刷新；可选）
"""
import asyncio
import json
import os
import sys
import tempfile
import subprocess
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notebooklm import NotebookLMClient
from notebooklm.auth import AuthTokens
from archive import archive, target_dir_for

DEFAULT_STORAGE = Path.home() / ".notebooklm/profiles/default/storage_state.json"
STORAGE = Path(os.environ.get("NOTEBOOKLM_STORAGE", str(DEFAULT_STORAGE)))
NBLM_CLI = os.environ.get("NOTEBOOKLM_CLI", "notebooklm")
SCRIPT_DIR = Path(__file__).parent


async def get_auth():
    try:
        return await AuthTokens.from_storage(STORAGE)
    except ValueError as e:
        if "Authentication expired" in str(e):
            print("cookies 过期，自动刷新中...")
            subprocess.run(
                [NBLM_CLI, "login", "--browser-cookies", "chrome"],
                check=True,
            )
            return await AuthTokens.from_storage(STORAGE)
        raise


def render_html(question: str, answer: str) -> str:
    q = question.replace('"', "&quot;")
    md = json.dumps(answer)
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{q[:60]}</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>MathJax={{tex:{{inlineMath:[['$','$']],displayMath:[['$$','$$']]}},options:{{skipHtmlTags:['script','noscript','style','textarea']}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
<style>
  ::-webkit-scrollbar{{width:8px}}::-webkit-scrollbar-track{{background:#f1f1f1}}::-webkit-scrollbar-thumb{{background:#888;border-radius:4px}}
  html{{overflow-y:scroll}}
  body{{font-family:-apple-system,sans-serif;max-width:860px;margin:40px auto;padding:0 20px 80px;line-height:1.8;color:#222}}
  h2,h3,h4{{color:#1a1a2e}}
  .q{{color:#555;font-style:italic;border-left:3px solid #4a9;padding-left:12px;margin-bottom:24px}}
</style>
</head><body>
<p class="q">Q: {q}</p>
<div id="c"></div>
<script>document.getElementById('c').innerHTML=marked.parse({md});</script>
</body></html>"""


def open_in_browser(path: str) -> None:
    """跨平台打开本地 HTML（macOS/Linux/Windows）。"""
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]


async def main():
    if len(sys.argv) < 3:
        print("用法: query.py <notebook_id> <question>")
        sys.exit(1)

    notebook_id, question = sys.argv[1], sys.argv[2]

    auth = await get_auth()
    async with NotebookLMClient(auth, storage_path=STORAGE) as client:
        result = await client.chat.ask(notebook_id, question)
        notebook_title = ""
        try:
            nb = await client.notebooks.get(notebook_id)
            notebook_title = getattr(nb, "title", "") or ""
        except Exception:
            pass

    # Chrome 渲染（无论后续如何归档，回答先给用户看）
    html = render_html(question, result.answer)
    tmp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp_html.write(html)
    tmp_html.close()
    open_in_browser(tmp_html.name)
    print(f"已在浏览器打开：{tmp_html.name}")

    # 归档决策
    target_dir = target_dir_for(notebook_id, notebook_title)
    target_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in target_dir.glob("*.md"))

    if not existing:
        saved = archive(notebook_id, notebook_title, question, result.answer)
        print(f"已归档到：{saved}")
        return

    # 把答案落到临时 md，Claude 自行决定是否 Read
    answer_tmp = Path(tempfile.gettempdir()) / f"nblm_answer_{uuid.uuid4().hex[:8]}.md"
    answer_tmp.write_text(result.answer, encoding="utf-8")

    staging = {
        "notebook_id": notebook_id,
        "notebook_title": notebook_title,
        "target_dir": str(target_dir),
        "question": question,
        "answer_path": str(answer_tmp),
        "existing_files": existing,
        "new_command": (
            f"{sys.executable} {SCRIPT_DIR/'archive.py'} new "
            f"{answer_tmp} {json.dumps(notebook_id)} "
            f"{json.dumps(notebook_title, ensure_ascii=False)} "
            f"{json.dumps(question, ensure_ascii=False)}"
        ),
    }
    print("\n==NOTEBOOKLM_STAGING_BEGIN==")
    print(json.dumps(staging, ensure_ascii=False, indent=2))
    print("==NOTEBOOKLM_STAGING_END==")


asyncio.run(main())
