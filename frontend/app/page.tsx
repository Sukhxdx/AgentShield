"use client";

import { useState } from "react";

import { Gauge } from "@/components/gauge";
import { Badge, decisionLabel, decisionTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AgentResponse, Decision } from "@/lib/types";

const ROLES = ["guest", "employee", "manager", "admin", "service"] as const;

const PRESETS = [
  {
    label: "Delete confidential database",
    request: "Delete the confidential employee database.",
    role: "employee",
    note: "Reference case. The rule engine scores this delete at 69.",
  },
  {
    label: "Public handbook",
    request: "Read the public handbook.",
    role: "employee",
    note: "A public guideline read should be approved.",
  },
  {
    label: "Guest opens payroll data",
    request: "Open the confidential employee database.",
    role: "guest",
    note: "The role is not allowed to touch confidential files.",
  },
  {
    label: "Email a vendor",
    request: "Email the vendor our launch timeline.",
    role: "employee",
    note: "External mail to an approved partner waits for a person.",
  },
  {
    label: "Pay 25,000 USD",
    request: "Pay the offshore consultant 25000 USD.",
    role: "employee",
    note: "Employees have no payment authority.",
  },
  {
    label: "Poisoned memo",
    request: "Summarize the memo at docs/poisoned_memo.md",
    role: "employee",
    note: "The document itself contains an indirect injection.",
  },
];

const STEPS = [
  "Request",
  "LLM proposal",
  "Prompt analysis",
  "Policy",
  "Rule risk",
  "ML risk",
  "Combined",
  "Decision",
];

