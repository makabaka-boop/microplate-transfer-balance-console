# 微孔板逐孔转移复核台

轻量全栈小工具，解决的问题：**微孔板逐孔转移母液时，后续步骤若继续从已被稀释的孔取液，
套用初始浓度会让整板目标浓度全部算错；只核对最终体积也看不出中途透支。**

本台以**完全混匀模型**按步骤顺序精确计算每一步前后来源孔/目标孔的体积、浓度与溶质量，
全程使用约分分数（`fractions.Fraction`），不做任何中途舍入；从空孔取液或余额不足时在
**第一条失败步骤**处中止并返回 409，不输出部分成功结论。

## 架构

```
web/   React 18 + TypeScript + Vite（孔板网格 + 有序步骤表共用一份响应状态）
api/   FastAPI + Pydantic（逐步精确计算、严格校验）
docker-compose.yml  web(nginx:8080) + api(uvicorn:8000)
```

## 运行（Docker Compose）

```bash
docker compose up --build
# 页面：http://localhost:8080   API 文档：http://localhost:8000/docs
```

## 本地开发

```bash
# 后端
python3 -m venv .venv && .venv/bin/pip install -r api/requirements.txt
.venv/bin/uvicorn --app-dir api app.main:app --reload --port 8000

# 前端（dev server 已把 /api 代理到 8000）
cd web && npm install && npm run dev   # http://localhost:5173
```

## API

`POST /api/review`

请求（孔位 2~48 个、转移 1~200 条；浓度 = 非负整数分子 / 正整数分母；额外字段一律拒绝）：

```json
{
  "wells": [
    {"id": "A", "volume_ul": 100, "concentration": {"numerator": 3, "denominator": 1}},
    {"id": "B", "volume_ul": 0,   "concentration": {"numerator": 0, "denominator": 1}}
  ],
  "transfers": [
    {"from": "A", "to": "B", "amount_ul": 25},
    {"from": "B", "to": "A", "amount_ul": 20}
  ]
}
```

- `200`：每步前后来源/目标的浓度、体积、溶质量，移走的溶质量，最终孔位表，
  以及**全板溶质量守恒证据**（初值、每步后值、终值逐位相等）与体积守恒。
- `409`：`EMPTY_SOURCE`（空孔取液）或 `INSUFFICIENT_VOLUME`（余额不足），
  带第一条失败步骤序号与当时可用余额；响应不含任何步骤结果。
- `422`：非法分母、负分子/负体积、非正取液量、孔位 id 缺失/重复、未知孔位、
  from==to、数量越界或出现额外字段。

### 计算模型

第 *k* 步从 S 取 x μL 至 T（S 当前体积 V>0）：

- 移走溶质 `m_move = M_S · x / V`
- S：`V ← V−x`，`M_S ← M_S − m_move`（混匀后吸出，浓度不变）
- T：`V ← V+x`，`M_T ← M_T + m_move`

## 测试

```bash
# 后端：手算黄金值 + 60 组随机计划的独立影子账本守恒核对 + 409/422 边界
.venv/bin/python -m pytest api/tests -q

# 浏览器：仅一条端到端用例，覆盖一次真实提交与展示
cd web && npx playwright install chromium && npx playwright test
```

## 页面

- 左侧：孔板网格（直接编辑 id / 初始体积 / 浓度分数）与有序转移步骤表（可排序、删除）。
- 右侧：提交后展示守恒徽标、每步前后状态追溯（分数原样显示）与按浓度着色的最终孔板。
- **任何编辑都会清除旧结论**，避免展示与输入不一致的结果。
