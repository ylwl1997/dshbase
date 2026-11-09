#!/usr/bin/env node
/**
 * L4 browser check for a booted dsh web profile.
 *
 * Replaces the host-local ~/webverify/l3.mjs + pinned Puppeteer Chrome path.
 * Uses Playwright to drive either the system Chrome/Chromium (ubuntu-latest
 * already has Google Chrome) or Playwright's own Chromium. Headless mode does
 * not need xvfb. This script does not send a model prompt and does not read
 * DEEPSEEK_API_KEY.
 *
 * The script records what the page did. scripts/verify-pilot.py decides
 * pass/fail from that record, so a missing plugin widget is a result, not a
 * crash.
 *
 * Usage:
 *   node scripts/l4-cdp.mjs --url http://127.0.0.1:3091/ --out result.json \
 *     --screenshot shot.png --timeout 60000 --expect '{"selectorsAny":[".dcq-float"]}'
 *
 * Exit 0: browser ran and result.json was written.
 * Exit 2: Playwright or the browser could not start (result.json still written
 *         when the process can write it).
 */
import { execFileSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";

function arg(name, fallback = "") {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) return fallback;
  return process.argv[index + 1];
}

function findChrome() {
  const fromEnv = (process.env.L4_CHROME_PATH || "").trim();
  if (fromEnv && existsSync(fromEnv)) return fromEnv;
  for (const name of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    try {
      const found = execFileSync("which", [name], { encoding: "utf8" }).trim().split("\n")[0];
      if (found) return found;
    } catch {
      /* next candidate */
    }
  }
  return "";
}

function playwrightApi(mod) {
  if (mod && mod.chromium) return mod;
  if (mod && mod.default && mod.default.chromium) return mod.default;
  throw new Error("playwright module has no chromium export");
}

