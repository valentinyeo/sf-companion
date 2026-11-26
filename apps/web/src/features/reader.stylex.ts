import * as stylex from "@stylexjs/stylex";

import { reader } from "./tokens.stylex.js";

export const readerStyles = stylex.create({
  bounded: {
    marginInline: "auto",
    maxWidth: reader.contentWidth,
    width: "calc(100% - 2rem)",
  },
  header: { marginBlockEnd: reader.spaceSmall },
  wide: {
    display: "block",
    marginInline: "auto",
    maxWidth: "none",
    width: "calc(100% - 2rem)",
  },
  shell: {
    display: "contents",
    fontFamily: reader.fontFamily,
    fontSize: reader.fontSize,
    lineHeight: reader.lineHeight,
  },
});
