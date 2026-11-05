/* eslint-disable @typescript-eslint/no-require-imports -- Node test harness */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "src/components/auto-submit-select.tsx"), "utf8");
const code = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
} }).outputText;
const context = { exports: {}, require };
vm.runInNewContext(code, context);
const Select = context.exports.AutoSubmitSelect;

test("department change submits the containing form without a report submitter", () => {
  const children = ["department options"];
  const element = Select({ name: "department_id", defaultValue: "3", children });
  assert.equal(element.type, "select");
  assert.equal(element.props.name, "department_id");
  assert.equal(element.props.defaultValue, "3");
  assert.equal(element.props.children, children);
  let calls = 0;
  element.props.onChange({ currentTarget: { form: { requestSubmit(...args) {
    calls++;
    assert.equal(args.length, 0);
  } } } });
  assert.equal(calls, 1);
});

test("no surrounding form is safe", () => {
  assert.doesNotThrow(() => Select({}).props.onChange({ currentTarget: { form: null } }));
});

test("period form preserves the fields needed by automatic consultation", () => {
  const page = fs.readFileSync(path.join(root, "src/app/staff/page.tsx"), "utf8");
  const form = page.slice(page.indexOf('<form className="mt-5'), page.indexOf('</form>', page.indexOf('<form className="mt-5')));
  assert.match(form, /<AutoSubmitSelect\s+name="department_id"/);
  for (const field of ['view', 'filter', 'q', 'sort']) assert.ok(form.includes(`name="${field}"`));
  assert.ok(form.includes('<PeriodDateRangeFields'));
  assert.ok(form.includes('Consultar'));
});
