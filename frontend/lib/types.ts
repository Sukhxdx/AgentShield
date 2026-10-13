export type Decision = "APPROVE" | "HUMAN_APPROVAL" | "BLOCK";

export type Governance = {
  decision: Decision;
  combined_risk: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  rule_risk: {
    score: number;
    breakdown: Record<string, number>;
    level: string;
    notes: Record<string, string>;
  };
  ml_risk: number;
  ml_fallback: boolean;
  prompt_analysis: {
    injection_score: number;
    sensitive_info_score: number;
    flags: string[];
    matched_patterns: string[];
    attack_type: string;
  };
  policy_result: {
    authorized: boolean;
    violations: string[];
    required_approval: boolean;
    reasons: string[];
  };
  explanation: string;
  reasons: string[];
  request_id: string;
};

export type AgentResponse = {
  proposed_action: { tool: string; arguments: Record<string, unknown>; reasoning: string };
  governance_result: Governance;
  decision: Decision;
  tool_result: Record<string, unknown> | null;
  message: string;
  trace: Array<Record<string, unknown>>;
  latency_ms: number;
  alternative: {
    proposal: { tool: string; arguments: Record<string, unknown> };
    governance_result: Governance;
  } | null;
};

export type Approval = {
  id: string;
  created_at: string;
  status: string;
  user_id: string;
  user_role: string;
  user_request: string;
  tool: string;
  arguments: Record<string, unknown>;
  approver: string | null;
  reason: string | null;
  governance: Governance;
  tool_result: Record<string, unknown> | null;
};

export type AuditEvent = {
  id: number;
  request_id: string;
  timestamp: string;
  user_id: string;
  user_role: string;
  user_request: string;
  phase: string;
  tool: string;
  arguments_json: string;
  injection_score: number;
  sensitive_info_score: number;
  attack_type: string;
  policy_authorized: number;
  violations_json: string;
  rule_risk: number;
  ml_risk: number;
  ml_fallback: number;
  combined_risk: number;
  risk_level: string;
  decision: Decision;
  explanation: string;
  approver: string | null;
  tool_executed: number;
  tool_result_summary: string | null;
  latency_ms: number | null;
};

export type ComparisonReport = {
  emulator: string;
  label: string;
  upstream_toolemu_executed: boolean;
  n_cases: number;
  n_trials: number;
  latency_overhead_ms: number;
  seeds: number[];
  modes: {
    baseline: ModeMetrics;
    protected: ModeMetrics;
  };
  confusion_matrix: { labels: string[]; matrix: number[][] };
};

export type ModeMetrics = {
  unsafe_action_execution_rate: number;
  attack_success_rate: number;
  over_blocking_rate: number;
  human_approval_rate: number | null;
  decision_accuracy: number | null;
  mean_latency_ms: number;
};

export type ModelMetrics = {
  mae: number;
  rmse: number;
  r2: number;
  n_train: number;
  n_test: number;
  n_samples: number;
  cv_mae_mean: number;
  feature_importances: Array<{ feature: string; importance: number }>;
};
