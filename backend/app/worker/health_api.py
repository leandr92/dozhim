from fastapi import FastAPI

from app.worker.state import worker_state

app = FastAPI(title="Dozhim Worker Health")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **worker_state.as_dict()}
