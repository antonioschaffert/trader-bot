import type { EquityCurvePoint } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";

interface Props {
  data: EquityCurvePoint[];
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  } catch {
    return dateStr;
  }
}

function formatCurrency(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${value.toFixed(2)}`;
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; dataKey: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const daily = payload.find((p) => p.dataKey === "daily_pnl");
  const cumulative = payload.find((p) => p.dataKey === "cumulative_pnl");
  return (
    <div className="rounded-lg border bg-background/95 px-3 py-2 text-xs shadow-md backdrop-blur">
      <p className="font-medium text-muted-foreground">{label}</p>
      {cumulative && (
        <p className={cumulative.value >= 0 ? "text-green-500" : "text-red-500"}>
          Cumulative: {formatCurrency(cumulative.value)}
        </p>
      )}
      {daily && (
        <p className={daily.value >= 0 ? "text-green-500" : "text-red-500"}>
          Daily: {formatCurrency(daily.value)}
        </p>
      )}
    </div>
  );
}

export function EquityCurve({ data }: Props) {
  if (data.length === 0) return null;

  const chartData = data.map((d) => ({
    ...d,
    date: formatDate(d.date),
  }));

  const maxVal = Math.max(...data.map((d) => Math.abs(d.cumulative_pnl)), 1);

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Equity Curve</span>
          <span className={`text-sm font-medium ${data[data.length - 1].cumulative_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
            {formatCurrency(data[data.length - 1].cumulative_pnl)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-green)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-green)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v}`}
              domain={[-maxVal * 0.1, "auto"]}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="var(--color-muted-foreground)" strokeDasharray="3 3" strokeOpacity={0.5} />
            <Bar
              dataKey="daily_pnl"
              fill="var(--color-chart-blue)"
              opacity={0.4}
              radius={[2, 2, 0, 0]}
              barSize={8}
            />
            <Area
              type="monotone"
              dataKey="cumulative_pnl"
              stroke="var(--color-chart-green)"
              strokeWidth={2}
              fill="url(#equityGrad)"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
