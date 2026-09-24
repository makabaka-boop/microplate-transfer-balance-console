"""FastAPI 入口：422 由 Pydantic 校验产生，409 来自逐步引擎失败。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import engine
from .schemas import ComputeRequest, ComputeResponse

app = FastAPI(title="微孔板转移复核台", version="1.0.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/compute", response_model=ComputeResponse)
def compute(payload: ComputeRequest) -> dict:
    try:
        return engine.compute(payload.wells, payload.transfers)
    except engine.TransferError as exc:
        # 只定位第一条失败步骤，不输出部分成功结论
        raise HTTPException(status_code=409, detail=exc.detail)
