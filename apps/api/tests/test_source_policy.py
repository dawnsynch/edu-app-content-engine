import pytest
from pydantic import ValidationError

from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType, StorageMode
from app.modules.sources.schemas import SourceCreate


def valid_source(**overrides: object) -> SourceCreate:
    values: dict[str, object] = {
        "name": "Example Learning",
        "slug": "example-learning",
        "source_type": SourceType.WEBSITE,
        "base_url": "https://learn.example.com",
        "status": SourceStatus.ACTIVE,
        "rights_status": RightsStatus.APPROVED,
        "storage_mode": StorageMode.METADATA_ONLY,
        "attribution_required": True,
        "attribution_text": "Example Learning",
    }
    values.update(overrides)
    return SourceCreate.model_validate(values)


def test_active_source_requires_reviewed_rights() -> None:
    with pytest.raises(ValidationError, match="active sources require approved or restricted"):
        valid_source(rights_status=RightsStatus.UNKNOWN)


def test_prohibited_source_rejects_transformations() -> None:
    with pytest.raises(ValidationError, match="prohibited sources"):
        valid_source(
            status=SourceStatus.BLOCKED,
            rights_status=RightsStatus.PROHIBITED,
            allow_embeddings=True,
        )


def test_full_text_requires_approved_rights() -> None:
    with pytest.raises(ValidationError, match="full-text storage requires approved rights"):
        valid_source(
            rights_status=RightsStatus.RESTRICTED,
            storage_mode=StorageMode.FULL_TEXT,
        )


def test_allowed_domains_are_normalized_and_deduplicated() -> None:
    source = valid_source(allowed_domains=["Docs.Example.com.", "docs.example.com"])

    assert source.allowed_domains == ["docs.example.com"]


def test_connector_configuration_rejects_embedded_secrets() -> None:
    with pytest.raises(ValidationError, match="environment variables, not secrets"):
        valid_source(connector_config={"api_key": "do-not-store-this"})


def test_youtube_source_requires_channel_id() -> None:
    with pytest.raises(ValidationError, match="channel_id"):
        valid_source(source_type=SourceType.YOUTUBE)
