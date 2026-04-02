"""Start the dj-tools API server.

Run:
    python -m src.scripts.run_api
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
