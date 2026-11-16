import * as stylex from "@stylexjs/stylex";

export const accent = stylex.defineVars({
  accent: "#ff1493",
  accentText: "#c8006e",
});

export const reader = stylex.defineVars({
  codeHighlight: "#e6e9ef",
  codeInk: "#4c4f69",
  codeKeyword: "#303446",
  codeLiteral: "#5c5f77",
  codeMuted: "#6c6f85",
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
  line: "#ccd0da",
  muted: "#6c6f85",
  radius: "0.25rem",
  wash: "#eff1f5",
});

export const state = stylex.defineVars({
  bad: "#a4161a",
  hot: "#7f1d1d",
  ok: "#2d6a4f",
  warm: "#8d5a00",
});
