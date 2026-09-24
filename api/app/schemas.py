"""请求/响应模型。

校验规则：
- 孔位 2~48 个，id 非空且唯一；
- 初始体积非负整数 μL；
- 浓度 = 非负整数分子 / 正整数分母；
- 转移 1~200 条，from/to 必须引用已声明孔位且不得相同，amount 为正整数；
- 所有模型 extra="forbid"：出现额外字段一律 422。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FractionIn(StrictModel):
    numerator: int = Field(..., ge=0)
    denominator: int = Field(..., ge=1)


class WellIn(StrictModel):
    id: str = Field(..., min_length=1, max_length=64)
    volume_ul: int = Field(..., ge=0)
    concentration: FractionIn


class TransferIn(StrictModel):
    from_: str = Field(..., alias="from", min_length=1, max_length=64)
    to: str = Field(..., min_length=1, max_length=64)
    amount_ul: int = Field(..., ge=1)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ReviewRequest(StrictModel):
    wells: list[WellIn] = Field(..., min_length=2, max_length=48)
    transfers: list[TransferIn] = Field(..., min_length=1, max_length=200)

    @field_validator("wells")
    @classmethod
    def _unique_well_ids(cls, v: list[WellIn]) -> list[WellIn]:
        ids = [w.id for w in v]
        if len(set(ids)) != len(ids):
            dup = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"孔位 id 必须唯一，重复：{', '.join(dup)}")
        return v

    def check_references(self) -> None:
        """跨字段校验：转移端点必须存在且不同。"""
        known = {w.id for w in self.wells}
        for idx, t in enumerate(self.transfers, start=1):
            if t.from_ == t.to:
                raise ValueError(f"第 {idx} 条转移的 from 与 to 相同：{t.from_}")
            missing = [name for name in (t.from_, t.to) if name not in known]
            if missing:
                raise ValueError(
                    f"第 {idx} 条转移引用了未知孔位：{', '.join(missing)}"
                )


class FractionOut(BaseModel):
    numerator: int
    denominator: int


class WellStateOut(BaseModel):
    well: str
    volume_ul: int
    concentration: FractionOut
    solute_mass: FractionOut


class StepOut(BaseModel):
    step: int
    from_: str = Field(..., alias="from")
    to: str
    amount_ul: int
    transferred_solute_mass: FractionOut
    source_before: WellStateOut
    source_after: WellStateOut
    target_before: WellStateOut
    target_after: WellStateOut

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MassConservation(BaseModel):
    initial_total_solute_mass: FractionOut
    final_total_solute_mass: FractionOut
    total_solute_mass_after_each_step: list[FractionOut]
    holds: bool


class VolumeConservation(BaseModel):
    initial_total_volume_ul: int
    final_total_volume_ul: int
    holds: bool


class ReviewResponse(BaseModel):
    status: Literal["ok"]
    steps: list[StepOut]
    final_wells: list[WellStateOut]
    conservation: dict[str, object]
