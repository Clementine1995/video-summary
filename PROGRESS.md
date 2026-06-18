# video-summary 当前开发进度

更新时间：2026-06-18

## 当前状态

项目已经从需求文档推进到第 3 阶段基础原型。

已完成：

- 搭建 Python CLI 项目结构。
- 支持 YouTube 链接输入。
- 使用 `yt-dlp` 读取 YouTube 元数据。
- 优先获取 YouTube 官方字幕或自动字幕。
- 字幕不可用时，使用 `yt-dlp` 下载音频，并通过 `ffmpeg` 转成 16kHz 单声道 wav。
- 接入 `faster-whisper` 做本地 ASR 转写。
- 对字幕/转写结果做轻量清洗：去重、合并短字幕、去除少量口头填充词。
- 支持 DeepSeek、OpenAI、其他 OpenAI-compatible LLM 配置。
- 支持长 transcript 自动分块、分块摘要和全局归纳。
- `yt-dlp` 调用优先使用当前 Python 环境中的 `python -m yt_dlp`，减少 PATH/虚拟环境激活问题。
- YouTube 字幕获取支持多个候选语言重试，避免单个语言字幕 429 或失败时直接中断。
- 导出：
  - `summary.md`
  - `transcript.raw.md`
  - `transcript.cleaned.md`
  - `chunk_summaries.md`（仅分块总结时生成）
  - `metadata.json`
- 增加 `.gitignore`，忽略 `__pycache__`、`outputs/`、虚拟环境等本地产物。
- 支持本地 `config.local.toml` 配置 LLM/ASR/分块参数，且该文件不会提交到 git。
- 已验证阿里云百炼 OpenAI-compatible 配置：
  - `base_url`: `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - `model`: `deepseek-v4-flash`
- ASR 音频转换支持系统 `ffmpeg`，也支持 `imageio-ffmpeg` 提供的内置 ffmpeg fallback。
- 已用真实 YouTube 有字幕视频完成端到端导出：
  - `https://www.youtube.com/watch?v=gN9dlisaQVM`
  - 字幕路径成功，输出 `summary.md`、`transcript.raw.md`、`transcript.cleaned.md`、`chunk_summaries.md`、`metadata.json`。
- 已用真实 YouTube 无字幕视频完成 ASR 端到端导出：
  - `https://www.youtube.com/watch?v=ARMSVQU7Qj8`
  - 字幕不可用后自动进入 ASR，使用 `faster-whisper small` 转写并成功导出。
- 已用真实 60 分钟以上长视频验证分块总结：
  - `https://www.youtube.com/watch?v=UuIEbpQms8o`
  - 标题：`CS50x 2026 - Lecture 0 - Scratch`
  - 时长：`7253` 秒，英文字幕路径成功。
  - 默认分块生成 `10` 个 chunk，完整导出 `summary.md`、`chunk_summaries.md`、transcript 和 metadata。
  - 实测完整运行耗时约 3 分半，分块摘要和全局汇总均成功。
- 已增加长视频基础缓存/断点续跑：
  - 新增 CLI 参数 `--resume`。
  - 同标题输出目录中已有 `transcript.raw.md` 和 `transcript.cleaned.md` 时会复用，不重新下载字幕或 ASR。
  - 已有 `chunk_summaries.md` 时会复用已完成 chunk。
  - 每个新 chunk 总结完成后立即写回 `chunk_summaries.md`，中途失败后可继续。
  - 已用 CS50x 2026 2 小时视频真实验证：10/10 chunk 可全部复用，续跑只重新生成全局 `summary.md`。
- 已增加失败诊断和运行记录：
  - 每次运行写入 `run_state.json`。
  - 记录运行状态、开始/结束时间、当前阶段、是否 `--resume`、LLM provider/base_url/model、分块参数。
  - 记录每个 chunk 的 `cached`、`completed` 或 `failed` 状态。
  - 失败时记录错误类型、错误信息和失败阶段。
  - 已验证成功路径和 LLM 401 失败路径；状态文件不保存 API key。
