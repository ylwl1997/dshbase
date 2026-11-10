import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { renderPluginPage } from '../../functions/_data/render-plugin.js';
import { validateEvidence } from './plugin-evidence.js';
import {
  INSTALL_LABELS,
  astroDetailBlocks,
  catalogInstall,
  functionDetailBlocks,
  metaInstallPhrase,
  pluginInstall,
  singleInstallCommand,
} from '../../functions/_data/plugin-install-cmd.js';

const PREFERRED = 'npm install -g @deepseek-ai/dsh @deepseek-harness-tui/dsh-tui';
const MANUAL = 'dsh plugin --profile dsh-tui add @deepseek-harness-tui/dsh-tui';
const NOTE = '目录安装规格改为官方 npm 包 @deepseek-harness-tui/dsh-tui（2026-11-10 的 latest 为 0.19.0）。git tarball 仍缺 vendor/dsh-std，已不再作为推荐安装。';

function legacySingle(p) {
  if (p.npm && p.pkg) return `dsh plugin add ${p.pkg}`;
  const repo = String(p.url || '').replace('https://github.com/', '');
  return `dsh plugin add github:${repo}`;
}

function legacyDetail(p) {
  const repo = String(p.url || '').replace('https://github.com/', '');
  if (p.npm && p.pkg) {
    return {
      web: `dsh plugin --profile web add ${p.installPkg || p.pkg}`,
      headless: `dsh plugin --profile headless add ${p.pkg}`,
    };
  }
  return {
    web: `dsh plugin --profile web add github:${repo}`,
    headless: `dsh plugin --profile headless add github:${repo}`,
  };
}

function legacyCatalog(p) {
  const repo = String(p.url || '').replace('https://github.com/', '').replace(/\/+$/, '');
  if (p.installPkg) return `dsh plugin --profile web add ${p.installPkg}`;
  if (p.npm && p.pkg) return `dsh plugin add ${p.pkg}`;
  return `dsh plugin add github:${repo}`;
}

