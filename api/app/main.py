"""FastAPI 入口：微孔板逐孔转移复核台。

- POST /api/review：逐步计算，成功 200；中途透支/空孔取液 409（定位第一条失败步骤，
  不输出任何步骤结果或部分成功结论）；请求非法 422。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .engine import TransferError, simulate
from .schemas import ReviewRequest, ReviewResponse

app = FastAPI(title="微孔板转移复核台 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_ZH_HINTS = {
    "extra_forbidden": "出现了不允许的额外字段",
    "greater_than_equal": "数值不满足下界要求",
    "missing": "缺少必填字段",
    "string_too_short": "字符串不得为空",
    "too_short": "列表元素数量不足",
    "too_long": "列表元素数量超限",
    "int_parsing": "必须是整数",
    "int_type": "必须是整数",
    "model_type": "必须是对象",
    "list_type": "必须是数组",
    "value_error": "取值不合法",
}


def _zh_hint(err: dict) -> str:
    t = err.get("type", "")
    return _ZH_HINTS.get(t, f"校验未通过（{t}）")


@app.exception_handler(RequestValidationError)
async def _on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        errors.append({
            "loc": loc,
            "type": err.get("type"),
            "message": err.get("msg"),
            "hint": _zh_hint(err),
        })
    return JSONResponse(
        status_code=422,
        content={"status": "invalid_request", "errors": errors},
    )


@app.exception_handler(TransferError)
async def _on_transfer_error(_: Request, exc: TransferError) -> JSONResponse:
    # 只报告第一条失败步骤；响应体不含 steps，避免任何“部分成功”结论。
    return JSONResponse(
        status_code=409,
        content={
            "status": "conflict",
            "error": {
                "code": exc.code,
                "step": exc.step,
                "from": exc.from_well,
                "to": exc.to_well,
                "requested_ul": exc.requested,
                "available_ul": exc.available,
                "message": exc.message,
            },
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/review", status_code=200, response_model=ReviewResponse)
def review(req: ReviewRequest) -> dict:
    # 跨字段引用校验属于请求合法性：未知孔位 / from==to -> 422
    try:
        req.check_references()
    except ValueError as exc:
        raise RequestValidationError([
            {"loc": ("body", "transfers"), "type": "value_error", "msg": str(exc)}
        ])

    wells = [w.model_dump() for w in req.wells]
    transfers = [t.model_dump(by_alias=True) for t in req.transfers]
    result = simulate(wells, transfers)
    return {"status": "ok", **result}
