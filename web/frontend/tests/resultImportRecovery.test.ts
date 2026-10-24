import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";
import { computed, ref } from "vue";
import { resolveImportError } from "../src/api/resultImportOutcome.ts";

// Execute the actual view handlers with controlled API and dialog responses.
// No DOM or new dependency is needed; build/type checks cover the template.
const view = readFileSync(new URL("../src/views/ResultDetailView.vue", import.meta.url), "utf8");
const setup = view.split('<script setup lang="ts">')[1]!.split("</script>")[0]!
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\r?$/gm, "");
const javascript = ts.transpileModule(setup, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText;

type Reply = string | Error | (() => Promise<string>);
function harness(reads: Reply[], posts: Reply[], confirm: () => Promise<void> = async () => {}) {
  const calls: string[] = [];
  const messages: string[] = [];
  let signalPost!: () => void;
  const postStarted = new Promise<void>(resolve => { signalPost = resolve; });
  async function reply(queue: Reply[], method: string) {
    calls.push(method);
    if (method === "POST") signalPost();
    const next = queue.shift();
    assert.notEqual(next, undefined, `Unexpected ${method}`);
    if (next instanceof Error) throw next;
    return { status: typeof next === "function" ? await next() : next, records: 10 };
  }
  const dependencies = {
    computed, ref, onMounted: () => {},
    useRoute: () => ({ params: { submissionUid: "test-submission" }, query: {} }),
    useRouter: () => ({}),
    useAuthStore: () => ({ hasPermission: () => true, isAdmin: true }),
    ElMessage: Object.fromEntries(["success", "warning", "error"].map(kind => [kind, (text: string) => messages.push(text)])),
    ElMessageBox: { confirm: async () => { calls.push("CONFIRM"); await confirm(); } },
    resolveImportError,
    getResultSubmission: () => reply(reads, "GET"),
    importResultSubmission: () => reply(posts, "POST"),
  };
  const handlers = new Function(...Object.keys(dependencies), `${javascript}
    return { importResult, retryImport, refresh, row, importUnconfirmed, workflowBusy };`)(...Object.values(dependencies));
  handlers.row.value = { status: "accepted" };
  return { ...handlers, calls, messages, postStarted };
}

function failure(code = "ECONNABORTED") {
  return Object.assign(new Error("private traceback"), { code });
}

for (const error of [failure(), failure("ERR_NETWORK"), Object.assign(new Error(), { response: { status: 500 } })]) {
  test(`lost response ${error.code ?? "500"}: imported is success without another POST`, async () => {
    const page = harness(["imported"], [error]);
    await page.importResult();
    assert.equal(page.row.value.status, "imported");
    assert.equal(page.importUnconfirmed.value, false);
    assert.deepEqual(page.calls, ["CONFIRM", "POST", "GET"]);
    assert.match(page.messages.at(-1)!, /已正式入库/);
  });
}

test("accepted after timeout stays uncertain until explicit recovery checks again and submits", async () => {
  const page = harness(["accepted", "accepted", "accepted", "imported"], [failure(), "imported"]);
  await page.importResult();
  await page.refresh();
  assert.equal(page.importUnconfirmed.value, true);
  await page.importResult(); // ordinary button remains guarded
  assert.equal(page.calls.filter((call: string) => call === "POST").length, 1);
  await page.retryImport();
  assert.deepEqual(page.calls, ["CONFIRM", "POST", "GET", "GET", "CONFIRM", "GET", "POST", "GET"]);
  assert.equal(page.importUnconfirmed.value, false);
  assert.equal(page.row.value.status, "imported");
});

test("500 with accepted also requires explicit recovery, not an automatic retry", async () => {
  const page = harness(["accepted", "accepted", "imported"], [Object.assign(new Error(), { response: { status: 500 } }), "imported"]);
  await page.importResult();
  assert.equal(page.importUnconfirmed.value, true);
  assert.equal(page.calls.filter((call: string) => call === "POST").length, 1);
  await page.retryImport();
  assert.equal(page.row.value.status, "imported");
});

test("failed initial and manual status queries preserve uncertainty without another POST", async () => {
  const page = harness([failure(), failure()], [failure()]);
  await page.importResult();
  await page.retryImport();
  assert.equal(page.importUnconfirmed.value, true);
  assert.deepEqual(page.calls, ["CONFIRM", "POST", "GET", "CONFIRM", "GET"]);
  assert.match(page.messages.at(-1)!, /尚未确认.*未再次提交/);
});

for (const status of ["imported", "conflict", "rejected"]) {
  test(`manual recovery sees ${status} and does not POST`, async () => {
    const page = harness(["accepted", status], [failure()]);
    await page.importResult();
    await page.retryImport();
    assert.equal(page.importUnconfirmed.value, false);
    assert.equal(page.row.value.status, status);
    assert.deepEqual(page.calls, ["CONFIRM", "POST", "GET", "CONFIRM", "GET"]);
  });
  test(`status refresh sees ${status} and leaves the uncertain flow`, async () => {
    const page = harness(["accepted", status], [failure()]);
    await page.importResult();
    await page.refresh();
    assert.equal(page.importUnconfirmed.value, false);
    assert.equal(page.row.value.status, status);
  });
}

test("cancelling recovery sends neither GET nor POST", async () => {
  const page = harness([], [], async () => { throw new Error("cancel"); });
  page.importUnconfirmed.value = true;
  await page.retryImport();
  assert.deepEqual(page.calls, ["CONFIRM"]);
  assert.equal(page.importUnconfirmed.value, true);
  assert.equal(page.workflowBusy.value, false);
});

test("in-flight manual recovery blocks a second click", async () => {
  let finish!: (status: string) => void;
  const pending = new Promise<string>(resolve => { finish = resolve; });
  const page = harness(["accepted", "imported"], [() => pending]);
  page.importUnconfirmed.value = true;
  const first = page.retryImport();
  // Wait on observable execution, not elapsed time.
  await page.postStarted;
  await page.retryImport();
  await page.importResult();
  assert.equal(page.calls.filter((call: string) => call === "POST").length, 1);
  finish("imported");
  await first;
  assert.equal(page.workflowBusy.value, false);
});

test("failed refresh preserves uncertainty and never sends another POST", async () => {
  const page = harness(["accepted", failure()], [failure()]);
  await page.importResult();
  await page.refresh();
  assert.equal(page.importUnconfirmed.value, true);
  assert.deepEqual(page.calls, ["CONFIRM", "POST", "GET", "GET"]);
  assert.match(page.messages.at(-1)!, /查询失败.*尚未确认/);
});
