import type { TransferInput } from "../types";

interface Props {
  transfers: TransferInput[];
  wellIds: string[];
  onPatch: (index: number, patch: Partial<TransferInput>) => void;
  onRemove: (index: number) => void;
  onMove: (index: number, delta: -1 | 1) => void;
}

/** 有序转移步骤表：顺序即执行顺序，可上下移动与删除。 */
export function StepTable({ transfers, wellIds, onPatch, onRemove, onMove }: Props) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>转移步骤（{transfers.length}/200，按顺序执行）</h2>
        <span className="hint">完全混匀模型；从空孔或余额不足取液将在该步中止（409）</span>
      </header>
      <div className="step-scroll">
        <table className="step-table">
          <thead>
            <tr>
              <th style={{ width: 44 }}>#</th>
              <th>from</th>
              <th>to</th>
              <th>取液量 (μL)</th>
              <th style={{ width: 88 }}>排序</th>
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {transfers.map((t, i) => {
              const sameEnd = t.from === t.to && t.from !== "";
              const unknown =
                !wellIds.includes(t.from) || !wellIds.includes(t.to);
              const badAmount = !Number.isInteger(t.amount_ul) || t.amount_ul < 1;
              return (
                <tr key={i} className={sameEnd || unknown || badAmount ? "row-warn" : undefined}>
                  <td className="step-no">{i + 1}</td>
                  <td>
                    <input
                      aria-label={`第 ${i + 1} 步 from`}
                      list="well-id-list"
                      value={t.from}
                      onChange={(e) => onPatch(i, { from: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`第 ${i + 1} 步 to`}
                      list="well-id-list"
                      value={t.to}
                      onChange={(e) => onPatch(i, { to: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`第 ${i + 1} 步取液量`}
                      type="number"
                      min={1}
                      step={1}
                      className={badAmount ? "invalid" : ""}
                      value={t.amount_ul}
                      onChange={(e) => onPatch(i, { amount_ul: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <button type="button" className="mini" disabled={i === 0}
                      onClick={() => onMove(i, -1)} title="上移">▲</button>
                    <button type="button" className="mini" disabled={i === transfers.length - 1}
                      onClick={() => onMove(i, 1)} title="下移">▼</button>
                  </td>
                  <td>
                    <button type="button" className="mini danger"
                      onClick={() => onRemove(i)} title="删除">×</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <datalist id="well-id-list">
          {wellIds.map((id) => <option key={id} value={id} />)}
        </datalist>
      </div>
    </section>
  );
}
