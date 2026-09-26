// Categorical palette (validated for adjacent stacks) in fixed slot order: a category keeps
// its color from month to month and matches the PNG charts of the bot. Separate steps for
// the dark theme, not an automatic inversion.
const LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
const OTHER = "#898781";

export function seriesColor(slot: number, scheme: "light" | "dark"): string {
  const colors = scheme === "dark" ? DARK : LIGHT;
  return colors[slot] ?? OTHER;
}

export const PALETTE_SIZE = LIGHT.length;
