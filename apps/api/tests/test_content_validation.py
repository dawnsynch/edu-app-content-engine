import pytest
from pydantic import ValidationError

from app.core.exceptions import PolicyViolationError
from app.modules.content.enums import ContentType
from app.modules.content.schemas import ContentCreate
from app.modules.content.validators import normalize_http_url, validate_source_host


def test_normalize_url_removes_fragment_and_default_port() -> None:
    normalized = normalize_http_url("HTTPS://Example.COM:443/learn?level=1#section")

    assert normalized == "https://example.com/learn?level=1"


def test_content_host_accepts_approved_subdomain() -> None:
    validate_source_host(
        "https://docs.example.com/course",
        "https://example.com/",
        [],
    )


def test_content_host_rejects_unapproved_domain() -> None:
    with pytest.raises(PolicyViolationError, match="outside the source's approved domains"):
        validate_source_host(
            "https://unapproved.example.net/course",
            "https://example.com/",
            [],
        )


def test_video_metadata_rejects_rehosted_media_fields() -> None:
    with pytest.raises(ValidationError, match="external videos cannot include"):
        ContentCreate.model_validate(
            {
                "source_id": 1,
                "canonical_url": "https://video.example.com/watch/1",
                "title": "A useful lesson",
                "content_type": ContentType.VIDEO,
                "raw_metadata": {"download_url": "https://cdn.example.com/video.mp4"},
            }
        )
