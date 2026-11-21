import assert from "node:assert/strict";
import { test } from "node:test";
import { api, APIError } from "./api.ts";

test("API helper preserves request methods, JSON bodies and empty deletes", async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, ...options });
    return options.method === "DELETE"
      ? new Response(null, { status: 204 })
      : Response.json({ id: "run", title: "Renamed" });
  };
  assert.equal((await api("/runs")).id, "run");
  await api("/analyses", { horizon: 20 });
  assert.equal((await api("/analyses/run", { title: "Renamed" }, "PATCH")).title, "Renamed");
  assert.equal(await api("/analyses/run", undefined, "DELETE"), undefined);
  assert.deepEqual(requests.map(r => [r.url, r.method]), [
    ["/api/runs", "GET"], ["/api/analyses", "POST"],
    ["/api/analyses/run", "PATCH"], ["/api/analyses/run", "DELETE"],
  ]);
  assert.equal(requests[2].headers["Content-Type"], "application/json");
  assert.equal(requests[2].body, JSON.stringify({ title: "Renamed" }));
  assert.equal(requests[3].body, undefined);
});

test("API helper preserves field and form validation reasons", async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  const fields = [{ loc: ["body", "holdings", 0, "weight"], msg: "Weight must be nonnegative" }];
  for (const detail of [fields, "holdings weights must sum to 1"]) {
    globalThis.fetch = async () => Response.json({ detail }, { status: 422 });
    await assert.rejects(api("/analyses", {}), error => {
      assert.ok(error instanceof APIError);
      assert.equal(error.status, 422);
      assert.deepEqual(error.fields, Array.isArray(detail) ? fields : []);
      assert.equal(error.message, Array.isArray(detail) ? fields[0].msg : detail);
      return true;
    });
  }
});

test("API helper hides server details and malformed response bodies", async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  for (const status of [401, 403, 404, 500]) {
    globalThis.fetch = async () => Response.json({ detail: "/private/server/path" }, { status });
    await assert.rejects(api("/runs"), error => error instanceof APIError && error.status === status && !error.message.includes("/private"));
  }
  globalThis.fetch = async () => new Response("not JSON");
  await assert.rejects(api("/runs"), error => error instanceof APIError && error.status === 502);
});

test("API helper reports network failures without leaking their details", async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => { throw new Error("private network detail"); };
  await assert.rejects(api("/runs"), error => error instanceof APIError && error.status === 0 && !error.message.includes("private"));
});
