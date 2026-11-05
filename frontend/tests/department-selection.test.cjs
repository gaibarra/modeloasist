/* eslint-disable @typescript-eslint/no-require-imports -- Node test harness */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const path = require('node:path');
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/department-selection.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, context);
const { changeDepartments, isBajaLabel } = context.exports;
const departments = [{ id: 1, name: 'CME-DTI' }, { id: 2, name: 'CME-Negocios' }, { id: 3, name: 'BAJAS' }, { id: 4, name: 'Bájas_Nómina' }];
const change = (...args) => JSON.parse(JSON.stringify(changeDepartments(...args)));
test('baja clears operating departments and sets principal', () => {
  assert.deepEqual(change([1, 2], 2, departments, departments[2], true), { department_ids: [3], primary_department_id: 3 });
  assert.deepEqual(change([3], 3, departments, departments[3], true), { department_ids: [4], primary_department_id: 4 });
});
test('reactivation removes both baja categories including inconsistent legacy assignments', () => {
  assert.deepEqual(change([1, 3, 4], 3, departments, departments[1], true), { department_ids: [1, 2], primary_department_id: 1 });
});
test('multiple operating departments and deselection work normally', () => {
  assert.deepEqual(change([1], 1, departments, departments[1], true), { department_ids: [1, 2], primary_department_id: 1 });
  assert.deepEqual(change([1, 2], 1, departments, departments[0], false), { department_ids: [2], primary_department_id: 2 });
  assert.deepEqual(change([1], 1, departments, departments[0], false), { department_ids: [], primary_department_id: null });
});
test('only baja groups are global exclusions', () => {
  assert.ok(isBajaLabel('Escuela Modelo / BAJAS-NÓMINA'));
  for (const label of ['CME-Pasantes', 'Consma Clean', 'Soluciones Castro', 'BAJAS MÉDICAS']) assert.equal(isBajaLabel(label), false);
});
