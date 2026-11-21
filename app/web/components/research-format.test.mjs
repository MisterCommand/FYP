import assert from "node:assert/strict";
import { test } from "node:test";
import { createdAtLabel, runEventHref, meetingName, runTitle, matchesSearch } from "./research-format.ts";

test("created timestamps use local date, time and short timezone", () => {
  const previous = process.env.TZ;
  process.env.TZ = "America/Los_Angeles";
  try {
    assert.equal(createdAtLabel("2026-11-21T03:02:29+00:00"), "Nov 20, 2026, 7:02:29 PM PST");
    assert.equal(createdAtLabel("2026-06-01T03:02:29+00:00"), "May 31, 2026, 8:02:29 PM PDT");
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

test("saved event links prefer effective cutoff over requested cutoff", () => {
  assert.equal(runEventHref({ request: { event_id: "481717", as_of: "2026-05-01" }, results: { as_of: "2026-06-01" } }), "/events/481717?as_of=2026-06-01");
});

test("legacy runs fall back to requested cutoff or latest when absent", () => {
  assert.equal(runEventHref({ request: { event_id: "481717", as_of: "2026-06-01" }, results: {} }), "/events/481717?as_of=2026-06-01");
  assert.equal(runEventHref({ request: { event_id: "481717" }, results: {} }), "/events/481717");
  assert.equal(runEventHref({ request: { event_id: "481717", as_of: null }, results: { as_of: "" } }), "/events/481717");
});

test("cutoff query values are encoded", () => {
  assert.equal(runEventHref({ request: { event_id: "481717" }, results: { as_of: "bad&other=value" } }), "/events/481717?as_of=bad%26other%3Dvalue");
});

test("run names use meeting, outcome and horizon unless renamed", () => {
  const event = { meeting_month: "2026-09" };
  const run = { request: { outcome: "25 bps increase", horizon: 5 } };
  assert.equal(meetingName(event), "FOMC · September 2026");
  assert.equal(runTitle(run, event), "FOMC · September 2026 · 25 bps increase · 5D");
  assert.equal(runTitle({ ...run, title: "My research" }, event), "My research");
  assert.equal(runTitle({ ...run, title: null }, event), runTitle(run, event));
  assert.equal(meetingName(), "FOMC meeting");
});

test("search matches all words case-insensitively across fields", () => {
  assert.equal(matchesSearch("  SEPTEMBER 2026 increase ", "FOMC September 2026", "25 bps increase"), true);
  assert.equal(matchesSearch("stress test", "My stress test", null), true);
  assert.equal(matchesSearch("2025 increase", "September 2026", "25 bps increase"), false);
  assert.equal(matchesSearch("", undefined), true);
  assert.equal(matchesSearch("missing", null, undefined), false);
  assert.equal(matchesSearch("[", "FOMC September 2026"), false);
});
