"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge, decisionTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";

export default function AuditPage() {
  const [decision, setDecision] = useState("");
  const [tool, setTool] = useState("");
  const [role, setRole] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (decision) params.set("decision", decision);
    if (tool) params.set("tool", tool);
    if (role) params.set("role", role);
    try {
      const body = await api<{ events: AuditEvent[] }>(`/audit?${params.toString()}`);
      setEvents(body.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the audit log.");
    } finally {
      setLoading(false);
    }
  }, [decision, role, tool]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-copper uppercase">Audit</p>
        <h1 className="font-serif text-4xl tracking-tight">Append-only trail</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          Every score, decision, and masked argument is inserted. Rows are not rewritten.
        </p>
      </div>
      <Card>
        <form
          className="grid gap-3 sm:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            void load();
          }}
        >
          <Filter label="Decision" value={decision} onChange={setDecision} options={["", "APPROVE", "HUMAN_APPROVAL", "BLOCK"]} />
          <Filter
            label="Tool"
            value={tool}
            onChange={setTool}
            options={["", "read_file", "search_documents", "send_email", "update_record", "delete_file", "make_payment", "none"]}
          />
          <Filter label="Role" value={role} onChange={setRole} options={["", "guest", "employee", "manager", "admin", "service"]} />
          <div className="flex items-end">
            <Button type="submit">Apply filters</Button>
          </div>
        </form>
      </Card>
      {error ? (
        <p className="rounded-2xl border border-block/30 bg-block/10 px-3 py-2 text-sm text-block" role="alert">
          {error}
        </p>
      ) : null}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Governance audit events</caption>
          <thead className="border-b border-line text-xs tracking-wide text-muted uppercase">
            <tr>
              <th className="px-4 py-3 font-semibold">Time</th>
              <th className="px-4 py-3 font-semibold">Role</th>
              <th className="px-4 py-3 font-semibold">Tool</th>
              <th className="px-4 py-3 font-semibold">Risk</th>
              <th className="px-4 py-3 font-semibold">Decision</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-4 py-6 text-muted" colSpan={5}>
                  Loading audit events…
                </td>
              </tr>
            ) : null}
            {!loading && events.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-muted" colSpan={5}>
                  No events match these filters. Run a playground request and they will show up here.
                </td>
              </tr>
            ) : null}
            {events.map((event) => (
              <tr key={event.id} className="border-b border-line last:border-0">
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="text-left underline decoration-line underline-offset-4"
                    onClick={() => setSelected(event)}
                  >
                    {event.timestamp.slice(0, 19).replace("T", " ")}
                  </button>
                </td>
                <td className="px-4 py-3">{event.user_role}</td>
                <td className="px-4 py-3">{event.tool}</td>
                <td className="px-4 py-3 tabular-nums">{event.combined_risk}</td>
                <td className="px-4 py-3">
                  <Badge tone={decisionTone(event.decision)}>{event.decision}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {selected ? (
        <Card>
          <div className="flex items-start justify-between gap-3">
            <h2 className="font-serif text-2xl">Event detail</h2>
            <Button type="button" variant="ghost" size="sm" onClick={() => setSelected(null)}>
              Close
            </Button>
          </div>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <Detail label="Rule" value={String(selected.rule_risk)} />
            <Detail label="ML" value={Number(selected.ml_risk).toFixed(2)} />
            <Detail label="Combined" value={String(selected.combined_risk)} />
            <Detail label="Injection" value={String(selected.injection_score)} />
            <Detail label="Sensitive info" value={String(selected.sensitive_info_score)} />
            <Detail label="Attack" value={selected.attack_type} />
          </dl>
          <p className="mt-4 text-sm leading-6">{selected.explanation}</p>
          <p className="mt-3 text-xs text-muted">Arguments are stored masked.</p>
          <pre className="mt-2 overflow-x-auto rounded-xl bg-paper p-3 text-xs">{selected.arguments_json}</pre>
        </Card>
      ) : null}
    </div>
  );
}

function Filter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  const id = label.toLowerCase();
  return (
    <label className="text-sm font-semibold" htmlFor={id}>
      {label}
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 block h-10 w-full rounded-full border border-line bg-paper px-3"
      >
        {options.map((option) => (
          <option key={option || "any"} value={option}>
            {option || "Any"}
          </option>
        ))}
      </select>
    </label>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-paper px-3 py-2">
      <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className="text-sm font-semibold">{value}</dd>
    </div>
  );
}
