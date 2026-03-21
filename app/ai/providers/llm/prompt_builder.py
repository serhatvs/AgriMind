"""Prompt builders for grounded agronomic assistant answers."""

from __future__ import annotations

from app.schemas.agri_assistant import AgriAssistantContext


def _format_list(items: list[str], *, empty_message: str) -> str:
    if not items:
        return f"- {empty_message}"
    return "\n".join(f"- {item}" for item in items)


def _format_profit(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _format_ranking_table(context: AgriAssistantContext) -> str:
    lines = [
        "| Rank | Field | Ranking Score | Agronomic Score | Economic Score | Estimated Profit |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in context.ranking_table:
        lines.append(
            "| "
            f"{row.rank} | "
            f"{row.field_name} | "
            f"{row.ranking_score:.1f} | "
            f"{row.total_score:.1f} | "
            f"{row.economic_score:.1f} | "
            f"{_format_profit(row.estimated_profit)} |"
        )
    return "\n".join(lines)


def build_agri_assistant_system_prompt() -> str:
    """Return the system prompt that constrains the assistant to deterministic truth."""

    return (
        "You are AgriMind's agronomic explanation assistant. "
        "The deterministic ranking output and explanation output are the only sources of truth. "
        "Do not invent agronomic facts, scores, ranks, blockers, economics, or missing inputs. "
        "If information is missing, say that it is missing from the current deterministic inputs. "
        "Stay within the supplied context and answer the user's question directly."
    )


def build_agri_assistant_user_prompt(question: str, context: AgriAssistantContext) -> str:
    """Render the user prompt from the deterministic assistant context."""

    return (
        f"Question:\n{question.strip()}\n\n"
        "Selected field summary:\n"
        f"- Crop: {context.crop.crop_name}\n"
        f"- Field: {context.selected_field_name}\n"
        f"- Rank: {context.selected_field_rank}\n"
        f"- Ranking score: {context.selected_ranking_score:.1f}/100\n"
        f"- Agronomic score: {context.selected_total_score:.1f}/100\n\n"
        "Why this field:\n"
        f"{_format_list(context.why_this_field, empty_message='No positive factors were captured.')}\n\n"
        "Alternatives:\n"
        f"{_format_list(context.alternatives, empty_message='No alternative fields are available in the current ranking.')}\n\n"
        "Risks:\n"
        f"{_format_list(context.risks, empty_message='No significant risks were identified from current deterministic inputs.')}\n\n"
        "Missing data:\n"
        f"{_format_list(context.missing_data, empty_message='None detected from current deterministic inputs.')}\n\n"
        "Ranking table:\n"
        f"{_format_ranking_table(context)}\n\n"
        "Answer requirements:\n"
        "- Use only the deterministic facts above.\n"
        "- Explain why the selected field was chosen when relevant.\n"
        "- Mention alternatives, risks, or missing data only when they help answer the question.\n"
        "- If the question asks for unavailable information, say it is unavailable from current deterministic inputs."
    )
