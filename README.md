# 微孔板逐孔转移复核台

针对“逐孔转移母液时，后续步骤继续从**已被稀释**的孔取液，若套用初始浓度会让整板
目标浓度错误；只核对最终体积也发现不了中途透支”这一问题的轻量全栈复核工具。

- **前端（web/）**：React + Vite。孔板网格编辑孔位、步骤表编辑有序转移；
  成功后展示终态孔板、每步前后来源/目标的浓度与体积、每步守恒证据。**任何编辑都会
  清除上一轮结论**。
- **后端（backend/）**：FastAPI。`POST /api/compute` 按步骤顺序以**完全混匀模型**
  计算，体积与溶质量全程用 `fractions.Fraction`（约分分数，**绝不中途舍入**）。
- **运行**：Docker Compose 起 `web`（nginx 静态站 + `/api` 反代）与 `api` 两个服务。

## 计算模型

- 孔的溶质量 = 初始浓度（分子/分母分数）× 初始体积。
- 第 k 步 `from -> to, a μL`（完全混匀）：
  - 移出溶质 = 来源孔当前溶质 × a / 来源孔当前体积；
  - 来源孔体积减 a、溶质减移出量；目标孔体积加 a、溶质加移出量。
- 取液不改变来源孔剩余液体的浓度；空孔浓度输出为 `null`。
- 每步记录移出量、来源/目标溶质增量（二者之和恒为 0）、全板总溶质与总体积。

## 请求约束（违例返回 422）

- `wells`：2–48 个，`id` 唯一非空；`volume_ul` 为非负整数 μL；
  `concentration = {numerator: 非负整数, denominator: 正整数}`。
- `transfers`：1–200 条有序转移；`from` / `to` 必须引用已知孔位且不得相同；
  `amount_ul` 为正整数。
- 任何层级出现**额外字段**一律 422（严格模型）。

## 运行期失败（返回 409，只定位第一条失败步骤）

- `empty_source`：从空孔（体积 0）取液；
- `insufficient_volume`：来源孔余额不足。

409 响应只含失败步骤的序号、原因、from/to、请求量与来源孔当前可用量，
**不输出任何部分成功结论**（无 wells / steps）。

## 响应（200）

```jsonc
{
  "wells":    [{"id": "W1", "volume_ul": 1, "concentration": {"numerator":1,"denominator":2}, "solute": {...}}],
  "steps":    [{"index": 1, "from": "S", "to": "W1", "amount_ul": 1,
                "before": {"source": {"id","volume_ul","concentration"}, "target": {...}},
                "after":  {...}}],
  "conservation": {
    "initial_total_solute": {...}, "final_total_solute": {...}, "difference": {"numerator":0,"denominator":1},
    "solute_conserved": true, "volume_conserved": true,
    "initial_total_volume_ul": 15, "final_total_volume_ul": 15,
    "steps": [{"index": 1, "moved_solute": {...}, "source_solute_delta": {...},
               "target_solute_delta": {...}, "delta_sum": {"numerator":0,"denominator":1},
               "plate_total_solute": {...}, "total_volume_ul": 15}]
  }
}
```

## 用 Docker Compose 运行

```bash
docker compose up --build
# 打开 http://localhost:8080
```

## 本地开发

```bash
# 后端（:8000）
cd backend
python3 -m pip install -r requirements-dev.txt   # 含 pytest/httpx
PYTHONPATH=. python3 -m uvicorn app.main:app --reload

# 前端（:5173，已配置 /api -> :8000 代理）
cd web
npm install
npm run dev
```

## 测试

- **pytest（手算 + 守恒性质）**：
  ```bash
  cd backend && python3 -m pytest tests -q
  ```
  - `tests/test_engine_handcalc.py`：手算逐步前后浓度/体积、约分分数、终态；
  - `tests/test_conservation_properties.py`：另写一份独立 Fraction 模拟器交叉验证，
    固定场景下核对守恒、完全混匀不变量、失败定位、分数均已约分；
  - `tests/test_api.py`：200 结构、409 首失败定位且无部分成功结论、422 全部非法类别、
    孔数 2–48 / 步骤数 1–200 边界。
- **浏览器（仅一次真实提交与展示）**：
  ```bash
  cd web && npx playwright test
  ```
  Playwright 会自动拉起 uvicorn（:8000）与 Vite（:5173）。无头浏览器若缺系统库，
  需自行安装 Chromium 运行依赖（如 `npx playwright install --with-deps chromium`）。
