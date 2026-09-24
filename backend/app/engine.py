"""逐步转移复核引擎：完全混匀模型，全程 Fraction 精确分数，无中途舍入。"""
from __future__ import annotations

from fractions import Fraction
from typing import Any


class TransferError(Exception):
    """某条转移无法执行（空孔取液 / 余额不足）。"""

    def __init__(
        self,
        index: int,
        reason: str,
        from_id: str,
        to_id: str,
        amount_ul: int,
        available_ul: int,
    ) -> None:
        self.index = index
        self.reason = reason
        self.detail = {
            "error": "transfer_failed",
            "index": index,
            "reason": reason,
            "from": from_id,
            "to": to_id,
            "amount_ul": amount_ul,
            "available_ul": available_ul,
            "message": (
                f"第 {index} 条转移失败：来源孔 {from_id} 为空，无法取液"
                if reason == "empty_source"
                else f"第 {index} 条转移失败：来源孔 {from_id} 仅剩 "
                f"{available_ul} μL，不足以转移 {amount_ul} μL"
            ),
        }
        super().__init__(self.detail["message"])


def frac_out(f: Fraction) -> dict[str, int]:
    """Fraction 序列化为约分分数。"""
    return {"numerator": f.numerator, "denominator": f.denominator}


def _snapshot(well: dict[str, Any]) -> dict[str, Any]:
    """孔位当前完整状态：体积、浓度、溶质量。空孔浓度为 null。"""
    concentration = (
        None if well["volume"] == 0 else well["solute"] / well["volume"]
    )
    return {
        "id": well["id"],
        "volume_ul": well["volume"],
        "concentration": None if concentration is None else frac_out(concentration),
        "solute": frac_out(well["solute"]),
    }


def _endpoint(well: dict[str, Any]) -> dict[str, Any]:
    """步骤端点视图：仅含浓度与体积（空孔浓度 null）。"""
    snap = _snapshot(well)
    return {
        "id": snap["id"],
        "volume_ul": snap["volume_ul"],
        "concentration": snap["concentration"],
    }


def compute(wells_in: list[Any], transfers_in: list[Any]) -> dict[str, Any]:
    """按顺序执行全部转移并返回逐步快照、终态与守恒证据。

    任一转移失败时抛 TransferError（第一条失败步骤），不产生任何成功结论。
    """
    wells: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for w in wells_in:
        # 初始溶质量 = 浓度(分数) × 初始体积；Fraction 自动约分，绝不舍入
        solute = Fraction(
            w.concentration.numerator * w.volume_ul,
            w.concentration.denominator,
        )
        wells[w.id] = {"id": w.id, "volume": w.volume_ul, "solute": solute}
        order.append(w.id)

    initial_total_solute = sum(
        (wells[i]["solute"] for i in order), Fraction(0)
    )
    initial_total_volume = sum(wells[i]["volume"] for i in order)

    steps: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for k, t in enumerate(transfers_in, start=1):
        src = wells[t.from_]
        dst = wells[t.to]

        # 失败定位：空孔取液与余额不足分开报告；只报第一条
        if src["volume"] == 0:
            raise TransferError(
                k, "empty_source", t.from_, t.to, t.amount_ul, 0
            )
        if src["volume"] < t.amount_ul:
            raise TransferError(
                k,
                "insufficient_volume",
                t.from_,
                t.to,
                t.amount_ul,
                src["volume"],
            )

        before = {"source": _endpoint(src), "target": _endpoint(dst)}

        # 完全混匀：取出部分的浓度 = 来源孔当前浓度
        moved_solute = src["solute"] * t.amount_ul / src["volume"]
        src["solute"] -= moved_solute
        src["volume"] -= t.amount_ul
        dst["solute"] += moved_solute
        dst["volume"] += t.amount_ul

        after = {"source": _endpoint(src), "target": _endpoint(dst)}
        plate_total_solute = sum(
            (wells[i]["solute"] for i in order), Fraction(0)
        )
        total_volume = sum(wells[i]["volume"] for i in order)

        steps.append(
            {
                "index": k,
                "from": t.from_,
                "to": t.to,
                "amount_ul": t.amount_ul,
                "before": before,
                "after": after,
            }
        )
        evidence.append(
            {
                "index": k,
                "moved_solute": frac_out(moved_solute),
                "source_solute_delta": frac_out(-moved_solute),
                "target_solute_delta": frac_out(moved_solute),
                "delta_sum": frac_out(Fraction(0)),
                "plate_total_solute": frac_out(plate_total_solute),
                "total_volume_ul": total_volume,
            }
        )

    final_wells = [_snapshot(wells[i]) for i in order]
    final_total_solute = sum(
        (wells[i]["solute"] for i in order), Fraction(0)
    )
    difference = final_total_solute - initial_total_solute
    solute_conserved = (
        difference == 0
        and all(
            Fraction(
                e["plate_total_solute"]["numerator"],
                e["plate_total_solute"]["denominator"],
            )
            == initial_total_solute
            for e in evidence
        )
    )
    volume_conserved = (
        sum(w["volume_ul"] for w in final_wells) == initial_total_volume
        and all(e["total_volume_ul"] == initial_total_volume for e in evidence)
    )

    return {
        "wells": final_wells,
        "steps": steps,
        "conservation": {
            "initial_total_solute": frac_out(initial_total_solute),
            "final_total_solute": frac_out(final_total_solute),
            "difference": frac_out(difference),
            "solute_conserved": solute_conserved,
            "volume_conserved": volume_conserved,
            "initial_total_volume_ul": initial_total_volume,
            "final_total_volume_ul": sum(
                w["volume_ul"] for w in final_wells
            ),
            "steps": evidence,
        },
    }
