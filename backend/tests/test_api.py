"""HTTP 层：200 成功结构、409 定位首失败且无部分成功、422 非法输入。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


OK_BODY = {
    "wells": [
        {"id": "A", "volume_ul": 6, "concentration": {"numerator": 1, "denominator": 2}},
        {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
    ],
    "transfers": [{"from": "A", "to": "B", "amount_ul": 3}],
}


def test_success_shape_and_aliases(client):
    r = client.post("/api/compute", json=OK_BODY)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"wells", "steps", "conservation"}
    step = body["steps"][0]
    assert step["from"] == "A"  # 响应使用 from 别名
    assert "from_" not in step
    assert step["before"]["source"]["concentration"] == {"numerator": 1, "denominator": 2}
    assert step["before"]["target"]["concentration"] is None
    assert step["after"]["source"]["volume_ul"] == 3
    assert step["after"]["target"]["volume_ul"] == 3
    cons = body["conservation"]
    assert cons["solute_conserved"] and cons["volume_conserved"]
    assert cons["steps"][0]["delta_sum"] == {"numerator": 0, "denominator": 1}


def test_409_empty_source_locates_first_step(client):
    body = {
        "wells": [
            {"id": "A", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
            {"id": "B", "volume_ul": 4, "concentration": {"numerator": 1, "denominator": 1}},
        ],
        "transfers": [{"from": "A", "to": "B", "amount_ul": 1}],
    }
    r = client.post("/api/compute", json=body)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["index"] == 1
    assert d["reason"] == "empty_source"
    assert d["available_ul"] == 0
    # 不输出任何部分成功结论
    assert set(r.json()) == {"detail"}
    assert "wells" not in d and "steps" not in d


def test_409_overdraw_after_partial_run(client):
    # 第一步后 A=3、第二步后 A=1，第三条要取 3 -> 余额不足；
    # 必须定位到第 3 条且无部分成功结论
    body = {
        "wells": [
            {"id": "A", "volume_ul": 4, "concentration": {"numerator": 3, "denominator": 1}},
            {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
        ],
        "transfers": [
            {"from": "A", "to": "B", "amount_ul": 1},
            {"from": "A", "to": "B", "amount_ul": 2},
            {"from": "A", "to": "B", "amount_ul": 3},
        ],
    }
    r = client.post("/api/compute", json=body)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["index"] == 3
    assert d["reason"] == "insufficient_volume"
    assert d["available_ul"] == 1
    assert "wells" not in r.json() and "steps" not in r.json()


def test_409_exact_balance_allowed(client):
    # 恰好取干是合法的；之后再取才是空孔失败
    body = {
        "wells": [
            {"id": "A", "volume_ul": 2, "concentration": {"numerator": 1, "denominator": 1}},
            {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
        ],
        "transfers": [
            {"from": "A", "to": "B", "amount_ul": 2},
            {"from": "A", "to": "B", "amount_ul": 1},
        ],
    }
    r = client.post("/api/compute", json=body)
    assert r.status_code == 409
    assert r.json()["detail"]["index"] == 2
    assert r.json()["detail"]["reason"] == "empty_source"


@pytest.mark.parametrize(
    "body",
    [
        # 非法分母（0 与负数）
        {**OK_BODY, "wells": [
            {"id": "A", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 0}},
            {"id": "B", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}}]},
        {**OK_BODY, "wells": [
            {"id": "A", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": -2}},
            {"id": "B", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}}]},
        # 未知孔位
        {**OK_BODY, "transfers": [{"from": "A", "to": "Z", "amount_ul": 1}]},
        {**OK_BODY, "transfers": [{"from": "Z", "to": "A", "amount_ul": 1}]},
        # 额外字段（各层级）
        {**OK_BODY, "unexpected": 1},
        {**OK_BODY, "wells": [
            {"id": "A", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}, "x": 9},
            {"id": "B", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}}]},
        {**OK_BODY, "transfers": [{"from": "A", "to": "B", "amount_ul": 1, "via": "robot"}]},
        # 非整数 / 负数 / 零量
        {**OK_BODY, "transfers": [{"from": "A", "to": "B", "amount_ul": 1.5}]},
        {**OK_BODY, "wells": [
            {"id": "A", "volume_ul": -1, "concentration": {"numerator": 1, "denominator": 1}},
            {"id": "B", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}}]},
        {**OK_BODY, "transfers": [{"from": "A", "to": "B", "amount_ul": 0}]},
        # from == to、重复 id
        {**OK_BODY, "transfers": [{"from": "A", "to": "A", "amount_ul": 1}]},
        {**OK_BODY, "wells": [
            {"id": "A", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}},
            {"id": "A", "volume_ul": 1, "concentration": {"numerator": 1, "denominator": 1}}]},
    ],
)
def test_422_invalid_payloads(client, body):
    r = client.post("/api/compute", json=body)
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("n_wells,code", [(1, 422), (2, 200), (48, 200), (49, 422)])
def test_well_count_bounds(client, n_wells, code):
    body = {
        "wells": [
            {"id": f"W{i}", "volume_ul": 1, "concentration": {"numerator": 0, "denominator": 1}}
            for i in range(n_wells)
        ],
        "transfers": [{"from": "W0", "to": "W1", "amount_ul": 1}],
    }
    r = client.post("/api/compute", json=body)
    assert r.status_code == code


def test_transfer_count_bounds(client):
    wells = [
        {"id": "A", "volume_ul": 200, "concentration": {"numerator": 1, "denominator": 1}},
        {"id": "B", "volume_ul": 0, "concentration": {"numerator": 0, "denominator": 1}},
    ]
    ts = [{"from": "A", "to": "B", "amount_ul": 1}]
    r0 = client.post("/api/compute", json={"wells": wells, "transfers": []})
    assert r0.status_code == 422
    r1 = client.post("/api/compute", json={"wells": wells, "transfers": ts})
    assert r1.status_code == 200


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
