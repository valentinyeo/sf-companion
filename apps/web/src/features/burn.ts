import { Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import { rankBurn, selectedBurnRows } from "../content/burn.js";
import type { BurnReportValue, BurnSelectionValue } from "../content/burn.js";
import { classes } from "./cue.js";
import { factoryStyles } from "./factory.stylex.js";
import { usageRouter } from "./route.js";

const RANGES = [
  { key: "24h", name: "24h" },
  { key: "7d", name: "7d" },
  { key: "week", name: "This plan week" },
  { key: "custom", name: "Custom" },
] satisfies readonly { key: BurnSelectionValue["range"]; name: string }[];

const numberText = (value: number): string =>
  new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format(value);

const unpricedNote = (
  group: ReturnType<typeof rankBurn>[number],
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  group.unpricedRequests > 0 && group.listCostUsd !== null
    ? [
        h.p(
          [],
          [
            `${numberText(group.unpricedRequests)} of ${numberText(group.requests)} requests unpriced`,
          ]
        ),
      ]
    : [];

const picker = (
  selection: BurnSelectionValue,
  h: HtmlBuilder<AppMessage>
): Html =>
  h.div(
    [h.Role("group"), h.AriaLabel("Burn range")],
    RANGES.map(({ key, name }) =>
      h.button(
        [
          h.Type("button"),
          h.AriaPressed(String(selection.range === key)),
          h.OnClick(Message.SelectedBurnRange({ range: key })),
        ],
        [name]
      )
    )
  );

const ranking = (
  title: string,
  groups: ReturnType<typeof rankBurn>,
  level: "plan" | "chat" | "ticket",
  h: HtmlBuilder<AppMessage>
): Html => {
  const total = groups.reduce((sum, group) => sum + group.weight, 0);

  const cell = (value: string): Html =>
    h.td(
      [h.Class(classes(factoryStyles.chartCell, factoryStyles.burnCell))],
      [value]
    );

  return h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], [title]),
      ...(groups.length === 0
        ? [h.p([], ["No recorded usage in this selection."])]
        : [
            h.div(
              [h.Class(classes(factoryStyles.chartScroll))],
              [
                h.table(
                  [
                    h.Class(
                      classes(factoryStyles.chartTable, factoryStyles.burnTable)
                    ),
                  ],
                  [
                    h.caption(
                      [],
                      [
                        "Ranked by known list-equivalent cost, not raw tokens. Share is of priced usage only; a note names the requests still unpriced.",
                      ]
                    ),
                    h.thead(
                      [h.Class(classes(factoryStyles.chartHead))],
                      [
                        h.tr(
                          [],
                          [
                            "Name",
                            "Share",
                            "Input",
                            "Output",
                            "Cache read",
                            "Cache write",
                            "Requests",
                            "List-equivalent USD",
                          ].map((name) =>
                            h.th(
                              [
                                h.Scope("col"),
                                h.Class(
                                  classes(
                                    factoryStyles.chartCell,
                                    factoryStyles.burnCell
                                  )
                                ),
                              ],
                              [name]
                            )
                          )
                        ),
                      ]
                    ),
                    h.tbody(
                      [],
                      groups.map((group) =>
                        h.tr(
                          [],
                          [
                            h.th(
                              [
                                h.Scope("row"),
                                h.Class(
                                  classes(
                                    factoryStyles.chartCell,
                                    factoryStyles.burnCell
                                  )
                                ),
                              ],
                              [
                                ...(level === "ticket"
                                  ? [group.name]
                                  : [
                                      h.button(
                                        [
                                          h.Type("button"),
                                          h.AriaLabel(
                                            `Show ${level === "plan" ? "chats for" : "tickets for"} ${group.name}`
                                          ),
                                          h.OnClick(
                                            level === "plan"
                                              ? Message.SelectedBurnPlan({
                                                  plan: group.key,
                                                })
                                              : Message.SelectedBurnChat({
                                                  chatId: group.key,
                                                })
                                          ),
                                        ],
                                        [group.name]
                                      ),
                                    ]),
                                ...(group.tokensKnown
                                  ? []
                                  : [
                                      h.p(
                                        [],
                                        [
                                          "Includes requests without token counts",
                                        ]
                                      ),
                                    ]),
                                ...unpricedNote(group, h),
                              ]
                            ),
                            cell(
                              total > 0 && group.listCostUsd !== null
                                ? `${((100 * group.weight) / total).toFixed(1)}%`
                                : "Unknown"
                            ),
                            ...[
                              group.input,
                              group.output,
                              group.cacheRead,
                              group.cacheWrite,
                            ].map((value) =>
                              cell(
                                group.tokensKnown
                                  ? numberText(value)
                                  : `${numberText(value)} known`
                              )
                            ),
                            cell(numberText(group.requests)),
                            cell(
                              group.listCostUsd === null
                                ? "Unknown"
                                : `$${group.listCostUsd.toFixed(2)}`
                            ),
                          ]
                        )
                      )
                    ),
                  ]
                ),
              ]
            ),
          ]),
    ]
  );
};

