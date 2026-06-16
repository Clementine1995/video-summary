# video-summary

个人使用的视频内容总结工具。当前实现到第 3 阶段基础原型：输入 YouTube 链接后，优先获取字幕；如果字幕不可用，会下载音频并使用本地 `faster-whisper` 转写。短 transcript 会直接调用 OpenAI-compatible LLM 总结，长 transcript 会先分块摘要，再全局归纳并导出 Markdown。

## 准备

安装当前项目、`yt-dlp` 和 `faster-whisper`：

```powershell
python -m pip install -e ".[all]"
```

还需要本机可用 `ffmpeg`，因为无字幕视频需要把音频统一转换成 16kHz 单声道 wav。

## 配置 LLM

默认推荐先用 DeepSeek：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek key"
$env:VIDEO_SUMMARY_LLM_PROVIDER="deepseek"
$env:VIDEO_SUMMARY_LLM_MODEL="deepseek-chat"
```

也可以切到 OpenAI：

```powershell
$env:OPENAI_API_KEY="你的 OpenAI API key"
$env:VIDEO_SUMMARY_LLM_PROVIDER="openai"
$env:VIDEO_SUMMARY_LLM_MODEL="gpt-4.1-mini"
```

其他 OpenAI-compatible 服务可以这样配：

```powershell
$env:VIDEO_SUMMARY_LLM_PROVIDER="openai_compatible"
$env:VIDEO_SUMMARY_LLM_API_KEY="你的 key"
$env:VIDEO_SUMMARY_LLM_BASE_URL="https://example.com/v1"
$env:VIDEO_SUMMARY_LLM_MODEL="your-model-name"
```

## 配置 ASR

默认 ASR 配置：

```powershell
$env:VIDEO_SUMMARY_ASR_MODEL="medium"
$env:VIDEO_SUMMARY_ASR_LANGUAGE="auto"
$env:VIDEO_SUMMARY_ASR_DEVICE="auto"
```

如果机器配置一般，可以先用更小的模型：

```powershell
$env:VIDEO_SUMMARY_ASR_MODEL="small"
```

## 配置分块

默认长 transcript 按约 12 分钟或 30000 字符切分：

```powershell
$env:VIDEO_SUMMARY_CHUNK_TARGET_MINUTES="12"
$env:VIDEO_SUMMARY_CHUNK_MAX_CHARS="30000"
```

## 使用

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs
```

也可以临时从命令行覆盖模型配置：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --llm-provider deepseek --llm-model deepseek-chat --asr-model small
```

长视频分块参数也可以临时覆盖：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --chunk-target-minutes 10 --chunk-max-chars 25000
```

每次成功运行会生成一个独立目录，包含：

- `summary.md`
- `transcript.raw.md`
- `transcript.cleaned.md`
- `chunk_summaries.md`（仅长视频触发分块总结时生成）
- `metadata.json`

如果进入 ASR 流程，下载后的音频会保留在 `outputs/_work/`，方便转写失败后重试。

## 当前范围

- 支持 YouTube 链接
- 优先使用视频已有字幕或自动字幕
- 字幕不可用时使用 `yt-dlp` + `ffmpeg` 提取音频
- 使用 `faster-whisper` 本地转写
- 长 transcript 会按时间或字符数分块总结，再做全局归纳
- 处理失败时给出可读错误信息

B站、本地文件、批处理和 Web UI 会在后续阶段加入。
