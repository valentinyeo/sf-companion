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
const routeSource = await readFile(
  join(site, "apps/web/src/features/route.ts"),
  "utf8"
).catch(() => "");
const declaredRoutes =
  routeSource === ""
    ? null
    : new Set(
        [...routeSource.matchAll(/^ {2}([A-Z][A-Za-z0-9]*):/gmu)].map(
          (match) => match[1]
        )
      );
const journeyRoutes = {
  "usage-burn": "Usage",
  "usage-cards": "Usage",
  "usage-details": "Usage",
  "usage-empty": "Usage",
  "usage-entry": "Usage",
  "usage-kpi-fixed": "Usage",
  "usage-window": "Usage",
};
const absentJourneys = new Map(
  Object.entries(journeyRoutes)
    .filter(
      ([journey, route]) =>
        (allJourneys || selected.has(journey)) &&
        declaredRoutes !== null &&
        !declaredRoutes.has(route)
    )
    .map(([journey, route]) => [
      journey,
      `apps/web/src/features/route.ts declares no ${route} route on this revision, so there is no page to drive.`,
    ])
);
const wants = (journey) =>
  (allJourneys || selected.has(journey)) && !absentJourneys.has(journey);
const shareToken = "verify-share-token";
process.env.SF_SHARE_TOKEN = shareToken;
const seededFactoryJourneys = [
  "factory-entry",
  "factory-layout",
  "factory-timestamp",
  "usage-entry",
  "usage-cards",
  "usage-window",
  "usage-burn",
  "usage-kpi-fixed",
  "usage-details",
  "kpi-tiles",
  "kpi-windows",
  "kpi-details",
  "shipping-chart",
  "shipping-source",
  "shipping-omission",
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
  "items-serve",
  "items-head",
  "items-missing",
  "items-invalid",
];
const shareJourneys = [
  "share-publish",
  "share-delete",
  "share-auth",
  "share-validate",
];
const seededJourneys = [
  ...seededFactoryJourneys,
  ...seededHubJourneys,
  ...shareJourneys,
];
const runSeeded = seededJourneys.some(wants);
const runEmpty = [
  "factory-empty",
  "usage-empty",
  "home-empty",
  "not-found",
].some(wants);
const runWindows = [
  "usage-window",
  "usage-burn",
  "usage-kpi-fixed",
  "kpi-windows",
].some(wants);
const runShare = shareJourneys.some(wants);
const untraced = JSON.parse(
  await readFile(
    fileURLToPath(new URL("./untraced.json", import.meta.url)),
    "utf8"
  )
);
const untracedJourneys = new Set(Object.keys(untraced));
const runLive = wants("access-anonymous");
const actionlessJourneys = new Set(["access-anonymous"]);
const expectedNotFound = "/no-such-page";
let expectingMissingPage = false;
const exportTime = "Numbers from 2026-11-15 00:41 UTC";
const shippingCostWindow = "2026-11-15 00:00 UTC to 2026-11-16 00:00 UTC";
const { chromium, request } = await import(
  pathToFileURL(playwrightModule).href
);
const proof = process.env.PROOF_DIR;
const fixture = fileURLToPath(new URL("./fixture.json", import.meta.url));
const fixtureHub = fileURLToPath(new URL("./fixture-hub", import.meta.url));
const result = {
  skipped: [...absentJourneys.entries()].map(([journey, reason]) => ({
    journey,
    reason,
  })),
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
  const excused = expected
    .filter((id) => untracedJourneys.has(id))
    .map((id) => ({ journey: id, reason: untraced[id] }));
  return {
    status: result.status,
    revision: result.revision,
    journeys,
    untraced: excused,
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
  ).filter((id) => !(actionlessJourneys.has(id) || absentJourneys.has(id)));
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
    env: {
      ...process.env,
      NO_COLOR: "1",
      PORTLESS: "0",
      SF_SHARE_TOKEN: shareToken,
    },
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
    if (message.type() !== "error") return;
    if (expectingMissingPage && message.text().includes("404")) return;
    entry.errors.push(message.text());
  });
  page.on("pageerror", (error) => entry.errors.push(error.message));
  page.on("response", (response) => {
    if (!response.url().startsWith(baseURL) || response.status() < 400) return;
    const path = new URL(response.url()).pathname;
    const expected = response.status() === 404 && path === expectedNotFound;
    if (!expected) {
      entry.errors.push(`HTTP ${response.status()} ${response.url()}`);
    }
  });
  const widget = (name) =>
    page
      .getByRole("listitem")
      .filter({ has: page.getByRole("heading", { name, exact: true }) });
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
      if (wants("usage-entry")) {
        const direct = await page.goto("/usage", { waitUntil: "networkidle" });
        assert.equal(direct.status(), 200, `${id}: /usage status`);
        await page
          .getByRole("heading", { name: "Usage", exact: true })
          .waitFor();
        await page
          .getByRole("link", {
            name: "Software Factory Companion",
            exact: true,
          })
          .waitFor();
        await page.goto("/", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", {
            name: "Software Factory Companion",
            exact: true,
          })
          .waitFor();
        await page
          .getByRole("navigation", { name: "Primary navigation" })
          .getByRole("link", { name: "Usage", exact: true })
          .click();
        await page
          .getByRole("heading", { name: "Usage", exact: true })
          .waitFor();
        await record(
          "usage: /usage answers directly and primary navigation reaches it",
          "usage-entry"
        );
      }
      if (wants("factory-timestamp")) {
        await page.goto("/factory", { waitUntil: "networkidle" });
        await page.getByText(exportTime, { exact: true }).waitFor();
        await record(
          "factory: the export time prints in UTC",
          "factory-timestamp"
        );
      }
      if (wants("usage-cards")) {
        await page.goto("/usage", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Usage", exact: true })
          .waitFor();
        const cards = [
          ["Claude Code", ["67%", "+13.2 vs pace · over pace"]],
          ["Codex", ["100%", "+21.5 vs pace · well over pace"]],
          ["Grok", ["89%", "+4.2 vs pace · well over pace"]],
          ["OpenCode", ["no reading"]],
          [
            "Vercel",
            ["$105.28 left", "credit · resets Tue 00:00 · as of 2h ago"],
          ],
          ["DeepSeek", ["$11.28 left", "as of 28h ago"]],
          ["OpenRouter", ["$45.85 left"]],
        ];
        for (const [name, readings] of cards) {
          await widget(name)
            .getByRole("heading", { name, exact: true })
            .waitFor();
          for (const reading of readings) {
            await widget(name).getByText(reading, { exact: true }).waitFor();
          }
        }
        await widget("Claude Code")
          .getByText("+2% · £0.00 in 1h on runners", { exact: true })
          .waitFor();
        await record(
          "usage: seven plan cards show their readings, resets and burn",
          "usage-cards"
        );
      }
      if (wants("kpi-tiles")) {
        await page.goto("/factory", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Factory", exact: true })
          .waitFor();
        const tiles = [
          [
            "Tickets delivered",
            [
              "29 / day · 87 / week",
              "Hypertask boards 15, 2060, 11514 · sectionChangedAt",
              "Rolling 24h and 7d",
            ],
          ],
          ["Verifier first-pass rate", ["75%"]],
          ["Plan usage pace", ["2/3 over pace", "off target"]],
          ["Drain-loop health", ["3 loops fired in 45m", "on target"]],
          [
            "PR throughput and merge time",
            ["1 / day · 3 / week · 20.0 min median"],
          ],
          ["Chat identity sync", ["50%", "off target"]],
          [
            "CI health",
            [
              "– to live · 0% confirmed infra · 0% confirmed code · 50% unclassified",
            ],
          ],
        ];
        for (const [name, texts] of tiles) {
          for (const text of texts) {
            await widget(name).getByText(text, { exact: true }).waitFor();
          }
        }
        await record(
          "kpi: seven tiles show their displays, sources and state cues",
          "kpi-tiles"
        );
      }
      if (
        !runWindows &&
        (wants("factory-layout") ||
          wants("kpi-details") ||
          wants("usage-cards"))
      ) {
        await page.screenshot({
          path: join(proof, `${id}-before.png`),
          fullPage: true,
        });
      }
      if (runWindows) {
        await page.goto("/usage", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Usage", exact: true })
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
          if (wants("usage-kpi-fixed") || wants("kpi-windows")) {
            assert.equal(
              await page
                .getByRole("heading", { name: "Output and waste" })
                .count(),
              0,
              `${id}: the usage page carried the KPI tiles`
            );
          }
        }
        if (wants("usage-kpi-fixed")) {
          await page.goto("/factory", { waitUntil: "networkidle" });
          await page
            .getByRole("heading", { name: "Factory", exact: true })
            .waitFor();
          await page
            .getByText("29 / day · 87 / week", { exact: true })
            .waitFor();
          await record(
            "usage: the window buttons leave Factory's KPI reading fixed",
            "usage-kpi-fixed"
          );
        }
        if (wants("kpi-windows")) {
          await page.goto("/factory", { waitUntil: "networkidle" });
          await page
            .getByRole("heading", { name: "Factory", exact: true })
            .waitFor();
          await widget("Tickets delivered")
            .getByText("Rolling 24h and 7d", { exact: true })
            .waitFor();
          await widget("Drain-loop health")
            .getByText("Rolling 45m", { exact: true })
            .waitFor();
          assert.equal(
            await page.getByRole("group", { name: "Usage window" }).count(),
            0,
            `${id}: the factory page carried the usage window buttons`
          );
          await record(
            "kpi: Factory keeps every tile on its own window and holds no usage buttons",
            "kpi-windows"
          );
        }
      }
      if (wants("usage-details")) {
        await page.goto("/usage", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Usage", exact: true })
          .waitFor();
        const card = widget("Claude Code");
        await card.getByText("Windows", { exact: true }).click();
        await card
          .getByText("Weekly 67%", { exact: true })
          .waitFor({ state: "visible" });
        await record(
          "usage: open Windows and read the weekly reading",
          "usage-details"
        );
      }
      if (wants("kpi-details")) {
        await page.goto("/factory", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Factory", exact: true })
          .waitFor();
        const delivered = widget("Tickets delivered");
        const third = delivered.getByText(
          "Synthetic third measurement detail",
          { exact: true }
        );
        assert.equal(
          await third.isVisible(),
          false,
          `${id}: the third detail was visible before its disclosure opened`
        );
        await delivered
          .getByText("Measurement details", { exact: true })
          .click();
        await third.waitFor({ state: "visible" });
        const pace = widget("Plan usage pace");
        await pace.getByText("Measurement details", { exact: true }).click();
        await pace
          .getByText("grok: 0.98× · at pace", { exact: true })
          .waitFor({ state: "visible" });
        await record(
          "kpi: each measurement disclosure expands inside its own tile",
          "kpi-details"
        );
      }
      if (
        wants("shipping-chart") ||
        wants("shipping-source") ||
        wants("shipping-omission")
      ) {
        await page.goto("/factory", { waitUntil: "networkidle" });
        await page
          .getByRole("heading", { name: "Factory", exact: true })
          .waitFor();
        await page
          .getByRole("heading", {
            name: "PRs shipped vs plan burn",
            exact: true,
          })
          .waitFor();
        const chart = page.getByRole("region", {
          name: "Daily shipping and burn chart",
        });
        if (wants("shipping-chart")) {
          await chart
            .getByText(
              "Last 30 UTC dates · fleet merges, observed weekly quota points and attributed £",
              { exact: true }
            )
            .waitFor();
          await chart
            .getByRole("rowheader", { name: "2026-11-15", exact: true })
            .waitFor();
          await chart
            .getByRole("rowheader", { name: "2026-10-17", exact: true })
            .waitFor();
          assert.equal(
            await chart.getByRole("rowheader").count(),
            30,
            `${id}: the chart did not render 30 dated rows`
          );
          await record(
            "shipping: 30 dated rows carry merges, burn, cost and cost per PR",
            "shipping-chart"
          );
        }
        if (wants("shipping-source")) {
          const newest = chart.getByRole("row").filter({
            has: page.getByRole("rowheader", {
              name: "2026-11-15",
              exact: true,
            }),
          });
          await newest.getByText("2 PRs", { exact: true }).click();
          await newest
            .getByText("GitHub search · fleet mergedAt", { exact: true })
            .waitFor({ state: "visible" });
          const opened = newest
            .locator("details[open]")
            .filter({ hasText: "GitHub search · fleet mergedAt" });
          assert.equal(
            await opened.getByText(shippingCostWindow, { exact: true }).count(),
            1,
            `${id}: the expanded shipping cell lost its UTC window`
          );
          await record(
            "shipping: a measured cell expands to its source and UTC window",
            "shipping-source"
          );
        }
        if (wants("shipping-omission")) {
          await page
            .getByText(
              "Grok, OpenCode omitted: pacing sampler retired on 2026-11-15.",
              { exact: true }
            )
            .waitFor();
          assert.equal(
            await chart.getByRole("columnheader", { name: "Grok pts" }).count(),
            0,
            `${id}: a plan with no readings still got a column`
          );
          await record(
            "shipping: plans with no readings are stated as omitted",
            "shipping-omission"
          );
        }
      }
    } else if (wants("factory-empty") || wants("usage-empty")) {
      if (wants("factory-empty")) {
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
      if (wants("usage-empty")) {
        const response = await page.goto("/usage", {
          waitUntil: "networkidle",
        });
        assert.equal(response.status(), 200, `${id}: empty /usage status`);
        await page
          .getByRole("heading", { name: "Usage", exact: true })
          .waitFor();
        await page
          .getByText("No usage numbers yet.", { exact: true })
          .waitFor();
        assert.equal(
          await page.getByRole("group", { name: "Usage window" }).count(),
          0,
          `${id}: the empty usage page still showed window buttons`
        );
        await record(
          "missing feed leaves Usage with an explicit empty line and no window buttons",
          "usage-empty"
        );
      }
    }
    await page.screenshot({ path: join(proof, `${id}.png`), fullPage: true });
    await writeFile(
      join(proof, `${id}.aria.txt`),
      await page.locator("body").ariaSnapshot()
    );
    await driveHub(page, state, record, id);
    await page.screenshot({
      path: join(proof, `${id}-final.png`),
      fullPage: true,
    });
    await writeFile(
      join(proof, `${id}-final.aria.txt`),
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

async function openStoredItem(
  page,
  record,
  id,
  journey,
  link,
  path,
  body,
  name
) {
  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) => new URL(candidate.url()).pathname === path
    ),
    page.getByRole("link", { name: link, exact: true }).click(),
  ]);
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
  await record(`hub: ${name} opens its stored artefact body`, journey);
}

async function driveItems(page, record, id) {
  if (wants("items-serve")) {
    const report = await page.request.get(
      "/reports/4b7c1d2e-client-pricing.html"
    );
    assert.equal(report.status(), 200, `${id}: item GET status`);
    assert.equal(
      report.headers()["content-type"],
      "text/html; charset=utf-8",
      `${id}: item GET content type`
    );
    assert.match(await report.text(), /Fixture client pricing body\./u);
    const exploration = await page.request.get(
      "/explorations/2a5e8f4d-motion-study.html"
    );
    assert.equal(exploration.status(), 200, `${id}: exploration GET status`);
    await record(
      "items: GET serves the stored bytes with their content type",
      "items-serve"
    );
  }
  if (wants("items-head")) {
    const head = await page.request.head(
      "/reports/4b7c1d2e-client-pricing.html"
    );
    assert.equal(head.status(), 200, `${id}: item HEAD status`);
    assert.ok(
      Number(head.headers()["content-length"]) > 0,
      `${id}: item HEAD lost its content length`
    );
    assert.equal((await head.body()).length, 0, `${id}: item HEAD sent a body`);
    await record("items: HEAD answers the headers and no body", "items-head");
  }
  if (wants("items-missing")) {
    const missing = await page.request.get("/reports/0000-missing.html");
    assert.equal(missing.status(), 404, `${id}: missing item status`);
    assert.equal(await missing.text(), "Not found", `${id}: missing item body`);
    await record(
      "items: a slug the store does not hold answers 404",
      "items-missing"
    );
  }
  if (wants("items-invalid")) {
    const invalid = await page.request.get("/reports/bad%24slug.html");
    assert.equal(invalid.status(), 400, `${id}: invalid slug status`);
    assert.deepEqual(
      await invalid.json(),
      { error: "Invalid slug" },
      `${id}: invalid slug body`
    );
    await record(
      "items: a slug outside the allowed characters answers 400",
      "items-invalid"
    );
  }
}

async function driveHub(page, state, record, id) {
  const navigation = page.getByRole("navigation", {
    name: "Primary navigation",
  });
  const label = (name) => page.getByRole("link", { name, exact: true });
  const heading = (name) => page.getByRole("heading", { name, exact: true });
  const section = (name) =>
    page
      .getByRole("main")
      .locator("section")
      .filter({ has: page.getByRole("heading", { name, exact: true }) });

  await page.goto("/", { waitUntil: "networkidle" });
  await heading("Software Factory Companion").waitFor();
  if (wants("home-sections")) {
    await heading("Explorations").waitFor();
    await heading("Reports").waitFor();
    await heading("Factory").waitFor();
    if (state === "seeded") {
      for (const name of [
        "Client pricing review",
        "Verifier scope audit",
        "Factory feed notes",
        "Retainer summary",
        "Build cost review",
        "Route parser notes",
        "Feed schema sketch",
        "Motion study",
        "Hydration check",
        "Style tokens study",
      ]) {
        await label(name).waitFor();
      }
      assert.equal(
        await label("Support volume report").count(),
        0,
        `${id}: home listed more than five reports`
      );
      assert.equal(
        await label("Nightly run log").count(),
        0,
        `${id}: home listed more than five explorations`
      );
      assert.equal(
        await label("All 10").count(),
        2,
        `${id}: home did not link both sections to their ten-item indexes`
      );
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
      await section("Reports")
        .getByRole("link", { name: "All 10", exact: true })
        .click();
      await heading("Reports").waitFor();
      await page.getByText("10 items.", { exact: false }).waitFor();
      await record(
        "hub: the home reports section link opens the reports index",
        "home-links"
      );
      await page.goto("/", { waitUntil: "networkidle" });
      await section("Explorations")
        .getByRole("link", { name: "All 10", exact: true })
        .click();
      await heading("Explorations").waitFor();
      await page.getByText("10 items.", { exact: false }).waitFor();
      await record(
        "hub: the home explorations section link opens the explorations index",
        "home-links"
      );
      await page.goto("/", { waitUntil: "networkidle" });
      await Promise.all([
        page.waitForResponse(
          (candidate) =>
            new URL(candidate.url()).pathname ===
            "/reports/4b7c1d2e-client-pricing.html"
        ),
        label("Client pricing review").click(),
      ]);
      await page
        .getByText("Fixture client pricing body.", { exact: true })
        .waitFor();
      await record(
        "hub: a home report row opens its stored item",
        "home-links"
      );
      await page.goto("/", { waitUntil: "networkidle" });
      await Promise.all([
        page.waitForResponse(
          (candidate) =>
            new URL(candidate.url()).pathname ===
            "/explorations/2a5e8f4d-motion-study.html"
        ),
        label("Motion study").click(),
      ]);
      await page.getByText("Fixture motion body.", { exact: true }).waitFor();
      await record(
        "hub: a home exploration row opens its stored item",
        "home-links"
      );
    }
    if (wants("reports-index")) {
      await page.goto("/", { waitUntil: "networkidle" });
      await navigation
        .getByRole("link", { name: "Reports", exact: true })
        .click();
      await heading("Reports").waitFor();
      await page.getByText("10 items.", { exact: false }).waitFor();
      await page.getByText("ezyfit · 2026-10-30", { exact: true }).waitFor();
      await page.getByText("yeo-ux · 2026-11-12", { exact: true }).waitFor();
      await page.screenshot({
        path: join(proof, `hub-reports-${id}.png`),
        fullPage: true,
      });
      await record(
        "hub: reports index lists every report with project and date",
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
      assert.equal(
        await label("Route parser notes").count(),
        0,
        `${id}: an exploration reached the reports index`
      );
      await record(
        "hub: reports index keeps exploration items off its list",
        "reports-scope"
      );
    }
    if (wants("reports-item")) {
      if (!wants("reports-index")) {
        await page.goto("/reports", { waitUntil: "networkidle" });
        await heading("Reports").waitFor();
      }
      await openStoredItem(
        page,
        record,
        id,
        "reports-item",
        "Client pricing review",
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
      await page.getByText("10 items.", { exact: false }).waitFor();
      await label("Motion study").waitFor();
      await page.getByText("2026-11-05", { exact: true }).waitFor();
      await page.screenshot({
        path: join(proof, `hub-explorations-${id}.png`),
        fullPage: true,
      });
      await record(
        "hub: explorations index lists every note with its date",
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
      if (!wants("explorations-index")) {
        await page.goto("/explorations", { waitUntil: "networkidle" });
        await heading("Explorations").waitFor();
      }
      await openStoredItem(
        page,
        record,
        id,
        "explorations-item",
        "Motion study",
        "/explorations/2a5e8f4d-motion-study.html",
        "Fixture motion body.",
        "exploration-item"
      );
    }
    await driveItems(page, record, id);
  } else {
    if (wants("home-empty")) {
      await page.getByText("No explorations yet.", { exact: true }).waitFor();
      await page.getByText("No reports yet.", { exact: true }).waitFor();
      assert.equal(await label("Motion study").count(), 0);
      assert.equal(await label("Client pricing review").count(), 0);
      assert.equal(await label("All 0").count(), 2);
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
    if (wants("not-found")) {
      expectingMissingPage = true;
      const response = await page.goto(expectedNotFound, {
        waitUntil: "networkidle",
      });
      assert.equal(
        response.status(),
        404,
        `${id}: an unknown URL answered ${response.status()}`
      );
      await page
        .getByRole("heading", { name: "Page not found", exact: true })
        .waitFor();
      await page
        .getByRole("link", { name: "Go to the home page.", exact: true })
        .click();
      await heading("Software Factory Companion").waitFor();
      expectingMissingPage = false;
      await record(
        "missing: an unknown URL answers 404 with a way home",
        "not-found"
      );
    }
  }
}

async function driveShare(baseURL) {
  const api = await request.newContext({ baseURL });
  const entry = {
    id: "seeded-share",
    status: "running",
    actions: [],
    errors: [],
  };
  result.cases.push(entry);
  const record = (action, journey, path) =>
    entry.actions.push({
      action,
      dimensions: null,
      journey,
      url: `${baseURL}${path}`,
    });
  const auth = { authorization: `Bearer ${shareToken}` };
  const html =
    '<!doctype html><html lang="en"><body><p>Verification publish body.</p></body></html>';
  const path = "/explorations/verify-publish.html";
  const url = "https://yeoux.net/explorations/verify-publish.html";
  try {
    if (wants("share-auth")) {
      const put = await api.put(path, {
        data: html,
        headers: { "content-type": "text/html" },
      });
      assert.equal(
        put.status(),
        401,
        "an unauthorised publish must answer 401"
      );
      const removal = await api.delete(path);
      assert.equal(
        removal.status(),
        401,
        "an unauthorised delete must answer 401"
      );
      record(
        "share: a write without the bearer token answers 401",
        "share-auth",
        path
      );
    }
    if (wants("share-validate")) {
      const date = await api.put(path, {
        data: html,
        headers: { ...auth, "x-date": "17/10/2026" },
      });
      assert.equal(date.status(), 400, "a malformed date must answer 400");
      assert.match(await date.text(), /X-Date must look like 2026-10-17/u);
      const project = await api.put(path, {
        data: html,
        headers: { ...auth, "x-project": "Yeo UX" },
      });
      assert.equal(
        project.status(),
        400,
        "a malformed project must answer 400"
      );
      assert.match(
        await project.text(),
        /X-Project must be lowercase letters, digits and dashes/u
      );
      const slug = await api.put("/reports/bad%24slug.html", {
        data: html,
        headers: auth,
      });
      assert.equal(slug.status(), 400, "an invalid slug must answer 400");
      assert.match(await slug.text(), /Invalid slug/u);
      record(
        "share: malformed date, project and slug answer 400 with the reason",
        "share-validate",
        path
      );
    }
    if (wants("share-publish") || wants("share-delete")) {
      const publish = await api.put(path, {
        data: html,
        headers: {
          ...auth,
          "content-type": "text/html",
          "x-date": "2026-11-16",
          "x-project": "verify",
          "x-title": "Verification publish",
        },
      });
      assert.equal(publish.status(), 200, "a valid publish must answer 200");
      assert.deepEqual(await publish.json(), { url });
      const listed = await (await api.get("/explorations")).text();
      assert.ok(listed.includes("Verification publish"), "publish is missing");
      assert.ok(
        listed.includes("verify · 2026-11-16"),
        "publish date is missing"
      );
      assert.ok(
        listed.includes("11 items."),
        "publish did not reach the index"
      );
      if (wants("share-publish")) {
        record(
          "share: a publish appears on the explorations index",
          "share-publish",
          path
        );
      }
      if (wants("share-delete")) {
        const removal = await api.delete(path, { headers: auth });
        assert.equal(removal.status(), 200, "a valid delete must answer 200");
        assert.deepEqual(await removal.json(), { deleted: true, url });
        const afterDelete = await (await api.get("/explorations")).text();
        assert.ok(
          !afterDelete.includes("Verification publish"),
          "the deleted item is still listed"
        );
        assert.ok(
          afterDelete.includes("10 items."),
          "the delete left the count"
        );
        const again = await api.delete(path, { headers: auth });
        assert.equal(again.status(), 404, "a second delete must answer 404");
        record(
          "share: a delete removes the item and its listing",
          "share-delete",
          path
        );
      }
    }
    entry.status = "passed";
  } catch (error) {
    entry.status = "failed";
    entry.error = error.stack;
    throw error;
  } finally {
    await api.dispose();
    await writeFile(
      join(proof, "seeded-share.json"),
      JSON.stringify(entry, null, 2)
    );
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
      if (state === "seeded" && runShare) await driveShare(url);
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