async function loadPlaywright() {
  const attempts = [() => import("playwright")];
  const root = (process.env.L4_BROWSER_DIR || "").trim();
  if (root) {
    attempts.push(() => import(pathToFileURL(join(root, "node_modules", "playwright", "index.js")).href));
  }
  const errors = [];
  for (const load of attempts) {
    try {
      return playwrightApi(await load());
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  throw new Error(errors.join(" | ") || "playwright is not installed. Set NODE_PATH or L4_BROWSER_DIR.");
}

function writeResult(outPath, result) {
  if (!outPath) return;
  writeFileSync(outPath, JSON.stringify(result, null, 2) + "\n", "utf8");
}

async function launchBrowser(chromium) {
  const errors = [];
  const chromePath = findChrome();
  const attempts = [];
  if (chromePath) {
    attempts.push({
      label: chromePath,
      options: {
        executablePath: chromePath,
        headless: true,
        args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
      },
    });
  }
  attempts.push({
    label: "playwright-chromium",
    options: {
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    },
  });
  for (const attempt of attempts) {
    try {
      const browser = await chromium.launch(attempt.options);
      return { browser, label: attempt.label };
    } catch (error) {
      errors.push(`${attempt.label}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  const error = new Error(errors.join("\n") || "no browser launch attempt");
  error.attempts = errors;
  throw error;
}

async function clickLabels(page, labels) {
  if (!labels || labels.length === 0) return false;
  for (const label of labels) {
    const locator = page.getByRole("button", { name: label, exact: true });
    if (await locator.count()) {
      await locator.first().click({ timeout: 2000 }).catch(() => {});
      return true;
    }
  }
  return false;
}

async function dismissLabels(page, labels) {
  if (!labels || labels.length === 0) return;
  const first = page.getByRole("button", { name: labels[0], exact: true });
  await first.waitFor({ timeout: 8000 }).catch(() => {});
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const clicked = await clickLabels(page, labels);
    if (!clicked) return;
    await page.waitForTimeout(500);
  }
}

async function main() {
  const url = arg("--url");
  const outPath = arg("--out");
  const screenshotPath = arg("--screenshot");
  const timeoutMs = Number(arg("--timeout", "60000")) || 60000;
  let expect = {};
  const expectRaw = arg("--expect", "");
  if (expectRaw) {
    try {
      expect = JSON.parse(expectRaw);
    } catch (error) {
      const result = {
        url,
        harnessError: `bad --expect JSON: ${error instanceof Error ? error.message : String(error)}`,
        shellMounted: false,
        pluginReady: false,
      };
      writeResult(outPath, result);
      console.error(result.harnessError);
      process.exit(2);
    }
  }
  if (!url) {
    const result = { url: "", harnessError: "--url is required", shellMounted: false, pluginReady: false };
    writeResult(outPath, result);
    console.error(result.harnessError);
    process.exit(2);
  }

  const result = {
    url,
    browser: "",
    shellMounted: false,
    bootFailed: false,
    bootText: "",
    title: "",
    selectors: {},
    route: null,
    consoleErrors: [],
    pageErrors: [],
    screenshot: screenshotPath || "",
    pluginReady: false,
    detail: "",
    harnessError: "",
  };

  let playwright;
  try {
    playwright = await loadPlaywright();
  } catch (error) {
    result.harnessError = error instanceof Error ? error.message : String(error);
    writeResult(outPath, result);
    console.error(result.harnessError);
    process.exit(2);
  }

  const deadline = Date.now() + timeoutMs;
  const left = () => Math.max(1000, deadline - Date.now());
  let browser;
  try {
    const launched = await launchBrowser(playwright.chromium);
    browser = launched.browser;
    result.browser = launched.label;
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on("console", (message) => {
      if (message.type() !== "error") return;
      if (result.consoleErrors.length < 8) result.consoleErrors.push(message.text().slice(0, 300));
    });
    page.on("pageerror", (error) => {
      if (result.pageErrors.length < 8) result.pageErrors.push(String(error).slice(0, 500));
    });
    const pluginResponses = [];
    page.on("response", (response) => {
      const responseUrl = response.url();
      if (!/\/plugins\/|commandcode|processing-status|usage-billing/i.test(responseUrl)) return;
      const official = responseUrl.includes("@deepseek-ai/");
      if (official && response.status() < 400) return;
      if (pluginResponses.length >= 20) return;
      pluginResponses.push(`${response.status()} ${responseUrl.slice(0, 180)}`);
    });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: left() });
    const selectors = [
      ...(expect.selectorsAny || []),
      ...(expect.forbid || []),
    ];
    try {
      await page.waitForFunction(() => {
        const boot = document.querySelector("[data-dsh-boot]");
        if (!boot) return true;
        return /fail/i.test(boot.innerText || "");
      }, { timeout: left() });
    } catch {
      /* still on the boot overlay; the snapshot records that */
    }
    await dismissLabels(page, expect.dismiss || ["Continue", "继续", "Got it", "知道了"]);
    const probeSelectors = [...(expect.selectorsAny || []), ...(expect.forbid || [])];
    if (probeSelectors.length > 0 && left() > 1500) {
      try {
        await page.waitForFunction((wanted) => wanted.some((selector) => {
          try {
            return document.querySelector(selector) !== null;
          } catch {
            return false;
          }
        }), expect.selectorsAny || [], { timeout: Math.min(15000, left()) });
      } catch {
        /* selector never appeared; a settings click may still reveal the client */
      }
    }
    const early = await page.evaluate((wanted) => wanted.some((selector) => {
      try {
        return document.querySelector(selector) !== null;
      } catch {
        return false;
      }
    }), expect.selectorsAny || []);
    if (!early) {
      for (const label of expect.openText || []) {
        const clicked = await clickLabels(page, [label]);
        if (!clicked) continue;
        await page.waitForTimeout(700);
        const appeared = await page.evaluate((wanted) => wanted.some((selector) => {
          try {
            return document.querySelector(selector) !== null;
          } catch {
            return false;
          }
        }), expect.selectorsAny || []);
        if (appeared) break;
      }
    }
    if ((expect.selectorsAny || []).length > 0 && left() > 1500) {
      try {
        await page.waitForFunction((wanted) => wanted.some((selector) => {
          try {
            return document.querySelector(selector) !== null;
          } catch {
            return false;
          }
        }), expect.selectorsAny, { timeout: Math.min(10000, left()) });
      } catch {
        /* still absent */
      }
    }
    const snap = await page.evaluate(({ selectors: wanted, texts }) => {
      const boot = document.querySelector("[data-dsh-boot]");
      const found = {};
      for (const selector of wanted) {
        try {
          found[selector] = document.querySelector(selector) !== null;
        } catch {
          found[selector] = false;
        }
      }
      const body = (document.body ? document.body.innerText : "").replace(/\s+/g, " ");
      const textHits = {};
      for (const text of texts) textHits[text] = body.includes(text);
      const buttons = [...document.querySelectorAll("button, a, [role='button']")]
        .map((node) => (node.textContent || "").replace(/\s+/g, " ").trim())
        .filter(Boolean)
        .slice(0, 24);
      return {
        shellMounted: boot === null,
        bootFailed: Boolean(boot && /fail/i.test(boot.innerText || "")),
        bootText: (boot ? boot.innerText : "").replace(/\s+/g, " ").trim().slice(0, 800),
        title: document.title || "",
        selectors: found,
        texts: textHits,
        buttons,
      };
    }, { selectors, texts: expect.textAny || [] });
    Object.assign(result, snap);
    result.pluginResponses = pluginResponses;
    if (expect.route) {
      result.route = await page.evaluate(async (path) => {
        try {
          const response = await fetch(path, { headers: { accept: "application/json" } });
          const contentType = response.headers.get("content-type") || "";
          const text = await response.text();
          let json = contentType.includes("json");
          if (!json) {
            try {
              JSON.parse(text);
              json = text.trim().startsWith("{") || text.trim().startsWith("[");
            } catch {
              json = false;
            }
          }
          return {
            path,
            status: response.status,
            contentType,
            json,
            bodySnippet: text.slice(0, 400),
          };
        } catch (error) {
          return {
            path,
            status: 0,
            contentType: "",
            json: false,
            bodySnippet: String(error).slice(0, 300),
          };
        }
      }, expect.route);
    }
    if (screenshotPath) {
      await page.screenshot({ path: screenshotPath, fullPage: false });
    }
    result.detail = result.shellMounted
      ? "shell mounted"
      : (result.bootText || "boot overlay still visible");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (!result.browser) {
      result.harnessError = message;
    } else if (!result.detail) {
      result.detail = message.slice(0, 500);
    }
  } finally {
    if (browser) await browser.close().catch(() => {});
  }

  writeResult(outPath, result);
  console.log(JSON.stringify({
    browser: result.browser,
    shellMounted: result.shellMounted,
    bootFailed: result.bootFailed,
    selectors: result.selectors,
    route: result.route ? { status: result.route.status, json: result.route.json } : null,
    harnessError: result.harnessError,
  }));
  process.exit(result.harnessError ? 2 : 0);
}

main();
