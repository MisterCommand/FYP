import Link from "next/link";
import { APIError } from "./api";

export function State({ error, loading, empty, onRetry }: { error?: Error | null; loading?: boolean; empty?: string; onRetry?: () => void }) {
  return <div className={`state ${error ? "error" : ""}`} role={error ? "alert" : "status"}>{error ? <><strong>Could not load research</strong><p>{error instanceof APIError ? error.message : "Research is temporarily unavailable. Please try again."}</p>{onRetry && (!(error instanceof APIError) || ![401, 403, 404].includes(error.status)) && <button type="button" className="button state-retry" onClick={onRetry}>Try again</button>}</> : loading ? <><span className="loading-dot" /> Loading research data…</> : empty}</div>;
}

export function Horizon({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return <div className="horizon" aria-label="Forecast horizon">{[1, 5, 20].map(n => <button type="button" key={n} aria-pressed={n === value} onClick={() => onChange(n)}>{n}D</button>)}<span>trading days</span></div>;
}

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="muted">{description}</p></div>{children}</div>;
}

export function Citation({ value }: { value: string }) {
  if (value.startsWith("run:")) return <Link href={`/runs/${value.slice(4)}`}>Run {value.slice(4, 12)} ↗</Link>;
  if (value.startsWith("event:")) return <Link href={`/events/${value.slice(6)}`}>Event {value.slice(6)} ↗</Link>;
  return <span>{value}</span>;
}
