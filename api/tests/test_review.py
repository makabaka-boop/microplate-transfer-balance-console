"""pytest：手算黄金值 + 守恒性质 + 409/422 规则。

核心问题的回归用例：第二次从已被稀释的孔取液时，必须按“当前”浓度计算，
绝不能套用初始浓度（见 test_diluted_source_not_initial_concentration）。
"""
from __future__ import annotations

import random
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from app.engine import TransferError, simulate
from app.main import app

client = TestClient(app)


def W(id, v, n, d=1):
    return {"id": id, "volume_ul": v, "concentration": {"numerator": n, "denominator": d}}


def T(src, dst, x):
    return {"from": src, "to": dst, "amount_ul": x}


# ---------------------------------------------------------------- 手算黄金值

def test_hand_calculated_two_step_transfer():
    """A:100@3 -> B 25 -> B:25 取 20 回 A，逐步手算。"""
    body = {
        "wells": [W("A", 100, 3), W("B", 0, 0)],
        "transfers": [T("A", "B", 25), T("B", "A", 20)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 200, r.text
    data = r.json()

    s1, s2 = data["steps"]

    # 第一步：A 100@3 --25--> B
    assert s1["source_before"] == {
        "well": "A", "volume_ul": 100,
        "concentration": {"numerator": 3, "denominator": 1},
        "solute_mass": {"numerator": 300, "denominator": 1},
    }
    assert s1["source_after"] == {
        "well": "A", "volume_ul": 75,
        "concentration": {"numerator": 3, "denominator": 1},
        "solute_mass": {"numerator": 225, "denominator": 1},
    }
    assert s1["target_after"] == {
        "well": "B", "volume_ul": 25,
        "concentration": {"numerator": 3, "denominator": 1},
        "solute_mass": {"numerator": 75, "denominator": 1},
    }
    assert s1["transferred_solute_mass"] == {"numerator": 75, "denominator": 1}

    # 第二步：B 25@3 --20--> A；B 浓度 3，移走溶质 60
    assert s2["source_after"]["well"] == "B"
    assert s2["source_after"]["volume_ul"] == 5
    assert s2["source_after"]["concentration"] == {"numerator": 3, "denominator": 1}
    assert s2["source_after"]["solute_mass"] == {"numerator": 15, "denominator": 1}

    # A: 75 μL + 225 溶质，加入 20 μL @3（60 溶质）=> 95 μL, 285 溶质
    # 285/95 约分 = 3（同浓度混合，浓度不变）
    assert s2["target_after"]["volume_ul"] == 95
    assert s2["target_after"]["solute_mass"] == {"numerator": 285, "denominator": 1}
    assert s2["target_after"]["concentration"] == {"numerator": 3, "denominator": 1}

    final = {w["well"]: w for w in data["final_wells"]}
    assert final["A"]["volume_ul"] == 95
    assert final["B"]["volume_ul"] == 5
    assert final["A"]["concentration"] == {"numerator": 3, "denominator": 1}

    assert data["conservation"]["mass"]["holds"] is True
    assert data["conservation"]["volume"]["holds"] is True
    assert data["conservation"]["mass"]["initial_total_solute_mass"] == {
        "numerator": 300, "denominator": 1
    }
    # 每步后（含第 0 步初态）全板溶质量逐位相等
    for entry in data["conservation"]["mass"]["total_solute_mass_after_each_step"]:
        assert entry == {"numerator": 300, "denominator": 1}


def test_fractional_concentration_is_exact_and_reduced():
    """1/3 浓度产生的 1/3 μL 溶质必须以约分分数保留，绝不中途舍入。"""
    body = {
        "wells": [W("A", 1, 1, 3), W("B", 0, 0)],
        "transfers": [T("A", "B", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    step = data["steps"][0]
    assert step["transferred_solute_mass"] == {"numerator": 1, "denominator": 3}
    assert step["target_after"]["solute_mass"] == {"numerator": 1, "denominator": 3}
    assert step["target_after"]["concentration"] == {"numerator": 1, "denominator": 3}
    # 空孔“零浓度”规范表示
    assert step["source_after"]["concentration"] == {"numerator": 0, "denominator": 1}


def test_mixing_different_concentrations_gives_reduced_fraction():
    """A:3@1/3 取 2 → B:4@1/2：B 溶质 2+2/3=8/3，体积 6，浓度 4/9（约分）。"""
    body = {
        "wells": [W("A", 3, 1, 3), W("B", 4, 1, 2)],
        "transfers": [T("A", "B", 2)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    step = data["steps"][0]
    assert step["transferred_solute_mass"] == {"numerator": 2, "denominator": 3}
    assert step["target_after"]["volume_ul"] == 6
    assert step["target_after"]["solute_mass"] == {"numerator": 8, "denominator": 3}
    assert step["target_after"]["concentration"] == {"numerator": 4, "denominator": 9}
    # 来源 A：3@1/3 取走 2/3 溶质，剩 1 μL 含 1/3
    assert step["source_after"]["volume_ul"] == 1
    assert step["source_after"]["solute_mass"] == {"numerator": 1, "denominator": 3}


def test_diluted_source_not_initial_concentration():
    """关键回归：后续步骤从已稀释孔取液，必须用当前浓度而非初始浓度。

    S:6@2 --2--> D => S:4@2（混匀后仍是 2），D:2@2
    S:4@2 --4--> X => 移走溶质 8
    然后 D:2@2 --2--> 空 S：若误用 D 初始浓度 0 会算出 0 溶质（错误）；
    正确为 4。
    """
    body = {
        "wells": [W("S", 6, 2), W("D", 0, 0), W("X", 0, 0)],
        "transfers": [T("S", "D", 2), T("S", "X", 4), T("D", "S", 2)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    step3 = data["steps"][2]
    assert step3["transferred_solute_mass"] == {"numerator": 4, "denominator": 1}
    final = {w["well"]: w for w in data["final_wells"]}
    # S 此时 2 μL 含 4 溶质 => 浓度 2
    assert final["S"] == {
        "well": "S", "volume_ul": 2,
        "concentration": {"numerator": 2, "denominator": 1},
        "solute_mass": {"numerator": 4, "denominator": 1},
    }


# ---------------------------------------------------------------- 409 冲突

def test_empty_source_returns_409_with_first_failing_step_only():
    body = {
        "wells": [W("A", 0, 5), W("B", 10, 0)],
        "transfers": [T("A", "B", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 409
    data = r.json()
    assert data["status"] == "conflict"
    assert data["error"]["code"] == "EMPTY_SOURCE"
    assert data["error"]["step"] == 1
    assert data["error"]["from"] == "A"
    assert data["error"]["requested_ul"] == 1
    assert data["error"]["available_ul"] == 0
    # 不输出任何步骤或最终表，杜绝部分成功结论
    assert "steps" not in data
    assert "final_wells" not in data


def test_insufficient_volume_returns_409_and_stops_at_first_failure():
    # 第一步合法（A:10 -> B 4），第二步想从仅剩 6 μL 的 A 取 9 μL
    body = {
        "wells": [W("A", 10, 1), W("B", 0, 0)],
        "transfers": [T("A", "B", 4), T("A", "B", 9), T("B", "A", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "INSUFFICIENT_VOLUME"
    assert err["step"] == 2
    assert err["requested_ul"] == 9
    assert err["available_ul"] == 6
    assert r.json().get("steps") is None


def test_engine_raises_on_first_failure_with_no_partial_output():
    wells = [W("A", 2, 1), W("B", 0, 0)]
    transfers = [T("A", "B", 3)]
    with pytest.raises(TransferError) as exc:
        simulate(wells, transfers)
    assert exc.value.step == 1
    assert exc.value.code == "INSUFFICIENT_VOLUME"


# ---------------------------------------------------------------- 422 非法请求

@pytest.mark.parametrize("body,field", [
    # 非法分母：0
    ({"wells": [W("A", 1, 1, 0), W("B", 0, 0)], "transfers": [T("A", "B", 1)]},
     "denominator"),
    # 非法分母：负数
    ({"wells": [W("A", 1, 1, -2), W("B", 0, 0)], "transfers": [T("A", "B", 1)]},
     "denominator"),
    # 负分子
    ({"wells": [W("A", 1, -1), W("B", 0, 0)], "transfers": [T("A", "B", 1)]},
     "numerator"),
    # 负初始体积
    ({"wells": [{"id": "A", "volume_ul": -1,
                 "concentration": {"numerator": 1, "denominator": 1}}, W("B", 0, 0)],
      "transfers": [T("A", "B", 1)]},
     "volume_ul"),
])
def test_invalid_fraction_or_volume_returns_422(body, field):
    r = client.post("/api/review", json=body)
    assert r.status_code == 422
    locs = [".".join(e["loc"]) for e in r.json()["errors"]]
    assert any(field in loc for loc in locs), locs


def test_unknown_well_in_transfer_returns_422():
    body = {
        "wells": [W("A", 5, 1), W("B", 5, 0)],
        "transfers": [T("A", "Z", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 422
    assert "未知孔位" in r.json()["errors"][0]["message"]


def test_from_equals_to_returns_422():
    body = {
        "wells": [W("A", 5, 1), W("B", 0, 0)],
        "transfers": [T("A", "A", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 422
    assert "相同" in r.json()["errors"][0]["message"]


def test_extra_field_returns_422():
    body = {
        "wells": [W("A", 5, 1), W("B", 0, 0)],
        "transfers": [dict(T("A", "B", 1), note="haha")],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 422
    assert any(
        e["type"] == "extra_forbidden" and "note" in ".".join(e["loc"])
        for e in r.json()["errors"]
    )


def test_extra_field_on_well_returns_422():
    w = dict(W("A", 5, 1))
    w["rack"] = "X1"
    body = {"wells": [w, W("B", 0, 0)], "transfers": [T("A", "B", 1)]}
    r = client.post("/api/review", json=body)
    assert r.status_code == 422


def test_duplicate_well_ids_returns_422():
    body = {
        "wells": [W("A", 5, 1), W("A", 3, 2)],
        "transfers": [T("A", "B", 1)],
    }
    r = client.post("/api/review", json=body)
    assert r.status_code == 422


@pytest.mark.parametrize("n_wells,n_steps,expected", [
    (1, 0, 422),    # 孔位不足 2（转移也为空，孔位错误先报）
    (49, 1, 422),   # 孔位超过 48
    (2, 0, 422),    # 转移为 0 条
    (2, 201, 422),  # 转移超过 200
])
def test_cardinality_limits(n_wells, n_steps, expected):
    wells = [W(f"W{i}", 10 if i == 0 else 0, 1) for i in range(n_wells)]
    steps = []
    for i in range(n_steps):
        dst = 1 + (i % max(n_wells - 1, 1))
        steps.append(T("W0", f"W{dst}", 1))
    r = client.post("/api/review", json={"wells": wells, "transfers": steps})
    assert r.status_code == expected


# ---------------------------------------------------------------- 守恒性质（随机）

def _random_valid_plan(rng: random.Random):
    n = rng.randint(2, 12)
    ids = [f"W{i}" for i in range(n)]
    wells = [
        W(ids[i], rng.randint(0, 50), rng.randint(0, 9), rng.randint(1, 7))
        for i in range(n)
    ]
    steps = []
    # 用影子体积生成一定可行的随机转移
    vol = {w["id"]: w["volume_ul"] for w in wells}
    for _ in range(rng.randint(1, 40)):
        donors = [i for i in ids if vol[i] > 0]
        if not donors:
            break
        src = rng.choice(donors)
        dst = rng.choice([i for i in ids if i != src])
        amount = rng.randint(1, vol[src])
        steps.append(T(src, dst, amount))
        vol[src] -= amount
        vol[dst] += amount
    if not steps:
        steps = [T(ids[0], ids[1], 1)]
    return wells, steps


def test_conservation_holds_over_many_random_plans():
    rng = random.Random(20260924)
    for _ in range(60):
        wells, steps = _random_valid_plan(rng)
        body = {"wells": wells, "transfers": steps}
        r = client.post("/api/review", json=body)
        assert r.status_code == 200, r.text
        data = r.json()

        init_mass = sum(
            Fraction(w["concentration"]["numerator"],
                     w["concentration"]["denominator"]) * w["volume_ul"]
            for w in wells
        )
        init_vol = sum(w["volume_ul"] for w in wells)

        # 逐步用独立的 Fraction 影子账本复算，逐孔逐字段比对
        mass = {
            w["id"]: Fraction(w["concentration"]["numerator"],
                              w["concentration"]["denominator"]) * w["volume_ul"]
            for w in wells
        }
        vol = {w["id"]: w["volume_ul"] for w in wells}
        for out, st in zip(data["steps"], steps):
            s, d, x = st["from"], st["to"], st["amount_ul"]
            moved = mass[s] * x / vol[s]
            mass[s] -= moved
            mass[d] += moved
            vol[s] -= x
            vol[d] += x
            assert Fraction(**out["transferred_solute_mass"]) == moved
            assert out["source_after"]["volume_ul"] == vol[s]
            assert Fraction(**out["source_after"]["solute_mass"]) == mass[s]
            assert out["target_after"]["volume_ul"] == vol[d]
            assert Fraction(**out["target_after"]["solute_mass"]) == mass[d]
            # 浓度恒为溶质/体积（空孔为 0）
            expect_c_s = mass[s] / vol[s] if vol[s] else Fraction(0)
            expect_c_d = mass[d] / vol[d] if vol[d] else Fraction(0)
            assert Fraction(**out["source_after"]["concentration"]) == expect_c_s
            assert Fraction(**out["target_after"]["concentration"]) == expect_c_d

        assert data["conservation"]["mass"]["holds"] is True
        assert Fraction(**data["conservation"]["mass"]["final_total_solute_mass"]) == init_mass
        assert data["conservation"]["volume"]["final_total_volume_ul"] == init_vol
        assert sum(mass.values()) == init_mass


def test_malformed_json_returns_422():
    r = client.post(
        "/api/review",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert r.json()["status"] == "invalid_request"


def test_health():
    assert client.get("/health").status_code == 200