function legacyFunction(p) {
  const repo = String(p.url || '').replace(/^https?:\/\/github\.com\//, '');
  const spec = p.installPkg || p.pkg;
  return p.npm && spec
    ? `dsh plugin --profile web add ${spec}`
    : `dsh plugin --profile web add github:${repo}`;
}

function legacyMeta(p, locale) {
  if (p.npm) return `dsh plugin add ${p.pkg}`;
  return locale === 'zh' ? 'npm 源码' : 'npm source';
}

test('official install pair replaces defaults; a partial pair does not', () => {
  const official = pluginInstall({
    npm: true,
    pkg: '@deepseek-harness-tui/dsh-tui',
    url: 'https://github.com/ccch1mneyyy/dsh-TUI',
    installPreferred: `  ${PREFERRED}  `,
    installManual: `  ${MANUAL}  `,
  });
  assert.equal(official.official, true);
  assert.equal(official.preferred, PREFERRED);
  assert.equal(official.manual, MANUAL);
  assert.equal(official.single, MANUAL);
  assert.equal(official.catalog, MANUAL);
  assert.equal(official.web, '');
  assert.equal(official.headless, '');
  assert.equal(singleInstallCommand({
    npm: true,
    pkg: '@deepseek-harness-tui/dsh-tui',
    installPreferred: PREFERRED,
    installManual: MANUAL,
  }), MANUAL);
  assert.notEqual(official.single, 'dsh plugin add @deepseek-harness-tui/dsh-tui');
  assert.doesNotMatch(official.single, /github:/);

  const manualOnly = pluginInstall({
    npm: true,
    pkg: 'foo',
    installManual: 'dsh plugin --profile x add foo',
  });
  assert.equal(manualOnly.official, false);
  assert.equal(manualOnly.single, 'dsh plugin add foo');

  const blank = pluginInstall({
    npm: true,
    pkg: 'foo',
    installPreferred: '   ',
    installManual: '   ',
  });
  assert.equal(blank.official, false);
  assert.equal(blank.single, 'dsh plugin add foo');
});

test('detail labels are the official README pair, not Web or Headless', () => {
  const plugin = {
    npm: true,
    pkg: '@deepseek-harness-tui/dsh-tui',
    ver: '0.19.0',
    installPreferred: PREFERRED,
    installManual: MANUAL,
  };
  assert.deepEqual(astroDetailBlocks(plugin, 'en'), [
    { label: 'Preferred (official README):', command: PREFERRED },
    { label: 'Manual equivalent:', command: MANUAL },
  ]);
  assert.deepEqual(astroDetailBlocks(plugin, 'zh'), [
    { label: '首选（官方 README）：', command: PREFERRED },
    { label: '手动等价：', command: MANUAL },
  ]);
  assert.deepEqual(functionDetailBlocks(plugin, 'zh'), astroDetailBlocks(plugin, 'zh'));
  assert.equal(metaInstallPhrase(plugin, 'en'), MANUAL);
  assert.equal(metaInstallPhrase(plugin, 'zh'), MANUAL);
  const labels = JSON.stringify(astroDetailBlocks(plugin, 'en')) + JSON.stringify(astroDetailBlocks(plugin, 'zh'));
  assert.doesNotMatch(labels, /Web profile|Headless|Web 配置/);
  assert.equal(INSTALL_LABELS.en.preferred, 'Preferred (official README):');
  assert.equal(INSTALL_LABELS.zh.manual, '手动等价：');
});

test('defaults stay on the historical command for npm, github, and installPkg', () => {
  const npm = { npm: true, pkg: 'dsh-memory', url: 'https://github.com/ex/dsh-memory' };
  const gotNpm = pluginInstall(npm);
  assert.equal(gotNpm.official, false);
  assert.equal(gotNpm.single, 'dsh plugin add dsh-memory');
  assert.equal(gotNpm.web, 'dsh plugin --profile web add dsh-memory');
  assert.equal(gotNpm.headless, 'dsh plugin --profile headless add dsh-memory');
  assert.deepEqual(astroDetailBlocks(npm, 'en'), [
    { label: 'Web profile:', command: gotNpm.web },
    { label: 'Headless (CLI) profile:', command: gotNpm.headless },
  ]);
  assert.deepEqual(astroDetailBlocks(npm, 'zh'), [
    { label: 'Web profile：', command: gotNpm.web },
    { label: 'Headless（CLI）profile：', command: gotNpm.headless },
  ]);
  assert.deepEqual(functionDetailBlocks(npm, 'zh'), [
    { label: 'Web 配置：', command: 'dsh plugin --profile web add dsh-memory' },
  ]);
  assert.equal(metaInstallPhrase(npm, 'en'), 'dsh plugin add dsh-memory');
  assert.equal(metaInstallPhrase({ npm: false, url: 'https://github.com/ex/src' }, 'zh'), 'npm 源码');
  assert.equal(metaInstallPhrase({ npm: false, url: 'https://github.com/ex/src' }, 'en'), 'npm source');

  const remote = {
    npm: true,
    pkg: 'dsh-remote-plugin',
    installPkg: 'dsh-remote-plugin@latest',
    url: 'https://github.com/Blank-not-black/dsh-Remote',
  };
  const gotRemote = pluginInstall(remote);
  assert.equal(gotRemote.single, 'dsh plugin add dsh-remote-plugin');
  assert.equal(gotRemote.web, 'dsh plugin --profile web add dsh-remote-plugin@latest');
  assert.equal(gotRemote.headless, 'dsh plugin --profile headless add dsh-remote-plugin');
  assert.equal(gotRemote.catalog, 'dsh plugin --profile web add dsh-remote-plugin@latest');
  assert.equal(gotRemote.functionWeb, 'dsh plugin --profile web add dsh-remote-plugin@latest');

  const git = { npm: false, pkg: '', url: 'https://github.com/liceses/dsh-gitbash-preset' };
  const gotGit = pluginInstall(git);
  assert.equal(gotGit.single, 'dsh plugin add github:liceses/dsh-gitbash-preset');
  assert.equal(gotGit.web, 'dsh plugin --profile web add github:liceses/dsh-gitbash-preset');
  assert.equal(gotGit.headless, 'dsh plugin --profile headless add github:liceses/dsh-gitbash-preset');
});

test('catalog dsh-TUI is the only official install spec and other commands are unchanged', () => {
  const plugins = JSON.parse(readFileSync(new URL('../data/plugins.json', import.meta.url), 'utf8'));
  const official = [];
  for (const items of Object.values(plugins)) {
    for (const p of items) {
      const got = pluginInstall(p);
      if (got.official) {
        official.push(p.slug);
        continue;
      }
      assert.equal(got.single, legacySingle(p), p.slug);
      assert.equal(got.catalog, legacyCatalog(p), p.slug);
      assert.equal(got.web, legacyDetail(p).web, p.slug);
      assert.equal(got.headless, legacyDetail(p).headless, p.slug);
      assert.equal(got.functionWeb, legacyFunction(p), p.slug);
      assert.equal(singleInstallCommand(p), legacySingle(p), p.slug);
      assert.equal(catalogInstall(p), legacyCatalog(p), p.slug);
      assert.equal(metaInstallPhrase(p, 'en'), legacyMeta(p, 'en'), p.slug);
      assert.equal(metaInstallPhrase(p, 'zh'), legacyMeta(p, 'zh'), p.slug);
      assert.equal(astroDetailBlocks(p, 'en')[0].label, 'Web profile:');
      assert.equal(astroDetailBlocks(p, 'zh')[1].label, 'Headless（CLI）profile：');
    }
  }
  assert.deepEqual(official, ['dsh-TUI']);

  const tui = Object.values(plugins).flat().find((p) => p.slug === 'dsh-TUI');
  assert.equal(tui.test, 'verified');
  assert.equal(tui.npm, true);
  assert.equal(tui.pkg, '@deepseek-harness-tui/dsh-tui');
  assert.equal(tui.ver, '0.19.0');
  assert.equal(tui.url, 'https://github.com/ccch1mneyyy/dsh-TUI');
  assert.equal(tui.note, NOTE);
  assert.doesNotMatch(tui.note, /Verified|已验证/);
  assert.equal(tui.installPreferred, PREFERRED);
  assert.equal(tui.installManual, MANUAL);
  const ins = pluginInstall(tui);
  assert.equal(ins.preferred, PREFERRED);
  assert.equal(ins.single, MANUAL);
  assert.equal(ins.catalog, MANUAL);
  assert.deepEqual(astroDetailBlocks(tui, 'en').map((b) => b.command), [PREFERRED, MANUAL]);
  assert.deepEqual(astroDetailBlocks(tui, 'zh').map((b) => b.label), ['首选（官方 README）：', '手动等价：']);
});

test('shipped dsh-TUI evidence is the npm run and does not claim a badge', () => {
  const file = JSON.parse(readFileSync(new URL('../data/plugin-evidence.json', import.meta.url), 'utf8'));
  const entry = file.plugins['dsh-TUI'];
  const result = validateEvidence(entry);
  assert.equal(result.ok, true, result.error || '');
  assert.equal(entry.dshVersionRequested, '@deepseek-ai/dsh@latest');
  assert.equal(entry.dshVersionActual, '0.2.2-rc.1');
  assert.equal(entry.testDate, '2026-11-10');
  assert.deepEqual(['L1', 'L2', 'L3', 'L4'].map((id) => entry.levels[id].status), ['pass', 'pass', 'pass', 'skip']);
  assert.match(entry.conclusion, /@deepseek-harness-tui\/dsh-tui@0\.19\.0/);
  assert.match(entry.conclusion, /vendor\/dsh-std/);
  assert.match(entry.levels.L1.reason, /react peer warning/);
  assert.match(entry.levels.L1.reason, /patch warnings/);
  assert.match(entry.levels.L4.reason, /terminal UI/);
  assert.doesNotMatch(`${entry.conclusion}\n${entry.conclusion_zh}`, /Verified|verified|已验证/);
  assert.equal(Object.keys(file.plugins).length, 28);
});

test('function renderer shows both official commands and keeps the catalog box', async () => {
  const plugins = JSON.parse(readFileSync(new URL('../data/plugins.json', import.meta.url), 'utf8'));
  const tui = Object.values(plugins).flat().find((p) => p.slug === 'dsh-TUI');
  const en = await (await renderPluginPage(tui, 'en')).text();
  const zh = await (await renderPluginPage(tui, 'zh')).text();
  assert.match(en, /Preferred \(official README\):/);
  assert.match(en, /Manual equivalent:/);
  assert.match(en, new RegExp(PREFERRED.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(en, /dsh plugin --profile dsh-tui add @deepseek-harness-tui\/dsh-tui/);
  assert.match(en, /dsh plugin add dshbase-catalog/);
  assert.doesNotMatch(en, /Web profile:/);
  assert.doesNotMatch(en, /Headless/);
  assert.doesNotMatch(en, /dsh plugin add @deepseek-harness-tui\/dsh-tui/);
  assert.doesNotMatch(en, /dsh plugin --profile web add/);
  assert.doesNotMatch(en, /github:ccch1mneyyy\/dsh-TUI/);
  assert.match(zh, /首选（官方 README）：/);
  assert.match(zh, /手动等价：/);
  assert.match(zh, /dsh plugin add dshbase-catalog/);
  assert.doesNotMatch(zh, /Web 配置：/);
  assert.doesNotMatch(zh, /Headless/);

  const git = Object.values(plugins).flat().find((p) => p.slug === 'dsh-gitbash-preset');
  const gitHtml = await (await renderPluginPage(git, 'en')).text();
  assert.match(gitHtml, /Web profile:/);
  assert.match(gitHtml, /dsh plugin --profile web add github:liceses\/dsh-gitbash-preset/);
  assert.doesNotMatch(gitHtml, /Preferred \(official README\):/);
});
