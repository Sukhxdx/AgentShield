"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge, decisionLabel, decisionTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Approval } from "@/lib/types";

export default function ApprovalsPage() {
  const [approver, setApprover] = useState("ada.ops");
  const [rows, setRows] = useState<Approval[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const body = await api<{ approvals: Approval[] }>("/approvals?status=pending");
      setRows(body.approvals);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function resolve(id: string, action: "approve" | "reject") {
    setBusy(id + action);
    setError("");
    try {
      await api(`/approvals/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify({
          approver,
          reason: action === "approve" ? "Reviewed in the queue" : "Rejected in the queue",
        }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The queue update failed.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-copper uppercase">Queue</p>
        <h1 className="font-serif text-4xl tracking-tight">Human approval</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          These calls were held. Approving mints a one-time permit and runs the simulated tool.
          Rejecting leaves the sandbox untouched.
        </p>
      </div>
      <Card>
        <label className="text-sm font-semibold" htmlFor="approver">
          Approver
          <input
            id="approver"
            value={approver}
            onChange={(event) => setApprover(event.target.value)}
            className="mt-2 block h-10 w-full max-w-sm rounded-full border border-line bg-paper px-3"
          />
        </label>
      </Card>
      {error ? (
        <p className="rounded-2xl border border-block/30 bg-block/10 px-3 py-2 text-sm text-block" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <Card>Loading the queue…</Card> : null}
      {!loading && rows.length === 0 ? (
        <Card>
          <h2 className="font-serif text-2xl">Nothing is waiting</h2>
          <p className="mt-2 text-sm text-muted">
            Run “Email a vendor” from the playground. That call should land here instead of sending.
          </p>
        </Card>
      ) : null}
      {rows.map((row) => (
        <Card key={row.id}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs text-muted">{row.user_role}</p>
              <h2 className="font-serif text-2xl">{row.tool}</h2>
              <p className="mt-1 text-sm">{row.user_request}</p>
            </div>
            <Badge tone={decisionTone(row.governance.decision)}>{decisionLabel(row.governance.decision)}</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">{row.governance.explanation}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" onClick={() => void resolve(row.id, "approve")} disabled={!approver || busy !== ""}>
              {busy === row.id + "approve" ? "Approving…" : "Approve and run"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void resolve(row.id, "reject")}
              disabled={!approver || busy !== ""}
            >
              {busy === row.id + "reject" ? "Rejecting…" : "Reject"}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
