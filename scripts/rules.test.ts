// @effect-diagnostics nodeBuiltinImport:off -- This test reads the repository's own styles and policy with Node tooling.
import { execSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Schema } from "effect";
import { describe, expect, it } from "vitest";

import { applyCommandPolicy } from "./vcs-command-policy.js";

const webSource = fileURLToPath(new URL("../apps/web/src/", import.meta.url));

const webManifest = new URL("../apps/web/package.json", import.meta.url);

const tokenHomes = ["client/rat.css", "features/tokens.stylex.ts"];

const pink = /#(?:ff1493|c8006e|f5c2e7)\b/iu;

const accentUse = /var\(--accent(?:-text)?\)/u;

const allowedSelectors = [/:focus-visible/u, /\.copy/u, /^:root$/u];

const bannedStyleDependencies = [
  /^@chakra-ui\//u,
  /^@mantine\//u,
  /^@mui\//u,
  /^@nivo\//u,
  /^@radix-ui\//u,
  /^@tailwindcss\//u,
  /^chart\.js$/u,
  /^d3(?:-[a-z]+)?$/u,
  /^recharts$/u,
  /^tailwindcss$/u,
  /^victory$/u,
];

const EvalFamily = Schema.Struct({
  family: Schema.String,
  model: Schema.String,
  provider: Schema.String,
  secret: Schema.String,
});

const EvalCase = Schema.Struct({
  expect: Schema.Literals(["PASS", "FAIL"]),
  id: Schema.String,
  patch: Schema.NullOr(Schema.String),
});

const EvalCases = Schema.Struct({
  cases: Schema.Array(EvalCase),
  families: Schema.Array(EvalFamily),
});

const WebManifest = Schema.Struct({
  dependencies: Schema.optional(Schema.Record(Schema.String, Schema.String)),
  devDependencies: Schema.optional(Schema.Record(Schema.String, Schema.String)),
});

const bypasses = [
  "git commit --no-verify -m x",
  "git commit -n -m x",
  "git push --no-verify",
  "LEFTHOOK=0 git commit -m x",
  "git -c core.hooksPath=/dev/null commit -m x",
  "GIT_EDITOR=: git merge --no-verify origin/main",
];

const ordinary = [
  "git commit -m x",
  "git status",
  "git rebase origin/main",
  "pnpm check",
  "echo hello",
];

interface Block {
  readonly selector: string;
  readonly body: string;
}

const blocksOf = (css: string): readonly Block[] => {
  const found: Block[] = [];
  let selector = "";
  let body = "";
  let depth = 0;

  for (const character of css) {
    if (character === "{") {
      depth += 1;

      if (depth === 1) {
        selector = body.trim();
        body = "";
        continue;
      }
    }

    if (character === "}") {
      depth -= 1;

      if (depth === 0) {
        found.push({ body, selector });
        body = "";
        continue;
      }
    }

    body += character;
  }

  return found;
};

const sourceFiles = (directory: string): readonly string[] =>
  readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.(?:ts|css)$/u.test(entry.name))
    .map((entry) => path.join(entry.parentPath, entry.name));

const pinkSources = (): readonly string[] =>
  sourceFiles(webSource)
    .map((file) => ({
      path: file.slice(webSource.length),
      text: readFileSync(file, "utf-8"),
    }))
    .filter(({ text }) => pink.test(text))
    .map(({ path: file }) => file)
    .toSorted((left, right) => left.localeCompare(right));

describe("the git bypass policy", () => {
  it("blocks every hook bypass", () => {
    for (const command of bypasses) {
      expect(applyCommandPolicy(command).action, command).toBe("block");
    }
  });

  it("allows ordinary work", () => {
    for (const command of ordinary) {
      expect(applyCommandPolicy(command).action, command).toBe("allow");
    }
  });

  it("explains the block in the fence grammar", () => {
    const result = applyCommandPolicy("git commit --no-verify -m x");

    expect(result.action).toBe("block");

    if (result.action === "block") {
      expect(result.reason).toMatch(/pnpm check/u);
      expect(result.reason).toMatch(/Fix:/u);
    }
  });
});

