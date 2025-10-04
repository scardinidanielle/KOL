from __future__ import annotations

import logging


def test_create_app_configures_logging_once():
    from smart_lighting_ai_dali.main import create_app

    root_logger = logging.getLogger()

    app1 = create_app()
    app2 = create_app()

    handlers = [
        handler
        for handler in root_logger.handlers
        if getattr(handler, "_smart_lighting_json_handler", False)
    ]

    assert len(handlers) == 1
    assert app1.state.logging_configured is True
    assert app2.state.logging_configured is True

    for app in (app1, app2):
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None and scheduler.running:
            try:
                scheduler.shutdown(wait=False)
            except Exception:  # noqa: BLE001
                pass
