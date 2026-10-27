"""
Structured logger for Nexora AI.

Every log line produced by the backend is captured here.
In production (Render), logs are streamed to stdout. No secrets are logged.
A request_id context var is set by the middleware so every log line
within a single request can be correlated.
"""
import logging
import contextvars

# Per-request trace ID (set by RequestTracingMiddleware in main.py)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class _RequestIdFilter(logging.Filter):
    """Inject the current request_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


def setup_logger(name: str = "nexora") -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    if not log.hasHandlers():
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s][%(levelname)s][%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        ch.setFormatter(formatter)
        ch.addFilter(_RequestIdFilter())
        log.addHandler(ch)

    return log


logger = setup_logger()
