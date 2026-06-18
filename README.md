# video-summary

个人使用的视频内容总结工具。支持 YouTube、B站和本地音视频文件：优先获取平台字幕；字幕不可用或输入为本地文件时，会用 `ffmpeg` 提取音频并通过 `faster-whisper` 本地转写。短 transcript 直接调用 OpenAI-compatible LLM 总结，长 transcript 会先分块摘要，再全局归纳并导出 Markdown。

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

阿里云百炼兼容模式示例：

```toml
[llm]
provider = "openai_compatible"
api_key = "你的百炼 API key"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = "deepseek-v4-flash"
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

## 命令速查

进入项目目录：

```powershell
cd E:\workspace\video-summary
```

创建并启用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -U pip
python -m pip install -e ".[all]"
```

查看帮助：

```powershell
python -m video_summary --help
```

YouTube 有字幕视频：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs
```

已验证样例：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=gN9dlisaQVM" --output outputs
```

YouTube 无字幕视频，走 ASR：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=ARMSVQU7Qj8" --output outputs --asr-model small
```

长视频：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=UuIEbpQms8o" --output outputs
```

长视频续跑：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=UuIEbpQms8o" --output outputs --resume
```

B站公开视频：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs
```

B站需要登录态、返回 412、会员/地区权限时，手动导出 `cookies.txt` 后传入：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV..." --output outputs --cookies path\to\cookies.txt
```

B站已验证样例：

```powershell
python -m video_summary "https://www.bilibili.com/video/BV1GY4y1U7oq" --output outputs --cookies bilibili.cookies.txt --asr-model small
```

本地音视频文件：

```powershell
python -m video_summary "D:\videos\meeting.mp4" --output outputs --asr-model small
```

临时覆盖 LLM：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --llm-provider deepseek --llm-model deepseek-v4-flash --asr-model small
```

临时覆盖 ASR：

```powershell
python -m video_summary "D:\videos\meeting.mp4" --output outputs --asr-model small --asr-language zh
```

临时覆盖分块参数：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --chunk-target-minutes 10 --chunk-max-chars 25000
```

复用 transcript 和 chunk summaries：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume
```

续跑会优先复用同标题输出目录里的：

- `transcript.raw.md`
- `transcript.cleaned.md`
- `chunk_summaries.md`

每个新 chunk 完成后会立刻写入 `chunk_summaries.md`，因此 LLM 在中途失败时，下次可以从未完成的 chunk 继续。

缓存控制：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume --reuse-summary
```

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume --force-chunks
```

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume --rerun-chunk 2
```

只重跑多个 chunk：

```powershell
python -m video_summary "https://www.youtube.com/watch?v=..." --output outputs --resume --rerun-chunk 2 --rerun-chunk 4
```

运行测试：

```powershell
python -m unittest discover -s tests
```

语法检查：

```powershell
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('src').rglob('*.py')]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('tests').rglob('*.py')]; print('syntax ok')"
```

检查不要提交本地私密文件和产物：

```powershell
git status --short --ignored
```

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
- 支持本地音视频文件：直接走 ffmpeg + ASR
- 优先使用视频已有字幕或自动字幕
- 字幕不可用时使用 `yt-dlp` + `ffmpeg` 提取音频
- 使用 `faster-whisper` 本地转写
- 长 transcript 会按时间或字符数分块总结，再做全局归纳
- 处理失败时给出可读错误信息

B站当前环境可能需要手动导出的 `cookies.txt`。批处理和 Web UI 会在后续阶段加入。