const paidKeys = (
  report: BurnReportValue,
  selection: BurnSelectionValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const usage = report.keyUsage ?? [];

  const selected = new Set(
    selectedBurnRows(
      { ...report, rows: usage.map((item) => item.row) },
      { ...selection, plan: "" },
      24
    )
  );

  const items = usage.filter((item) => selected.has(item.row));

  const groups = rankBurn(
    items.map((item) => item.row),
    "plan"
  )
    .map((group) => {
      const entries = items.filter((item) => group.rows.includes(item.row));

      return {
        ...group,
        billedCostUsd: entries.every((item) => item.billedCostUsd !== null)
          ? entries.reduce((sum, item) => sum + (item.billedCostUsd ?? 0), 0)
          : null,
      };
    })
    .toSorted(
      (left, right) =>
        (right.billedCostUsd ?? 0) - (left.billedCostUsd ?? 0) ||
        left.key.localeCompare(right.key)
    );

  const cell = (value: string): Html =>
    h.td(
      [h.Class(classes(factoryStyles.chartCell, factoryStyles.burnCell))],
      [value]
    );

  return h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], ["Paid keys · provider totals"]),
      h.p(
        [],
        [
          "Separate from the chat totals below, never added to them. Ranked by reported charge. Provider APIs report whole UTC days; a range includes each intersecting day. API totals can include other servers and callers. See Coverage and limits for unavailable or stale sources.",
        ]
      ),
      ...(groups.length === 0
        ? [h.p([], ["No provider API totals available in this range."])]
        : [
            h.div(
              [h.Class(classes(factoryStyles.chartScroll))],
              [
                h.table(
                  [
                    h.Class(
                      classes(factoryStyles.chartTable, factoryStyles.burnTable)
                    ),
                  ],
                  [
                    h.caption(
                      [],
                      [
                        "Provider totals have no chat attribution. Charges are not list-equivalent cost or subscription fees.",
                      ]
                    ),
                    h.thead(
                      [h.Class(classes(factoryStyles.chartHead))],
                      [
                        h.tr(
                          [],
                          [
                            "Plan or key",
                            "Requests",
                            "Input",
                            "Output",
                            "Cache read",
                            "Cache write",
                            "Reported charge USD",
                            "List-equivalent USD",
                          ].map((name) =>
                            h.th(
                              [
                                h.Scope("col"),
                                h.Class(
                                  classes(
                                    factoryStyles.chartCell,
                                    factoryStyles.burnCell
                                  )
                                ),
                              ],
                              [name]
                            )
                          )
                        ),
                      ]
                    ),
                    h.tbody(
                      [],
                      groups.map((group) =>
                        h.tr(
                          [],
                          [
                            h.th(
                              [
                                h.Scope("row"),
                                h.Class(
                                  classes(
                                    factoryStyles.chartCell,
                                    factoryStyles.burnCell
                                  )
                                ),
                              ],
                              [group.name, ...unpricedNote(group, h)]
                            ),
                            cell(numberText(group.requests)),
                            ...[
                              group.input,
                              group.output,
                              group.cacheRead,
                              group.cacheWrite,
                            ].map((value) =>
                              cell(
                                group.tokensKnown
                                  ? numberText(value)
                                  : "Unknown"
                              )
                            ),
                            cell(
                              group.billedCostUsd === null
                                ? "Unknown"
                                : `$${group.billedCostUsd.toFixed(2)}`
                            ),
                            cell(
                              group.listCostUsd === null
                                ? "Unknown"
                                : `$${group.listCostUsd.toFixed(2)}`
                            ),
                          ]
                        )
                      )
                    ),
                  ]
                ),
              ]
            ),
          ]),
    ]
  );
};

