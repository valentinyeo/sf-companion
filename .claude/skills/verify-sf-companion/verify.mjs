#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import {
  copyFile,
  cp,
  mkdir,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import { createServer } from "node:net";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const positional = args.filter((value) => !value.startsWith("--"));
const [site, playwrightModule] = positional;
const live = args.includes("--live");
const journeysArgument = args.find((value) => value.startsWith("--journeys="));
const journeys =
  journeysArgument === undefined
    ? []
    : journeysArgument.slice("--journeys=".length).split(",").filter(Boolean);
const selected = new Set(journeys);
const allJourneys = selected.size === 0;
const wants = (journey) => allJourneys || selected.has(journey);
const seededJourneys = [
  "factory-entry",
  "factory-layout",
  "factory-readings",
  "factory-shipping",
  "usage-window",
  "usage-burn",
  "usage-kpi-fixed",
  "usage-details",
];
const seededHubJourneys = [
  "explorations-index",
  "explorations-item",
  "explorations-scope",
  "home-links",
  "home-sections",
  "reports-index",
  "reports-item",
  "reports-scope",
];
const runSeeded = [...seededJourneys, ...seededHubJourneys].some(wants);
const runEmpty = ["factory-empty", "home-empty"].some(wants);
const liveOnlyJourneys = new Set(["access-anonymous"]);
const runWindows = ["usage-window", "usage-burn", "usage-kpi-fixed"].some(
  wants
);
const runLive = wants("access-anonymous");
const { chromium, request } = await import(
  pathToFileURL(playwrightModule).href
);
const proof = process.env.PROOF_DIR;
const fixture = fileURLToPath(new URL("./fixture.json", import.meta.url));
const fixtureHub = fileURLToPath(new URL("./fixture-hub", import.meta.url));
const result = {
  status: "running",
  cases: [],
  live: "skipped",
  journeys: allJourneys ? "all" : [...selected].sort(),
};
const children = new Set();
let journeyIds = [];

function traceIndex() {
  const journeys = {};
  for (const entry of result.cases) {
    if (entry.trace === undefined) continue;
    for (const action of entry.actions) {
      if (action.journey === null) continue;
      journeys[action.journey] ??= [];
      if (!journeys[action.journey].includes(entry.trace)) {
        journeys[action.journey].push(entry.trace);
      }
    }
  }
  const expected = (
    allJourneys ? journeyIds : journeyIds.filter((id) => selected.has(id))
  ).filter((id) => journeys[id] === undefined);
  const untraced = expected
    .filter((id) => liveOnlyJourneys.has(id))
    .map((id) => ({
      journey: id,
      reason: "live HTTP request, no browser context to record",
    }));
  return {
    status: result.status,
    revision: result.revision,
    journeys,
    untraced,
  };
}

async function featureJourneyIds() {
  const directory = fileURLToPath(new URL("./features/", import.meta.url));
  const names = (await readdir(directory)).filter((name) =>
    name.endsWith(".md")
  );
  const ids = new Set();
  for (const name of names) {
    const text = await readFile(join(directory, name), "utf8");
    for (const [, id] of text.matchAll(/^- `([a-z0-9][a-z0-9-]*)`/gmu)) {
      ids.add(id);
    }
  }
  return [...ids].sort();
}

async function assertFeatureGates(ids) {
  const source = await readFile(fileURLToPath(import.meta.url), "utf8");
  const gated = new Set(
    [...source.matchAll(/wants\("([a-z0-9][a-z0-9-]*)"\)/gu)].map(
      (match) => match[1]
    )
  );
  const ungated = ids.filter((id) => !gated.has(id));
  assert.deepEqual(
    ungated,
    [],
    `Feature ids with no wants() gate in verify.mjs: ${ungated.join(", ")}`
  );
}

