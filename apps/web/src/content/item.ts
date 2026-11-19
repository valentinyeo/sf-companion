import { Schema } from "effect";

export const Section = Schema.Literals(["explorations", "reports"]);

export type SectionValue = typeof Section.Type;

export const SECTION_PREFIX: Readonly<Record<SectionValue, string>> = {
  explorations: "x/",
  reports: "r/",
};

export const Item = Schema.Struct({
  date: Schema.String,
  project: Schema.String,
  section: Section,
  slug: Schema.NonEmptyString,
  title: Schema.NonEmptyString,
});

export type ItemValue = typeof Item.Type;

export const titleFromSlug = (slug: string): string => {
  const stem = slug
    .replace(/^[0-9a-f]{8}-/u, "")
    .replace(/\.[A-Za-z0-9]{1,5}$/u, "");

  const words = stem.replaceAll(/[-_.]+/gu, " ").trim();

  return words === "" ? slug : words.slice(0, 1).toUpperCase() + words.slice(1);
};

export const itemOf = (
  section: SectionValue,
  slug: string,
  metadata: Readonly<Record<string, string>>,
  uploaded: string
): ItemValue => {
  const date = metadata.date ?? "";

  return {
    date: /^\d{4}-\d{2}-\d{2}$/u.test(date) ? date : uploaded.slice(0, 10),
    project: metadata.project ?? "",
    section,
    slug,
    title: metadata.title ?? titleFromSlug(slug),
  };
};

export const itemsIn = (
  items: readonly ItemValue[],
  section: SectionValue
): readonly ItemValue[] => items.filter((item) => item.section === section);

export const sortListed = (
  listed: readonly { readonly item: ItemValue; readonly uploaded: string }[]
): readonly ItemValue[] =>
  listed
    .toSorted(
      (left, right) =>
        right.item.date.localeCompare(left.item.date) ||
        right.uploaded.localeCompare(left.uploaded)
    )
    .map((entry) => entry.item);
