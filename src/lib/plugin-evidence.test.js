import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { claimsVerifiedBadge, presentEvidence, validateEvidence, filledSections, REQUESTED_DIST_TAG } from './plugin-evidence.js';

const file = JSON.parse(readFileSync(new URL('../data/plugin-evidence.json', import.meta.url), 'utf8'));

function level(status, reason, reasonZh = '这是一句给人读的中文原因，不是日志。') {
  return { status, reason, reason_zh: reasonZh };
}

function record(overrides = {}) {
  return {
    conclusion: 'Install and load succeeded on the version resolved from the latest dist-tag.',
    conclusion_zh: '在 latest 发行标签解析出的版本上，安装和加载都成功。',
    dshVersionRequested: '@deepseek-ai/dsh@latest',
    dshVersionActual: '0.2.4',
    testDate: '2026-11-10',
    levels: {
      L1: level('pass', 'dsh plugin add finished in a clean profile and the package was recorded there.'),
      L2: level('pass', 'The profile booted and dump-config listed the plugin bundle.'),
      L3: level('skip', 'Headless stopped while waiting for service webServer. That web-only result is not a pass and not a plugin failure.', '无头模式停在 waiting for service webServer。这个 web-only 结果不是通过，也不是插件故障。'),
      L4: level('skip', 'Web CDP was not run for this record, so there is no browser result to report.', '这条记录没有跑 Web CDP，所以没有浏览器结果。'),
    },
    ...overrides,
  };
}

test('schema examples are valid evidence and not catalog results', () => {
  const schema = JSON.parse(readFileSync(new URL('../data/plugin-evidence.schema.json', import.meta.url), 'utf8'));
  assert.ok(schema.examples.length >= 2);
  for (const example of schema.examples) {
    for (const [slug, entry] of Object.entries(example.plugins)) {
      const result = validateEvidence(entry);
      assert.equal(result.ok, true, `${slug}: ${result.error || ''}`);
      assert.equal(result.value.dshVersionRequested, REQUESTED_DIST_TAG);
      const view = presentEvidence(slug, { locale: 'zh', data: example });
      assert.equal(view.hasEvidence, true);
      assert.equal(view.levels.length, 4);
      assert.equal(view.dshVersionRequested, REQUESTED_DIST_TAG);
    }
  }
});

test('shipped evidence records validate and do not claim Verified', () => {
  const slugs = Object.keys(file.plugins);
  assert.ok(slugs.length > 0);
  for (const slug of slugs) {
    const entry = file.plugins[slug];
    const result = validateEvidence(entry);
    assert.equal(result.ok, true, `${slug}: ${result.error || ''}`);
    const zh = presentEvidence(slug, { locale: 'zh', data: file });
    const en = presentEvidence(slug, { locale: 'en', data: file });
    assert.equal(zh.hasEvidence, true, slug);
    assert.equal(en.hasEvidence, true, slug);
    assert.equal(claimsVerifiedBadge(entry.conclusion), false, `${slug} conclusion`);
    assert.equal(claimsVerifiedBadge(entry.conclusion_zh), false, `${slug} conclusion_zh`);
    assert.doesNotMatch(`${entry.conclusion}\n${entry.conclusion_zh}`, /Verified|verified|已验证/);
  }
  assert.equal(presentEvidence('modlens', { locale: 'zh', data: file }).hasEvidence, false);
  assert.equal(presentEvidence('modlens', { locale: 'en', data: file, archived: true }).hasEvidence, false);
});

test('empty report does not invent a pass from catalog metadata', () => {
  const zh = presentEvidence('any-slug', {
    locale: 'zh',
    archived: true,
    data: { plugins: {} },
  });
  assert.equal(zh.headline, '尚无短证据报告');
  assert.match(zh.body, /Star/);
  assert.match(zh.body, /web-only/);
  assert.doesNotMatch(`${zh.headline} ${zh.body}`, /推荐|实测可用|已验证|Verified|pass/i);
  assert.match(zh.archivedNote, /已归档/);
  assert.equal(zh.dshVersionActual, '');
  assert.equal(zh.levels.length, 0);

  const en = presentEvidence('any-slug', { locale: 'en', data: {} });
  assert.equal(en.headline, 'No short evidence report');
  assert.match(en.body, /catalog test field/);
  assert.doesNotMatch(`${en.headline} ${en.body}`, /Recommended|verified working|Verified/i);
});

