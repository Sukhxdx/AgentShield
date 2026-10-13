import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";
import type { Decision } from "@/lib/types";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide",
  {
    variants: {
      tone: {
        neutral: "border-line bg-panel text-ink",
        approve: "border-approve/30 bg-approve/10 text-approve",
        hold: "border-hold/30 bg-hold/10 text-hold",
        block: "border-block/30 bg-block/10 text-block",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export function decisionTone(decision: Decision | string | undefined) {
  if (decision === "APPROVE") return "approve" as const;
  if (decision === "HUMAN_APPROVAL") return "hold" as const;
  if (decision === "BLOCK") return "block" as const;
  return "neutral" as const;
}

export function decisionLabel(decision: Decision | string | undefined) {
  if (decision === "HUMAN_APPROVAL") return "Human approval";
  if (decision === "APPROVE") return "Approve";
  if (decision === "BLOCK") return "Block";
  return "Pending";
}
