from urllib.parse import SplitResult, urlsplit, urlunsplit

from app.core.exceptions import PolicyViolationError


def normalize_http_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise PolicyViolationError("URL must use HTTP or HTTPS and include a hostname")
    if parsed.username or parsed.password:
        raise PolicyViolationError("URLs containing credentials are not allowed")

    hostname = parsed.hostname.lower().rstrip(".")
    port = parsed.port
    is_default_port = (parsed.scheme.lower(), port) in {("http", 80), ("https", 443)}
    if port and not is_default_port:
        hostname = f"{hostname}:{port}"

    normalized = SplitResult(
        scheme=parsed.scheme.lower(),
        netloc=hostname,
        path=parsed.path or "/",
        query=parsed.query,
        fragment="",
    )
    return urlunsplit(normalized)


def validate_source_host(content_url: str, base_url: str, allowed_domains: list[str]) -> None:
    content_host = urlsplit(content_url).hostname
    base_host = urlsplit(base_url).hostname
    if content_host is None or base_host is None:
        raise PolicyViolationError("content and source URLs require hostnames")

    approved = {base_host.lower(), *(domain.lower() for domain in allowed_domains)}
    host = content_host.lower()
    if not any(host == domain or host.endswith(f".{domain}") for domain in approved):
        raise PolicyViolationError("content URL is outside the source's approved domains")
