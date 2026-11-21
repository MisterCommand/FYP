import type { Run } from "./api";

export const createdAtLabel = (value: string) => new Date(value).toLocaleString("en-US", {
  year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short",
});

export function runEventHref(run: Run) {
  const asOf = run.results.as_of || run.request.as_of;
  return `/events/${run.request.event_id}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`;
}
