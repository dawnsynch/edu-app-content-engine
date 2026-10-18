SYSTEM_PROMPT = """You classify technology-learning content for Edu DawnSynch.
Use only the supplied metadata. Do not infer facts that are not supported.
Return concise normalized labels. Assess educational quality, not popularity.
The supplied evaluated_at, publication_date_status, and publication_age_days
are deterministic application values and are authoritative. Never describe a
past_or_present publication as future. A future status requires human review,
but is not by itself grounds for rejection.
Source rights status describes application storage and transformation limits,
which are enforced before this call. Approved and restricted sources have both
passed the source-governance gate; restricted status alone must not change the
content moderation decision.
Mark content for review or rejection when it is unsafe, deceptive, unrelated to
technology learning, or too ambiguous to classify confidently. Follow the JSON
schema exactly."""


def content_prompt(payload: dict[str, object]) -> str:
    lines = ["Classify and assess this approved-source content metadata:"]
    for key in (
        "title",
        "description",
        "content_type",
        "author_name",
        "published_at",
        "evaluated_at",
        "publication_date_status",
        "publication_age_days",
        "source_name",
        "source_rights_status",
    ):
        value = payload.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
