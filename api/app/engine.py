"""微孔板转移复核计算引擎。

完全混匀（well-mixed）模型：
- 每次转移从来源孔吸走 x μL 均匀混合液；
- 来源孔吸出后：体积 V -> V-x，溶质量 M -> M*(V-x)/V（V>0）；
- 目标孔加入后：体积 V -> V+x，溶质量 M -> M + x*M_src/V_src；
- 全部计算使用 fractions.Fraction 精确分数，全程不舍入。
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any


class TransferError(Exception):
    """业务级转移失败：空孔取液或余额不足。

    code 为 EMPTY_SOURCE / INSUFFICIENT_VOLUME。
    """

    def __init__(self, code: str, step: int, from_well: str, to_well: str,
                 requested: int, available: int, message: str):
        super().__init__(message)
        self.code = code
        self.step = step
        self.from_well = from_well
        self.to_well = to_well
        self.requested = requested
        self.available = available
        self.message = message


@dataclass
class Well:
    id: str
    volume: int                       # μL，转移后仍为整数
    mass: Fraction                    # 溶质量（任意单位）

    @property
    def concentration(self) -> Fraction:
        if self.volume == 0:
            return Fraction(0, 1)
        return self.mass / self.volume


def frac(n: int, d: int) -> Fraction:
    """构造精确分数；d 必须为正整数（分母合法性由模型层先校验）。"""
    return Fraction(n, d)


def _fraction_out(f: Fraction) -> dict[str, int]:
    return {"numerator": f.numerator, "denominator": f.denominator}


def _well_state(well: Well) -> dict[str, Any]:
    return {
        "well": well.id,
        "volume_ul": well.volume,
        "concentration": _fraction_out(well.concentration),
        "solute_mass": _fraction_out(well.mass),
    }


def simulate(wells_in: list[dict[str, Any]],
             transfers_in: list[dict[str, Any]]) -> dict[str, Any]:
    """按顺序执行全部转移并返回逐步复核结果。

    输入已经过 Pydantic 校验（孔位 2-48、转移 1-200、id 唯一、端点存在且不同）。
    失败时抛出 TransferError，定位第一条失败步骤，不产生任何“部分成功”结论。
    """
    order = [w["id"] for w in wells_in]
    wells: dict[str, Well] = {}
    for w in wells_in:
        c = w["concentration"]
        concentration = Fraction(c["numerator"], c["denominator"])
        wells[w["id"]] = Well(
            id=w["id"],
            volume=w["volume_ul"],
            mass=concentration * w["volume_ul"],
        )

    initial_mass = Fraction(sum((w.mass for w in wells.values()), Fraction(0)))
    initial_volume = sum(w.volume for w in wells.values())
    steps_out: list[dict[str, Any]] = []
    total_mass_log = [_fraction_out(initial_mass)]

    for idx, t in enumerate(transfers_in, start=1):
        src = wells[t["from"]]
        dst = wells[t["to"]]
        amount = t["amount_ul"]

        # —— 失败判定：只报告第一条失败步骤 ——
        if src.volume == 0:
            raise TransferError(
                code="EMPTY_SOURCE",
                step=idx,
                from_well=src.id,
                to_well=dst.id,
                requested=amount,
                available=0,
                message=f"第 {idx} 步失败：来源孔 {src.id} 为空，无法取出 {amount} μL。",
            )
        if amount > src.volume:
            raise TransferError(
                code="INSUFFICIENT_VOLUME",
                step=idx,
                from_well=src.id,
                to_well=dst.id,
                requested=amount,
                available=src.volume,
                message=(
                    f"第 {idx} 步失败：来源孔 {src.id} 余额 {src.volume} μL，"
                    f"不足以取出 {amount} μL。"
                ),
            )

        before_src, before_dst = _well_state(src), _well_state(dst)

        # —— 完全混匀模型，精确分数 ——
        transfer_mass = src.mass * amount / src.volume
        src.mass = src.mass * (src.volume - amount) / src.volume
        src.volume -= amount
        dst.mass += transfer_mass
        dst.volume += amount

        after_src, after_dst = _well_state(src), _well_state(dst)
        total_mass = sum((w.mass for w in wells.values()), Fraction(0))
        total_mass_log.append(_fraction_out(total_mass))

        steps_out.append({
            "step": idx,
            "from": src.id,
            "to": dst.id,
            "amount_ul": amount,
            "transferred_solute_mass": _fraction_out(transfer_mass),
            "source_before": before_src,
            "source_after": after_src,
            "target_before": before_dst,
            "target_after": after_dst,
        })

    final_mass = sum((w.mass for w in wells.values()), Fraction(0))
    final_volume = sum(w.volume for w in wells.values())

    # 守恒证据：每步后全板溶质量必须与初始完全相等（分数逐位相等）
    initial_mass_out = _fraction_out(initial_mass)
    mass_conservation = {
        "initial_total_solute_mass": initial_mass_out,
        "final_total_solute_mass": _fraction_out(final_mass),
        "total_solute_mass_after_each_step": total_mass_log,
        "holds": all(
            entry == initial_mass_out for entry in total_mass_log
        ) and final_mass == initial_mass,
    }

    return {
        "steps": steps_out,
        "final_wells": [_well_state(wells[wid]) for wid in order],
        "conservation": {
            "mass": mass_conservation,
            "volume": {
                "initial_total_volume_ul": initial_volume,
                "final_total_volume_ul": final_volume,
                "holds": final_volume == initial_volume,
            },
        },
    }
