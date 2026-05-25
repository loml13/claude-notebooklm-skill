"""把 NotebookLM 的一次 Q&A 归档到 Obsidian vault。

路径解析（archive_config.json）：
- 若 notebook_id 在 by_notebook_id 里有映射 → vault / <映射路径>
- 否则 → vault / <default> / <notebook_title>

文件名：`YYYY-MM-DD HHMMSS <question 前 40 字>.md`
"""
import json
import re
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent / "archive_config.json"


def _load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"找不到 {CONFIG_PATH}。请按 archive_config.example.json 创建。"
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _slug(text, maxlen=40):
    bad = '/\\:*?"<>|\n\r\t'
    cleaned = "".join(c for c in text if c not in bad).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:maxlen].rstrip() or "untitled"


def _normalize_math(md: str) -> str:
    """把行内的 $$...$$ 转成 $...$，让 Obsidian 能渲染。

    Obsidian 要求块级公式 $$...$$ 独占一行；出现在列表项、缩进段落
    或行尾带引用编号时会失败。NotebookLM 经常把短公式写成 $$...$$
    嵌在文字里，所以这里统一降级为行内。
    """
    out = []
    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("$$") and s.endswith("$$") and s.count("$$") == 2 and len(s) > 4:
            out.append(line)
            continue
        out.append(re.sub(r"\$\$([^$\n]+?)\$\$", r"$\1$", line))
    return "\n".join(out)


def target_dir_for(notebook_id: str, notebook_title: str) -> Path:
    """归档目录解析（不创建）。给 query.py 用来枚举已有文件。"""
    cfg = _load_config()
    vault = Path(cfg["vault"]).expanduser()
    mapped = cfg.get("by_notebook_id", {}).get(notebook_id)
    if mapped:
        return vault / mapped
    return vault / cfg["default"] / _slug(notebook_title, 60)


def archive(notebook_id: str, notebook_title: str, question: str, answer_md: str) -> Path:
    target_dir = target_dir_for(notebook_id, notebook_title)
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    fname = f"{now:%Y-%m-%d %H%M%S} {_slug(question)}.md"
    target = target_dir / fname

    # frontmatter 里的 question 用 JSON 转义防止特殊字符破坏 YAML
    q_yaml = json.dumps(question, ensure_ascii=False)
    body = (
        f"---\n"
        f"notebook: {notebook_title}\n"
        f"notebook_id: {notebook_id}\n"
        f"date: {now:%Y-%m-%d %H:%M}\n"
        f"question: {q_yaml}\n"
        f"tags: [notebooklm]\n"
        f"---\n\n"
        f"> [!question] 问题\n"
        f"> {question}\n\n"
        f"# 回答\n\n"
        f"{_normalize_math(answer_md).rstrip()}\n"
    )
    target.write_text(body, encoding="utf-8")
    return target


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 6 or sys.argv[1] != "new":
        print("用法: archive.py new <answer_path> <notebook_id> <notebook_title> <question>")
        sys.exit(1)
    _, _, answer_path, notebook_id, notebook_title, question = sys.argv
    answer = Path(answer_path).read_text(encoding="utf-8")
    saved = archive(notebook_id, notebook_title, question, answer)
    print(saved)
