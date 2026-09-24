"""手算核对：逐步前后端点浓度/体积、终态、守恒证据。"""
from __future__ import annotations

from fractions import Fraction

from app import engine
from app.schemas import ComputeRequest


def run(payload):
    req = ComputeRequest.model_validate(payload)
    return engine.compute(req.wells, req.transfers)


# 手算例 1：同浓度逐级转移，混合不改变浓度，但体积/溶质严格按比例移动
#
# A=10uL@1/2, B=C=0
# t1 A->B 3 : A=7@1/2(s=7/2) B=3@1/2(s=3/2) C=0
# t2 B->C 2 : A=7(s=7/2) B=1(s=1/2) C=2(s=1)
# t3 C->A 1 : A=8(s=4) B=1(s=1/2) C=1(s=1/2)，各孔仍 @1/2
def test_handcalc_same_concentration_chain():
    r = run(
        {
            "wells": [
                {"id": "A", "volume_ul": 10, "concentration": {"numerator": 1, "denominator": 2}},
                {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
                {"id": "C", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 7}},
            ],
            "transfers": [
                {"from": "A", "to": "B", "amount_ul": 3},
                {"from": "B", "to": "C", "amount_ul": 2},
                {"from": "C", "to": "A", "amount_ul": 1},
            ],
        }
    )

    s1, s2, s3 = r["steps"]
    assert (s1["before"]["source"]["volume_ul"], s1["before"]["source"]["concentration"]) == (
        10,
        {"numerator": 1, "denominator": 2},
    )
    assert s1["before"]["target"]["concentration"] is None  # 空孔浓度 null
    assert s1["after"]["source"] == {
        "id": "A",
        "volume_ul": 7,
        "concentration": {"numerator": 1, "denominator": 2},
    }
    assert s1["after"]["target"] == {
        "id": "B",
        "volume_ul": 3,
        "concentration": {"numerator": 1, "denominator": 2},
    }
    assert s2["after"]["source"]["volume_ul"] == 1
    assert s2["after"]["target"] == {
        "id": "C",
        "volume_ul": 2,
        "concentration": {"numerator": 1, "denominator": 2},
    }
    assert s3["after"]["source"] == {
        "id": "C",
        "volume_ul": 1,
        "concentration": {"numerator": 1, "denominator": 2},
    }
    assert s3["after"]["target"] == {
        "id": "A",
        "volume_ul": 8,
        "concentration": {"numerator": 1, "denominator": 2},
    }

    final = {w["id"]: w for w in r["wells"]}
    assert final["A"]["solute"] == {"numerator": 4, "denominator": 1}
    assert final["B"]["solute"] == {"numerator": 1, "denominator": 2}
    assert final["C"]["solute"] == {"numerator": 1, "denominator": 2}
    assert final["C"]["concentration"] == {"numerator": 1, "denominator": 2}

    c = r["conservation"]
    assert c["solute_conserved"] is True
    assert c["volume_conserved"] is True
    assert c["difference"] == {"numerator": 0, "denominator": 1}
    assert c["initial_total_solute"] == {"numerator": 5, "denominator": 1}
    assert c["final_total_solute"] == {"numerator": 5, "denominator": 1}
    assert [e["plate_total_solute"] for e in c["steps"]] == [
        {"numerator": 5, "denominator": 1}
    ] * 3
    assert [e["total_volume_ul"] for e in c["steps"]] == [10, 10, 10]
    # 每步来源与目标溶质增量之和恰为 0
    for e in c["steps"]:
        assert e["delta_sum"] == {"numerator": 0, "denominator": 1}


# 手算例 2：不同浓度混合，出现约分分数且全程无舍入
# A=3uL@2(s=6), B=5uL@1/3(s=5/3)
# A->B 3（全部 A）: A 空；B=8, s=6+5/3=23/3, c=23/24
# B->A 2: B=6, 取出 s = 23/3 * 2/8 = 23/12; B 余 s=23/4, c=23/24
#        A=2, s=23/12, c=23/24
def test_handcalc_mixed_fractions():
    r = run(
        {
            "wells": [
                {"id": "A", "volume_ul": 3, "concentration": {"numerator": 2, "denominator": 1}},
                {"id": "B", "volume_ul": 5, "concentration": {"numerator": 1, "denominator": 3}},
            ],
            "transfers": [
                {"from": "A", "to": "B", "amount_ul": 3},
                {"from": "B", "to": "A", "amount_ul": 2},
            ],
        }
    )
    f = {w["id"]: w for w in r["wells"]}
    # 终态是第二步（回注 2uL）之后：A=2@23/24, B=6@23/24
    assert f["A"]["volume_ul"] == 2
    assert f["A"]["concentration"] == {"numerator": 23, "denominator": 24}
    assert f["B"]["volume_ul"] == 6
    assert f["B"]["concentration"] == {"numerator": 23, "denominator": 24}

    s2 = r["steps"][1]
    assert s2["after"]["source"] == {
        "id": "B",
        "volume_ul": 6,
        "concentration": {"numerator": 23, "denominator": 24},
    }
    assert s2["after"]["target"] == {
        "id": "A",
        "volume_ul": 2,
        "concentration": {"numerator": 23, "denominator": 24},
    }
    assert f["A"]["solute"] == {"numerator": 23, "denominator": 12}
    assert f["B"]["solute"] == {"numerator": 23, "denominator": 4}
    # 初始总溶质 6 + 5/3 = 23/3
    assert r["conservation"]["initial_total_solute"] == {"numerator": 23, "denominator": 3}
    assert r["conservation"]["solute_conserved"] is True


def test_fractions_are_reduced():
    # 输入 2/4 与转移后 4/8 都应被 Fraction 约成最简
    r = run(
        {
            "wells": [
                {"id": "A", "volume_ul": 4, "concentration": {"numerator": 2, "denominator": 4}},
                {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
            ],
            "transfers": [{"from": "A", "to": "B", "amount_ul": 2}],
        }
    )
    f = {w["id"]: w for w in r["wells"]}
    assert f["A"]["concentration"] == {"numerator": 1, "denominator": 2}
    assert f["B"]["solute"] == {"numerator": 1, "denominator": 1}
