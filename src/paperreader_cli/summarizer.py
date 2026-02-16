from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .llm_client import LLMClient


SUMMARY_INSTRUCTION = """
请阅读论文内容并输出结构化 Markdown，总结必须包含以下小节：
1. 论文标题识别
2. 核心贡献（需要指出文章的背景，解决了什么问题）
3. 方法论（包括模型架构、算法流程、创新点等）
4. 实验结论（数据集、指标、对比结果亮点）
5. 个人评价（优点、局限、可改进方向）
要求：
- 语言简洁严谨，优先保留可验证信息。
- 避免编造数据；若原文缺失信息请明确写“原文未明确给出”。
- 公式格式需要使用 LaTeX 语法，并放在行内或独立行展示。涉及到的所有公式需要使用Latex语法
""".strip()


@dataclass(slots=True)
class SummaryResult:
    content: str
    chunks_used: int
    total_tokens: int


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
    chunk_workers: int = 3,
    profile: str = "paper",
) -> SummaryResult:
    chunks = chunk_text(paper_text, chunk_chars)
    total_tokens = 0
    profile_name = profile if profile in {"paper", "report"} else "paper"
    max_merge_chars = 60000 if profile_name == "paper" else 36000

    if len(chunks) == 1:
        user_prompt = f"{SUMMARY_INSTRUCTION}\n\n论文内容：\n{chunks[0]}"
        summary = llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        total_tokens += summary.total_tokens
        return SummaryResult(content=summary.content, chunks_used=1, total_tokens=total_tokens)

    partials: list[str] = [""] * len(chunks)
    partial_tokens: list[int] = [0] * len(chunks)

    def _summarize_one(idx: int, chunk: str) -> tuple[int, str, int]:
        chunk_prompt = (
            f"你将阅读论文的一部分（第 {idx}/{len(chunks)} 部分）。"
            "请仅输出该部分的关键信息要点（Markdown 列表），"
            "用于后续全局汇总，不要捏造缺失内容。"
            f"\n\n论文片段：\n{chunk}"
        )
        partial = llm.chat(system_prompt=system_prompt, user_prompt=chunk_prompt)
        return idx, partial.content, partial.total_tokens

    if chunk_workers <= 1:
        for idx, chunk in enumerate(chunks, start=1):
            resolved_idx, partial_content, partial_total_tokens = _summarize_one(idx, chunk)
            partials[resolved_idx - 1] = partial_content
            partial_tokens[resolved_idx - 1] = partial_total_tokens
    else:
        max_workers = min(max(1, int(chunk_workers)), len(chunks))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_summarize_one, idx, chunk)
                for idx, chunk in enumerate(chunks, start=1)
            ]
            for future in as_completed(futures):
                resolved_idx, partial_content, partial_total_tokens = future.result()
                partials[resolved_idx - 1] = partial_content
                partial_tokens[resolved_idx - 1] = partial_total_tokens

    total_tokens += sum(partial_tokens)

    merged_sections: list[str] = []
    merged_chars = 0
    for i, part in enumerate(partials, start=1):
        section = f"### 片段 {i}\n{part}".strip()
        next_len = len(section) + 2
        if merged_sections and merged_chars + next_len > max_merge_chars:
            break
        merged_sections.append(section)
        merged_chars += next_len

    merge_prompt = (
        f"{SUMMARY_INSTRUCTION}\n\n"
        "以下是同一篇论文各片段的要点，请进行全局整合，输出最终结构化 Markdown：\n\n"
        + "\n\n".join(merged_sections)
    )
    final_summary = llm.chat(system_prompt=system_prompt, user_prompt=merge_prompt)
    total_tokens += final_summary.total_tokens
    return SummaryResult(content=final_summary.content, chunks_used=len(chunks), total_tokens=total_tokens)
