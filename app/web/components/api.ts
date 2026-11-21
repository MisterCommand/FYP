import { useQuery } from "@tanstack/react-query";

export type Snapshot = { outcome: string; market_probability: number; date: string };
export type Event = { id: string; title: string; meeting_date: string; meeting_month: string; status: string; realized_outcome: string | null; latest_snapshot: Snapshot[]; total_volume: number; volume_note: string };
export type Detail = Event & { history: Record<string, { date: string; market_probability: number }[]>; evidence: string; evidence_rule: string; wallet_informed: { available: boolean; reason: string } };
export type Metrics = { mse: number; qlike: number; n: number; floor_hits: number; latest_floor_hit: boolean; latest_variance: number; latest_volatility: number };
export type Forecast = { asset: string; horizon: number; as_of: string; models: Record<string, Metrics>; floor_policy: string; forecast_floor: number; series: { date: string; realized: number; baseline: number; augmented: number }[]; notes: string };
export type Holding = { asset: string; weight: number };
export type AnalysisRequest = { event_id?: string; outcome?: string; as_of?: string; horizon: number; holdings: Holding[]; notional: number; overrides?: { mu_yes?: number; mu_no?: number } };
export type Run = { id: string; created_at: string; request: AnalysisRequest; data_version: string; seed: number; results: { probability: number; probability_date: string; as_of: string; sample_counts: Record<string, number>; conditional_spy: Record<string, { mean: number; variance: number; effective_n: number; status?: string }>; mu_mix: number; sigma2_mix: number; horizon_volatility: number; var_95_pct: number; es_95_pct: number; var_95_usd: number; es_95_usd: number; scenario_returns: number[]; assumptions: string[]; evidence: string; method: string; residual_pool_n?: number } };
export type Answer = { mode: string; answer: string; citations: string[] };
export type FieldError = { loc: (string | number)[]; msg: string };

export class APIError extends Error {
  fields: FieldError[];
  constructor(detail: string | FieldError[]) {
    super(typeof detail === "string" ? detail : detail.map(e => e.msg).join("; "));
    this.fields = typeof detail === "string" ? [] : detail;
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
    throw new APIError(data.detail || "Request failed. Please try again.");
  }
  return response.json();
}

export function useEvents() { return useQuery({ queryKey: ["events"], queryFn: () => api<Event[]>("/events") }); }
export function useEvent(id: string) { return useQuery({ queryKey: ["event", id], queryFn: () => api<Detail>(`/events/${id}`), enabled: !!id }); }
export function defaultEvent(events: Event[]) { const observed = events.filter(e => e.latest_snapshot.length); return observed.find(e => e.status === "upcoming") || observed.at(-1); }
export function defaultOutcome(event?: Event) { const snapshots = event?.latest_snapshot || []; const changes = snapshots.filter(s => s.outcome !== "No change"); return [...(changes.length ? changes : snapshots)].sort((a, b) => b.market_probability - a.market_probability)[0]?.outcome || "No change"; }
export const pct = (value: number, digits = 2) => `${(value * 100).toFixed(digits)}%`;
export const usd = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
export const dateLabel = (value: string) => new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
