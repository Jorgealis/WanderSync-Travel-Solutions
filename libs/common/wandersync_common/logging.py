import logging

import structlog


def configure_logging(service_name: str, level: str = "INFO") -> None:
    """Logs en JSON (una línea por evento) con el servicio y el correlation_id.

    El correlation_id lo enlaza CorrelationIdMiddleware mediante contextvars, así
    que cualquier log emitido durante una petición lo incluye automáticamente.
    """

    def add_service(_logger, _method, event_dict):
        event_dict.setdefault("service", service_name)
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_service,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
