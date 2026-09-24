"""请求 / 响应 Pydantic 模型：严格整数校验，额外字段一律拒绝。"""
from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 浓度：非负整数分子 + 正整数分母（分母非法 -> 422）
PosInt = Annotated[int, Field(strict=True, ge=1)]
NonNegInt = Annotated[int, Field(strict=True, ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class FractionInput(StrictModel):
    numerator: NonNegInt
    denominator: PosInt


class WellInput(StrictModel):
    id: str = Field(min_length=1)
    volume_ul: NonNegInt  # 非负整数微升
    concentration: FractionInput


class TransferInput(StrictModel):
    from_: str = Field(min_length=1, alias="from")
    to: str = Field(min_length=1)
    amount_ul: Annotated[int, Field(strict=True, ge=1)]  # 正整数微升

    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def endpoints_distinct(self) -> "TransferInput":
        if self.from_ == self.to:
            raise ValueError("from 与 to 不得相同")
        return self


class ComputeRequest(StrictModel):
    wells: list[WellInput] = Field(min_length=2, max_length=48)
    transfers: list[TransferInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def cross_validate(self) -> "ComputeRequest":
        ids = [w.id for w in self.wells]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"孔位 id 必须唯一，重复：{', '.join(duplicates)}")

        known = set(ids)
        for n, t in enumerate(self.transfers, start=1):
            if t.from_ not in known:
                raise ValueError(f"第 {n} 条转移引用了未知孔位：{t.from_}")
            if t.to not in known:
                raise ValueError(f"第 {n} 条转移引用了未知孔位：{t.to}")
        return self


# ---------- 响应模型 ----------


class FractionOut(BaseModel):
    numerator: int
    denominator: int


class EndpointOut(BaseModel):
    id: str
    volume_ul: int
    concentration: Optional[FractionOut] = None


class StepEndpoints(BaseModel):
    source: EndpointOut
    target: EndpointOut


class StepOut(BaseModel):
    index: int
    from_: str = Field(alias="from")
    to: str
    amount_ul: int
    before: StepEndpoints
    after: StepEndpoints

    model_config = ConfigDict(populate_by_name=True)


class WellOut(BaseModel):
    id: str
    volume_ul: int
    concentration: Optional[FractionOut] = None
    solute: FractionOut


class EvidenceStep(BaseModel):
    index: int
    moved_solute: FractionOut
    source_solute_delta: FractionOut
    target_solute_delta: FractionOut
    delta_sum: FractionOut
    plate_total_solute: FractionOut
    total_volume_ul: int


class Conservation(BaseModel):
    initial_total_solute: FractionOut
    final_total_solute: FractionOut
    difference: FractionOut
    solute_conserved: bool
    volume_conserved: bool
    initial_total_volume_ul: int
    final_total_volume_ul: int
    steps: list[EvidenceStep]


class ComputeResponse(BaseModel):
    wells: list[WellOut]
    steps: list[StepOut]
    conservation: Conservation
