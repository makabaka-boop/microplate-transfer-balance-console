import { Fragment, useState } from "react";
import type { ConflictError, ReviewOk, ValidationError } from "../types";
import { formatFraction, fractionValue } from "../types";

/** 单孔状态：体积 + 浓度分数 + 溶质分数。 */
function StateCell({ state }: { state: ReviewOk["final_wells"][number] }) {
  return (
    <div className="state-cell">
      <span className="state-line">
        V=<b>{state.volume_ul}</b> μL
      </span>
      <span className="state-line">
        C=<b>{formatFraction(state.concentration)}</b>
      </span>
      <span className="state-line dim">M={formatFraction(state.solute_mass)}</span>
    </div>
  );
}

function StepTrace({ result }: { result: ReviewOk }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>逐步追溯（{result.steps.length} 步，精确分数无舍入）</h2>
      </header>
      <div className="step-scroll">
        <table className="trace-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th>转移</th>
              <th>来源：前 → 后</th>
              <th>目标：前 → 后</th>
              <th>移走溶质</th>
            </tr>
          </thead>
          <tbody>
            {result.steps.map((s) => {
              const expanded = open === s.step;
              return (
                <Fragment key={s.step}>
                  <tr
                    className={`trace-row ${expanded ? "expanded" : ""}`}
                    onClick={() => setOpen(expanded ? null : s.step)}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="step-no">{s.step}</td>
                    <td>
                      {s.from} <span className="arrow">→</span> {s.to}
                      <div className="dim">{s.amount_ul} μL</div>
                    </td>
                    <td>
                      <div className="state-pair">
                        <StateCell state={s.source_before} />
                        <span className="arrow">→</span>
                        <StateCell state={s.source_after} />
                      </div>
                    </td>
                    <td>
                      <div className="state-pair">
                        <StateCell state={s.target_before} />
                        <span className="arrow">→</span>
                        <StateCell state={s.target_after} />
                      </div>
                    </td>
                    <td className="mass-cell">{formatFraction(s.transferred_solute_mass)}</td>
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FinalGrid({ result }: { result: ReviewOk }) {
  const maxC = Math.max(1e-12, ...result.final_wells.map((w) => fractionValue(w.concentration)));
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>最终孔位表</h2>
      </header>
      <div className="final-grid">
        {result.final_wells.map((w) => {
          const t = fractionValue(w.concentration) / maxC;
          const bg = `rgba(64, 128, 224, ${0.08 + 0.55 * t})`;
          return (
            <div key={w.well} className="final-cell" style={{ background: bg }}>
              <div className="final-id">{w.well}</div>
              <div>{w.volume_ul} μL</div>
              <div className="final-c">C = {formatFraction(w.concentration)}</div>
              <div className="dim">M = {formatFraction(w.solute_mass)}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ConservationBar({ result }: { result: ReviewOk }) {
  const c = result.conservation;
  return (
    <section className="panel conservation">
      <header className="panel-head">
        <h2>全板守恒证据</h2>
      </header>
      <div className="cons-grid">
        <div className={c.mass.holds ? "badge ok" : "badge bad"}>
          溶质量守恒：{c.mass.holds ? "成立" : "不成立"}
        </div>
        <div className={c.volume.holds ? "badge ok" : "badge bad"}>
          总体积守恒：{c.volume.holds ? "成立" : "不成立"}
        </div>
      </div>
      <table className="cons-table">
        <tbody>
          <tr>
            <th>初始总溶质</th>
            <td>{formatFraction(c.mass.initial_total_solute_mass)}</td>
            <th>最终总溶质</th>
            <td>{formatFraction(c.mass.final_total_solute_mass)}</td>
          </tr>
          <tr>
            <th>初始总体积</th>
            <td>{c.volume.initial_total_volume_ul} μL</td>
            <th>最终总体积</th>
            <td>{c.volume.final_total_volume_ul} μL</td>
          </tr>
        </tbody>
      </table>
      <details>
        <summary>每步后全板溶质量（{c.mass.total_solute_mass_after_each_step.length} 个点，含初态）</summary>
        <ol className="mass-log">
          {c.mass.total_solute_mass_after_each_step.map((f, i) => (
            <li key={i}>
              {i === 0 ? "初态" : `第 ${i} 步后`}：{formatFraction(f)}
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

export function ConflictPanel({ err }: { err: ConflictError["error"] }) {
  return (
    <section className="panel conflict" role="alert">
      <h2>第 {err.step} 步失败：{err.code === "EMPTY_SOURCE" ? "来源孔为空" : "余额不足"}</h2>
      <p>
        {err.from} <span className="arrow">→</span> {err.to}，请求取出{" "}
        <b>{err.requested_ul} μL</b>，来源实际仅有 <b>{err.available_ul} μL</b>。
      </p>
      <p className="dim">{err.message}</p>
      <p className="dim">计算在该步中止，未生成任何后续步骤或最终结论。</p>
    </section>
  );
}

export function ValidationPanel({ errors }: { errors: ValidationError["errors"] }) {
  return (
    <section className="panel invalid" role="alert">
      <h2>请求不合法（{errors.length} 项）</h2>
      <ul className="error-list">
        {errors.map((e, i) => (
          <li key={i}>
            <code>{e.loc.join(" → ") || "(请求体)"}</code>：{e.message}
            {e.hint ? <span className="dim">（{e.hint}）</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ResultPanels({ result }: { result: ReviewOk }) {
  return (
    <div className="results">
      <ConservationBar result={result} />
      <StepTrace result={result} />
      <FinalGrid result={result} />
    </div>
  );
}