function assertJourneysRecorded(ids) {
  const recorded = new Set(
    result.cases
      .flatMap((entry) => entry.actions.map((action) => action.journey))
      .filter((journey) => journey !== null)
  );
  const expected = (
    allJourneys ? ids : ids.filter((id) => selected.has(id))
  ).filter((id) => !liveOnlyJourneys.has(id));
  const missing = expected.filter((id) => !recorded.has(id));
  assert.deepEqual(
    missing,
    [],
    `Journeys requested but never driven: ${missing.join(", ")}`
  );
}

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
  const trace = `${id}.trace.zip`;
  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();
  page.setDefaultNavigationTimeout(120000);
  const entry = { id, status: "running", actions: [], errors: [], trace };
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
  async function record(action, journey = null) {
    const dimensions = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }));
    entry.actions.push({ action, dimensions, journey, url: page.url() });
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
    if (wants("factory-layout")) {
      await record(
        "factory: layout fits this viewport width and color scheme",
        "factory-layout"
      );
    }
    if (wants("factory-entry")) {
      await page
        .getByRole("link", { name: "Software Factory Companion", exact: true })
        .click();
      await page
        .getByRole("heading", {
          name: "Software Factory Companion",
          exact: true,
        })
        .waitFor();
      await page
        .getByRole("navigation", { name: "Primary navigation" })
        .getByRole("link", { name: "Factory", exact: true })
        .click();
      await page
        .getByRole("heading", { name: "Factory", exact: true })
        .waitFor();
      await record(
        "navigate home, then choose Factory in primary navigation",
        "factory-entry"
      );
    }
    if (state === "seeded") {
      if (wants("factory-readings")) {
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
        await record(
          "factory: seeded readings, export time and KPI display",
          "factory-readings"
        );
      }
      if (runWindows || wants("factory-layout") || wants("factory-readings")) {
        await page.screenshot({
          path: join(proof, `${id}-before.png`),
          fullPage: true,
        });
      }
      if (runWindows) {
        for (const window of ["3h", "6h", "12h", "24h", "7d", "30d", "1h"]) {
          const button = page
            .getByRole("group", { name: "Usage window" })
            .getByRole("button", { name: window, exact: true });
          await button.click();
          await page
            .locator(`button[aria-pressed="true"]`)
            .filter({ hasText: new RegExp(`^${window}$`, "u") })
            .waitFor();
          if (wants("usage-window")) {
            await record(
              `usage: choose ${window}; its button reports pressed`,
              "usage-window"
            );
          }
          if (wants("usage-burn") && window === "7d") {
            await page
              .getByText("+14% · £7.00 in 7d on runners", { exact: true })
              .waitFor();
            await record(
              "usage: the 7d window changes burn to the 7d reading",
              "usage-burn"
            );
          }
          if (wants("usage-kpi-fixed")) {
            await page
              .getByText("29 / day · 87 / week", { exact: true })
              .waitFor();
            await record(
              `usage: ${window} leaves the KPI reading fixed`,
              "usage-kpi-fixed"
            );
          }
        }
      }
      if (wants("usage-details")) {
        await page.getByText("Windows", { exact: true }).click();
        await page
          .getByText("Weekly 67%", { exact: true })
          .waitFor({ state: "visible" });
        await record("open Windows and read Weekly 67%", "usage-details");
        await page.getByText("Measurement details", { exact: true }).click();
        await page
          .getByText("Synthetic third measurement detail", { exact: true })
          .waitFor({ state: "visible" });
        await record(
          "open Measurement details and read third detail",
          "usage-details"
        );
      }
      if (wants("factory-shipping")) {
        await page
          .getByRole("heading", {
            name: "PRs shipped vs plan burn",
            exact: true,
          })
          .waitFor();
        const chart = page.getByRole("region", {
          name: "Daily shipping and burn chart",
        });
        await chart
          .getByRole("rowheader", { name: "2026-11-15", exact: true })
          .waitFor();
        await chart
          .getByRole("rowheader", { name: "2026-11-14", exact: true })
          .waitFor();
        const newest = chart.getByRole("row").filter({
          has: page.getByRole("rowheader", { name: "2026-11-15", exact: true }),
        });
        await newest.getByText("2 PRs", { exact: true }).click();
        await newest
          .getByText("GitHub search · fleet mergedAt", { exact: true })
          .waitFor();
        await record(
          "expand one shipping source inside the chart",
          "factory-shipping"
        );
      }
    } else if (wants("factory-empty")) {
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
      assert.equal(
        await page
          .getByRole("heading", { name: "PRs shipped vs plan burn" })
          .count(),
        0
      );
      await record(
        "missing feed shows explicit empty state, not measured zeroes",
        "factory-empty"
      );
    }
    await driveHub(page, state, record, id);
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
    const traced = await context.tracing
      .stop({ path: join(proof, trace) })
      .then(
        () => true,
        () => false
      );
    if (!traced) delete entry.trace;
    await context.close();
    await writeFile(join(proof, `${id}.json`), JSON.stringify(entry, null, 2));
  }
}