const reportView = (
  report: BurnReportValue,
  selection: BurnSelectionValue,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => {
  const rows = selectedBurnRows(report, selection);

  const chatRows =
    selection.chatId === ""
      ? rows
      : rows.filter((row) => row.chatId === selection.chatId);

  const planRows = selectedBurnRows(report, { ...selection, plan: "" });

  const customInvalid =
    selection.range === "custom" &&
    (!Number.isFinite(Date.parse(selection.start)) ||
      !Number.isFinite(Date.parse(selection.end)) ||
      selection.start > selection.end);

  const activeChat = rows.find((row) => row.chatId === selection.chatId);

  return [
    h.p([], [`Updated ${report.generatedAt}. Refreshed hourly.`]),
    picker(selection, h),
    ...(selection.range === "custom"
      ? [
          h.div(
            [],
            [
              h.label(
                [],
                [
                  "From (UTC) ",
                  h.input([
                    h.Type("date"),
                    h.AriaLabel("From (UTC)"),
                    h.Value(selection.start),
                    h.OnInput((value) => Message.ChangedBurnStart({ value })),
                  ]),
                ]
              ),
              h.label(
                [],
                [
                  "Through (UTC) ",
                  h.input([
                    h.Type("date"),
                    h.AriaLabel("Through (UTC)"),
                    h.Value(selection.end),
                    h.OnInput((value) => Message.ChangedBurnEnd({ value })),
                  ]),
                ]
              ),
            ]
          ),
          ...(customInvalid
            ? [
                h.p(
                  [h.Role("status")],
                  [
                    "Choose a start and end date, with the end on or after the start.",
                  ]
                ),
              ]
            : []),
        ]
      : []),
    h.p(
      [],
      [
        "UTC hourly buckets, including the boundary hour. Custom dates include the whole end date. Ranges end at the last export, not the browser clock.",
      ]
    ),
    h.details(
      [],
      [
        h.summary([], ["Coverage and limits"]),
        h.p(
          [],
          [
            "Rankings use each model's list-equivalent price for input, output, cache reads and cache writes. Shares cover priced usage only, not provider quota. Unpriced usage stays unknown.",
          ]
        ),
        h.p(
          [],
          [
            "Ticket labels come from worker receipts or the most-mentioned ticket in assistant text that hour (inferred). No message text is exported.",
          ]
        ),
        h.ul(
          [],
          report.notes.map((note) => h.li([], [note]))
        ),
        h.p(
          [],
          [
            report.rows.length === 0
              ? "No history recorded."
              : `Recorded history: ${report.rows.at(0)?.hour ?? "unknown"} through ${report.rows.at(-1)?.hour ?? "unknown"}.`,
          ]
        ),
      ]
    ),
    ...(selection.range === "week"
      ? [
          h.details(
            [h.Open(true)],
            [
              h.summary([], ["Plan week boundaries"]),
              h.ul(
                [],
                report.plans.map((plan) =>
                  h.li(
                    [],
                    [
                      plan.weekStartsAt === null || plan.weekResetsAt === null
                        ? `${plan.plan}: reset time unavailable; excluded from this plan week.`
                        : `${plan.plan}: ${plan.weekStartsAt} to ${plan.weekResetsAt}`,
                    ]
                  )
                )
              ),
            ]
          ),
        ]
      : []),
    paidKeys(report, selection, h),
    ranking("Plans and accounts / keys", rankBurn(planRows, "plan"), "plan", h),
    h.p(
      [],
      [
        selection.plan === "" ? "Showing all plans" : selection.plan,
        " · ",
        h.button(
          [h.Type("button"), h.OnClick(Message.SelectedBurnPlan({ plan: "" }))],
          ["All plans"]
        ),
      ]
    ),
    ranking("Chats", rankBurn(rows, "chat"), "chat", h),
    h.p(
      [],
      [
        activeChat === undefined ? "Showing all chats" : activeChat.chat,
        " · ",
        h.button(
          [
            h.Type("button"),
            h.OnClick(Message.SelectedBurnChat({ chatId: "" })),
          ],
          ["All chats"]
        ),
      ]
    ),
    ranking("Tickets", rankBurn(chatRows, "ticket"), "ticket", h),
  ];
};

export const burnView = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => [
  h.h1([], ["Where did the tokens go?"]),
  h.p([], [h.a([h.Href(usageRouter())], ["Back to Usage"])]),
  ...Option.match(model.feed, {
    onNone: () => [
      h.p([], ["No burn report yet. The hourly feed will populate it."]),
    ],
    onSome: (feed) =>
      feed.usage.report === undefined
        ? [h.p([], ["No burn report yet. The hourly feed will populate it."])]
        : reportView(feed.usage.report, model.burn, h),
  }),
];
