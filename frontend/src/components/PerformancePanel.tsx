import type { AnalyticsData, PortfolioGreeksData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EquityCurve } from "@/components/EquityCurve";
import { PnlBySymbolChart } from "@/components/PnlBySymbolChart";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

interface Props {
  analytics: AnalyticsData | null;
  greeks: PortfolioGreeksData | null;
}

function formatCurrency(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${value.toFixed(2)}`;
}

function pnlColor(value: number): string {
  if (value > 0) return "text-green-500";
  if (value < 0) return "text-red-500";
  return "text-muted-foreground";
}

function metricColor(value: number, goodAbove: number, badBelow: number): string {
  if (value >= goodAbove) return "text-green-500";
  if (value <= badBelow) return "text-red-500";
  return "text-yellow-500";
}

function GreeksBarChart({ perSymbol }: { perSymbol: Record<string, Record<string, number>> }) {
  const symbols = Object.keys(perSymbol);
  if (symbols.length === 0) return null;

  const chartData = symbols.map((sym) => ({
    symbol: sym,
    delta: perSymbol[sym].delta ?? 0,
    theta: perSymbol[sym].theta ?? 0,
    vega: perSymbol[sym].vega ?? 0,
  }));

  return (
    <Card size="sm" className="md:col-span-2 xl:col-span-3">
      <CardHeader>
        <CardTitle>Greeks by Symbol</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="symbol"
              tick={{ fontSize: 11, fill: "var(--color-foreground)" }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-background)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value, name) => [Number(value).toFixed(2), String(name)]}
            />
            <Bar dataKey="delta" fill="var(--color-chart-blue)" barSize={10} radius={[0, 3, 3, 0]} name="Delta" />
            <Bar dataKey="theta" fill="var(--color-chart-green)" barSize={10} radius={[0, 3, 3, 0]} name="Theta" />
            <Bar dataKey="vega" fill="var(--color-chart-purple)" barSize={10} radius={[0, 3, 3, 0]} name="Vega" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function GreeksTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string; fill: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-background/95 px-3 py-2 text-xs shadow-md backdrop-blur">
      <p className="font-medium">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.fill }}>{p.name}: {p.value.toFixed(2)}</p>
      ))}
    </div>
  );
}

// Suppress unused for now -- GreeksTooltip is available for future use
void GreeksTooltip;

function DailyPnlMiniChart({ equityCurve }: { equityCurve: { date: string; daily_pnl: number }[] }) {
  const recent = equityCurve.slice(-14);
  if (recent.length === 0) return null;

  const data = recent.map((d) => ({
    date: (() => {
      try {
        const dt = new Date(d.date);
        return `${dt.getMonth() + 1}/${dt.getDate()}`;
      } catch {
        return d.date;
      }
    })(),
    pnl: d.daily_pnl,
  }));

  return (
    <ResponsiveContainer width="100%" height={100}>
      <BarChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `$${v}`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--color-background)",
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            fontSize: "11px",
          }}
          formatter={(value) => [formatCurrency(Number(value)), "P&L"]}
        />
        <Bar dataKey="pnl" radius={[2, 2, 0, 0]} barSize={12}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.pnl >= 0 ? "var(--color-chart-green)" : "var(--color-chart-red)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function PerformancePanel({ analytics, greeks }: Props) {
  if (!analytics && !greeks) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Performance & Greeks</h2>
        <Skeleton className="h-64 w-full rounded-xl" />
      </section>
    );
  }

  const hasEquityCurve = analytics && analytics.equity_curve && analytics.equity_curve.length > 0;
  const hasBySymbol = analytics && analytics.by_symbol && Object.keys(analytics.by_symbol).length > 0;
  const hasGreeksPerSymbol = greeks && Object.keys(greeks.per_symbol).length > 0;

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Performance & Greeks</h2>

      {/* Charts row */}
      {(hasEquityCurve || hasBySymbol) && (
        <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {hasEquityCurve && (
            <div className="lg:col-span-2">
              <EquityCurve data={analytics.equity_curve} />
            </div>
          )}
          {hasBySymbol && (
            <div>
              <PnlBySymbolChart bySymbol={analytics.by_symbol} />
            </div>
          )}
        </div>
      )}

      {/* Daily P&L mini chart */}
      {hasEquityCurve && (
        <div className="mb-4">
          <Card size="sm">
            <CardHeader>
              <CardTitle>Daily P&L (Last 14 Days)</CardTitle>
            </CardHeader>
            <CardContent>
              <DailyPnlMiniChart equityCurve={analytics.equity_curve} />
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {/* Key Metrics */}
        {analytics && analytics.total_trades > 0 && (
          <Card size="sm">
            <CardHeader>
              <CardTitle>Key Metrics (90d)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Total P&L</span>
                  <p className={`text-lg font-bold ${pnlColor(analytics.total_pnl)}`}>
                    {formatCurrency(analytics.total_pnl)}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Win Rate</span>
                  <p className={`text-lg font-bold ${metricColor(analytics.win_rate, 60, 40)}`}>
                    {analytics.win_rate.toFixed(0)}%
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Sharpe Ratio</span>
                  <p className={`font-medium ${metricColor(analytics.sharpe_ratio, 1.5, 0.5)}`}>
                    {analytics.sharpe_ratio.toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Profit Factor</span>
                  <p className={`font-medium ${metricColor(analytics.profit_factor, 1.5, 1.0)}`}>
                    {analytics.profit_factor === Infinity ? "Inf" : analytics.profit_factor.toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Expectancy</span>
                  <p className={`font-medium ${pnlColor(analytics.expectancy)}`}>
                    {formatCurrency(analytics.expectancy)}/trade
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Sortino</span>
                  <p className="font-medium">{analytics.sortino_ratio.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Trades</span>
                  <p className="font-medium">{analytics.total_trades}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Avg Duration</span>
                  <p className="font-medium">{analytics.avg_trade_duration_hours.toFixed(0)}h</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Rolling Performance */}
        {analytics && analytics.total_trades > 0 && (
          <Card size="sm">
            <CardHeader>
              <CardTitle>Rolling Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b pb-2">
                  <span className="text-sm font-medium">7 Day</span>
                  <div className="text-right text-sm">
                    <span className={pnlColor(analytics.pnl_7d)}>{formatCurrency(analytics.pnl_7d)}</span>
                    <span className="ml-2 text-muted-foreground">
                      {analytics.trades_7d} trades, {analytics.win_rate_7d.toFixed(0)}% win
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between border-b pb-2">
                  <span className="text-sm font-medium">30 Day</span>
                  <div className="text-right text-sm">
                    <span className={pnlColor(analytics.pnl_30d)}>{formatCurrency(analytics.pnl_30d)}</span>
                    <span className="ml-2 text-muted-foreground">
                      {analytics.trades_30d} trades, {analytics.win_rate_30d.toFixed(0)}% win
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between border-b pb-2">
                  <span className="text-sm font-medium">Best Day</span>
                  <span className={`text-sm ${pnlColor(analytics.best_day)}`}>{formatCurrency(analytics.best_day)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Worst Day</span>
                  <span className={`text-sm ${pnlColor(analytics.worst_day)}`}>{formatCurrency(analytics.worst_day)}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Portfolio Greeks */}
        {greeks && (
          <Card size="sm">
            <CardHeader>
              <CardTitle>Portfolio Greeks</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Net Delta</span>
                  <p className={`font-medium ${Math.abs(greeks.net_delta) > 50 ? "text-red-500" : ""}`}>
                    {greeks.net_delta > 0 ? "+" : ""}{greeks.net_delta.toFixed(1)}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Net Gamma</span>
                  <p className="font-medium">{greeks.net_gamma.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Net Theta</span>
                  <p className={`font-medium ${greeks.net_theta > 0 ? "text-green-500" : "text-red-500"}`}>
                    {formatCurrency(greeks.net_theta)}/day
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Net Vega</span>
                  <p className="font-medium">{greeks.net_vega.toFixed(1)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Premium at Risk</span>
                  <p className="font-medium text-red-500">${greeks.total_premium_at_risk.toFixed(0)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Theta/Delta</span>
                  <p className="font-medium">{greeks.theta_to_delta_ratio.toFixed(2)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Greeks Bar Chart */}
        {hasGreeksPerSymbol && (
          <GreeksBarChart perSymbol={greeks.per_symbol} />
        )}

        {/* Strategy Breakdown */}
        {analytics && analytics.by_strategy && analytics.by_strategy.length > 0 && (
          <Card size="sm" className="md:col-span-2 xl:col-span-3">
            <CardHeader>
              <CardTitle>Strategy Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Trades</TableHead>
                    <TableHead>Win Rate</TableHead>
                    <TableHead>P&L</TableHead>
                    <TableHead>Avg Win</TableHead>
                    <TableHead>Avg Loss</TableHead>
                    <TableHead>Profit Factor</TableHead>
                    <TableHead>Expectancy</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analytics.by_strategy.map((s) => (
                    <TableRow key={s.strategy}>
                      <TableCell>
                        <Badge variant="outline">{s.strategy}</Badge>
                      </TableCell>
                      <TableCell>{s.total_trades}</TableCell>
                      <TableCell className={metricColor(s.win_rate, 60, 40)}>
                        {s.win_rate.toFixed(0)}%
                      </TableCell>
                      <TableCell className={pnlColor(s.total_pnl)}>
                        {formatCurrency(s.total_pnl)}
                      </TableCell>
                      <TableCell className="text-green-500">{formatCurrency(s.avg_win)}</TableCell>
                      <TableCell className="text-red-500">{formatCurrency(s.avg_loss)}</TableCell>
                      <TableCell>{s.profit_factor === Infinity ? "Inf" : s.profit_factor.toFixed(2)}</TableCell>
                      <TableCell className={pnlColor(s.expectancy)}>
                        {formatCurrency(s.expectancy)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </section>
  );
}
