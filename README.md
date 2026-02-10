# Claude Adapter Python

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

[English](#overview) | [中文](README_CN.md)

![UI.png](./image/ui.png)
---

## Overview

Claude Adapter Python is a local HTTP proxy server that lets you use **OpenAI-compatible APIs** with [**Claude Code**](https://github.com/anthropics/claude-code).

It translates Anthropic Messages API requests to OpenAI Chat Completions format, so you can:

- Use any OpenAI-compatible API with Claude Code
- Easily switch between different AI providers
- Run local models with Ollama or LM Studio
- Full tool calling support, both native and XML modes
- Streaming responses for real-time interaction

## Supported Providers

| Category | Provider | Type | Description |
|----------|----------|------|-------------|
| **Free** | NVIDIA NIM | Cloud API | https://build.nvidia.com |
| **Free** | Ollama | Local + Cloud | https://ollama.com, supports local and cloud models |
| **Free** | LM Studio | Local only | https://lmstudio.ai, local models only |
| **Paid** | Kimi | Cloud API | https://platform.moonshot.cn |
| **Paid** | DeepSeek | Cloud API | https://platform.deepseek.com |
| **Paid** | GLM Z.ai | Cloud API | https://bigmodel.cn |
| **Paid** | MiniMax | Cloud API | https://platform.minimaxi.com |
| **Custom** | OpenAI-compatible | Any | Any OpenAI-compatible endpoint |

## Installation

```bash
# From source
git clone <repo-url>
cd claude-adapter-py
pip install -e .

# Or from PyPI when published
pip install claude-adapter-py
```

## Quick Start

### 1. Run the adapter

```bash
claude-adapter-py
```

### 2. Select provider type

The CLI starts with provider selection. You will see three categories plus navigation:

```
? Choose provider type 选择提供商类型:
  Free    NVIDIA, Ollama, LM Studio
  Paid    Kimi, DeepSeek, GLM, MiniMax
  Custom  OpenAI-compatible endpoint
  Go back  返回重新选择
  Exit  退出
```

![Select.png](./image/Select.png)

### 3. Select specific provider

After choosing a category, pick the provider (each menu also has **Go back** and **Exit**):

```
? Choose provider 选择提供商:
  NVIDIA NIM              NVIDIA NIM API (https://build.nvidia.com/)
  Ollama                  Ollama localhost:11434 (https://ollama.com/)
  LM Studio               LM Studio localhost:1234 (https://lmstudio.ai/)
  Go back  返回重新选择
  Exit  退出
```

![provider.png](./image/provider.png)

### 4. Use saved config or configure

**If a saved config exists** for the selected provider:

```
? NVIDIA NIM found, choose action 已有配置，选择操作:
  Use saved config  使用已存储的 NVIDIA NIM 配置启动
  Reconfigure  重新配置 NVIDIA NIM 参数
  Go back  返回重新选择
  Exit  退出
```

![config.png](./image/config.png)

**If no saved config exists**:

```
? No config for Ollama, choose action 无已存储配置，选择操作:
  Configure  配置 Ollama 参数
  Go back  返回重新选择
  Exit  退出
```

Every step (including setup guidance and tool-format selection) offers **Go back** to return to the previous choice and **Exit** to quit.

### 5. The adapter will

- Show setup guidance specific to your provider
- Walk you through API key, base URL, port, model mappings, tool format
- Save the configuration for future use
- Start the HTTP server on `http://localhost:3080`
- Update `~/.claude/settings.json` automatically

### 6. Use Claude Code normally

All requests will be routed through the adapter.

```bash
# Copy this to set the environment variable:
export ANTHROPIC_BASE_URL="http://localhost:3080"
```

---

## Provider Setup Guides

### NVIDIA NIM  Free, Cloud

1. Visit https://build.nvidia.com and sign up
2. Get your API Key, format: `nvapi-xxxx`
3. Choose a model, recommended: `minimaxai/minimax-m2.1`
4. Configure and start

![NVIDIA.png](./image/NVIDIA.png)
![claudecode-nvidia.png](./image/claudecode-nvidia.png)

### Ollama  Free, Local + Cloud

Ollama supports both **local models** and **cloud models**.

```bash
# 1. Install Ollama
#    curl -fsSL https://ollama.com/install.sh | sh

# 2. Start the service
ollama serve

# 3. Pull a local model
ollama pull gpt-oss:20b

# 3b. Or pull a cloud model
ollama pull kimi-k2.5:cloud

# 4. Check available models
ollama list
```

> Make sure `ollama serve` is running before starting the adapter.

![ollama_list.png](./image/ollama_list.png)
![ollama_serve.png](./image/ollama_serve.png)
![ollama.png](./image/ollama.png)
![ollama_config.png](./image/ollama_config.png)
![claudecode_ollama.png](./image/claudecode_ollama.png)
![ollama_cloud.png](./image/ollama_cloud.png)

### LM Studio  Free, Local only

LM Studio **only supports local models**. You must download, load, and serve before use.

```bash
# 1. Download LM Studio from https://lmstudio.ai

# 2. Download a model
lms get <model-name>

# 3. Load the model into memory
lms load <model-name>

# 4. Start the server
lms server start
```

> The server runs on port 1234 by default. Increase Context Length to 16384+ in LM Studio settings.

![lms_model.png](./image/lms_model.png)
![lms_config.png](./image/lms_config.png)
![lms.png](./image/lms.png)
![claudecode_lms.png](./image/claudecode_lms.png)

### Kimi  Paid, Cloud

1. Visit https://platform.moonshot.cn/console/api-keys
2. Sign up and create an API Key, format: `sk-xxxx`
3. Recommended model: `kimi-k2.5`

### DeepSeek  Paid, Cloud

1. Visit https://platform.deepseek.com/api_keys
2. Sign up and create an API Key, format: `sk-xxxx`
3. Recommended model: `deepseek-chat`

### Z.ai  Paid, Cloud

1. Visit https://bigmodel.cn/usercenter/proj-mgmt/apikeys
2. Sign up and create an API Key, format: `xxxx.xxxx`
3. Recommended model: `glm-4.7`

### MiniMax  Paid, Cloud

1. Visit https://platform.minimaxi.com/user-center/basic-information/interface-key
2. Sign up and create an API Key, format: `eyxxxx`
3. Recommended model: `MiniMax-M2.1`

### Custom OpenAI-compatible

1. Prepare any OpenAI-compatible API endpoint
2. Enter the Base URL, e.g. `https://api.openai.com/v1`
3. Enter your API Key
4. Enter the model name

---

## CLI Commands

```bash
# Start server (interactive: select provider, then use config / reconfigure / configure)
claude-adapter-py

# Force reconfigure current provider
claude-adapter-py -r

# Custom port
claude-adapter-py -p 8080

# Skip Claude settings update
claude-adapter-py --no-claude-settings

# List saved providers
claude-adapter-py ls

# Remove a provider config (prompt includes Go back / Exit)
claude-adapter-py rm <provider-name>

# Show help
claude-adapter-py -h
```

In every interactive menu you can choose **Go back** to return to the previous step or **Exit** to quit.

## Configuration

All configs are stored in `~/.claude-adapter/`:

```
~/.claude-adapter/
├── settings.json           # Active provider
├── metadata.json           # User metadata
├── providers/              # Per-provider configs
│   ├── nvidia.json
│   ├── ollama.json
│   └── ...
├── token_usage/            # Daily token usage logs
│   └── 2026-02-10.jsonl
└── error_logs/             # Error logs
    └── 2026-02-10.jsonl
```

### Example provider config

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama",
  "models": {
    "opus": "qwen2.5-coder:32b",
    "sonnet": "qwen2.5-coder:14b",
    "haiku": "qwen2.5-coder:7b"
  },
  "tool_format": "native",
  "port": 3080,
  "max_context_window": 8192
}
```

## Architecture

```
Claude Code  ->  Anthropic API request
                     |
              Claude Adapter  localhost:3080
                     |
              Convert to OpenAI format
                     |
              OpenAI-compatible API  NVIDIA, Ollama, etc.
                     |
              Convert back to Anthropic format
                     |
              Claude Code  receives response
```

## Tool Calling Modes

### Native mode  Recommended for cloud APIs

Uses OpenAI native function calling. Best for NVIDIA, Kimi, DeepSeek, GLM, MiniMax, and cloud providers.

### XML mode  Recommended for local models

Injects XML tool instructions into the system prompt. Models output `<tool_code>` XML tags. Better for local models without native function calling support.

## Troubleshooting

### Port already in use

The adapter auto-finds the next available port, or specify one:

```bash
# Check and kill the process using the port
lsof -i :3080
kill -9 <id>

# Or change the port
claude-adapter-py -p 8080
```

### Context window errors with LM Studio or Ollama

- Increase context length in LM Studio GUI to 16384+
- Or edit `~/.claude-adapter/providers/lmstudio.json` and set `"max_context_window": 32768`

### API key issues

```bash
claude-adapter-py -r
```

### Model not found

**Ollama**: run `ollama list` and `ollama pull <model>`

**LM Studio**: make sure the model is loaded with `lms load <model>` and server is running with `lms server start`

## Project Structure

```
claude-adapter-py/
├── src/claude_adapter/
│   ├── __init__.py         # Package init
│   ├── __main__.py         # Entry point
│   ├── cli.py              # CLI implementation
│   ├── server.py           # FastAPI server
│   ├── providers.py        # Provider presets and categories
│   ├── models/             # Pydantic data models
│   ├── converters/         # Protocol converters
│   ├── handlers/           # API handlers
│   └── utils/              # Utilities
├── pyproject.toml
├── README.md
└── README_CN.md
```

## License

MIT License

## Credits

Python rewrite of the TypeScript [claude-adapter](https://github.com/shantoislamdev/claude-adapter) with enhanced features, multi-provider support, and improved architecture.
