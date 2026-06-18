# video-summary

个人使用的视频内容总结工具。当前实现到第 3 阶段基础原型：输入 YouTube 链接后，优先获取字幕；如果字幕不可用，会下载音频并使用本地 `faster-whisper` 转写。短 transcript 会直接调用 OpenAI-compatible LLM 总结，长 transcript 会先分块摘要，再全局归纳并导出 Markdown。

## 准备

安装当前项目、`yt-dlp` 和 `faster-whisper`：

```powershell
python -m pip install -e ".[all]"
```

无字幕视频需要用 `ffmpeg` 把音频统一转换成 16kHz 单声道 wav；项目会优先使用系统 `ffmpeg`，如果没有安装，则使用 `imageio-ffmpeg` 提供的内置可执行文件。

## 配置 LLM

复制配置模板：

```powershell
Copy-Item config.example.toml config.local.toml
```

然后打开 `config.local.toml`，直接填写：

```toml
[llm]
provider = "deepseek"
api_key = "你的 DeepSeek key"
model = "deepseek-v4-flash"
```

如果你想用质量更强的 Pro，把这一行改成：

```toml
model = "deepseek-v4-pro"
```

也可以切到 OpenAI：

```toml
[llm]
provider = "openai"
api_key = "你的 OpenAI API key"
model = "gpt-4.1-mini"
```

其他 OpenAI-compatible 服务可以这样配：

```toml
[llm]
provider = "openai_compatible"
api_key = "你的 key"
base_url = "https://example.com/v1"
model = "your-model-name"
```

`config.local.toml` 是本地私密文件，已被 `.gitignore` 忽略，不会被提交。命令行参数和环境变量仍然可用，并且优先级高于配置文件。也可以用 `VIDEO_SUMMARY_CONFIG` 指定其他配置文件路径。

## 配置 ASR

默认 ASR 配置：

```toml
[asr]
model = "medium"
language = "auto"
device = "auto"
compute_type = "default"
```

如果机器配置一般，可以先用更小的模型：

```toml
[asr]
model = "small"
```

## 配置分块

默认长 transcript 按约 12 分钟或 30000 字符切分：

```toml
[chunking]
target_minutes = 12
max_chars = 30000
```

## 使用

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs
```

也支持 B站公开视频链接：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs
```

如果 B站返回 412、登录限制或需要会员/地区权限，可以手动导出 `cookies.txt` 后传入：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs --cookies path\to\cookies.txt
```

也可以临时从命令行覆盖模型配置：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --llm-provider deepseek --llm-model deepseek-v4-flash --asr-model small
```

长视频分块参数也可以临时覆盖：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --chunk-target-minutes 10 --chunk-max-chars 25000
```

如果长视频中途失败，或想复用已经生成的 transcript / chunk summaries，可以加 `--resume`：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume
```

续跑会优先复用同标题输出目录里的：

- `transcript.raw.md`
- `transcript.cleaned.md`
- `chunk_summaries.md`

每个新 chunk 完成后会立刻写入 `chunk_summaries.md`，因此 LLM 在中途失败时，下次可以从未完成的 chunk 继续。

每次成功运行会生成一个独立目录，包含：

- `summary.md`
- `transcript.raw.md`
- `transcript.cleaned.md`
- `chunk_summaries.md`（仅长视频触发分块总结时生成）
- `metadata.json`
- `run_state.json`

`run_state.json` 会记录本次运行状态、是否使用 `--resume`、LLM provider/model、分块参数、每个 chunk 的 cached/completed/failed 状态，以及失败阶段和错误信息。它不会保存 API key。

如果进入 ASR 流程，下载后的音频会保留在 `outputs/_work/`，方便转写失败后重试。

## 当前范围

- 支持 YouTube 链接
- 支持 B站公开视频链接 MVP：优先字幕，字幕不可用时走 ASR
- 优先使用视频已有字幕或自动字幕
- 字幕不可用时使用 `yt-dlp` + `ffmpeg` 提取音频
- 使用 `faster-whisper` 本地转写
- 长 transcript 会按时间或字符数分块总结，再做全局归纳
- 处理失败时给出可读错误信息

B站、本地文件、批处理和 Web UI 会在后续阶段加入。
