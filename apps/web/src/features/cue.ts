import * as stylex from "@stylexjs/stylex";
import type { Html, HtmlBuilder } from "foldkit/html";

import type { AppMessage } from "../client/app/message.js";
import { factoryStyles } from "./factory.stylex.js";

export type StateWord = "ok" | "bad" | "warm" | "hot";

export const classes = (
  ...styles: readonly (stylex.StyleXStyles | null)[]
): string =>
  stylex.props(
    ...styles.filter((style): style is stylex.StyleXStyles => style !== null)
  ).className ?? "";

const cueStyle = (word: StateWord): stylex.StyleXStyles => {
  if (word === "ok") {
    return factoryStyles.cueOk;
  }

  if (word === "bad") {
    return factoryStyles.cueBad;
  }

  return word === "warm" ? factoryStyles.cueWarm : factoryStyles.cueHot;
};

export const cue = (
  word: StateWord,
  label: string,
  h: HtmlBuilder<AppMessage>
): Html =>
  h.span([h.Class(classes(factoryStyles.cue, cueStyle(word)))], [label]);
