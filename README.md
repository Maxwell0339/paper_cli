# PaperReader-CLI

个人使用AI编程的一个本地终端工具：递归扫描 PDF，调用LLM进行学术总结，并输出 Markdown。支持多 provider 配置（OpenAI、Claude、Gemini、DeepSeek、others）。 支持爬取 ArXiv 论文 PDF。

## 安装

推荐使用虚拟环境：

```bash
git clone https://github.com/Maxwell0339/paper_cli.git
```
```bash
pip install -e .
```

## 配置

首次运行 `paperreader scan` 时，如果不存在配置文件，会进入交互式引导并创建：`~/.paper_cli/config.yaml`

编辑 `~/.paper_cli/config.yaml`：

- `provider`: 模型供应商（`openai` / `claude` / `gemini` / `deepseek` / `others`）
- `provider_name`: 当 `provider=others` 时必填（手动填写具体供应商名）
- `base_url`: OpenAI 或 OneAPI/NewAPI 地址
- `api_key`: API 密钥（也可用环境变量 `PAPERREADER_API_KEY`）
- `model`: 模型名（如 `gpt-4o` / `deepseek-chat`）
- `system_prompt`: 学术人设
- `max_chars`: 单篇论文最大输入长度（超出将截断并提示）
- `chunk_chars`: 长文本分块大小（分块总结再汇总）
- `default_scan_folder`: 论文目录默认路径（`scan` 默认扫描目录、`crawl` 默认保存目录；默认 `~/.paper_cli/papers`）
- `default_summary_output_dir`: `scan` 默认总结输出目录（默认 `~/.paper_cli/summary`）

配置优先级：`CLI 参数 > 环境变量 > ~/.paper_cli/config.yaml`

可用环境变量：

- `PAPERREADER_BASE_URL`
- `PAPERREADER_API_KEY`
- `PAPERREADER_MODEL`
- `PAPERREADER_SYSTEM_PROMPT`
- `PAPERREADER_OPENAI_API_KEY`
- `PAPERREADER_CLAUDE_API_KEY`
- `PAPERREADER_GEMINI_API_KEY`
- `PAPERREADER_DEEPSEEK_API_KEY`
- `PAPERREADER_OTHERS_API_KEY`

provider 预设（首次向导自动带出默认值）：

- `openai`: `https://api.openai.com/v1`, `gpt-5`
- `deepseek`: `https://api.deepseek.com/v1`, `deepseek-chat`
- `claude`: `https://api.anthropic.com/v1/`, `claude-opus-4-6`
- `gemini`: `https://generativelanguage.googleapis.com/v1beta/openai/`, `gemini-3-flash-preview`
- `others`: 由你自定义 `provider_name`、`base_url` 与 `model`

## 使用

1. 读取文件夹中的PDF并生成总结：
```bash
paperreader scan ./papers
```

不传文件夹路径时，`scan` 默认读取 `~/.paper_cli/papers`：

```bash
paperreader scan
```
2. `scan` 生成的总结 Markdown 默认保存到 `~/.paper_cli/summary`，可用 `--output-dir` 自定义：

```bash
paperreader scan --output-dir ./summary
```

3. 可选覆盖参数：

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
4. 论文搜索：
按关键词从 ArXiv 抓取论文 PDF（默认保存到 `default_scan_folder`，初始为 `~/.paper_cli/papers`）：

```bash
paperreader crawl --query "visual slam" --max-results 20
```

自定义保存目录：

```bash
paperreader crawl --query "vins mono" --output-dir ./papers
```

未传 `--query` 时会回退到上次 crawl 使用的关键词；若历史关键词为空则报错。

5. 查看命令帮助：

```bash
paperreader scan --help
```

## 输出

- 控制台展示 Rich 进度与简报（不展示 LLM 摘要正文）
- 批处理结束后输出本次总 token 消耗（`total_tokens`，若响应无 usage 则按 0 计入）
- 在 PDF 同级目录写入同名 `.md` 文件（默认覆盖）
- `crawl` 会输出 `fetched/saved/skipped/failed` 统计；当目标目录同名 PDF 已存在时会跳过，且不计入 `saved`

## 错误处理

- API 认证失败、网络失败、限流会在终端给出明确提示
- PDF 损坏或无法读取时会跳过该文件并继续后续处理
