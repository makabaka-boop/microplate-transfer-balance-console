import type { WellInput } from "../types";

interface Props {
  wells: WellInput[];
  selected: string | null;
  onSelect: (id: string) => void;
  onChange: (index: number, patch: Partial<WellInput>) => void;
  onConcentration: (index: number, patch: Partial<WellInput["concentration"]>) => void;
  onRemove: (index: number) => void;
}

/** 孔板网格：8 列排布，每个孔位卡片可直接编辑体积与浓度分数。 */
export function WellGrid({ wells, selected, onSelect, onChange, onConcentration, onRemove }: Props) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>孔位（{wells.length}/48，至少 2）</h2>
        <span className="hint">浓度以 分子/分母 表示，分母必须为正整数</span>
      </header>
      <div className="well-grid">
        {wells.map((w, i) => (
          <article
            key={`${w.id}-${i}`}
            className={`well-card ${selected === w.id ? "selected" : ""}`}
            onClick={() => onSelect(w.id)}
          >
            <div className="well-row">
              <input
                aria-label={`孔位 ${i + 1} id`}
                className="well-id"
                value={w.id}
                onChange={(e) => onChange(i, { id: e.target.value })}
                placeholder="id"
              />
              <button
                type="button"
                className="mini danger"
                title="删除该孔位"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(i);
                }}
              >
                ×
              </button>
            </div>
            <label className="well-field">
              初始体积
              <span className="inline-input">
                <input
                  aria-label={`${w.id} 初始体积 μL`}
                  type="number"
                  min={0}
                  step={1}
                  value={w.volume_ul}
                  onChange={(e) => onChange(i, { volume_ul: Number(e.target.value) })}
                />
                μL
              </span>
            </label>
            <label className="well-field">
              浓度
              <span className="inline-input frac">
                <input
                  aria-label={`${w.id} 浓度分子`}
                  type="number"
                  min={0}
                  step={1}
                  value={w.concentration.numerator}
                  onChange={(e) => onConcentration(i, { numerator: Number(e.target.value) })}
                />
                <span className="slash">/</span>
                <input
                  aria-label={`${w.id} 浓度分母`}
                  className={w.concentration.denominator < 1 ? "invalid" : ""}
                  type="number"
                  min={1}
                  step={1}
                  value={w.concentration.denominator}
                  onChange={(e) => onConcentration(i, { denominator: Number(e.target.value) })}
                />
              </span>
            </label>
          </article>
        ))}
      </div>
    </section>
  );
}
