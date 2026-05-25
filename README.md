# claude-notebooklm-skill

让 [Claude Code](https://claude.com/claude-code) 通过 [NotebookLM](https://notebooklm.google.com) 提问，并把回答智能合并到你的 [Obsidian](https://obsidian.md) 笔记里。

适用场景：用 NotebookLM 把教材 / 论文 / 文档喂进去当 RAG 源，让 Claude Code 当你的 CLI 入口，问出来的答案直接长进你的知识库 —— 而不是散落成一堆"YYYY-MM-DD 问题.md"碎片。

## 工作流

```
你           Claude Code             NotebookLM            Obsidian Vault
 │                │                       │                       │
 │ /notebooklm Q  │                       │                       │
 ├───────────────►│                       │                       │
 │                │  query.py(Q)          │                       │
 │                ├──────────────────────►│                       │
 │                │              Gemini 答 │                       │
 │                │◄──────────────────────┤                       │
 │                │  Chrome 渲染（MathJax）                        │
 │                │                       │                       │
 │                │  归档目录空？                                  │
 │                │   ├─ 是 ──► 直接新建 ──────────────────────────►│
 │                │   └─ 否 ──► 输出 STAGING 信息                  │
 │                │            ↓                                  │
 │                │       Claude 读现有笔记 frontmatter            │
 │                │       挑相关候选，Read 全文                    │
 │                │       合并改写，保留结构 + 提问历史 ──────────►│
```

## 解决了什么问题

直觉做法是"每次提问 → 存一份新 md"，但很快就发现：
- 第二轮追问得到的补充信息，跟第一轮的答案被存在两个文件里，知识被割裂
- 同一个主题反复提问，会出现 5、6 份内容高度重叠的笔记

这个 skill 把"归档"这步交给 Claude 自己做决策（**两段式**）：
1. 脚本先把回答写到临时文件，再把目录里已有笔记列表打印出来（不传内容，省 token）
2. Claude 用 `head` 看 frontmatter 挑出相关候选，再 Read 全文进行**改写式合并** —— 新信息按主题嵌入对应小节，重叠内容择优保留，旧文档"长大"而不是被堆叠

如果归档目录是空的（第一次问），脚本直接新建，**不调用 Claude**，零 token 开销。

## 安装

### 0. 先决条件
- Python 3.10+
- macOS / Linux / Windows（脚本里的"打开浏览器"做了跨平台分支）
- [Claude Code](https://claude.com/claude-code) 已安装
- Obsidian vault（任何位置都行）
- 一个 Google 账号 + 一个 [NotebookLM](https://notebooklm.google.com) 笔记本（已上传你想检索的资料）

### 1. 克隆
```bash
git clone https://github.com/loml13/claude-notebooklm-skill.git
cd claude-notebooklm-skill
```

### 2. 装 Python 依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 给 notebooklm-py 做一次性登录
```bash
notebooklm login --browser-cookies chrome
```
（从已登录的 Chrome cookies 里抽 NotebookLM 凭据；详见 [notebooklm-py](https://github.com/teng-lin/notebooklm-py)）

### 4. 配置归档路由
```bash
cp skill/archive_config.example.json skill/archive_config.json
```
编辑 `skill/archive_config.json`：

```json
{
  "vault": "~/Documents/MyVault",
  "default": "Inbox/notebooklm",
  "by_notebook_id": {
    "<your-notebook-uuid>": "Books/通信原理/notebooklm"
  }
}
```
- `vault`：你的 Obsidian vault 根目录
- `default`：未在 `by_notebook_id` 里映射的笔记本，会归到 `vault/default/<笔记本标题>/`
- `by_notebook_id`：把特定笔记本钉到特定子目录（建议每门课程/每个项目一个）

### 5. 设默认笔记本（可选）
```bash
echo "<your-notebook-uuid>" > skill/default_notebook
```
不设也行，命令里手动传 notebook_id 即可。

> 取笔记本 ID：先随便挑一个，用 `python3 -c "..."`（见 SKILL.md 里的 list 命令）打印出来；或者打开 https://notebooklm.google.com，URL 末段 `notebook/<UUID>` 就是。

### 6. 注册 skill 到 Claude Code
把 SKILL.md 软链到 Claude Code 的全局 skills 目录：
```bash
mkdir -p ~/.claude/skills
ln -sf "$(pwd)/skill" ~/.claude/skills/notebooklm
```

然后**编辑 `~/.claude/skills/notebooklm/SKILL.md`**，把里面 `<PY>` 替换成你 venv 里的 Python 绝对路径（如 `/path/to/repo/.venv/bin/python3`），`<SKILL_DIR>` 替换成 `~/.claude/skills/notebooklm`。

## 用法

```bash
claude
> /notebooklm 解释残留边带调制的频谱互补对称条件
```

接下来：
- 浏览器自动弹出，渲染 Gemini 的回答（含 LaTeX 公式）
- 同时 Claude Code 那边：
  - 若该笔记本目录是空的 → 终端打印 `已归档到：<路径>`，结束
  - 否则 Claude 自动决定新建 or 合并到现有笔记，告诉你最终落到哪个文件

列出所有笔记本：
```bash
> /notebooklm list
```

## 归档文件长什么样

```markdown
---
notebook: 通信原理（樊昌信第 7 版）
notebook_id: c33a803a-...
date: 2026-05-24 11:30
updated: 2026-05-25 10:30
question: "全面讲解复习第五章内容"
questions:
  - "2026-05-24 11:30 — 全面讲解复习第五章内容"
  - "2026-05-24 14:07 — 详细讲解常规调幅..."
  - "2026-05-25 10:30 — 每种调制方法都像 AM 这样详细展开"
tags: [notebooklm]
---

> [!question] 问题
> 全面讲解复习第五章内容

# 回答

## 1. 常规调幅 (AM)
... 详细内容 ...

## 提问历史
- 2026-05-25 10:30 — 每种调制方法都像 AM 这样详细展开
- 2026-05-24 14:07 — 详细讲解常规调幅...
- 2026-05-24 11:30 — 全面讲解复习第五章内容
```

第二次、第三次追问的新信息会按主题嵌入到对应小节，frontmatter 维护一份完整的提问时间线。

## 致谢

- [notebooklm-py](https://github.com/teng-lin/notebooklm-py) by [@teng-lin](https://github.com/teng-lin) —— 提供与 NotebookLM 对话的 Python 客户端
- [Claude Code](https://claude.com/claude-code) by Anthropic —— 让 skill 这种工作流变得可能

## License

[MIT](LICENSE)
