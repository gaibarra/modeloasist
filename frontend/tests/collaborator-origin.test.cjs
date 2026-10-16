/* eslint-disable @typescript-eslint/no-require-imports -- Node CommonJS test harness */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");
const code = ts.transpileModule(fs.readFileSync(path.join(root, "src/lib/collaborator-origin.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {}, URL, process: { env: { NODE_ENV: "production" } } };
vm.runInNewContext(code, context);
const check = context.exports.isTrustedCollaboratorOrigin;
test("public HTTPS is allowed behind the internal HTTP listener", () => {
  assert.equal(check("https://asistenciamodelo.online", "http://localhost:3101"), true);
});
test("missing, opaque and foreign origins remain blocked", () => {
  for (const origin of [null, "", "null", "https://evil.example", "https://asistenciamodelo.online.evil.example",
    "http://asistenciamodelo.online", "https://asistenciamodelo.online:444", "https://asistenciamodelo.online/",
    "https://asistenciamodelo.online@evil.example", "https://evil.example, https://asistenciamodelo.online"]) {
    assert.equal(check(origin, "http://localhost:3101"), false, origin);
  }
});
test("spoofed request host does not authorize an external origin", () => {
  assert.equal(check("https://evil.example", "https://evil.example"), false);
});
test("production rejects loopback origins", () => {
  assert.equal(check("http://localhost:3002", "http://localhost:3002"), false);
});
test("development accepts only matching loopback origins", () => {
  for (const origin of ["http://localhost:3002", "http://127.0.0.1:3002", "http://[::1]:3002"]) {
    assert.equal(check(origin, origin, true), true);
  }
  assert.equal(check("http://localhost:3003", "http://localhost:3002", true), false);
  assert.equal(check("https://evil.example", "https://evil.example", true), false);
});
test("route guards mutations, requires a session and delegates authorization", async () => {
  const routeCode = ts.transpileModule(fs.readFileSync(path.join(root, "src/app/api/colaboradores/[[...path]]/route.ts"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  let fetched = 0;
  class Response {
    constructor(body, init) { this.body = body; this.status = init.status; }
    static json(body, init) { return new Response(body, init); }
  }
  const ctx = { exports: {}, AbortSignal, fetch: async () => { fetched++; return { status: 403, text: async () => "owner only" }; },
    require: (name) => name === "next/server" ? { NextResponse: Response } : name.endsWith("collaborator-origin") ? { isTrustedCollaboratorOrigin: check } : { BACKEND_API_BASE_URL: "http://backend", SESSION_COOKIE_NAME: "session" },
  };
  vm.runInNewContext(routeCode, ctx);
  const req = (method, origin, token) => ({ method, headers: { get: () => origin }, nextUrl: { origin: "http://localhost:3101", search: "" }, cookies: { get: () => token ? { value: token } : undefined }, text: async () => "{}" });
  for (const method of ["POST", "PUT", "DELETE"]) {
    const params = { params: Promise.resolve({ path: ["0"] }) };
    assert.equal((await ctx.exports[method](req(method, "https://evil.example", "token"), params)).status, 403);
    assert.equal((await ctx.exports[method](req(method, "https://asistenciamodelo.online", null), params)).status, 401);
    assert.equal(fetched, 0);
  }
  assert.equal((await ctx.exports.PUT(req("PUT", "https://asistenciamodelo.online", "token"), { params: Promise.resolve({ path: ["0"] }) })).status, 403);
  assert.equal(fetched, 1); // Backend owner-only rejection is preserved.
});