test('a filled record shows conclusion, resolved version, date, four levels, and needs', () => {
  const data = {
    plugins: {
      'example-plugin': record({
        levels: {
          L1: level('pass', 'dsh plugin add finished in a clean profile and the package was recorded there.'),
          L2: level('pass', 'The profile booted and dump-config listed the plugin bundle.'),
          L3: level('needs', 'The headless prompt never called the model because DEEPSEEK_API_KEY was not set.', '没有设置 DEEPSEEK_API_KEY，无头提问没有调用模型。'),
          L4: level('skip', 'Web CDP was not run. A missing API key is not a browser result.', '没有跑 Web CDP。缺少 API key 不是浏览器结果。'),
        },
        needs: 'A DeepSeek API key for the headless model call. This run did not set one.',
        needs_zh: '无头模型调用需要 DeepSeek API key。这次没有配置。',
        dshVersionRequested: 'latest',
        dshVersionActual: '0.1.2-rc.1',
      }),
    },
  };
  const zh = presentEvidence('example-plugin', { locale: 'zh', data });
  assert.equal(zh.hasEvidence, true);
  assert.match(zh.headline, /安装和加载都成功/);
  assert.equal(zh.dshVersionRequested, REQUESTED_DIST_TAG);
  assert.equal(zh.dshVersionActual, '0.1.2-rc.1');
  assert.equal(zh.testDate, '2026-11-10');
  assert.deepEqual(zh.levels.map((row) => row.status), ['pass', 'pass', 'needs', 'skip']);
  assert.deepEqual(zh.levels.map((row) => row.id), ['L1', 'L2', 'L3', 'L4']);
  assert.match(zh.levels[2].reason, /DEEPSEEK_API_KEY/);
  assert.match(zh.levels[2].statusLabel, /需外部条件/);
  assert.match(zh.needs, /API key/);
  assert.doesNotMatch(JSON.stringify(zh), /Verified|已验证/);

  const en = presentEvidence('example-plugin', { locale: 'en', data });
  assert.match(en.headline, /Install and load succeeded/);
  assert.equal(en.levels[0].statusLabel, 'Pass');
  assert.match(en.needs, /DeepSeek API key/);
  assert.match(en.disclaimer, /does not change the catalog badge/);
});

test('web-only and needs cannot be stored as pass or fail', () => {
  const webFail = record({
    levels: {
      ...record().levels,
      L3: level('fail', 'Failed because the plugin is web-only and waiting for service webServer.', '失败，因为它是 web-only，停在 waiting for service。'),
    },
  });
  assert.equal(validateEvidence(webFail).ok, false);
  assert.match(validateEvidence(webFail).error, /web-only/);

  const webPass = record({
    levels: {
      ...record().levels,
      L3: level('pass', 'Passed as web-only while waiting for service webServer.', '以 web-only 通过，停在 waiting for service。'),
    },
  });
  assert.equal(validateEvidence(webPass).ok, false);

  const needsFail = record({
    needs: 'A DeepSeek API key for the headless model call. This run did not set one.',
    needs_zh: '无头模型调用需要 DeepSeek API key。这次没有配置。',
    levels: {
      ...record().levels,
      L3: level('fail', 'Failed because DEEPSEEK_API_KEY was not set and the external account is missing.', '失败，因为没有设置 DEEPSEEK_API_KEY，外部账号缺失。'),
    },
  });
  assert.equal(validateEvidence(needsFail).ok, false);
  assert.match(validateEvidence(needsFail).error, /needs/);

  const page = presentEvidence('example-plugin', { locale: 'en', data: { plugins: { 'example-plugin': webFail } } });
  assert.equal(page.hasEvidence, false);
  assert.equal(page.headline, 'No short evidence report');
});

