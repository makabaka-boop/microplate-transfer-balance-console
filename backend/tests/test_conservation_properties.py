"""守恒性质与不变量核对：独立参考实现 + 随机批量场景。

不依赖引擎自身的证据字段，另写一份朴素 Fraction 模拟器交叉验证：
1. 每步前后 全板总溶质 == 初始总溶质，总体积 == 初始总体积；
2. 完全混匀不变量：来源孔取液前后浓度不变；
3. 目标孔新浓度 == (旧溶质 + 移入溶质) / 新体积；
4. 引擎返回的每个分数均为约分形式。
"""
from __future__ import annotations

from fractions import Fraction

import pytest

from app import engine
from app.schemas import ComputeRequest


def _is_reduced(f: dict) -> bool:
    from math import gcd

    n, d = f["numerator"], f["denominator"]
    return d > 0 and gcd(abs(n), d) == 1


def reference_simulate(req):
    # 与引擎完全独立的朴素 Fraction 模拟器，直接吃校验后的 Pydantic 对象
    wells = {}
    for w in req.wells:
        wells[w.id] = {
            "v": w.volume_ul,
            "s": Fraction(
                w.concentration.numerator * w.volume_ul, w.concentration.denominator
            ),
        }
    total_s0 = sum(w["s"] for w in wells.values())
    total_v0 = sum(w["v"] for w in wells.values())
    trace = []
    for i, t in enumerate(req.transfers, start=1):
        if wells[t.from_]["v"] == 0:
            return {"failed": i, "reason": "empty_source"}
        if wells[t.from_]["v"] < t.amount_ul:
            return {"failed": i, "reason": "insufficient_volume"}
        src, dst = wells[t.from_], wells[t.to]
        c_src_before = src["s"] / src["v"]
        moved = src["s"] * t.amount_ul / src["v"]
        c_dst_before = None if dst["v"] == 0 else dst["s"] / dst["v"]
        src["s"] -= moved
        src["v"] -= t.amount_ul
        dst["s"] += moved
        dst["v"] += t.amount_ul
        trace.append(
            {
                "i": i,
                "c_src_before": c_src_before,
                "c_src_after": None if src["v"] == 0 else src["s"] / src["v"],
                "c_dst_before": c_dst_before,
                "c_dst_after": dst["s"] / dst["v"],
                "total_s": sum(w["s"] for w in wells.values()),
                "total_v": sum(w["v"] for w in wells.values()),
                "moved": moved,
            }
        )
    return {
        "failed": None,
        "wells": wells,
        "trace": trace,
        "total_s0": total_s0,
        "total_v0": total_v0,
    }


SCENARIOS = [
    # 经典二倍连续稀释：母液池 + 空孔串，逐级转移
    {
        "wells": [
            {"id": "S", "volume_ul": 48, "concentration": {"numerator": 1, "denominator": 1}},
        ]
        + [
            {"id": f"W{i}", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}}
            for i in range(1, 6)
        ],
        "transfers": [
            {"from": "S", "to": "W1", "amount_ul": 1},
            {"from": "W1", "to": "W2", "amount_ul": 1},
            {"from": "W2", "to": "W3", "amount_ul": 1},
            {"from": "W3", "to": "W4", "amount_ul": 1},
            {"from": "W4", "to": "W5", "amount_ul": 1},
        ],
    },
    # 分数浓度 + 双向回抽
    {
        "wells": [
            {"id": "P", "volume_ul": 7, "concentration": {"numerator": 3, "denominator": 5}},
            {"id": "Q", "volume_ul": 4, "concentration": {"numerator": 2, "denominator": 9}},
            {"id": "R", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 3}},
        ],
        "transfers": [
            {"from": "P", "to": "R", "amount_ul": 2},
            {"from": "R", "to": "Q", "amount_ul": 1},
            {"from": "Q", "to": "P", "amount_ul": 3},
            {"from": "P", "to": "R", "amount_ul": 5},
        ],
    },
    # 取空后再重新被注入
    {
        "wells": [
            {"id": "X", "volume_ul": 5, "concentration": {"numerator": 4, "denominator": 1}},
            {"id": "Y", "volume_ul": 5, "concentration": {"numerator": 0, "denominator": 1}},
        ],
        "transfers": [
            {"from": "X", "to": "Y", "amount_ul": 5},
            {"from": "Y", "to": "X", "amount_ul": 2},
        ],
    },
    # 必须失败：第二条把来源抽干后第三条透支
    {
        "wells": [
            {"id": "A", "volume_ul": 3, "concentration": {"numerator": 1, "denominator": 2}},
            {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
        ],
        "transfers": [
            {"from": "A", "to": "B", "amount_ul": 3},
            {"from": "B", "to": "A", "amount_ul": 1},
            {"from": "A", "to": "B", "amount_ul": 2},
        ],
    },
    # 必须失败：第一步即从空孔取液
    {
        "wells": [
            {"id": "A", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
            {"id": "B", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}},
        ],
        "transfers": [{"from": "A", "to": "B", "amount_ul": 1}],
    },
]


