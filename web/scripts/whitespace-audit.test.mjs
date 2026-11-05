import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { auditTemplates } from './whitespace-audit.mjs';

async function auditSource(source) {
  const dir = mkdtempSync(join(tmpdir(), 'ws-audit-'));
  try {
    writeFileSync(join(dir, 'Page.astro'), source);
    return await auditTemplates(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('templates have no text that relies on a line break for spacing', async () => {
  const findings = await auditTemplates();
  assert.deepEqual(findings, [], findings.map((f) => `${f.file}: ${f.between}`).join('\n'));
});

test('flags text split from a link by line breaks', async () => {
  const findings = await auditSource(`<p>
  use
  <a href="/x">this link</a>
  to continue
</p>`);
  assert.equal(findings.length, 2);
});

test('accepts explicit spaces around a link', async () => {
  const findings = await auditSource(`<p>
  use{' '}
  <a href="/x">this link</a>{' '}
  to continue
</p>`);
  assert.deepEqual(findings, []);
});

test('ignores breaks between block elements and at element edges', async () => {
  const findings = await auditSource(`<div>
  <p>
    One
  </p>
  <p>Two</p>
</div>`);
  assert.deepEqual(findings, []);
});
