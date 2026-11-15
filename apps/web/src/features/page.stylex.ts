import * as stylex from "@stylexjs/stylex";

import { site } from "./tokens.stylex.js";

export const styles = stylex.create({
  actions: {
    alignItems: "center",
    display: "flex",
    gap: "0.75rem",
    marginTop: "2rem",
  },
  article: {
    maxWidth: "68ch",
  },
  back: {
    marginTop: "2rem",
  },
  branchList: {
    listStyle: "none",
    margin: "2rem 0 0",
    padding: 0,
  },
  button: {
    backgroundColor: site.surface,
    borderColor: site.border,
    borderRadius: "4px",
    borderStyle: "solid",
    borderWidth: "1px",
    color: site.text,
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: "0.875rem",
    paddingBlock: "0.375rem",
    paddingInline: "0.75rem",
  },
  empty: {
    color: site.muted,
    marginTop: "2rem",
  },
  entryList: {
    listStyle: "none",
    margin: "2rem 0 0",
    padding: 0,
  },
  footer: {
    borderTopColor: site.border,
    borderTopStyle: "solid",
    borderTopWidth: "1px",
    color: site.muted,
    fontSize: "0.875rem",
    marginTop: "4rem",
    paddingTop: "1rem",
  },
  header: {
    alignItems: "baseline",
    borderBottomColor: site.border,
    borderBottomStyle: "solid",
    borderBottomWidth: "1px",
    display: "flex",
    flexWrap: "wrap",
    gap: "1rem",
    justifyContent: "space-between",
    paddingBottom: "1rem",
  },
  lede: {
    color: site.muted,
    fontSize: "1.125rem",
    maxWidth: "60ch",
  },
  meta: {
    color: site.muted,
    fontSize: "0.875rem",
  },
  navList: {
    display: "flex",
    gap: "1rem",
    listStyle: "none",
    margin: 0,
    padding: 0,
  },
  prose: {
    lineHeight: 1.65,
    marginTop: "1.5rem",
  },
  row: {
    borderBottomColor: site.border,
    borderBottomStyle: "solid",
    borderBottomWidth: "1px",
    paddingBlock: "1rem",
  },
  rowTitle: {
    fontSize: "1.125rem",
    textDecorationLine: "none",
  },
  shell: {
    backgroundColor: site.background,
    color: site.text,
    marginInline: "auto",
    maxWidth: "80ch",
    paddingBlock: "2rem",
    paddingInline: "1.5rem",
  },
  summary: {
    color: site.muted,
    margin: "0.375rem 0",
  },
  wordmark: {
    fontWeight: 600,
    textDecorationLine: "none",
  },
});
