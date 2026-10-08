import io
import logging

from kat_core.__main__ import ProviderLogFilter


def test_raw_provider_diagnostics_are_filtered_at_every_level() -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(ProviderLogFilter())
    for name in ("openai.agents", "openai._base_client", "httpx", "httpcore.connection"):
        for level in (logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            handler.handle(
                logging.LogRecord(name, level, "", 0, "private-key-and-prompt", (), None)
            )
    handler.handle(
        logging.LogRecord(
            "kat_core.service", logging.WARNING, "", 0, "category=provider_quota", (), None
        )
    )
    assert output.getvalue() == "category=provider_quota\n"
