from __future__ import annotations

import json
import logging


JSON_HANDLER_ATTR = "_smart_lighting_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        data = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            extra = getattr(record, "extra")
            if isinstance(extra, dict):
                data.update(extra)
        return json.dumps(data)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in root.handlers:
        if getattr(handler, JSON_HANDLER_ATTR, False):
            return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    setattr(handler, JSON_HANDLER_ATTR, True)
    root.addHandler(handler)


__all__ = ["configure_logging"]
