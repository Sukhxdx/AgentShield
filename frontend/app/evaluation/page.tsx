"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ComparisonReport, ModelMetrics } from "@/lib/types";

type Payload = {
  available: boolean;
  label: string;
  comparison: ComparisonReport | null;
  model_metrics: ModelMetrics | null;
};

const BARS = [
  { key: "unsafe_action_execution_rate", label: "Unsafe execution" },
  { key: "attack_success_rate", label: "Attack success" },
  { key: "over_blocking_rate", label: "Over-blocking" },
] as const;

export default function EvaluationPage() {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api<Payload>("/evaluation/latest")
        .then(setPayload)
        .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load evaluation."));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const comparison = payload?.comparison;
  const metrics = payload?.model_metrics;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-copper uppercase">Evaluation</p>
        <h1 className="font-serif text-4xl tracking-tight">With and without the shield</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          {payload?.label ??
            "Same scripted proposals. Baseline runs the emulator immediately. Protected mode runs it only after approve."}
        </p>
      </div>
      {error ? (
        <p className="rounded-2xl border border-block/30 bg-block/10 px-3 py-2 text-sm text-block" role="alert">
          {error}
        </p>
      ) : null}
      {!payload && !error ? <Card>Loading the latest report…</Card> : null}
      {payload && !comparison ? (
        <Card>
          <h2 className="font-serif text-2xl">No comparison yet</h2>
          <p className="mt-2 text-sm text-muted">Run make eval from the repo root to write results/comparison.json.</p>
        </Card>
      ) : null}
      {comparison ? (
        <Card>
          <h2 className="font-serif text-2xl">Rates across {comparison.n_cases} cases</h2>
          <p className="mt-1 text-xs text-muted">
            ToolEmu-style local emulator. Upstream ToolEmu was not executed. {comparison.n_trials} trials
            across seeds {comparison.seeds.join(", ")}. Governance overhead {comparison.latency_overhead_ms.toFixed(1)} ms.
          </p>
          <div className="mt-5 space-y-4">
            {BARS.map((bar) => (
              <div key={bar.key}>
                <p className="text-sm font-semibold">{bar.label}</p>
                <Bar label="Baseline" value={comparison.modes.baseline[bar.key]} tone="block" />
                <Bar label="Protected" value={comparison.modes.protected[bar.key]} tone="approve" />
              </div>
            ))}
          </div>
          <dl className="mt-5 grid gap-3 sm:grid-cols-3">
            <Metric label="Decision accuracy" value={percent(comparison.modes.protected.decision_accuracy)} />
            <Metric label="Human approval rate" value={percent(comparison.modes.protected.human_approval_rate)} />
            <Metric label="Protected unsafe rate" value={percent(comparison.modes.protected.unsafe_action_execution_rate)} />
          </dl>
          <h3 className="mt-6 font-serif text-xl">Confusion matrix</h3>
          <p className="text-xs text-muted">
            Rows are expected decisions. Columns are actual decisions. Counts cover every trial.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-2" />
                  {comparison.confusion_matrix.labels.map((label) => (
                    <th key={label} className="px-3 py-2 text-left font-semibold">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.confusion_matrix.matrix.map((row, rowIndex) => (
                  <tr key={comparison.confusion_matrix.labels[rowIndex]}>
                    <th className="px-3 py-2 text-left font-semibold">{comparison.confusion_matrix.labels[rowIndex]}</th>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-3 py-2 tabular-nums">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
      {metrics ? (
        <Card>
          <h2 className="font-serif text-2xl">Risk model</h2>
          <p className="mt-1 text-sm text-muted">
            Random forest on {metrics.n_samples} synthetic scenarios, {metrics.n_train} train / {metrics.n_test} test.
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <Metric label="MAE" value={metrics.mae.toFixed(2)} />
            <Metric label="RMSE" value={metrics.rmse.toFixed(2)} />
            <Metric label="R²" value={metrics.r2.toFixed(4)} />
          </dl>
          <p className="mt-2 text-xs text-muted">5-fold CV MAE {metrics.cv_mae_mean.toFixed(2)} on the training split.</p>
          <h3 className="mt-5 font-serif text-xl">Feature importances</h3>
          <ul className="mt-3 space-y-2">
            {metrics.feature_importances.slice(0, 8).map((item) => (
              <li key={item.feature}>
                <div className="flex justify-between gap-3 text-xs">
                  <span className="truncate">{item.feature}</span>
                  <span className="tabular-nums">{item.importance.toFixed(3)}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-line">
                  <div className="h-1.5 rounded-full bg-ink" style={{ width: `${Math.min(100, item.importance * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function Bar({ label, value, tone }: { label: string; value: number; tone: "block" | "approve" }) {
  return (
    <div className="mt-1 grid grid-cols-[88px_1fr_48px] items-center gap-2 text-xs">
      <span>{label}</span>
      <div className="h-2 rounded-full bg-line">
        <div
          className={`h-2 rounded-full ${tone === "block" ? "bg-block" : "bg-approve"}`}
          style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
        />
      </div>
      <span className="tabular-nums">{percent(value)}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-paper px-3 py-3">
      <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className="font-serif text-2xl tabular-nums">{value}</dd>
    </div>
  );
}

function percent(value: number | null) {
  if (value === null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}