export default function PlaygroundPage() {
  const [request, setRequest] = useState(PRESETS[0].request);
  const [role, setRole] = useState<(typeof ROLES)[number]>("employee");
  const [userId, setUserId] = useState("demo.employee");
  const [note, setNote] = useState(PRESETS[0].note);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AgentResponse | null>(null);

  async function run(nextRequest = request, nextRole = role) {
    setLoading(true);
    setError("");
    try {
      const body = await api<AgentResponse>("/agent", {
        method: "POST",
        body: JSON.stringify({ request: nextRequest, user_role: nextRole, user_id: userId }),
      });
      setResult(body);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "The agent request failed.");
    } finally {
      setLoading(false);
    }
  }

  const governance = result?.governance_result;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <Card>
        <p className="text-xs font-semibold tracking-[0.16em] text-copper uppercase">Playground</p>
        <h1 className="mt-2 font-serif text-3xl tracking-tight">Ask the agent. Watch the shield.</h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          The language model proposes one simulated tool. AgentShield scores the call and only an
          approve decision can run it.
        </p>
        <label className="mt-5 block text-sm font-semibold" htmlFor="request">
          Request
        </label>
        <textarea
          id="request"
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          rows={5}
          className="mt-2 w-full rounded-2xl border border-line bg-paper px-3 py-2 text-sm leading-6 focus-visible:outline-2 focus-visible:outline-copper"
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-semibold" htmlFor="role">
            Role
            <select
              id="role"
              value={role}
              onChange={(event) => setRole(event.target.value as (typeof ROLES)[number])}
              className="mt-2 block h-10 w-full rounded-full border border-line bg-paper px-3"
            >
              {ROLES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold" htmlFor="user-id">
            User id
            <input
              id="user-id"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="mt-2 block h-10 w-full rounded-full border border-line bg-paper px-3"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <Button
              key={preset.label}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setRequest(preset.request);
                setRole(preset.role as (typeof ROLES)[number]);
                setNote(preset.note);
                void run(preset.request, preset.role as (typeof ROLES)[number]);
              }}
            >
              {preset.label}
            </Button>
          ))}
        </div>
        <p className="mt-3 text-sm text-muted">{note}</p>
        <Button className="mt-4" type="button" onClick={() => void run()} disabled={loading || !request.trim()}>
          {loading ? "Running agent…" : "Run agent"}
        </Button>
        {error ? (
          <p className="mt-4 rounded-2xl border border-block/30 bg-block/10 px-3 py-2 text-sm text-block" role="alert">
            {error}
          </p>
        ) : null}
      </Card>

      <div className="space-y-4">
        <Card>
          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step} className="rounded-xl border border-line bg-paper px-2 py-2">
                <p className="text-[11px] font-semibold text-muted">{index + 1}</p>
                <p className="text-sm font-semibold">{step}</p>
                <p className="truncate text-xs text-muted">{stepValue(step, result)}</p>
              </li>
            ))}
          </ol>
        </Card>

        {!result && !loading ? (
          <Card>
            <h2 className="font-serif text-2xl">No decision yet</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              Run the confidential-database preset. The tool must not execute, and the breakdown
              should show a rule score of 69 with a block decision.
            </p>
          </Card>
        ) : null}

        {loading ? (
          <Card aria-live="polite">
            <p className="text-sm font-semibold">Scoring the proposal…</p>
          </Card>
        ) : null}

        {governance ? (
          <>
            <Card>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold tracking-[0.16em] text-muted uppercase">Decision</p>
                  <h2 className="font-serif text-3xl">{decisionLabel(governance.decision)}</h2>
                </div>
                <Badge tone={decisionTone(governance.decision)}>{governance.decision}</Badge>
              </div>
              <div className="mt-4">
                <Gauge score={governance.combined_risk} level={governance.risk_level} />
              </div>
              <p className="mt-4 text-sm leading-6">{governance.explanation}</p>
              <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                <Stat label="Rule" value={String(governance.rule_risk.score)} />
                <Stat label="ML" value={governance.ml_risk.toFixed(2)} />
                <Stat label="Combined" value={String(governance.combined_risk)} />
              </dl>
            </Card>
            <Card>
              <h2 className="font-serif text-xl">Score breakdown</h2>
              <ul className="mt-3 space-y-2">
                {Object.entries(governance.rule_risk.breakdown).map(([factor, points]) => (
                  <li key={factor}>
                    <div className="flex justify-between text-sm">
                      <span>{factor.replaceAll("_", " ")}</span>
                      <span className="tabular-nums">{points}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-line">
                      <div
                        className="h-1.5 rounded-full bg-copper"
                        style={{ width: `${Math.min(100, Math.max(0, points))}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">
                Parts sum to {governance.rule_risk.score}. Policy can only make this stricter.
                {governance.ml_fallback ? " The ML model was missing, so the rule score was reused." : ""}
              </p>
            </Card>
            <Card>
              <h2 className="font-serif text-xl">What happened</h2>
              <p className="mt-2 text-sm leading-6">{result?.message}</p>
              <p className="mt-3 text-sm">
                Proposed tool: <strong>{result?.proposed_action.tool}</strong>
              </p>
              <pre className="mt-2 overflow-x-auto rounded-xl bg-paper p-3 text-xs">
                {JSON.stringify(result?.proposed_action.arguments, null, 2)}
              </pre>
              {result?.tool_result ? (
                <p className="mt-3 text-sm text-approve">Simulated tool result returned. The call was approved.</p>
              ) : (
                <p className="mt-3 text-sm text-muted">No tool result. The sandbox was not changed by this call.</p>
              )}
              {result?.alternative ? (
                <p className="mt-2 text-sm text-muted">
                  A safer alternative ({result.alternative.proposal.tool}) was assessed as{" "}
                  {result.alternative.governance_result.decision} and was not executed.
                </p>
              ) : null}
            </Card>
          </>
        ) : null}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-paper px-2 py-2">
      <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className="font-serif text-xl tabular-nums">{value}</dd>
    </div>
  );
}

function stepValue(step: string, result: AgentResponse | null) {
  if (!result) return "—";
  const governance = result.governance_result;
  const values: Record<string, string> = {
    Request: "received",
    "LLM proposal": result.proposed_action.tool,
    "Prompt analysis": governance.prompt_analysis.attack_type,
    Policy: governance.policy_result.authorized ? "allowed" : "denied",
    "Rule risk": String(governance.rule_risk.score),
    "ML risk": governance.ml_risk.toFixed(1),
    Combined: String(governance.combined_risk),
    Decision: result.decision as Decision,
  };
  return values[step] ?? "—";
}
