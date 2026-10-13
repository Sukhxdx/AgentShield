"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, type ReactNode } from "react";

const LINKS = [
  { href: "/", label: "Playground" },
  { href: "/approvals", label: "Queue" },
  { href: "/audit", label: "Audit" },
  { href: "/evaluation", label: "Evaluation" },
];

function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto" aria-label="Primary">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 text-sm font-semibold ${
              active ? "bg-ink text-paper" : "text-ink hover:bg-line/70"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-panel/90">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-serif text-2xl tracking-tight text-ink">AgentShield</p>
            <p className="text-sm text-muted">Governance for tool-using agents. The model does not grade its own homework.</p>
          </div>
          <Suspense fallback={<div className="h-9 w-64 rounded-full bg-line/60" />}>
            <Nav />
          </Suspense>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
