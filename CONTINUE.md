# 回家继续开发手册

更新时间：2026-06-18

这份文档用于换电脑或隔一段时间后快速接上当前进度。

## 当前代码状态

- 当前分支：`main`
- 最近提交：`c06bb20 Add resumable runs and Bilibili MVP`
- `main` 当前比 `origin/main` ahead 1，尚未推送。
- 本地私密配置和产物不会提交：
  - `config.local.toml`
  - `*.cookies.txt`
  - `outputs/`

## 已完成能力

- YouTube 链接总结。
- B站链接 MVP：支持 `bilibili.com` / `b23.tv`，但当前环境直连 B站常见 `HTTP Error 412`，通常需要手动导出的 `cookies.txt`。
- 优先读取平台字幕。
- 平台字幕不可用时下载音频并用 `faster-whisper` ASR。
- 短 transcript 直接总结。
- 长 transcript 分块总结，再全局汇总。
- `--resume` 断点续跑：
  - 复用 `transcript.raw.md`
  - 复用 `transcript.cleaned.md`
  - 复用已完成的 `chunk_summaries.md`
- 每次运行生成 `run_state.json`，记录阶段、LLM 配置摘要、chunk 状态和失败信息。
- 完整 transcript 会保留，不只是保留 LLM 总结。

## 回家环境准备

```powershell
cd F:\codex-project\video-summary
python -m pip install -e ".[all]"
python -m unittest discover -s tests
```

如果换了电脑，先复制模板：

```powershell
Copy-Item config.example.toml config.local.toml
```

然后编辑 `config.local.toml`。阿里云百炼推荐配置：

```toml
[llm]
provider = "openai_compatible"
api_key = "你的百炼 API key"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = "deepseek-v4-flash"
temperature = 0.2
timeout = 120
```

ASR 推荐先用小模型：

```toml
[asr]
model = "small"
language = "auto"
device = "auto"
compute_type = "default"
```

## 常用命令

有字幕 YouTube：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=gN9dlisaQVM" --output outputs
```

无字幕 YouTube，走 ASR：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=ARMSVQU7Qj8" --output outputs --asr-model small
```

长视频断点续跑：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=UuIEbpQms8o" --output outputs --resume
```

B站公开视频：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs
```

B站需要登录态时：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs --cookies path\to\bilibili.cookies.txt
```

不要把 cookie 内容发到聊天里，也不要提交到 git。

## 已真实验证的视频

YouTube 有字幕：

- URL: `https://www.youtube.com/watch?v=gN9dlisaQVM`
- 结果：字幕路径成功，完整导出成功。

YouTube 无字幕 / ASR：

- URL: `https://www.youtube.com/watch?v=ARMSVQU7Qj8`
- 结果：字幕不可用后进入 ASR，完整导出成功。

YouTube 长视频：

- URL: `https://www.youtube.com/watch?v=UuIEbpQms8o`
- 标题：`CS50x 2026 - Lecture 0 - Scratch`
- 时长：7253 秒
- 结果：10 个 chunk，完整导出成功；`--resume` 可 10/10 chunk 复用。

B站：

- 当前环境直连公开视频遇到 `HTTP Error 412`。
- 代码已支持 `--cookies`，但还需要用户手动提供 `cookies.txt` 后做真实端到端验证。

## 输出文件说明

每个输出目录通常包含：

- `summary.md`：最终总结。
- `transcript.raw.md`：平台字幕或 ASR 原始 transcript。
- `transcript.cleaned.md`：清洗后的完整 transcript。
- `chunk_summaries.md`：长视频分块摘要。
- `metadata.json`：视频元数据、LLM 配置摘要、分块参数。
- `run_state.json`：运行状态、失败阶段、chunk 状态。

## 下一步建议

优先级最高：

1. 用手动导出的 B站 `cookies.txt` 做一次真实端到端验证。
2. 修复验证中暴露的 B站字幕、分 P、音频下载或 ASR 问题。

随后可以做：

1. 增强缓存控制：
   - 强制重跑全部 chunk。
   - 只重跑指定 chunk。
   - 复用最终 `summary.md`。
2. 本地文件输入。
3. 批处理。
4. Web UI。

## 提交前检查

```powershell
python -m unittest discover -s tests
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('src').rglob('*.py')]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('tests').rglob('*.py')]; print('syntax ok')"
git status --short --ignored
```

确认不要提交：

- `config.local.toml`
- `*.cookies.txt`
- `outputs/`
- `__pycache__/`
