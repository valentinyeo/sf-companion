#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const [site, playwrightModule, live] = process.argv.slice(2);
const { chromium, request } = await import(
  pathToFileURL(playwrightModule).href
);
const proof = process.env.PROOF_DIR;
const fixture = fileURLToPath(new URL("./fixture.json", import.meta.url));
const result = { status: "running", cases: [], live: "skipped" };
const children = new Set();

function start(args, logName) {
  const log = createWriteStream(join(proof, logName));
  const child = spawn("pnpm", args, {
    cwd: site,
    detached: true,
    env: { ...process.env, PORTLESS: "0", NO_COLOR: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.add(child);
  child.stdout.pipe(log);
  child.stderr.pipe(log);
  child.done = new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => resolve({ code, signal }));
  });
  child.done.catch(() => {});
  return child;
}

async function stop(child) {
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }
  const force = setTimeout(() => {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch (error) {
      if (error.code !== "ESRCH") console.error(error);
    }
  }, 5000);
  try {
    await child.done;
  } finally {
    clearTimeout(force);
    children.delete(child);
  }
}

async function freePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function ready(child, url) {
  let timer;
  let onData;
  try {
    await new Promise((resolve, reject) => {
      let output = "";
      timer = setTimeout(
        () => reject(new Error(`Vite readiness timeout at ${url}`)),
        60000
      );
      onData = (data) => {
        output += data.toString();
        if (output.includes(url)) resolve();
      };
      child.stdout.on("data", onData);
      child.done.then(
        ({ code }) =>
          reject(new Error(`Vite exited before readiness: ${code}`)),
        reject
      );
    });
  } finally {
    clearTimeout(timer);
    child.stdout.off("data", onData);
  }
}

