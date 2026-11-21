"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, dateLabel, Run, usd } from "./api";
import { Assistant } from "./assistant";
import { RunResults } from "./results";
import { PageHeading, State } from "./ui";

export function Runs() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<Run[]>("/runs") });
  return <main className="page"><PageHeading eyebrow="Your research archive" title="Saved research" description="Revisit the inputs, evidence and assumptions behind every scenario."><Link className="button primary" href="/scenarios">New scenario ↗</Link></PageHeading>{runs.isPending ? <State loading /> : runs.error ? <State error={runs.error} /> : !runs.data.length ? <div className="empty-archive"><span className="eyebrow">No saved runs yet</span><h2>Build a record of your research.</h2><p>Every scenario is saved automatically, with its inputs, dataset version and simulation seed.</p><Link className="button" href="/scenarios">Run your first scenario ↗</Link></div> : <div className="table-scroll bordered"><table><thead><tr><th>Research run</th><th>Event / YES outcome</th><th>Allocation</th><th>95% VaR</th><th>95% ES</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{runs.data.map(run => <tr key={run.id}><td><Link className="table-title" href={`/runs/${run.id}`}>Scenario {run.id.slice(0, 8)}</Link><small className="muted">{dateLabel(run.created_at)} · {run.request.horizon}D</small></td><td><Link href={`/events/${run.request.event_id}`}>Event {run.request.event_id}</Link><small className="muted">{run.request.outcome}</small></td><td>{usd(run.request.notional)}<small className="muted">{run.request.holdings.map(h => `${h.asset} ${(h.weight * 100).toFixed(0)}%`).join(" / ")}</small></td><td>{run.results.var_95_pct.toFixed(2)}%<small className="muted">{usd(run.results.var_95_usd)}</small></td><td>{run.results.es_95_pct.toFixed(2)}%<small className="muted">{usd(run.results.es_95_usd)}</small></td><td><Link className="arrow-link" href={`/runs/${run.id}`} aria-label={`Open run ${run.id.slice(0, 8)}`}>↗</Link></td></tr>)}</tbody></table></div>}</main>;
}

export function RunDetail({ id }: { id: string }) {
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api<Run>(`/runs/${id}`) });
  if (run.isPending || run.error) return <main className="page"><Link className="back-link" href="/runs">← Saved research</Link><State loading={run.isPending} error={run.error} /></main>;
  const r = run.data;
  return <main className="page"><Link className="back-link" href="/runs">← Saved research</Link><PageHeading eyebrow="Saved research" title={`Scenario ${r.id.slice(0, 8)}`} description={`Created ${new Date(r.created_at).toLocaleString()} · ${usd(r.request.notional)} paper portfolio`} /><div className="info-strip"><span>{r.request.holdings.map(h => `${h.asset} ${(h.weight * 100).toFixed(1)}%`).join(" / ")}</span><Link href={`/events/${r.request.event_id}`}>Inspect event {r.request.event_id} ↗</Link></div><div className="saved-layout"><RunResults run={r} /><Assistant key={r.id} eventId={r.request.event_id} runId={r.id} /></div></main>;
}