describe("the hot pink accent", () => {
  it("lives only in the token files", () => {
    expect(pinkSources()).toEqual([...tokenHomes].toSorted());
  });

  it("reaches only focus rings and copy controls", () => {
    const css = readFileSync(path.join(webSource, "client/rat.css"), "utf-8");

    const offenders = blocksOf(css)
      .filter((block) => accentUse.test(block.body))
      .filter(
        (block) =>
          !allowedSelectors.some((allowed) => allowed.test(block.selector))
      )
      .map((block) => block.selector);

    expect(offenders).toEqual([]);
  });
});

describe("the web style rules", () => {
  it("keeps Tailwind, UI kits, and chart libraries out", () => {
    const manifest = Schema.decodeUnknownSync(WebManifest)(
      JSON.parse(readFileSync(webManifest, "utf-8"))
    );

    const declared = [
      ...Object.keys(manifest.dependencies ?? {}),
      ...Object.keys(manifest.devDependencies ?? {}),
    ];

    expect(
      declared.filter((name) =>
        bannedStyleDependencies.some((banned) => banned.test(name))
      )
    ).toEqual([]);
  });
});

describe("the verify-skill evaluation", () => {
  const folder = new URL(
    "../.claude/skills/verify-sf-companion/evals/",
    import.meta.url
  );

  const workflow = readFileSync(
    new URL("../.github/workflows/verify-skill-eval.yml", import.meta.url),
    "utf-8"
  );

  const spec = Schema.decodeUnknownSync(EvalCases)(
    JSON.parse(readFileSync(new URL("cases.json", folder), "utf-8"))
  );

  const patches = readdirSync(new URL("patches/", folder))
    .filter((name) => name.endsWith(".patch"))
    .toSorted((left, right) => left.localeCompare(right));

  const planted = spec.cases.filter((entry) => entry.patch !== null);

  const clean = spec.cases.filter((entry) => entry.patch === null);

  it("plants every patch as a failing case", () => {
    expect(
      planted
        .map((entry) => entry.patch ?? "")
        .toSorted((left, right) => left.localeCompare(right))
    ).toEqual(patches);
    expect(planted.filter((entry) => entry.expect !== "FAIL")).toEqual([]);
  });

  it("keeps one case with no patch and a passing verdict", () => {
    expect(clean.map((entry) => entry.id)).toEqual(["clean"]);
    expect(clean.map((entry) => entry.expect)).toEqual(["PASS"]);
  });

  it("judges every case with two families", () => {
    expect(spec.families.map((entry) => entry.family)).toEqual([
      "deepseek",
      "moonshot",
    ]);

    expect(new Set(spec.families.map((entry) => entry.model)).size).toBe(
      spec.families.length
    );

    for (const family of spec.families) {
      expect(workflow).toContain(family.secret);
      expect(workflow).toContain(family.provider);
    }

    expect(workflow).toContain('eval.py" matrix --cases');
  });

  it("drives journeys that need no live gate", () => {
    const evalPy = fileURLToPath(
      new URL(
        "../.claude/skills/verify-sf-companion/evals/eval.py",
        import.meta.url
      )
    );

    const casesJson = fileURLToPath(new URL("cases.json", folder));

    const journeys = execSync(
      `python3 ${JSON.stringify(evalPy)} journeys --cases ${JSON.stringify(casesJson)}`,
      {
        encoding: "utf-8",
      }
    )
      .trim()
      .split(",")
      .filter(Boolean);

    expect(journeys).not.toContain("access-anonymous");
    expect(new Set(journeys).size).toBe(journeys.length);
  });

  it("stays off pull requests and cancels superseded runs", () => {
    expect(workflow).toMatch(/^ {2}schedule:\n/mu);
    expect(workflow).toMatch(/^ {2}workflow_dispatch:\n/mu);
    expect(workflow).toContain("cancel-in-progress: true");
    expect(workflow).not.toContain("pull_request");
  });
});