@pytest.mark.parametrize("payload", SCENARIOS)
def test_matches_independent_reference(payload):
    req = ComputeRequest.model_validate(payload)
    ref = reference_simulate(req)

    if ref["failed"] is not None:
        with pytest.raises(engine.TransferError) as exc:
            engine.compute(req.wells, req.transfers)
        assert exc.value.index == ref["failed"]
        assert exc.value.reason == ref["reason"]
        return

    result = engine.compute(req.wells, req.transfers)
    finals = {w["id"]: w for w in result["wells"]}
    for wid, state in ref["wells"].items():
        got = finals[wid]
        assert got["volume_ul"] == state["v"]
        if state["v"] == 0:
            assert got["concentration"] is None
            assert got["solute"] == {"numerator": 0, "denominator": 1}
        else:
            assert Fraction(**got["concentration"]) == state["s"] / state["v"]
        assert Fraction(**got["solute"]) == state["s"]
        assert _is_reduced(got["solute"])
        if got["concentration"]:
            assert _is_reduced(got["concentration"])

    assert len(result["steps"]) == len(ref["trace"])
    for step, tr in zip(result["steps"], ref["trace"]):
        assert Fraction(**step["after"]["source"]["concentration"]) == tr["c_src_after"] \
            if tr["c_src_after"] is not None else step["after"]["source"]["concentration"] is None
        assert Fraction(**step["after"]["target"]["concentration"]) == tr["c_dst_after"]
        # 完全混匀：取液不改变来源孔浓度
        if tr["c_src_after"] is not None:
            assert tr["c_src_before"] == tr["c_src_after"]
        ev = result["conservation"]["steps"][tr["i"] - 1]
        assert Fraction(**ev["plate_total_solute"]) == ref["total_s0"] == tr["total_s"]
        assert ev["total_volume_ul"] == ref["total_v0"] == tr["total_v"]
        assert Fraction(**ev["moved_solute"]) == tr["moved"]
        assert Fraction(**ev["source_solute_delta"]) == -tr["moved"]
        assert Fraction(**ev["target_solute_delta"]) == tr["moved"]

    cons = result["conservation"]
    assert cons["solute_conserved"] is True
    assert cons["volume_conserved"] is True
    assert Fraction(**cons["difference"]) == 0
    assert Fraction(**cons["initial_total_solute"]) == ref["total_s0"]
    assert Fraction(**cons["final_total_solute"]) == ref["total_s0"]


def test_serial_dilution_handcheck_power_of_two():
    """S 每孔 1uL@1 向空孔链转移 1uL：浓度应恒为 1（空孔接收母液）。"""
    payload = SCENARIOS[0]
    req = ComputeRequest.model_validate(payload)
    r = engine.compute(req.wells, req.transfers)
    for w in r["wells"]:
        if w["volume_ul"]:
            assert w["concentration"] == {"numerator": 1, "denominator": 1}
    assert r["conservation"]["solute_conserved"] is True
