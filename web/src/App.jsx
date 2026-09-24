import React from 'react'
import { compute, fracText } from './api.js'

// 初始示例：经典二倍连续稀释——母液 S=10μL@1，W1..W5 各预置 1μL 稀释液（浓度 0），
// 逐级转移 1 μL 后各孔应为 @1/2、1/4、1/8、1/16，W5=2μL@1/32
const SAMPLE = {
  wells: [
    { id: 'S', volume: '10', num: '1', den: '1' },
    ...['W1', 'W2', 'W3', 'W4', 'W5'].map((id) => ({
      id,
      volume: '1',
      num: '0',
      den: '1',
    })),
  ],
  transfers: [
    { from: 'S', to: 'W1', amount: '1' },
    { from: 'W1', to: 'W2', amount: '1' },
    { from: 'W2', to: 'W3', amount: '1' },
    { from: 'W3', to: 'W4', amount: '1' },
    { from: 'W4', to: 'W5', amount: '1' },
  ],
}

function FieldIssue({ loc, issues }) {
  const hit = issues.find((i) =>
    loc.every((seg, k) => String(i.loc[k]) === String(seg)),
  )
  if (!hit) return null
  return <span className="field-issue">{hit.msg.replace(/^Value error,\s*/, '')}</span>
}

export default function App() {
  const [wells, setWells] = React.useState(SAMPLE.wells)
  const [transfers, setTransfers] = React.useState(SAMPLE.transfers)
  const [result, setResult] = React.useState(null) // 成功结论
  const [error, setError] = React.useState(null) // 409/422/异常
  const [submitting, setSubmitting] = React.useState(false)

  // 任何编辑都清除上一轮结论（成功与失败都清）
  const touch = () => {
    setResult(null)
    setError(null)
  }

  const updateWell = (k, key, value) => {
    touch()
    setWells((ws) => ws.map((w, i) => (i === k ? { ...w, [key]: value } : w)))
  }
  const addWell = () => {
    touch()
    setWells((ws) => [
      ...ws,
      { id: `W${ws.length + 1}`, volume: '0', num: '0', den: '1' },
    ])
  }
  const removeWell = (k) => {
    touch()
    setWells((ws) => ws.filter((_, i) => i !== k))
  }

  const updateTransfer = (k, key, value) => {
    touch()
    setTransfers((ts) => ts.map((t, i) => (i === k ? { ...t, [key]: value } : t)))
  }
  const addTransfer = () => {
    touch()
    setTransfers((ts) => [
      ...ts,
      { from: wells[0]?.id ?? '', to: wells[1]?.id ?? '', amount: '1' },
    ])
  }
  const removeTransfer = (k) => {
    touch()
    setTransfers((ts) => ts.filter((_, i) => i !== k))
  }
  const moveTransfer = (k, dir) => {
    touch()
    setTransfers((ts) => {
      const j = k + dir
      if (j < 0 || j >= ts.length) return ts
      const copy = [...ts]
      ;[copy[k], copy[j]] = [copy[j], copy[k]]
      return copy
    })
  }

  const clientIssues = () => {
    const out = []
    if (wells.length < 2 || wells.length > 48)
      out.push(`孔位数量需在 2–48 之间（当前 ${wells.length}）`)
    const ids = wells.map((w) => w.id.trim())
    if (ids.some((id) => !id)) out.push('存在空的孔位 id')
    const dup = ids.filter((id, i) => id && ids.indexOf(id) !== i)
    if (dup.length) out.push(`孔位 id 重复：${[...new Set(dup)].join('、')}`)
    wells.forEach((w, k) => {
      if (!Number.isInteger(+w.volume) || +w.volume < 0)
        out.push(`孔 ${k + 1} 体积需为非负整数`)
      if (!Number.isInteger(+w.num) || +w.num < 0)
        out.push(`孔 ${k + 1} 浓度分子需为非负整数`)
      if (!Number.isInteger(+w.den) || +w.den <= 0)
        out.push(`孔 ${k + 1} 浓度分母需为正整数`)
    })
    if (transfers.length < 1 || transfers.length > 200)
      out.push(`转移条数需在 1–200 之间（当前 ${transfers.length}）`)
    const known = new Set(ids)
    transfers.forEach((t, k) => {
      if (!known.has(t.from.trim())) out.push(`第 ${k + 1} 条：未知来源孔 ${t.from}`)
      if (!known.has(t.to.trim())) out.push(`第 ${k + 1} 条：未知目标孔 ${t.to}`)
      if (t.from.trim() && t.from.trim() === t.to.trim())
        out.push(`第 ${k + 1} 条：from 与 to 不得相同`)
      if (!Number.isInteger(+t.amount) || +t.amount <= 0)
        out.push(`第 ${k + 1} 条：转移量需为正整数`)
    })
    return out
  }

  const submit = async () => {
    const issues = clientIssues()
    if (issues.length) {
      setResult(null)
      setError({
        status: 422,
        message: '浏览器预检未通过，请先修正：',
        local: issues,
        issues: [],
      })
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        wells: wells.map((w) => ({
          id: w.id.trim(),
          volume_ul: +w.volume,
          concentration: { numerator: +w.num, denominator: +w.den },
        })),
        transfers: transfers.map((t) => ({
          from: t.from.trim(),
          to: t.to.trim(),
          amount_ul: +t.amount,
        })),
      }
      const r = await compute(payload)
      if (r.ok) {
        setResult(r.data)
        setError(null)
      } else {
        setResult(null)
        setError(r)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const wellOptions = wells.map((w, k) => [w.id.trim() || `#${k + 1}`, k])

  return (
    <div className="page">
      <header>
        <h1>微孔板逐孔转移复核台</h1>
        <p className="subtitle">
          完全混匀模型 · 分数精确计算无舍入 · 逐步追溯来源/目标的浓度与体积 · 全板溶质守恒证据
        </p>
      </header>

      <section className="panel">
        <h2>① 孔位（{wells.length}，要求 2–48，id 唯一）</h2>
        <div className="well-grid" data-testid="well-editor-grid">
          {wells.map((w, k) => (
            <div className="well-card" key={k}>
              <div className="well-card-head">
                <input
                  aria-label={`孔 ${k + 1} id`}
                  value={w.id}
                  onChange={(e) => updateWell(k, 'id', e.target.value)}
                  className="id-input"
                />
                <button
                  type="button"
                  className="mini danger"
                  onClick={() => removeWell(k)}
                  disabled={wells.length <= 2}
                  title="删除孔位"
                >
                  ×
                </button>
              </div>
              <label>
                体积(μL)
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={w.volume}
                  onChange={(e) => updateWell(k, 'volume', e.target.value)}
                />
              </label>
              <label>
                浓度分子
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={w.num}
                  onChange={(e) => updateWell(k, 'num', e.target.value)}
                />
              </label>
              <label>
                浓度分母
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={w.den}
                  onChange={(e) => updateWell(k, 'den', e.target.value)}
                />
              </label>
              <FieldIssue loc={['wells', k]} issues={error?.issues ?? []} />
            </div>
          ))}
        </div>
        <button type="button" className="mini" onClick={addWell} disabled={wells.length >= 48}>
          ＋ 添加孔位
        </button>
      </section>

      <section className="panel">
        <h2>② 转移步骤（{transfers.length}，要求 1–200，按序执行）</h2>
        <div className="transfer-table-wrap">
          <table className="transfer-table">
            <thead>
              <tr>
                <th>#</th>
                <th>from</th>
                <th>to</th>
                <th>μL</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {transfers.map((t, k) => (
                <tr
                  key={k}
                  className={
                    error?.status === 409 && error.detail?.index === k + 1
                      ? 'failed-row'
                      : undefined
                  }
                >
                  <td>{k + 1}</td>
                  <td>
                    <select
                      aria-label={`第 ${k + 1} 条来源`}
                      value={wells.findIndex((w) => w.id.trim() === t.from.trim())}
                      onChange={(e) =>
                        updateTransfer(k, 'from', wells[+e.target.value]?.id ?? '')
                      }
                    >
                      {wellOptions.map(([label, idx]) => (
                        <option key={idx} value={idx}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      aria-label={`第 ${k + 1} 条目标`}
                      value={wells.findIndex((w) => w.id.trim() === t.to.trim())}
                      onChange={(e) =>
                        updateTransfer(k, 'to', wells[+e.target.value]?.id ?? '')
                      }
                    >
                      {wellOptions.map(([label, idx]) => (
                        <option key={idx} value={idx}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={t.amount}
                      onChange={(e) => updateTransfer(k, 'amount', e.target.value)}
                    />
                  </td>
                  <td className="row-ops">
                    <button
                      type="button"
                      className="mini"
                      onClick={() => moveTransfer(k, -1)}
                      disabled={k === 0}
                      title="上移"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="mini"
                      onClick={() => moveTransfer(k, 1)}
                      disabled={k === transfers.length - 1}
                      title="下移"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="mini danger"
                      onClick={() => removeTransfer(k)}
                      title="删除"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="mini"
          onClick={addTransfer}
          disabled={transfers.length >= 200}
        >
          ＋ 添加转移
        </button>
      </section>

      <div className="submit-bar">
        <button
          type="button"
          className="primary"
          onClick={submit}
          disabled={submitting}
          data-testid="compute-submit"
        >
          {submitting ? '计算中…' : '逐步复核'}
        </button>
        {(result || error) && (
          <span className="stale-hint">编辑任意孔位或步骤将清除当前结论</span>
        )}
      </div>

      {error && <ErrorPanel error={error} />}
      {result && <ResultView result={result} fracText={fracText} />}
    </div>
  )
}

function ErrorPanel({ error }) {
  if (error.status === 409 && error.detail) {
    const d = error.detail
    return (
      <section className="panel error-panel" data-testid="conflict-panel">
        <h2>⛔ 第 {d.index} 条转移失败，整板未继续执行</h2>
        <p className="error-message">{d.message}</p>
        <ul className="error-facts">
          <li>
            <strong>from → to：</strong>
            {d.from} → {d.to}，请求 {d.amount_ul} μL
          </li>
          <li>
            <strong>原因：</strong>
            {d.reason === 'empty_source'
              ? `来源孔 ${d.from} 已为空（0 μL）`
              : `来源孔 ${d.from} 仅剩 ${d.available_ul} μL，余额不足`}
          </li>
          <li>
            <strong>结论：</strong>不输出任何部分成功的终态；上游编辑器中第 {d.index}{' '}
            行已标红。
          </li>
        </ul>
      </section>
    )
  }

  const issues = error.local ?? error.issues?.map((i) => `${i.loc.join('.')}: ${i.msg}`)
  return (
    <section className="panel error-panel" data-testid="validation-panel">
      <h2>请求不合法（{error.status ?? 422}）</h2>
      <p className="error-message">{error.message}</p>
      <ul className="error-facts">
        {(issues ?? [error.message]).map((m, k) => (
          <li key={k}>{String(m).replace(/^Value error,\s*/, '')}</li>
        ))}
      </ul>
    </section>
  )
}

function concentrationColor(f) {
  if (!f) return 'rgba(0,0,0,0.04)'
  const v = f.numerator / f.denominator
  // 浓度越高颜色越深（饱和在 2）
  const t = Math.min(1, v / 2)
  return `rgba(37, 99, 235, ${0.08 + 0.62 * t})`
}

function ResultView({ result, fracText }) {
  const c = result.conservation
  return (
    <div data-testid="result-view">
      <section
        className={`panel conservation ${
          c.solute_conserved && c.volume_conserved ? 'ok' : 'bad'
        }`}
        data-testid="conservation-banner"
      >
        <h2>
          {c.solute_conserved && c.volume_conserved
            ? '✅ 守恒核对通过'
            : '❌ 守恒核对失败'}
        </h2>
        <div className="cons-grid">
          <div>
            <span className="label">初始总溶质</span>
            <strong>{fracText(c.initial_total_solute)}</strong>
          </div>
          <div>
            <span className="label">终态总溶质</span>
            <strong>{fracText(c.final_total_solute)}</strong>
          </div>
          <div>
            <span className="label">差值</span>
            <strong>{fracText(c.difference)}</strong>
          </div>
          <div>
            <span className="label">总体积</span>
            <strong>
              {c.initial_total_volume_ul} → {c.final_total_volume_ul} μL
            </strong>
          </div>
        </div>
        <details>
          <summary>每步守恒证据（溶质增量之和恒为 0，全板总量恒定）</summary>
          <table className="evidence-table">
            <thead>
              <tr>
                <th>步</th>
                <th>移出溶质</th>
                <th>来源 Δ</th>
                <th>目标 Δ</th>
                <th>Δ 之和</th>
                <th>全板总溶质</th>
                <th>全板总体积(μL)</th>
              </tr>
            </thead>
            <tbody>
              {c.steps.map((e) => (
                <tr key={e.index}>
                  <td>{e.index}</td>
                  <td>{fracText(e.moved_solute)}</td>
                  <td>{fracText(e.source_solute_delta)}</td>
                  <td>{fracText(e.target_solute_delta)}</td>
                  <td>{fracText(e.delta_sum)}</td>
                  <td>{fracText(e.plate_total_solute)}</td>
                  <td>{e.total_volume_ul}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>

      <section className="panel">
        <h2>③ 终态孔板（颜色深浅表示浓度）</h2>
        <div className="well-grid result-grid" data-testid="result-grid">
          {result.wells.map((w) => (
            <div
              className="well-cell"
              key={w.id}
              style={{ background: concentrationColor(w.concentration) }}
            >
              <span className="well-cell-id">{w.id}</span>
              <span className="well-cell-c">{fracText(w.concentration)}</span>
              <span className="well-cell-v">{w.volume_ul} μL</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>④ 逐步追溯（每步前后来源/目标的浓度与体积）</h2>
        <div className="transfer-table-wrap">
          <table className="trace-table" data-testid="trace-table">
            <thead>
              <tr>
                <th>步</th>
                <th>转移</th>
                <th colSpan={2}>前（from / to）</th>
                <th colSpan={2}>后（from / to）</th>
              </tr>
              <tr>
                <th></th>
                <th></th>
                <th>来源</th>
                <th>目标</th>
                <th>来源</th>
                <th>目标</th>
              </tr>
            </thead>
            <tbody>
              {result.steps.map((s) => (
                <tr key={s.index}>
                  <td>{s.index}</td>
                  <td>
                    {s.from} → {s.to}
                    <br />
                    <small>{s.amount_ul} μL</small>
                  </td>
                  <Endpoint e={s.before.source} fracText={fracText} />
                  <Endpoint e={s.before.target} fracText={fracText} />
                  <Endpoint e={s.after.source} fracText={fracText} />
                  <Endpoint e={s.after.target} fracText={fracText} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Endpoint({ e, fracText }) {
  return (
    <td>
      <strong>{e.id}</strong>
      <br />
      <small>
        {fracText(e.concentration)} · {e.volume_ul} μL
      </small>
    </td>
  )
}
