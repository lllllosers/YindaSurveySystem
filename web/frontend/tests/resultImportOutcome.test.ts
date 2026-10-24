import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { resolveImportError } from "../src/api/resultImportOutcome.ts";

for (const code of ["ECONNABORTED", "ETIMEDOUT", "ERR_NETWORK"]) {
  test(`${code}: query once, preserve uncertain state, never repeat POST`, async () => {
    let queries = 0;
    const result = await resolveImportError({ code }, async () => {
      queries++;
      return { status: "accepted" };
    });
    assert.equal(queries, 1);
    assert.equal(result.uncertain, true);
    assert.match(result.message, /入库结果尚未确认/);
    assert.match(result.message, code === "ERR_NETWORK" ? /网络/ : /超时/);
  });
}

test("lost response after server commit is resolved as imported", async () => {
  const result = await resolveImportError({ code: "ERR_NETWORK" }, async () => ({ status: "imported" }));
  assert.equal(result.imported, true);
  assert.equal(result.uncertain, false);
  assert.match(result.message, /已正式入库/);
});

test("failed status query cannot turn timeout into confirmed failure", async () => {
  const result = await resolveImportError({ code: "ECONNABORTED" }, async () => { throw new Error("offline"); });
  assert.equal(result.submission, null);
  assert.equal(result.uncertain, true);
});

for (const [status, text] of [[409, /冲突/], [410, /缺失/], [500, /服务器/], [403, /权限/]] as const) {
  test(`HTTP ${status} uses safe specific copy and refreshes saved state`, async () => {
    const result = await resolveImportError({ response: { status, data: "private traceback" } } as any,
      async () => ({ status: "conflict" }));
    assert.equal(result.submission?.status, "conflict");
    assert.match(result.message, text);
    assert.doesNotMatch(result.message, /traceback/);
  });
}

test("only import overrides the global ten second timeout", () => {
  const api = readFileSync(new URL("../src/api/results.ts", import.meta.url), "utf8");
  const http = readFileSync(new URL("../src/api/http.ts", import.meta.url), "utf8");
  assert.match(api, /`\/result-submissions\/\$\{submissionUid\}\/import`,\s*undefined,\s*\{ timeout: 120000 \}/);
  assert.match(http, /timeout: 10000/);
});
