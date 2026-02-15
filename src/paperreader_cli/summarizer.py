from __future__ import annotations

from dataclasses import dataclass

from .llm_client import LLMClient


SUMMARY_INSTRUCTION = """
请阅读论文内容并输出结构化 Markdown，总结必须包含以下小节：
1. 论文标题识别
2. 核心贡献
3. 方法论（给出关键的推导公式以及算法过程）
4. 实验结论（数据集、指标、对比结果亮点）
5. 个人评价（优点、局限、可改进方向）
要求：
- 语言简洁严谨，优先保留可验证信息。
- 避免编造数据；若原文缺失信息请明确写“原文未明确给出”。
- 输出格式必须使用 Markdown，且层级清晰。
- 公式格式需要使用 LaTeX 语法，并放在行内或独立行展示。涉及到的所有公式需要使用Latex语法
""".strip()


@dataclass(slots=True)
class SummaryResult:
    content: str
    chunks_used: int


def chunk_text(text: str, chunk_chars: int) -> list[str]:
    if len(text) <= chunk_chars:
        return [text]

    chunks: list[str] = []
    current = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        para_len = len(paragraph)
        if current_len + para_len + 2 <= chunk_chars:
            current.append(paragraph)
            current_len += para_len + 2
        else:
            if current:
                chunks.append("\n\n".join(current))
            if para_len > chunk_chars:
                for i in range(0, para_len, chunk_chars):
                    chunks.append(paragraph[i : i + chunk_chars])
                current = []
                current_len = 0
            else:
                current = [paragraph]
                current_len = para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def summarize_paper(
    llm: LLMClient,
    *,
    system_prompt: str,
    paper_text: str,
    chunk_chars: int,
) -> SummaryResult:
    chunks = chunk_text(paper_text, chunk_chars)

    if len(chunks) == 1:
        user_prompt = f"{SUMMARY_INSTRUCTION}\n\n论文内容：\n{chunks[0]}"
        summary = llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        return SummaryResult(content=summary, chunks_used=1)

    partials: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_prompt = (
            f"你将阅读论文的一部分（第 {idx}/{len(chunks)} 部分）。"
            "请仅输出该部分的关键信息要点（Markdown 列表），"
            "用于后续全局汇总，不要捏造缺失内容。"
            f"\n\n论文片段：\n{chunk}"
        )
        partials.append(llm.chat(system_prompt=system_prompt, user_prompt=chunk_prompt))

    merge_prompt = (
        f"{SUMMARY_INSTRUCTION}\n\n"
        "以下是同一篇论文各片段的要点，请进行全局整合，输出最终结构化 Markdown：\n\n"
        + "\n\n".join(
            f"### 片段 {i}\n{part}" for i, part in enumerate(partials, start=1)
        )
    )
    final_summary = llm.chat(system_prompt=system_prompt, user_prompt=merge_prompt)
    return SummaryResult(content=final_summary, chunks_used=len(chunks))
