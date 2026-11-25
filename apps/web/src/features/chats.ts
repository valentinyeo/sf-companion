import { DateTime, Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import type {
  ChatsServerLineValue,
  ChatsSnapshotValue,
  ChatHarnessValue,
  ChatRowValue,
} from "../content/chats.js";
import { classes } from "./cue.js";
import { factoryStyles } from "./factory.stylex.js";
import { hubStyles } from "./hub.stylex.js";

const MILLIS_PER_MINUTE = 60_000;

const HARNESS_LABELS: Readonly<Record<ChatHarnessValue, string>> = {
  antigravity: "Antigravity",
  claude: "Claude Code",
  codex: "Codex",
  cursor: "Cursor",
  pi: "Pi",
  unknown: "unknown",
};

const COLUMNS = ["Chat", "Project", "Harness", "Model", "Effort"] as const;

const updatedText = (generatedAt: string, nowMs: number): string | null =>
  Option.match(DateTime.make(generatedAt), {
    onNone: () => null,
    onSome: (generated) => {
      const minutes = Math.floor(
        Math.max(0, nowMs - DateTime.toEpochMillis(generated)) /
          MILLIS_PER_MINUTE
      );

      const clock = DateTime.formatLocal(generated, {
        hour: "2-digit",
        hourCycle: "h23",
        minute: "2-digit",
      });

      return `Updated ${clock} (${minutes} min ago)`;
    },
  });

const updatedLine = (
  snapshot: ChatsSnapshotValue,
  nowMs: Option.Option<number>,
  h: HtmlBuilder<AppMessage>
): Html => {
  const line = Option.match(nowMs, {
    onNone: () => null,
    onSome: (measured) => updatedText(snapshot.generatedAt, measured),
  });

  return h.p(
    [h.Class(classes(factoryStyles.small))],
    [line ?? "Refresh every few minutes."]
  );
};

const cell = (text: string, h: HtmlBuilder<AppMessage>): Html =>
  h.td([h.Class(classes(factoryStyles.chartCell))], [text]);

const chatRow = (chat: ChatRowValue, h: HtmlBuilder<AppMessage>): Html =>
  h.tr(
    [
      h.Key(`${chat.server}-${chat.name}-${chat.project}`),
      h.Class(classes(factoryStyles.chartRow)),
    ],
    [
      h.th(
        [h.Scope("row"), h.Class(classes(factoryStyles.chartCell))],
        [chat.name]
      ),
      cell(chat.project, h),
      cell(HARNESS_LABELS[chat.harness], h),
      cell(chat.model, h),
      cell(chat.effort, h),
    ]
  );

const chatsTable = (
  rows: readonly ChatRowValue[],
  h: HtmlBuilder<AppMessage>
): Html =>
  h.div(
    [
      h.Role("region"),
      h.AriaLabel("Live chats"),
      h.Tabindex(0),
      h.Class(classes(factoryStyles.chartScroll)),
    ],
    [
      h.table(
        [h.Class(classes(factoryStyles.chartTable))],
        [
          h.thead(
            [h.Class(classes(factoryStyles.chartHead))],
            [
              h.tr(
                [h.Class(classes(factoryStyles.chartRow))],
                COLUMNS.map((label) =>
                  h.th(
                    [h.Scope("col"), h.Class(classes(factoryStyles.chartCell))],
                    [label]
                  )
                )
              ),
            ]
          ),
          h.tbody(
            [h.Class(classes(factoryStyles.chartBody))],
            rows.map((row) => chatRow(row, h))
          ),
        ]
      ),
    ]
  );

const serverBody = (
  line: ChatsServerLineValue,
  rows: readonly ChatRowValue[],
  h: HtmlBuilder<AppMessage>
): readonly Html[] => {
  if (line.state === "not-connected") {
    return [
      h.p(
        [h.Class(classes(hubStyles.empty))],
        ["The inne server does not answer its read-only collector yet."]
      ),
    ];
  }

  return rows.length === 0
    ? [h.p([h.Class(classes(hubStyles.empty))], ["No live chats."])]
    : [chatsTable(rows, h)];
};

const serverSection = (
  line: ChatsServerLineValue,
  rows: readonly ChatRowValue[],
  h: HtmlBuilder<AppMessage>
): Html =>
  h.section(
    [h.Class(classes(hubStyles.section))],
    [
      h.h2([], [line.server]),
      h.p(
        [h.Class(classes(factoryStyles.small))],
        [
          line.state === "not-connected"
            ? "not connected yet"
            : `${rows.length} live ${rows.length === 1 ? "chat" : "chats"}`,
        ]
      ),
      ...serverBody(line, rows, h),
    ]
  );

export const chatsView = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  Option.match(model.chats, {
    onNone: () => [
      h.h1([], ["Chats"]),
      h.p([], ["No chat snapshot yet."]),
      h.p(
        [h.Class(classes(hubStyles.empty))],
        [
          "The collector writes one snapshot per run; the page reads the latest one.",
        ]
      ),
    ],
    onSome: (snapshot) => [
      h.h1([], ["Chats"]),
      h.p(
        [h.Class(classes(hubStyles.lede))],
        [
          "Every live chat on both factory servers, with the harness, model and effort each one runs.",
        ]
      ),
      updatedLine(snapshot, model.nowMs, h),
      ...snapshot.servers.map((line) =>
        serverSection(
          line,
          snapshot.chats.filter((chat) => chat.server === line.server),
          h
        )
      ),
    ],
  });
