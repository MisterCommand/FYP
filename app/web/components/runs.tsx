"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, Run, usd, useEvents } from "./api";
import { createdAtLabel, runEventHref, meetingName, runTitle, matchesSearch } from "./research-format";
import { DirectorySearch, NoMatches, useDirectorySearch } from "./directory-search";
import { RunActions } from "./run-actions";
import { Assistant } from "./assistant";
import { RunResults } from "./results";
import { PageHeading, State } from "./ui";

export function Runs({ initialQuery = "" }: { initialQuery?: string }) {
  const events = useEvents();
  const { query, changeQuery } = useDirectorySearch(initialQuery);
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<Run[]>("/runs") });
  const eventFor = (run: Run) => events.data?.find(event => event.id === run.request.event_id);
  const filtered = runs.data?.filter(run => matchesSearch(query, runTitle(run, eventFor(run)), meetingName(eventFor(run)), run.request.outcome));
  return <main className="page"><PageHeading eyebrow="Your research archive" title="Saved research" description="Revisit the inputs, evidence and assumptions behind every scenario."><Link className="button primary" href="/scenarios">New scenario ↗</Link></PageHeading><DirectorySearch label="Search saved research" query={query} onChange={changeQuery} />{runs.isPending ? <State loading /> : runs.error ? <State error={runs.error} /> : !runs.data.length ? <div className="empty-archive"><span className="eyebrow">No saved runs yet</span><h2>Build a record of your research.</h2><p>Every scenario is saved automatically, with its inputs, dataset version and simulation seed.</p><Link className="button" href="/scenarios">Run your first scenario ↗</Link></div> : !filtered?.length ? <NoMatches clear={() => changeQuery("")} /> : <div className="table-scroll bordered"><table><thead><tr><th>Research run</th><th>Event / YES outcome</th><th>Allocation</th><th>95% VaR</th><th>95% ES</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{filtered.map(run => <tr key={run.id}><td><Link className="table-title" href={`/runs/${run.id}`}>{runTitle(run, eventFor(run))}</Link><small className="muted">{createdAtLabel(run.created_at)} · {run.request.horizon}D</small></td><td><Link href={runEventHref(run)}>{meetingName(eventFor(run))}</Link><small className="muted">{run.request.outcome}</small></td><td>{usd(run.request.notional)}<small className="muted">{run.request.holdings.map(h => `${h.asset} ${(h.weight * 100).toFixed(1)}%`).join(" / ")}</small></td><td>{run.results.var_95_pct.toFixed(2)}%<small className="muted">{usd(run.results.var_95_usd)}</small></td><td>{run.results.es_95_pct.toFixed(2)}%<small className="muted">{usd(run.results.es_95_usd)}</small></td><td><Link className="arrow-link" href={`/runs/${run.id}`} aria-label={`Open ${runTitle(run, eventFor(run))}`}>↗</Link><RunActions run={run} title={runTitle(run, eventFor(run))} /></td></tr>)}</tbody></table></div>}</main>;
}

export function RunDetail({ id }: { id: string }) {
  const events = useEvents();
  const run = useQuery({ queryKey: ["run", id], queryFn: () => api<Run>(`/runs/${id}`) });
  if (run.isPending || run.error) return <main className="page"><Link className="back-link" href="/runs">← Saved research</Link><State loading={run.isPending} error={run.error} /></main>;
  const r = run.data;
  const event = events.data?.find(event => event.id === r.request.event_id);
  const title = runTitle(r, event);
  return <main className="page"><Link className="back-link" href="/runs">← Saved research</Link><PageHeading eyebrow="Saved research" title={title} description={`Created ${createdAtLabel(r.created_at)} · ${usd(r.request.notional)} paper portfolio`} /><div className="info-strip"><span>{r.request.holdings.map(h => `${h.asset} ${(h.weight * 100).toFixed(1)}%`).join(" / ")}</span><Link href={runEventHref(r)}>Inspect {meetingName(event)} ↗</Link></div><RunActions run={r} title={title} detail /><div className="saved-layout"><RunResults run={r} /><Assistant key={r.id} eventId={r.request.event_id} runId={r.id} /></div></main>;
}