async function openStoredItem(page, record, id, journey, path, body, name) {
  const response = await page.goto(path, { waitUntil: "networkidle" });
  assert.equal(
    response.status(),
    200,
    `${id}: ${path} answered ${response.status()}`
  );
  await page.getByText(body, { exact: true }).waitFor();
  assert.equal(
    await page.getByRole("navigation", { name: "Primary navigation" }).count(),
    0,
    `${id}: ${path} carried site navigation`
  );
  await page.screenshot({
    path: join(proof, `hub-${name}-${id}.png`),
    fullPage: true,
  });
  await writeFile(
    join(proof, `hub-${name}-${id}.aria.txt`),
    await page.locator("body").ariaSnapshot()
  );
  await record(`hub: ${name} serves the stored artefact body`, journey);
}

async function driveHub(page, state, record, id) {
  const navigation = page.getByRole("navigation", {
    name: "Primary navigation",
  });
  const label = (name) => page.getByRole("link", { name, exact: true });
  const heading = (name) => page.getByRole("heading", { name, exact: true });

  await page.goto("/", { waitUntil: "networkidle" });
  await heading("Software Factory Companion").waitFor();
  if (wants("home-sections")) {
    await heading("Explorations").waitFor();
    await heading("Reports").waitFor();
    if (state === "seeded") {
      await label("Motion study").waitFor();
      await label("Client pricing review").waitFor();
      await label("Retainer summary").waitFor();
      await label("All 1").waitFor();
      await label("All 2").waitFor();
      await page.getByText("yeo-ux · 2026-11-12", { exact: true }).waitFor();
      await page.screenshot({
        path: join(proof, `hub-home-${id}.png`),
        fullPage: true,
      });
    }
    await record(
      "hub: home shows both sections with their newest rows",
      "home-sections"
    );
  }
  if (state === "seeded") {
    if (wants("home-links")) {
      await page.goto("/", { waitUntil: "networkidle" });
      await label("Client pricing review").click();
      await page
        .getByText("Fixture client pricing body.", { exact: true })
        .waitFor();
      await record("hub: home report row opens its stored item", "home-links");
      await page.goto("/", { waitUntil: "networkidle" });
      await label("Motion study").click();
      await page.getByText("Fixture motion body.", { exact: true }).waitFor();
      await record(
        "hub: home exploration row opens its stored item",
        "home-links"
      );
      await page.goto("/", { waitUntil: "networkidle" });
      await label("All 2").click();
      await heading("Reports").waitFor();
      await page.getByText("2 items.", { exact: false }).waitFor();
      await record(
        "hub: home reports section link opens the reports index",
        "home-links"
      );
      await page.goto("/", { waitUntil: "networkidle" });
      await label("All 1").click();
      await heading("Explorations").waitFor();
      await page.getByText("1 items.", { exact: false }).waitFor();
      await record(
        "hub: home explorations section link opens the explorations index",
        "home-links"
      );
    }
    if (wants("reports-index")) {
      await page.goto("/", { waitUntil: "networkidle" });
      await navigation
        .getByRole("link", { name: "Reports", exact: true })
        .click();
      await heading("Reports").waitFor();
      await page.getByText("2 items.", { exact: false }).waitFor();
      await page.getByText("ezyfit · 2026-10-30", { exact: true }).waitFor();
      await page.getByText("yeo-ux · 2026-11-12", { exact: true }).waitFor();
      await page.screenshot({
        path: join(proof, `hub-reports-${id}.png`),
        fullPage: true,
      });
      await record(
        "hub: reports index lists both report rows with project and date",
        "reports-index"
      );
    }
    if (wants("reports-scope")) {
      if (!wants("reports-index")) {
        await page.goto("/reports", { waitUntil: "networkidle" });
        await heading("Reports").waitFor();
      }
      assert.equal(
        await label("Motion study").count(),
        0,
        `${id}: an exploration reached the reports index`
      );
      await record(
        "hub: reports index keeps exploration items off its list",
        "reports-scope"
      );
    }
    if (wants("reports-item")) {
      await openStoredItem(
        page,
        record,
        id,
        "reports-item",
        "/reports/4b7c1d2e-client-pricing.html",
        "Fixture client pricing body.",
        "report-item"
      );
    }
    if (wants("explorations-index")) {
      await page.goto("/", { waitUntil: "networkidle" });
      await navigation
        .getByRole("link", { name: "Explorations", exact: true })
        .click();
      await heading("Explorations").waitFor();
      await page.getByText("1 items.", { exact: false }).waitFor();
      await label("Motion study").waitFor();
      await page.getByText("2026-11-05", { exact: true }).waitFor();
      await page.screenshot({
        path: join(proof, `hub-explorations-${id}.png`),
        fullPage: true,
      });
      await record(
        "hub: explorations index lists the item with its date",
        "explorations-index"
      );
    }
    if (wants("explorations-scope")) {
      if (!wants("explorations-index")) {
        await page.goto("/explorations", { waitUntil: "networkidle" });
        await heading("Explorations").waitFor();
      }
      assert.equal(
        await label("Retainer summary").count(),
        0,
        `${id}: a report reached the explorations index`
      );
      assert.equal(
        await label("Client pricing review").count(),
        0,
        `${id}: a report reached the explorations index`
      );
      await record(
        "hub: explorations index keeps report items off its list",
        "explorations-scope"
      );
    }
    if (wants("explorations-item")) {
      await openStoredItem(
        page,
        record,
        id,
        "explorations-item",
        "/explorations/2a5e8f4d-motion-study.html",
        "Fixture motion body.",
        "exploration-item"
      );
    }
  } else {
    if (wants("home-empty")) {
      await page.getByText("No explorations yet.", { exact: true }).waitFor();
      await page.getByText("No reports yet.", { exact: true }).waitFor();
      assert.equal(await label("Motion study").count(), 0);
      assert.equal(await label("Client pricing review").count(), 0);
      await record(
        "hub: empty home says a section holds nothing",
        "home-empty"
      );
    }
    if (wants("reports-index")) {
      await page.goto("/reports", { waitUntil: "networkidle" });
      await heading("Reports").waitFor();
      await page.getByText("0 items.", { exact: false }).waitFor();
      await page.getByText("No reports yet.", { exact: true }).waitFor();
      await record("hub: empty reports index says 0 items", "reports-index");
    }
    if (wants("explorations-index")) {
      await page.goto("/explorations", { waitUntil: "networkidle" });
      await heading("Explorations").waitFor();
      await page.getByText("0 items.", { exact: false }).waitFor();
      await page.getByText("No explorations yet.", { exact: true }).waitFor();
      await record(
        "hub: empty explorations index says 0 items",
        "explorations-index"
      );
    }
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
  journeyIds = await featureJourneyIds();
  await assertFeatureGates(journeyIds);
  browser = await chromium.launch();
  for (const state of ["seeded", "empty"]) {
    if (state === "seeded" ? !runSeeded : !runEmpty) continue;
    const feed = join(site, "apps/web/content/feed/factory.json");
    const hub = join(site, "apps/web/content/hub");
    await mkdir(join(site, "apps/web/content/feed"), { recursive: true });
    await rm(hub, { recursive: true, force: true });
    if (state === "seeded") {
      await copyFile(fixture, feed);
      await cp(fixtureHub, hub, { recursive: true });
    } else {
      await rm(feed, { force: true });
    }
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
  if (live && runLive) {
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
  assertJourneysRecorded(journeyIds);
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
  await writeFile(
    join(proof, "traces.json"),
    JSON.stringify(traceIndex(), null, 2)
  );
}
