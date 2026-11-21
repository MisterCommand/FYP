import { useQuery } from "@tanstack/react-query";

export type Snapshot = { outcome: string; market_probability: number; date: string };
export type Event = { id: string; title: string; meeting_date: string; meeting_month: string; status: string; realized_outcome: string | null; latest_snapshot: Snapshot[]; total_volume: number; volume_note: string };
export type WalletEstimate = { available: false; reason: string } | { available: true; method: string; signal_timestamp: string; coverage_complete: boolean; outcomes: { outcome: string; market_id: string; wallet_probability: number; signal_timestamp: string; active_wallets: number; coverage_complete: boolean; complete_wallets: number; cluster_members: number }[] };
export type Detail = Event & { history: Record<string, { date: string; market_probability: number }[]>; evidence: string; evidence_rule: string; wallet_informed: WalletEstimate };
export type Metrics = { mse: number; qlike: number; n: number; floor_hits: number; latest_floor_hit: boolean; latest_variance: number; latest_volatility: number };
export type Forecast = { asset: string; horizon: number; as_of: string; models: Record<string, Metrics>; floor_policy: string; forecast_floor: number; series: { date: string; realized: number; baseline: number; augmented: number }[]; notes: string };
export type Holding = { asset: string; weight: number };
export type AnalysisRequest = { event_id?: string; outcome?: string; as_of?: string; horizon: number; holdings: Holding[]; notional: number; overrides?: { mu_yes?: number; mu_no?: number } };
export type Run = { id: string; title?: string | null; created_at: string; request: AnalysisRequest; data_version: string; seed: number; results: { probability: number; probability_date: string; as_of: string; sample_counts: Record<string, number>; conditional_spy: Record<string, { mean: number; variance: number; effective_n: number; status?: string }>; mu_mix: number; sigma2_mix: number; horizon_volatility: number; var_95_pct: number; es_95_pct: number; var_95_usd: number; es_95_usd: number; scenario_returns: number[]; assumptions: string[]; evidence: string; method: string; residual_pool_n?: number } };
export type Answer = { mode: string; answer: string; citations: string[] };
export type FieldError = { loc: (string | number)[]; msg: string };

export class APIError extends Error {
  fields: FieldError[];
  status: number;
  constructor(status: number, fields: FieldError[] = [], validationMessage?: string) {
    super(status === 404 ? "This research could not be found. It may no longer be available." : status === 422 ? validationMessage || fields.map(e => e.msg).join("; ") || "Some research inputs could not be used. Check your selections and values." : status === 0 ? "We couldn’t connect. Check your connection and try again." : status === 401 || status === 403 ? "You don’t have access to this research." : "Research is temporarily unavailable. Please try again.");
    this.status = status;
    this.fields = fields;
  }
}

export async function api<T>(path: string, body?: unknown, method = body === undefined ? "GET" : "POST"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  } catch {
    throw new APIError(0);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const fields: FieldError[] = response.status === 422 && Array.isArray(data?.detail) ? data.detail.filter((e: FieldError) => Array.isArray(e?.loc) && typeof e.msg === "string").map((e: FieldError) => ({ loc: e.loc, msg: e.msg })) : [];
    throw new APIError(response.status, fields, response.status === 422 && typeof data?.detail === "string" ? data.detail : undefined);
  }
  try {
    return response.status === 204 ? undefined as T : await response.json();
  } catch {
    throw new APIError(502);
  }
}

export function useEvents() { return useQuery({ queryKey: ["events"], queryFn: () => api<Event[]>("/events") }); }
export function useEvent(id: string, asOf?: string) { return useQuery({ queryKey: ["event", id, ...(asOf ? [asOf] : [])], queryFn: () => api<Detail>(`/events/${id}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`), enabled: !!id }); }
export function defaultEvent(events: Event[]) { const observed = events.filter(e => e.latest_snapshot.length); return observed.find(e => e.status === "upcoming") || observed.at(-1); }
export function defaultOutcome(event?: Event) { const snapshots = event?.latest_snapshot || []; const changes = snapshots.filter(s => s.outcome !== "No change"); return [...(changes.length ? changes : snapshots)].sort((a, b) => b.market_probability - a.market_probability)[0]?.outcome || "No change"; }
export const pct = (value: number, digits = 2) => `${(value * 100).toFixed(digits)}%`;
export const usd = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
export const dateLabel = (value: string) => new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
