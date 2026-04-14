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

export function PerformancePanel({ analytics, greeks }: Props) {
  if (!analytics && !greeks) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Performance & Greeks</h2>
        <Skeleton className="h-64 w-full rounded-xl" />
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Performance & Greeks</h2>
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
              {/* Per-symbol breakdown */}
              {Object.keys(greeks.per_symbol).length > 0 && (
                <div className="mt-3 border-t pt-2">
                  <span className="text-xs text-muted-foreground">Per Symbol</span>
                  {Object.entries(greeks.per_symbol).map(([sym, g]) => (
                    <div key={sym} className="mt-1 flex items-center justify-between text-xs">
                      <span className="font-medium">{sym}</span>
                      <span>
                        D:{g.delta?.toFixed(0)} G:{g.gamma?.toFixed(2)} T:{g.theta?.toFixed(1)} V:{g.vega?.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
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
