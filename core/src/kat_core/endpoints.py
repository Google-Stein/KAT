"""Local inference URLs cannot point to remote hosts, proxies or other routes."""

from urllib.parse import urlsplit


def local_endpoint(value: str) -> str:
    try:
        url = urlsplit(value)
        port = url.port if url.port is not None else 11434
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username is not None
            or url.password is not None
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or port == 42800
            or not 1 <= port <= 65535
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError(
            "Local backend must use a loopback HTTP origin with an optional port."
        ) from None
    # Resolve localhost to a literal address rather than delegating it to DNS/proxies.
    host = "[::1]" if url.hostname == "::1" else "127.0.0.1"
    return f"http://{host}:{port}"
