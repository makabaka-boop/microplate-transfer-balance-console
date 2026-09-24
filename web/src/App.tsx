import { useMemo, useState } from "react";
import { WellGrid } from "./components/WellGrid";
import { StepTable } from "./components/StepTable";
import { ConflictPanel, ResultPanels, ValidationPanel } from "./components/Results";
import { submitReview } from "./api";
import type {
  ConflictError,
  ReviewOk,
  TransferInput,
  ValidationError,
  WellInput,
} from "./types";

type Outcome =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; result: ReviewOk }
  | { kind: "conflict"; error: ConflictError["error"] }
  | { kind: "invalid"; errors: ValidationError["errors"] }
  | { kind: "network"; message: string };

let wellSeq = 0;
function newWell(): WellInput {
  wellSeq += 1;
  return {
    id: `W${wellSeq}`,
    volume_ul: 0,
    concentration: { numerator: 0, denominator: 1 },
  };
}

export default function App() {
  const [wells, setWells] = useState<WellInput[]>(() => {
    // 预置一个能体现“逐孔稀释”问题的最小示例（2 孔 2 步）
    return [
      { id: "A", volume_ul: 100, concentration: { numerator: 3, denominator: 1 } },
      { id: "B", volume_ul: 0, concentration: { numerator: 0, denominator: 1 } },
    ];
  });
  const [transfers, setTransfers] = useState<TransferInput[]>([
    { from: "A", to: "B", amount_ul: 25 },
    { from: "B", to: "A", amount_ul: 20 },
  ]);
  const [selected, setSelected] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });

  const wellIds = useMemo(() => wells.map((w) => w.id), [wells]);

  // 编辑即清除旧结论，避免展示与输入不一致的结果
  function invalidate() {
    setOutcome((o) => (o.kind === "idle" || o.kind === "loading" ? o : { kind: "idle" }));
  }

  function patchWell(i: number, patch: Partial<WellInput>) {
    invalidate();
    setWells((ws) => ws.map((w, j) => (j === i ? { ...w, ...patch } : w)));
  }
  function patchWellConc(i: number, patch: Partial<WellInput["concentration"]>) {
    invalidate();
    setWells((ws) =>
      ws.map((w, j) =>
        j === i ? { ...w, concentration: { ...w.concentration, ...patch } } : w,
      ),
    );
  }
  function removeWell(i: number) {
    invalidate();
    setWells((ws) => ws.filter((_, j) => j !== i));
  }

  function patchStep(i: number, patch: Partial<TransferInput>) {
    invalidate();
    setTransfers((ts) => ts.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  }
  function removeStep(i: number) {
    invalidate();
    setTransfers((ts) => ts.filter((_, j) => j !== i));
  }
  function moveStep(i: number, delta: -1 | 1) {
    invalidate();
    setTransfers((ts) => {
      const j = i + delta;
      if (j < 0 || j >= ts.length) return ts;
      const next = [...ts];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  async function onSubmit() {
    setOutcome({ kind: "loading" });
    try {
      const { status, data } = await submitReview({ wells, transfers });
      if (status === 200 && data.status === "ok") {
        setOutcome({ kind: "ok", result: data as ReviewOk });
      } else if (status === 409 && data.status === "conflict") {
        setOutcome({ kind: "conflict", error: (data as ConflictError).error });
      } else if (status === 422 && data.status === "invalid_request") {
        setOutcome({ kind: "invalid", errors: (data as ValidationError).errors });
      } else {
        setOutcome({ kind: "network", message: `意外的响应：HTTP ${status}` });
      }
    } catch (e) {
      setOutcome({
        kind: "network",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const localIssues = useMemo(() => {
    const issues: string[] = [];
    if (wells.length < 2 || wells.length > 48) issues.push("孔位数量需在 2~48 之间");
    if (transfers.length < 1 || transfers.length > 200) issues.push("转移步骤需在 1~200 条之间");
    const ids = new Set<string>();
    for (const w of wells) {
      if (w.id.trim() === "") issues.push("存在空孔位 id");
      if (ids.has(w.id)) issues.push(`孔位 id 重复：${w.id}`);
      ids.add(w.id);
      if (!Number.isInteger(w.volume_ul) || w.volume_ul < 0)
        issues.push(`孔位 ${w.id} 初始体积必须是非负整数`);
      if (!Number.isInteger(w.concentration.numerator) || w.concentration.numerator < 0)
        issues.push(`孔位 ${w.id} 浓度分子必须是非负整数`);
      if (!Number.isInteger(w.concentration.denominator) || w.concentration.denominator < 1)
        issues.push(`孔位 ${w.id} 浓度分母必须是正整数`);
    }
    transfers.forEach((t, i) => {
      if (!ids.has(t.from)) issues.push(`第 ${i + 1} 步 from 未知：${t.from || "(空)"}`);
      if (!ids.has(t.to)) issues.push(`第 ${i + 1} 步 to 未知：${t.to || "(空)"}`);
      if (t.from === t.to && t.from !== "") issues.push(`第 ${i + 1} 步 from 与 to 不得相同`);
      if (!Number.isInteger(t.amount_ul) || t.amount_ul < 1)
        issues.push(`第 ${i + 1} 步取液量必须是正整数`);
    });
    return issues;
  }, [wells, transfers]);

  return (
    <div className="page">
      <header className="app-head">
        <h1>微孔板逐孔转移复核台</h1>
        <p className="subtitle">
          完全混匀模型 · 精确分数（无中途舍入）· 每步前后浓度/体积可追溯 · 全板溶质量守恒证据
        </p>
      </header>

      <div className="toolbar">
        <button type="button" className="secondary"
          onClick={() => { invalidate(); setWells((ws) => [...ws, newWell()]); }}
          disabled={wells.length >= 48}>
          + 添加孔位
        </button>
        <button type="button" className="secondary"
          onClick={() => {
            invalidate();
            const first = wells[0]?.id ?? "";
            const second = wells[1]?.id ?? first;
            setTransfers((ts) => [...ts, { from: first, to: second, amount_ul: 1 }]);
          }}
          disabled={transfers.length >= 200}>
          + 添加步骤
        </button>
        <div className="spacer" />
        {localIssues.length > 0 && (
          <span className="local-warn" title={localIssues.join("\n")}>
            本地检查：{localIssues.length} 项待修正
          </span>
        )}
        <button type="button" className="primary" onClick={onSubmit}
          disabled={localIssues.length > 0 || outcome.kind === "loading"}
          data-testid="submit-review">
          {outcome.kind === "loading" ? "计算中…" : "提交复核"}
        </button>
      </div>

      <main className="layout">
        <div className="editor-col">
          <WellGrid
            wells={wells}
            selected={selected}
            onSelect={setSelected}
            onChange={patchWell}
            onConcentration={patchWellConc}
            onRemove={removeWell}
          />
          <StepTable
            transfers={transfers}
            wellIds={wellIds}
            onPatch={patchStep}
            onRemove={removeStep}
            onMove={moveStep}
          />
        </div>

        <div className="result-col" data-testid="result-area">
          {outcome.kind === "idle" && (
            <section className="panel placeholder">
              <h2>复核结果将显示在这里</h2>
              <p>编辑孔位与有序转移步骤后点击「提交复核」。任何编辑都会清除旧结论。</p>
              <p className="dim">
                注意：后续步骤从已被稀释的孔取液时，本台按该孔<b>当前</b>浓度计算，
                而非套用初始浓度；只核对最终体积无法发现中途透支。
              </p>
            </section>
          )}
          {outcome.kind === "network" && (
            <section className="panel invalid" role="alert">
              <h2>请求失败</h2>
              <p>{outcome.message}</p>
            </section>
          )}
          {outcome.kind === "invalid" && <ValidationPanel errors={outcome.errors} />}
          {outcome.kind === "conflict" && <ConflictPanel err={outcome.error} />}
          {outcome.kind === "ok" && <ResultPanels result={outcome.result} />}
        </div>
      </main>
    </div>
  );
}