- 已开始 B站支持 MVP：
  - 支持识别 `bilibili.com` 和 `b23.tv` 链接。
  - 元数据、字幕和音频下载复用 yt-dlp 通道。
  - B站字幕 JSON 可解析为标准 transcript segment。
  - 字幕不可用时复用现有音频下载、ffmpeg fallback 和 faster-whisper ASR。
  - CLI 新增 `--cookies path\to\cookies.txt`，用于 B站登录态或受限视频。
  - 当前环境直连 B站公开视频遇到 `HTTP Error 412`，需要用户手动提供 cookies.txt 后继续真实端到端验证。
- 修正 ASR 清洗阶段连续短句过度合并的问题，避免长视频转写被压成过少片段，保留更细的时间戳粒度。

未完成：

- B站真实端到端导出尚未完成：当前环境需要手动导出的 B站 cookies.txt。
- 本地文件输入未开始。
- 长视频缓存/断点续跑仍可增强：最终 `summary.md` 也可缓存，或增加强制重跑某个 chunk 的参数。
- 批处理和 Web UI 未开始。

新增需求记录：

- 后续增强中增加“说话人分离”：无字幕视频进入 ASR 流程时，可选识别不同说话人并标注 Speaker 1、Speaker 2。
- 可选增加“声音类型辅助推测”：如疑似男声/疑似女声，但只能作为参考信息，不作为强准确字段。

## 重要文件

- `video-summary-dev-requirements.md`：原始需求文档。
- `README.md`：当前安装、配置和使用说明。
- `pyproject.toml`：项目配置和可选依赖。
- `.gitignore`：忽略 Python 缓存、输出目录、虚拟环境。
- `src/video_summary/cli.py`：命令行入口和主流程。
- `src/video_summary/youtube.py`：YouTube 元数据和字幕获取。
- `src/video_summary/audio.py`：YouTube 音频下载与 ffmpeg 转换。
- `src/video_summary/transcriber.py`：`faster-whisper` 转写。
- `src/video_summary/config.py`：LLM 和 ASR 配置。
- `src/video_summary/llm.py`：OpenAI-compatible chat completions 调用。
- `src/video_summary/cleaner.py`：文本清洗。
- `src/video_summary/chunker.py`：长 transcript 分块。
- `src/video_summary/exporter.py`：Markdown 和 metadata 导出。
- `src/video_summary/models.py`：数据结构。
- `src/video_summary/errors.py`：用户可读错误类型。

## 当前运行方式

安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[all]"
```

还需要本机安装并配置好：

- `ffmpeg`
- 可访问 YouTube 的网络环境
- DeepSeek 或 OpenAI-compatible API key

推荐先用 DeepSeek：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek key"
$env:VIDEO_SUMMARY_LLM_PROVIDER="deepseek"
$env:VIDEO_SUMMARY_LLM_MODEL="deepseek-chat"
```

如果机器配置一般，可以先用小 ASR 模型：

```powershell
$env:VIDEO_SUMMARY_ASR_MODEL="small"
```

运行：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --asr-model small
```

## 当前主流程

```text
CLI
  -> 校验 YouTube URL
  -> probe_youtube_metadata
  -> fetch_subtitles_for_metadata
      -> 成功：进入清洗
      -> 失败：download_youtube_audio -> transcribe_audio
  -> clean_segments
  -> summarize_with_chunking
      -> 短 transcript：单次 LLM 总结
      -> 长 transcript：分块摘要 -> 全局归纳
  -> export_result
