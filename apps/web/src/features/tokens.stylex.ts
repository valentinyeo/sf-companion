import * as stylex from "@stylexjs/stylex";

const DARK = "@media (prefers-color-scheme: dark)";

export const accent = stylex.defineVars({
  accent: "#ff1493",
  accentText: { default: "#c8006e", [DARK]: "#f5c2e7" },
});

export const reader = stylex.defineVars({
  codeHighlight: { default: "#e6e9ef", [DARK]: "#313244" },
  codeInk: { default: "#4c4f69", [DARK]: "#bac2de" },
  codeKeyword: { default: "#303446", [DARK]: "#cdd6f4" },
  codeLiteral: { default: "#5c5f77", [DARK]: "#a6adc8" },
  codeMuted: { default: "#6c6f85", [DARK]: "#9399b2" },
  contentWidth: "80ch",
  fontBig: "1.5rem",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  fontSize: "16px",
  fontLabel: "0.625rem",
  fontSmall: "0.875rem",
  fontTiny: "0.75rem",
  lineHeight: "1.5",
  spaceSection: "2rem",
  spaceSmall: "0.75rem",
  spaceTight: "0.375rem",
});

export const surface = stylex.defineVars({
  line: { default: "#ccd0da", [DARK]: "#45475a" },
  muted: { default: "#6c6f85", [DARK]: "#a6adc8" },
  radius: "0.25rem",
  wash: { default: "#eff1f5", [DARK]: "#313244" },
});

export const state = stylex.defineVars({
  bad: { default: "#a4161a", [DARK]: "#f38ba8" },
  hot: { default: "#7f1d1d", [DARK]: "#eba0ac" },
  ok: { default: "#2d6a4f", [DARK]: "#a6e3a1" },
  warm: { default: "#8d5a00", [DARK]: "#f9e2af" },
});
