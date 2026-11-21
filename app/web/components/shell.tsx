"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return <><header className="topbar"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">◒</span> EventLens</Link><nav aria-label="Main navigation">{[["/", "Overview"], ["/events", "Events"], ["/scenarios", "Scenarios"], ["/runs", "Saved research"]].map(([href, label]) => <Link key={href} href={href} aria-current={path === href || (href !== "/" && path.startsWith(href + "/")) ? "page" : undefined}>{label}</Link>)}</nav><span className="prototype"><i /> Research prototype</span></header>{children}<footer><span>Research prototype — market data from datasets/; not investment advice</span><a href="https://app.devin.ai/sessions/4451613795f84ac2b9b5d68ea0f99a27" target="_blank" rel="noreferrer">Request changes ↗</a></footer></>;
}
