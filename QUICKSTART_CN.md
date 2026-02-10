# 快速开始指南

## 安装

```bash
# 进入项目目录
cd /data/sharedata/xuyan/LLMs/claudecode/claude-adapter-py

# 安装项目（可编辑模式）
python3 -m pip install -e .

# 或安装到用户目录
python3 -m pip install --user -e .
```

## 首次运行

```bash
# 启动适配器
claude-adapter-py

# 或使用 python3 直接运行
python3 -m claude_adapter
```

## 配置示例

### 1. 使用 Ollama（本地）

```bash
claude-adapter-py
```

选择 **Ollama**，然后：
- Base URL: `http://localhost:11434/v1` (默认)
- Opus Model: `qwen2.5-coder:32b`
- Sonnet Model: `qwen2.5-coder:14b`
- Haiku Model: `qwen2.5-coder:7b`
- Tool Format: **XML**
- Port: 3080

**前提条件**：
```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull qwen2.5-coder:32b
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:7b

# 启动 Ollama（通常自动启动）
ollama serve
```

### 2. 使用 LM Studio（本地）

选择 **LM Studio**，然后：
- Base URL: `http://localhost:1234/v1` (默认)
- 模型：根据已加载的模型填写
- Tool Format: **XML**
- Port: 3080

**前提条件**：
1. 下载并安装 [LM Studio](https://lmstudio.ai/)
2. 在 LM Studio 中下载并加载模型
3. 点击 "Start Server"
4. **重要**：在设置中将 Context Length 增加到至少 16384

### 3. 使用 NVIDIA NIM（云端）

选择 **NVIDIA NIM**，然后：
- API Key: 从 https://build.nvidia.com/ 获取
- Base URL: `https://integrate.api.nvidia.com/v1` (默认)
- Tool Format: **Native**
- Port: 3080

### 4. 使用 Kimi（云端）

选择 **Kimi (Moonshot)**，然后：
- API Key: 从 https://platform.moonshot.cn/ 获取
- Base URL: `https://api.moonshot.cn/v1` (默认)
- Tool Format: **Native**
- Port: 3080

## 配置完成后

适配器会：
1. 启动 HTTP 服务器在 `http://127.0.0.1:3080`
2. 自动更新 `~/.claude/settings.json`
3. 保存配置到 `~/.claude-adapter/providers/<provider>.json`

现在就可以使用 Claude Code 了！

## 常用命令

```bash
# 切换提供商
claude-adapter-py --switch

# 重新配置当前提供商
claude-adapter-py --reconfigure

# 列出已保存的提供商
claude-adapter-py list-providers

# 删除提供商配置
claude-adapter-py remove ollama

# 使用自定义端口
claude-adapter-py --port 8080
```

## 测试安装

```bash
# 运行测试
python3 -m pytest

# 检查版本
python3 -c "import claude_adapter; print(claude_adapter.__version__)"
```

## 故障排除

### 问题：模块找不到

```bash
# 确保已安装
python3 -m pip list | grep claude

# 重新安装
python3 -m pip install --force-reinstall -e .
```

### 问题：依赖冲突

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装项目
pip install -e .
```

### 问题：LM Studio 上下文错误

在 LM Studio 中：
1. 点击已加载模型旁的设置图标
2. 将 "Context Length" 改为 16384 或 32768
3. 点击 "Reload Model"

### 问题：Ollama 连接失败

```bash
# 检查 Ollama 状态
systemctl status ollama

# 或手动启动
ollama serve

# 检查端口
curl http://localhost:11434/api/version
```

## 查看日志

```bash
# Token 使用日志
cat ~/.claude-adapter/token_usage/$(date +%Y-%m-%d).jsonl

# 错误日志
cat ~/.claude-adapter/error_logs/$(date +%Y-%m-%d).jsonl

# 查看配置
cat ~/.claude-adapter/providers/ollama.json
```

## 下一步

- 查看完整文档：[README_CN.md](README_CN.md)
- 查看英文文档：[README.md](README.md)
- 运行测试：`pytest`
- 贡献代码：Fork 并提交 PR

祝使用愉快！🎉
