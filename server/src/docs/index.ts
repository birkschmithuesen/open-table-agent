import { readFileSync } from "node:fs";

export const DOC_TOPICS: readonly string[] = [
  "automation.api", "automation.send-email", "automation.trigger",
  "field.basic", "field.colors", "field.formatting", "field.formula", "field.link", "field.lookup",
  "field.rollup", "field.select", "field.show-as", "field.simple",
  "integration.slack", "record.value-format", "reference.url",
  "scrape.datasets", "scrape.guide",
  "view.column", "view.filter", "view.group", "view.sort", "view.statistic",
];

export function readDoc(topic: string): string {
  if (!DOC_TOPICS.includes(topic)) throw new Error(`Unknown doc topic: ${topic}`);
  return readFileSync(new URL(`../../docs-bundle/${topic}.md`, import.meta.url), "utf8");
}
