# PaperReader-CLI

一个本地终端工具：递归扫描 PDF，调用 OpenAI 兼容接口进行学术总结，并输出 Markdown。

## 安装

```bash
pip install -e .
```

## 配置

首次运行 `paperreader scan ...` 时，如果不存在配置文件，会进入交互式引导并创建：`~/.paper_cli/config.yaml`

编辑 `~/.paper_cli/config.yaml`：

- `base_url`: OpenAI 或 OneAPI/NewAPI 地址
- `api_key`: API 密钥（也可用环境变量 `PAPERREADER_API_KEY`）
- `model`: 模型名（如 `gpt-4o` / `deepseek-chat`）
- `system_prompt`: 学术人设
- `max_chars`: 单篇论文最大输入长度（超出将截断并提示）
- `chunk_chars`: 长文本分块大小（分块总结再汇总）

配置优先级：`CLI 参数 > 环境变量 > ~/.paper_cli/config.yaml`

可用环境变量：

- `PAPERREADER_BASE_URL`
- `PAPERREADER_API_KEY`
- `PAPERREADER_MODEL`
- `PAPERREADER_SYSTEM_PROMPT`

## 使用

```bash
paperreader scan ./papers
```

可选覆盖参数：

```bash
paperreader scan ./papers --model deepseek-chat --base-url https://your-gateway/v1
```

也可临时指定其它配置文件：

```bash
paperreader scan ./papers --config /path/to/custom-config.yaml
```

一键重新进入首次配置向导（覆盖现有配置）：

```bash
paperreader reconfigure
```

查看命令帮助：

```bash
paperreader scan --help
```

## 输出

- 控制台展示 Rich 进度与简报
- 在 PDF 同级目录写入同名 `.md` 文件（默认覆盖）

## 错误处理

- API 认证失败、网络失败、限流会在终端给出明确提示
- PDF 损坏或无法读取时会跳过该文件并继续后续处理
