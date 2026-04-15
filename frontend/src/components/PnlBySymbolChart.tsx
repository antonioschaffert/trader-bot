import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";

interface Props {
  bySymbol: Record<string, { trades: number; pnl: number; win_rate: number }>;
}

const COLORS = [
  "var(--color-chart-blue)",
  "var(--color-chart-green)",
  "var(--color-chart-amber)",
  "var(--color-chart-purple)",
  "var(--color-chart-red)",
  "var(--color-chart-1)",
  "var(--color-chart-2)",
];

function formatCurrency(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${value.toFixed(2)}`;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: { payload: { name: string; pnl: number; trades: number; win_rate: number } }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border bg-background/95 px-3 py-2 text-xs shadow-md backdrop-blur">
      <p className="font-medium">{d.name}</p>
      <p className={d.pnl >= 0 ? "text-green-500" : "text-red-500"}>
        P&L: {formatCurrency(d.pnl)}
      </p>
      <p className="text-muted-foreground">{d.trades} trades, {d.win_rate.toFixed(0)}% win</p>
    </div>
  );
}

export function PnlBySymbolChart({ bySymbol }: Props) {
  const entries = Object.entries(bySymbol);
  if (entries.length === 0) return null;

  const chartData = entries.map(([symbol, data]) => ({
    name: symbol,
    value: Math.abs(data.pnl),
    pnl: data.pnl,
    trades: data.trades,
    win_rate: data.win_rate,
  }));

  const totalPnl = entries.reduce((sum, [, d]) => sum + d.pnl, 0);

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>P&L by Symbol</span>
          <span className={`text-sm font-medium ${totalPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
            {formatCurrency(totalPnl)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                  stroke="var(--color-background)"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(value: string) => (
                <span className="text-xs text-foreground">{value}</span>
              )}
              iconSize={8}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
