---
name: notebooklm
description: 向 NotebookLM 笔记本提问，基于已上传的资料给出 Gemini 的回答，结果在浏览器中渲染（含公式）；归档时智能合并到现有相关笔记。用法：/notebooklm <问题>
---

# notebooklm

> 安装、配置见仓库 [README](../README.md)。本文件是 Claude Code 加载 skill 时读的运行手册。

## 用法
- `/notebooklm <问题>` — 用默认笔记本回答
- `/notebooklm list` — 列出所有笔记本

## 执行

> 下方命令里的 `<PY>` 指你装好 notebooklm-py 的 Python 解释器（venv 里的 `bin/python3`）。
> 装好后在本文件里把 `<PY>` 直接替换成绝对路径，或者把 Python 加到 PATH 上。

**list：**
```bash
<PY> -c "
import asyncio, os
from pathlib import Path
from notebooklm import NotebookLMClient
from notebooklm.auth import AuthTokens
storage = Path(os.environ.get('NOTEBOOKLM_STORAGE',
    str(Path.home()/'.notebooklm/profiles/default/storage_state.json')))
async def main():
    auth = await AuthTokens.from_storage(storage)
    async with NotebookLMClient(auth) as c:
        for nb in await c.notebooks.list(): print(nb.id, nb.title)
asyncio.run(main())"
```

**提问：**
默认笔记本 ID 从 `default_notebook` 文件读取（首行）。
```bash
<PY> <SKILL_DIR>/query.py "<notebook_id>" "<question>"
```

## 归档决策（两段式）

query.py 的输出有两种情况：

### 情况 A — 自动归档完成
输出包含 `已归档到：<路径>`：归档目录之前是空的，脚本已直接新建。**无需后续动作。**

### 情况 B — STAGING 块
输出包含 `==NOTEBOOKLM_STAGING_BEGIN==` ... `==NOTEBOOKLM_STAGING_END==`，里面是 JSON：
```json
{
  "notebook_id": "...",
  "notebook_title": "...",
  "target_dir": "/path/to/.../notebooklm",
  "question": "本次提问",
  "answer_path": "/tmp/nblm_answer_xxxx.md",
  "existing_files": ["a.md", "b.md", ...],
  "new_command": "python3 .../archive.py new ..."
}
```

收到 STAGING 后按以下流程处理：

1. **轻量筛选**：用 `head -n 12` 批量看 `existing_files` 的 frontmatter（取每个文件的 `question:` 字段），判断哪些与本次 question 主题相关。
   - 示例：`for f in target_dir/*.md; do echo "=== $f ==="; head -n 12 "$f"; done`
2. **决策分支**：
   - **全部不相关** → 跑 `new_command` 新建归档。
   - **有相关候选**（通常 1–2 个）→ Read 候选全文 + Read `answer_path`，进入合并改写。

### 合并改写原则

**目标**：把新答的信息融合进旧文档，让旧文档"长大"，而不是堆砌新段落。

- **保留原文结构**（小节标题、frontmatter、Obsidian 块引用），不要推倒重来
- **新信息按主题嵌入对应小节**；旧文档没有的小节再新增
- **重叠内容择优**：保留更详细、更准确、推导更完整的版本
- **frontmatter 更新**：
  - 在原 `question` 字段附近加 `updated: YYYY-MM-DD HH:MM`
  - 追加本次 question 到 `questions: [...]` 列表（如无则新建）
- **不要丢失提问历史**：在文档底部维护 `## 提问历史` 小节，按时间倒序追加 `- YYYY-MM-DD HH:MM — <question>`
- 改完后告知用户合并到了哪个文件

### 临时文件
`answer_path` 是 `/tmp/` 下的临时 md，系统会自动清理；不需要手动删除。

## 注意
- 认证过期会自动刷新（从 Chrome cookies 读取，需要 `NOTEBOOKLM_CLI` 指向 notebooklm-py 的 CLI 入口）
- 结果自动在浏览器中打开，含 MathJax 公式渲染
- 手动刷新登录：`notebooklm login --browser-cookies chrome`
- 国内网络环境如果 NotebookLM 直连不通，需要确保系统代理已生效（TUN/全局），或在执行命令前 `export HTTPS_PROXY=...`
