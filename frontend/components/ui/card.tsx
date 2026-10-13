import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn("rounded-2xl border border-line bg-panel p-5 shadow-[0_1px_0_rgba(28,25,21,0.04)]", className)}
      {...props}
    />
  );
}