test('a frozen rc dist-tag and a raw log are rejected', () => {
  for (const requested of ['0.1.0-rc.8', '@deepseek-ai/dsh@0.1.0-rc.8', '@deepseek-ai/dsh@0.2.4']) {
    const result = validateEvidence(record({ dshVersionRequested: requested }));
    assert.equal(result.ok, false, requested);
    assert.match(result.error, /frozen rc|dshVersionRequested/);
  }
  const log = record();
  log.levels.L1 = level(
    'fail',
    'Error: boom\n    at install (plugin.js:1:1)\n    at run (cli.js:2:2)\n    at main (main.js:3:3)\n    at start (start.js:4:4)',
    '日志太长，不能当原因。\n    at install (plugin.js:1:1)\n    at run (cli.js:2:2)\n    at main (main.js:3:3)',
  );
  assert.equal(validateEvidence(log).ok, false);
  assert.match(validateEvidence(log).error, /human sentence|raw log/);
});

test('actual version may be the rc that latest resolved to', () => {
  const result = validateEvidence(record({ dshVersionActual: 'dsh 0.1.2-rc.1' }));
  assert.equal(result.ok, true);
  assert.equal(result.value.dshVersionActual, 'dsh 0.1.2-rc.1');
  assert.equal(result.value.dshVersionRequested, REQUESTED_DIST_TAG);
  assert.equal(validateEvidence(record({ dshVersionActual: '@deepseek-ai/dsh@latest' })).ok, false);
  assert.equal(validateEvidence(record({ dshVersionActual: 'latest' })).ok, false);
});

test('filled review and report show different fields of the same record', () => {
  assert.deepEqual(filledSections('review'), {
    conclusion: true,
    meta: false,
    levels: false,
    needs: true,
    disclaimer: true,
  });
  assert.deepEqual(filledSections('report'), {
    conclusion: false,
    meta: true,
    levels: true,
    needs: true,
    disclaimer: false,
  });
});

test('conclusions that say Verified or 已验证 are rejected', () => {
  const rejected = [
    { conclusion: 'Install and load succeeded. This plugin is Verified.' },
    { conclusion: 'Install and load succeeded. Status: VERIFIED today.' },
    { conclusion: 'Install and load succeeded and the result is verified.' },
    { conclusion: '安装和加载都已验证，记录写在最新发行标签上。' },
    { conclusion_zh: '安装和加载都成功，该插件已验证。' },
    { conclusion_zh: 'Install and load succeeded. This plugin is Verified.' },
  ];
  for (const patch of rejected) {
    const result = validateEvidence(record(patch));
    assert.equal(result.ok, false, JSON.stringify(patch));
    assert.match(result.error, /Verified|已验证/);
  }

  const blocked = presentEvidence('s', {
    locale: 'zh',
    data: { plugins: { s: record({ conclusion_zh: '安装和加载都成功，该插件已验证。' }) } },
  });
  assert.equal(blocked.hasEvidence, false);
  assert.equal(blocked.headline, '尚无短证据报告');

  const allowed = validateEvidence(record({
    conclusion: 'Install and load succeeded on the version resolved from the latest dist-tag.',
    conclusion_zh: '这次只记下安装和加载。未验证不是徽章结论。',
  }));
  assert.equal(allowed.ok, true, allowed.error);
  assert.doesNotMatch(allowed.value.conclusion, /verified/i);
  assert.equal(allowed.value.conclusion_zh.includes('已验证'), false);
});

test('incomplete records do not render', () => {
  const missingLevel = record();
  delete missingLevel.levels.L4;
  assert.equal(presentEvidence('s', { data: { plugins: { s: missingLevel } } }).hasEvidence, false);
  assert.equal(validateEvidence(record({ testDate: '2026-02-31' })).ok, false);
  assert.equal(validateEvidence(record({ conclusion_zh: '' })).ok, false);
  const needsStatus = record({
    levels: {
      ...record().levels,
      L3: level('needs', 'The headless prompt never called the model because DEEPSEEK_API_KEY was not set.', '没有设置 DEEPSEEK_API_KEY，无头提问没有调用模型。'),
    },
  });
  assert.equal(validateEvidence(needsStatus).ok, false);
});