```

## LLM 配置口子

默认 provider 是 `deepseek`。

DeepSeek：

```powershell
$env:DEEPSEEK_API_KEY="..."
$env:VIDEO_SUMMARY_LLM_PROVIDER="deepseek"
$env:VIDEO_SUMMARY_LLM_MODEL="deepseek-chat"
```

OpenAI：

```powershell
$env:OPENAI_API_KEY="..."
$env:VIDEO_SUMMARY_LLM_PROVIDER="openai"
$env:VIDEO_SUMMARY_LLM_MODEL="gpt-4.1-mini"
```

任意 OpenAI-compatible：

```powershell
$env:VIDEO_SUMMARY_LLM_PROVIDER="openai_compatible"
$env:VIDEO_SUMMARY_LLM_API_KEY="..."
$env:VIDEO_SUMMARY_LLM_BASE_URL="https://example.com/v1"
$env:VIDEO_SUMMARY_LLM_MODEL="your-model"
```

也可以用 CLI 参数临时覆盖：

```powershell
python -m video_summary "URL" --llm-provider deepseek --llm-model deepseek-chat
```

## ASR 配置口子

环境变量：

```powershell
$env:VIDEO_SUMMARY_ASR_MODEL="small"
$env:VIDEO_SUMMARY_ASR_LANGUAGE="auto"
$env:VIDEO_SUMMARY_ASR_DEVICE="auto"
$env:VIDEO_SUMMARY_ASR_COMPUTE_TYPE="default"
```

CLI 参数：

```powershell
python -m video_summary "URL" --asr-model small --asr-language zh
```

## 已做过的本地验证

通过：

```powershell
$env:PYTHONPATH='src'
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('src').rglob('*.py')]; print('syntax ok')"
```

通过：

```powershell
$env:PYTHONPATH='src'
python -m video_summary --help
```

通过：

```powershell
$env:PYTHONPATH='src'
python -c "from video_summary.config import load_asr_config; c=load_asr_config(model='small', language='auto'); print(c.model, c.language, c.device, c.compute_type)"
```

通过：

```powershell
$env:PYTHONPATH='src'
python -m video_summary not-a-url
```

预期输出为用户可读错误：

```text
处理失败：第 2 阶段仍只支持 YouTube 链接。B站和本地文件会在后续阶段加入。
```

真实 YouTube 预检：

- 用户在本机成功读取视频 `https://www.youtube.com/watch?v=gN9dlisaQVM` 的元数据。
- 元数据结果：
  - 标题：`TED 中英雙語字幕:  如何讓壓力成為你的朋友`
  - 时长：`869` 秒
- 首次字幕下载在 `zh-Hans` 上遇到 `HTTP Error 429: Too Many Requests`。
- 已修复为多候选字幕语言重试；用户后续反馈“没报错了”。
- 该预检命令只打印结果，不会生成 `outputs/`；完整导出仍需运行 `python -m video_summary ... --output outputs` 并配置 LLM API key。

## 回家继续前建议先做

1. 确认文件完整同步到新电脑。
2. 在新电脑安装依赖：

```powershell
python -m pip install -e ".[all]"
```

3. 确认 `ffmpeg` 可用：

```powershell
ffmpeg -version
```

4. 配置 DeepSeek key。
5. 找一个有字幕的短 YouTube 视频先测试字幕路径。
6. 再找一个无字幕或字幕不可用的短视频测试 ASR 路径。

## 下一步开发建议

优先顺序建议：

1. 配置 DeepSeek 或 OpenAI-compatible API key。
2. 跑通一个真实 YouTube 有字幕视频完整导出。
3. 跑通一个真实 YouTube 无字幕视频 ASR 端到端。
4. 修正真实运行中暴露的 `yt-dlp`、字幕格式、DeepSeek 返回格式、ASR 设备兼容问题。
5. 使用 60 分钟以上视频验证长视频分块总结。

以上 1-5 已完成。下一步建议优先做：

1. 增强缓存控制：
   - 支持强制重跑全部 chunk。
   - 支持只重跑指定 chunk。
   - 支持复用最终 `summary.md`。
2. 再考虑 B站支持或本地文件输入。

第 3 阶段建议改动：

- 已增加 `chunker.py`。
- 已支持按目标分钟数或最大字符数切分 cleaned transcript。
- 已支持每个 chunk 单独调用 LLM 生成局部摘要。
- 已增加全局汇总 prompt，把 chunk summaries 去重归纳为最终 `summary.md`。
- 已导出 `chunk_summaries.md`，方便调试和失败重试。
