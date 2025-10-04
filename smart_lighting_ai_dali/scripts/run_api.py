from __future__ import annotations

import uvicorn

from smart_lighting_ai_dali.main import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
