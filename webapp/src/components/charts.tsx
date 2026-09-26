import { type RefObject, useLayoutEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Tooltip,
  type TooltipContentProps,
  type TooltipValueType,
  XAxis,
  YAxis,
} from "recharts";
import { PALETTE_SIZE, seriesColor } from "../palette";
import type { Category, MemberStats } from "../types";

/** Width of the element, measured after layout and kept up to date. */
function useWidth(): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = () => setWidth(Math.floor(element.getBoundingClientRect().width));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** Current value of a theme CSS variable (charts are SVG attributes, not CSS). */
function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function ChartTooltip({ active, payload, label }: TooltipContentProps<TooltipValueType, string | number>) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((item) => Number(item.value) > 0);
  if (!rows.length) return null;
  return (
    <div className="tooltip">
      <div>
        <b>{label}</b>
      </div>
      {rows.map((item) => (
        <div className="row" key={String(item.dataKey)}>
          <span className="swatch" style={{ background: item.color }} />
          {item.name}: <b>{item.value}</b>
        </div>
      ))}
    </div>
  );
}

/** Horizontal stacked bars: chores per member, one segment per category. */
export function MemberChart({
  members,
  categories,
  scheme,
}: {
  members: MemberStats[];
  categories: Category[];
  scheme: "light" | "dark";
}) {
  const rows = members
    .filter((m) => m.done > 0)
    .map((m) => ({
      name: m.name,
      ...Object.fromEntries(categories.map((c) => [`c${c.id}`, m.by_category[c.id] ?? 0])),
    }));
  // Color follows the category's position in the room (fixed slots), never its rank.
  const series = categories
    .map((category, slot) => ({ category, slot: Math.min(slot, PALETTE_SIZE) }))
    .filter(({ category }) => members.some((m) => (m.by_category[category.id] ?? 0) > 0));
  const surface = cssVar("--surface", scheme === "dark" ? "#232322" : "#ffffff");
  const grid = cssVar("--separator", "#e1e0d9");
  const muted = cssVar("--muted", "#6f6e69");
  const [ref, width] = useWidth();
  const height = 70 + rows.length * 44;
  return (
    <div ref={ref} className="chart" style={{ height }}>
      {width > 0 && (
      <BarChart
        width={width}
        height={height}
        data={rows}
        layout="vertical"
        margin={{ top: 4, right: 12, bottom: 0, left: 0 }}
      >
        <CartesianGrid horizontal={false} stroke={grid} />
        <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: muted }} />
        <YAxis type="category" dataKey="name" width={88} tickLine={false} axisLine={false} tick={{ fill: muted }} />
        <Tooltip content={ChartTooltip} cursor={{ fill: grid, opacity: 0.35 }} />
        <Legend verticalAlign="top" height={32} iconType="square" iconSize={10} />
        {series.map(({ category, slot }, index) => (
          <Bar
            key={category.id}
            dataKey={`c${category.id}`}
            name={`${category.emoji} ${category.name}`}
            stackId="done"
            fill={seriesColor(slot, scheme)}
            stroke={surface}
            strokeWidth={2}
            barSize={20}
            radius={index === series.length - 1 ? [0, 4, 4, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
      )}
    </div>
  );
}

/** Columns: chores done per day of the month (a single series, so no legend). */
export function DailyChart({
  daily,
  label,
  scheme,
}: {
  daily: { day: string; done: number }[];
  label: string;
  scheme: "light" | "dark";
}) {
  const rows = daily.map((d) => ({ day: Number(d.day.slice(8, 10)), done: d.done }));
  const grid = cssVar("--separator", "#e1e0d9");
  const muted = cssVar("--muted", "#6f6e69");
  const [ref, width] = useWidth();
  return (
    <div ref={ref} className="chart" style={{ height: 180 }}>
      {width > 0 && (
      <BarChart width={width} height={180} data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke={grid} />
        <XAxis dataKey="day" tickLine={false} axisLine={{ stroke: grid }} tick={{ fill: muted }} minTickGap={6} />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: muted }} width={40} />
        <Tooltip content={ChartTooltip} cursor={{ fill: grid, opacity: 0.35 }} />
        <Bar
          dataKey="done"
          name={label}
          fill={seriesColor(0, scheme)}
          maxBarSize={14}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
      </BarChart>
      )}
    </div>
  );
}