async function drive(browser, state, width, colorScheme, baseURL) {
  const id = `${state}-${width}-${colorScheme}`;
  const context = await browser.newContext({
    baseURL,
    viewport: { width, height: width === 390 ? 844 : 900 },
    colorScheme,
  });
  const page = await context.newPage();
  page.setDefaultNavigationTimeout(120000);
  const entry = { id, status: "running", actions: [], errors: [] };
  result.cases.push(entry);
  page.on("console", (message) => {
    if (message.type() === "error") entry.errors.push(message.text());
  });
  page.on("pageerror", (error) => entry.errors.push(error.message));
  page.on("response", (response) => {
    if (response.url().startsWith(baseURL) && response.status() >= 400) {
      entry.errors.push(`HTTP ${response.status()} ${response.url()}`);
    }
  });
  async function record(action) {
    const dimensions = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }));
    entry.actions.push({ action, url: page.url(), dimensions });
    assert.ok(
      dimensions.scroll <= dimensions.viewport,
      `${id}: horizontal overflow after ${action}`
    );
  }
  try {
    const response = await page.goto("/factory", { waitUntil: "networkidle" });
    assert.equal(response.status(), 200);
    await page.getByRole("heading", { name: "Factory", exact: true }).waitFor();
    await page
      .getByRole("link", { name: "Software Factory Companion", exact: true })
      .waitFor();
    assert.equal(
      await page.evaluate(
        () => matchMedia("(prefers-color-scheme: dark)").matches
      ),
      colorScheme === "dark"
    );
    await record("doctor: load /factory and confirm app identity");
    await page
      .getByRole("link", { name: "Software Factory Companion", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Software Factory Companion", exact: true })
      .waitFor();
    await page
      .getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link", { name: "Factory", exact: true })
      .click();
    await page.getByRole("heading", { name: "Factory", exact: true }).waitFor();
    await record("navigate home, then choose Factory in primary navigation");
    if (state === "seeded") {
      await page
        .getByRole("heading", { name: "Fixture Plan", exact: true })
        .waitFor();
      await page
        .getByText("Numbers from 2026-11-15 00:41 UTC", { exact: true })
        .waitFor();
      await page.getByText("29 / day · 87 / week", { exact: true }).waitFor();
      await page
        .getByText("+2% · £0.00 in 1h on runners", { exact: true })
        .waitFor();
      await page.screenshot({
        path: join(proof, `${id}-before.png`),
        fullPage: true,
      });
      for (const window of ["3h", "6h", "12h", "24h", "7d", "30d", "1h"]) {
        const button = page
          .getByRole("group", { name: "Usage window" })
          .getByRole("button", { name: window, exact: true });
        await button.click();
        await page
          .locator(`button[aria-pressed="true"]`)
          .filter({ hasText: new RegExp(`^${window}$`, "u") })
          .waitFor();
        if (window === "7d")
          await page
            .getByText("+14% · £7.00 in 7d on runners", { exact: true })
            .waitFor();
        await page.getByText("29 / day · 87 / week", { exact: true }).waitFor();
        await record(
          `choose ${window}; selected window changes, KPI stays fixed`
        );
      }
      await page.getByText("Windows", { exact: true }).click();
      await page
        .getByText("Weekly 67%", { exact: true })
        .waitFor({ state: "visible" });
      await record("open Windows and read Weekly 67%");
      await page.getByText("Measurement details", { exact: true }).click();
      await page
        .getByText("Synthetic third measurement detail", { exact: true })
        .waitFor({ state: "visible" });
      await record("open Measurement details and read third detail");
    } else {
      await page
        .getByText("No factory numbers yet.", { exact: true })
        .waitFor();
      assert.equal(
        await page.getByRole("group", { name: "Usage window" }).count(),
        0
      );
      assert.equal(
        await page.getByRole("heading", { name: "Output and waste" }).count(),
        0
      );
      await record(
        "missing feed shows explicit empty state, not measured zeroes"
      );
    }
    await page.screenshot({ path: join(proof, `${id}.png`), fullPage: true });
    await writeFile(
      join(proof, `${id}.aria.txt`),
      await page.locator("body").ariaSnapshot()
    );
    assert.deepEqual(entry.errors, [], `${id}: browser errors`);
    entry.status = "passed";
  } catch (error) {
    entry.status = "failed";
    entry.error = error.stack;
    await page
      .screenshot({ path: join(proof, `${id}-failure.png`), fullPage: true })
      .catch(() => {});
    throw error;
  } finally {
    await context.close();
    await writeFile(join(proof, `${id}.json`), JSON.stringify(entry, null, 2));
  }
}

let browser;
async function interrupted(signal) {
  result.status = "failed";
  result.error = `Verification interrupted by ${signal}`;
  await Promise.all([...children].map(stop));
  await browser?.close();
  await writeFile(join(proof, "result.json"), JSON.stringify(result, null, 2));
  process.exit(signal === "SIGINT" ? 130 : 143);
}
process.once("SIGTERM", () => {
  void interrupted("SIGTERM");
});
process.once("SIGINT", () => {
  void interrupted("SIGINT");
});
try {
  result.revision = (
    await readFile(join(proof, "revision.txt"), "utf8")
  ).trim();
  browser = await chromium.launch();
  for (const state of ["seeded", "empty"]) {
    const feed = join(site, "apps/web/content/feed/factory.json");
    await mkdir(join(site, "apps/web/content/feed"), { recursive: true });
    if (state === "seeded") await copyFile(fixture, feed);
    else await rm(feed);
    const build = start(
      ["--filter", "@sf-companion/web", "build"],
      `${state}-build.log`
    );
    const built = await build.done;
    children.delete(build);
    assert.equal(
      built.code,
      0,
      `${state} build failed; see ${state}-build.log`
    );
    await writeFile(
      join(site, "apps/web/verify.vite.config.ts"),
      `import { mergeConfig } from "vite";
import config from "./vite.config.ts";
export default mergeConfig(config, {
  optimizeDeps: { entries: ["src/client/entry.ts"] },
});
`
    );
    const port = await freePort();
    const url = `http://127.0.0.1:${port}`;
    const dev = start(
      [
        "--filter",
        "@sf-companion/web",
        "dev",
        "--host",
        "127.0.0.1",
        "--port",
        String(port),
        "--strictPort",
        "--config",
        "verify.vite.config.ts",
      ],
      `${state}-dev.log`
    );
    try {
      await ready(dev, url);
      for (const width of [1280, 390]) {
        for (const theme of ["light", "dark"])
          await drive(browser, state, width, theme, url);
      }
    } finally {
      await stop(dev);
    }
  }
  if (live === "--live") {
    const context = await request.newContext();
    try {
      const response = await context.get("https://yeoux.net/factory/", {
        maxRedirects: 0,
      });
      assert.ok(
        [301, 302, 303, 307, 308].includes(response.status()),
        "Anonymous live request must redirect"
      );
      const location = new URL(response.headers().location);
      assert.ok(
        location.hostname.endsWith(".cloudflareaccess.com"),
        "Redirect must go to Cloudflare Access"
      );
      assert.ok(
        location.pathname.startsWith("/cdn-cgi/access/login"),
        "Redirect must be an Access login"
      );
      result.live = {
        status: response.status(),
        destination: `${location.origin}${location.pathname}`,
      };
    } finally {
      await context.dispose();
    }
  }
  result.status = "passed";
} catch (error) {
  result.status = "failed";
  result.error = error.stack;
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser?.close();
  await Promise.all([...children].map(stop));
  await writeFile(join(proof, "result.json"), JSON.stringify(result, null, 2));
}
