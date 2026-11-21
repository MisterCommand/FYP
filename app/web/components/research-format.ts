import type { Event, Run } from "./api";

export const createdAtLabel = (value: string) => new Date(value).toLocaleString("en-US", {
  year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short",
});

export function runEventHref(run: Run) {
  const asOf = run.results.as_of || run.request.as_of;
  return `/events/${run.request.event_id}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
}

export function meetingName(event?: Event) {
  if (!event) return "FOMC meeting";
  const month = new Date(`${event.meeting_month}-01T12:00:00`).toLocaleDateString("en-US", { month: "long", year: "numeric" });
  return `FOMC · ${month}`;
}

export function runTitle(run: Run, event?: Event) {
  return run.title || `${meetingName(event)} · ${run.request.outcome || "Selected outcome"} · ${run.request.horizon}D`;
}

export function matchesSearch(query: string, ...values: (string | null | undefined)[]) {
  const text = values.filter(Boolean).join(" ").toLowerCase();
  return query.trim().toLowerCase().split(/\s+/).every(word => text.includes(word));
}
