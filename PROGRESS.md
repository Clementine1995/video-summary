# video-summary 当前开发进度

更新时间：2026-06-16

## 当前状态

项目已经从需求文档推进到第 2 阶段原型。

已完成：

- 搭建 Python CLI 项目结构。
- 支持 YouTube 链接输入。
- 使用 `yt-dlp` 读取 YouTube 元数据。
- 优先获取 YouTube 官方字幕或自动字幕。
- 字幕不可用时，使用 `yt-dlp` 下载音频，并通过 `ffmpeg` 转成 16kHz 单声道 wav。
- 接入 `faster-whisper` 做本地 ASR 转写。
- 对字幕/转写结果做轻量清洗：去重、合并短字幕、去除少量口头填充词。
- 支持 DeepSeek、OpenAI、其他 OpenAI-compatible LLM 配置。
- 导出：
  - `summary.md`
  - `transcript.raw.md`
  - `transcript.cleaned.md`
  - `metadata.json`
- 增加 `.gitignore`，忽略 `__pycache__`、`outputs/`、虚拟环境等本地产物。

未完成：

- 真实 YouTube + ASR + LLM 端到端测试尚未跑通，因为当前环境没有确认 API key、网络、ffmpeg、faster-whisper 模型下载状态。
- B站支持未开始。
- 本地文件输入未开始。
- 长视频分块总结未开始。
- 批处理和 Web UI 未开始。
- 当前改动尚未成功 git commit，原因是当前沙箱不允许写入 `.git/index.lock`。

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
- `src/video_summary/exporter.py`：Markdown 和 metadata 导出。
- `src/video_summary/models.py`：数据结构。
- `src/video_summary/errors.py`：用户可读错误类型。

## 当前运行方式

安装：

```powershell
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
  -> summarize_with_openai_compatible
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
$env:PYTHONDONTWRITEBYTECODE='1'
python -m compileall src
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

## 建议提交命令

当前这台电脑上提交被权限限制卡住了。换到正常终端后执行：

```powershell
cd F:\codex-project\video-summary
git add .
git commit -m "Implement YouTube summary CLI with ASR fallback"
```

如果回家路径不同，先进入项目目录再执行即可。

## 下一步开发建议

优先顺序建议：

1. 跑通一个真实 YouTube 有字幕视频端到端。
2. 跑通一个真实 YouTube 无字幕视频 ASR 端到端。
3. 修正真实运行中暴露的 `yt-dlp`、字幕格式、DeepSeek 返回格式、ASR 设备兼容问题。
4. 开始第 3 阶段：长视频分块总结。

第 3 阶段建议改动：

- 增加 `chunker.py`。
- 按 8-15 分钟或最大字符数切分 cleaned transcript。
- 每个 chunk 单独调用 LLM 生成局部摘要。
- 增加全局汇总 prompt，把 chunk summaries 去重归纳为最终 `summary.md`。
- 导出 `chunks/` 或 `chunk_summaries.md`，方便调试和失败重试。
