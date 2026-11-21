"use client";

import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Detail, Forecast, pct } from "./api";

const colors = ["#141414", "#737373", "#a3a3a3", "#525252", "#b5b5b5", "#333333"];
const dateTick = (date: string) => date.slice(5);
const axis = { stroke: "#a3a3a3", tick: { fontSize: 11, fill: "#737373" }, tickLine: false, axisLine: false };

export function ProbabilityChart({ event, markDecision = false }: { event: Detail; markDecision?: boolean }) {
  const dates: Record<string, Record<string, string | number>> = {};
  const outcomes = Object.keys(event.history);
  outcomes.forEach((outcome, index) => event.history[outcome].forEach(p => { (dates[p.date] ||= { date: p.date })[`p${index}`] = p.market_probability; }));
  const points = Object.values(dates).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (!points.length) return <p className="state">No probability observations available.</p>;
  return <div className="chart" role="img" aria-label="Daily market probability history by outcome"><ResponsiveContainer width="100%" height="100%"><LineChart data={markDecision ? points.map(p => ({ ...p, date: Date.parse(String(p.date)) })) : points} margin={{ top: markDecision ? 26 : 8, right: 12, bottom: 0, left: -16 }}><CartesianGrid vertical={false} stroke="#e8e8e8" strokeDasharray="3 3" /><XAxis dataKey="date" type={markDecision ? "number" : "category"} scale={markDecision ? "time" : "auto"} domain={markDecision ? [Math.min(Date.parse(String(points[0].date)), Date.parse(event.meeting_date)), Math.max(Date.parse(String(points[points.length - 1].date)), Date.parse(event.meeting_date))] : undefined} minTickGap={60} tickFormatter={value => dateTick(markDecision ? new Date(Number(value)).toISOString().slice(0, 10) : String(value))} {...axis} /><YAxis domain={[0, 1]} tickFormatter={v => pct(v, 0)} {...axis} />{markDecision && <ReferenceLine x={Date.parse(event.meeting_date)} stroke="#525252" strokeDasharray="4 3" label={{ value: `Decision ${event.meeting_date}`, position: "insideTopRight", fontSize: 11, fill: "#525252" }} />}<Tooltip labelFormatter={value => markDecision ? new Date(Number(value)).toISOString().slice(0, 10) : String(value)} formatter={(value) => pct(Number(value))} contentStyle={{ border: "1px solid #ddd", fontSize: 12 }} /><Legend iconType="plainline" wrapperStyle={{ fontSize: 11, paddingTop: 12 }} />{outcomes.map((outcome, i) => <Line key={outcome} name={outcome} dataKey={`p${i}`} stroke={colors[i % colors.length]} strokeDasharray={i > 1 ? `${i + 2} 3` : undefined} strokeWidth={i === 0 ? 2 : 1.5} dot={false} connectNulls={false} isAnimationActive={false} />)}</LineChart></ResponsiveContainer></div>;
}

export function ForecastChart({ forecast }: { forecast: Forecast }) {
  const day = 24 * 60 * 60 * 1000;
  const points: { timestamp: number; realized: number | null; baseline: number | null; augmented: number | null }[] = [];
  forecast.series.forEach((point, i) => {
    const timestamp = Date.parse(point.date);
    const previous = forecast.series[i - 1];
    if (previous && timestamp - Date.parse(previous.date) > 10 * day) {
      points.push({ timestamp: Date.parse(previous.date) + day, realized: null, baseline: null, augmented: null });
    }
    points.push({ timestamp, realized: point.realized * 10000, baseline: point.baseline * 10000, augmented: point.augmented * 10000 });
  });
  if (!points.length) return <p className="state">No forecasts available.</p>;
  const monthYear = (value: number) => new Date(value).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
  const variance = (value: number) => value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return <div className="chart forecast-chart" role="img" aria-label="Out-of-sample forecast versus realized horizon variance in percentage points squared"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 20, right: 10, left: 8 }}><CartesianGrid vertical={false} stroke="#e8e8e8" strokeDasharray="3 3" /><XAxis dataKey="timestamp" type="number" scale="time" domain={["dataMin", "dataMax"]} minTickGap={55} tickFormatter={monthYear} {...axis} /><YAxis tickFormatter={v => Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })} width={72} label={{ value: "Variance (pp²)", position: "top", offset: 8, fontSize: 11, fill: "#737373" }} {...axis} /><Tooltip labelFormatter={value => new Date(Number(value)).toISOString().slice(0, 10)} formatter={v => `${variance(Number(v))} pp²`} contentStyle={{ fontSize: 12, border: "1px solid #ddd" }} /><Legend iconType="plainline" wrapperStyle={{ fontSize: 11 }} /><Line name="Realized RV" dataKey="realized" stroke="#c4c4c4" dot={false} strokeWidth={1} connectNulls={false} isAnimationActive={false} /><Line name="Baseline" dataKey="baseline" stroke="#111" dot={false} strokeWidth={1.5} connectNulls={false} isAnimationActive={false} /><Line name="Augmented" dataKey="augmented" stroke="#777" strokeDasharray="4 3" dot={false} strokeWidth={1.5} connectNulls={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>;
}

export function ReturnHistogram({ returns }: { returns: number[] }) {
  const sorted = [...returns].sort((a, b) => a - b);
  const min = sorted[0] || 0;
  const span = (sorted.at(-1) || 0) - min || .01;
  const bins = Array.from({ length: 36 }, (_, i) => ({ x: min + (i + .5) * span / 36, regular: 0, tail: 0 }));
  sorted.forEach((v, i) => { const bin = bins[Math.min(35, Math.floor((v - min) / span * 36))]; bin[i < sorted.length * .05 ? "tail" : "regular"]++; });
  return <div className="chart" role="img" aria-label="Simulated portfolio return histogram; darkest bars show worst five percent"><ResponsiveContainer width="100%" height="100%"><BarChart data={bins} barCategoryGap={1} margin={{ right: 8, left: -16 }}><CartesianGrid vertical={false} stroke="#eee" /><XAxis dataKey="x" type="number" domain={[min, min + span]} tickFormatter={v => pct(v, 1)} {...axis} /><YAxis {...axis} /><Tooltip labelFormatter={v => `Return ${pct(Number(v))}`} contentStyle={{ fontSize: 12 }} /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar name="Worst 5%" dataKey="tail" stackId="returns" fill="#111" isAnimationActive={false} /><Bar name="Other scenarios" dataKey="regular" stackId="returns" fill="#d4d4d4" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>;
}
