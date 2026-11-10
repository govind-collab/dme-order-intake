from fastapi import FastAPI

app = FastAPI(title="DME order intake")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
