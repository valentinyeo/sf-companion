import * as stylex from "@stylexjs/stylex";

import { reader, surface } from "./tokens.stylex.js";

export const hubStyles = stylex.create({
  empty: {
    color: surface.muted,
    marginBlock: reader.spaceSmall,
  },
  heading: {
    alignItems: "baseline",
    display: "flex",
    flexWrap: "wrap",
    gap: "0.5rem 2ch",
    justifyContent: "space-between",
    marginBlockEnd: reader.spaceSmall,
  },
  lede: {
    color: surface.muted,
    marginBlockEnd: reader.spaceSection,
  },
  meta: {
    color: surface.muted,
    fontSize: "0.875rem",
    minWidth: 0,
    overflowWrap: "anywhere",
  },
  row: {
    alignItems: "baseline",
    borderBlockEnd: `1px solid ${surface.line}`,
    display: "grid",
    gap: "0.25rem 2ch",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    paddingBlock: reader.spaceSmall,
  },
  rows: {
    listStyle: "none",
    margin: 0,
    padding: 0,
  },
  section: {
    marginBlockEnd: reader.spaceSection,
  },
  title: {
    minWidth: 0,
    overflowWrap: "anywhere",
  },
});
