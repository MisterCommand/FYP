import assert from "node:assert/strict";
import { test } from "node:test";
import { createdAtLabel, runEventHref } from "./research-format.ts";

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
