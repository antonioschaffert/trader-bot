import type { TradesResponse, OrderLog, EquityCurvePoint } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
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
import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";

interface Props {
  data: TradesResponse | null;
  orderLogs: OrderLog[] | null;
  equityCurve?: EquityCurvePoint[];
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

function field(row: Record<string, unknown>, key: string): string {
  const v = row[key];
  if (v == null) return "--";
  if (typeof v === "number") return v.toFixed(2);
  return String(v);
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Determine if this is a sell/open action (selling premium) or a buy/close action */
function isOpenAction(action: string): boolean {
  return action === "open" || action === "wheel_open";
}

function DailyPnlChart({ equityCurve }: { equityCurve: EquityCurvePoint[] }) {
  const recent = equityCurve.slice(-7);
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
    <ResponsiveContainer width="100%" height={80}>
      <BarChart data={data} margin={{ top: 5, right: 0, left: -15, bottom: 0 }}>
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
        <Bar dataKey="pnl" radius={[3, 3, 0, 0]} barSize={16}>
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.pnl >= 0 ? "var(--color-chart-green)" : "var(--color-chart-red)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ActivityStream({ logs }: { logs: OrderLog[] }) {
  if (logs.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">No order activity yet.</p>;
  }

  return (
    <div className="space-y-2">
      {logs.map((log) => {
        const signal = log.signal ?? {};
        const symbol = log.symbol || String(signal.symbol ?? "--");
        const strategy = String(signal.strategy_mode ?? signal.phase ?? "");
        const premium = signal.target_premium != null ? `$${Number(signal.target_premium).toFixed(2)}` : "";
        const spread = signal.spread_type ? String(signal.spread_type) : "";
        const strike = signal.strike_price ? `$${Number(signal.strike_price).toFixed(0)}` : "";
        const exp = signal.expiration ? String(signal.expiration) : "";
        const open = isOpenAction(log.action);

        // Build detail string
        const parts = [spread, strike, premium, exp].filter(Boolean);
        const detail = parts.join(" | ") || (log.limit_price ? `@ $${log.limit_price.toFixed(2)}` : "");

        return (
          <div
            key={log._id}
            className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 sm:px-4 sm:py-3 ${
              open
                ? "border-l-4 border-l-green-500 bg-green-500/5"
                : "border-l-4 border-l-blue-500 bg-blue-500/5"
            }`}
          >
            {/* Arrow indicator */}
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
              open
                ? "bg-green-500/15 text-green-600"
                : "bg-blue-500/15 text-blue-600"
            }`}>
              {open ? "S" : "B"}
            </div>

            {/* Main content */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                <span className="font-semibold">{symbol}</span>
                <Badge
                  variant={open ? "default" : "secondary"}
                  className={`text-[10px] px-1.5 ${
                    open
                      ? "bg-green-600 hover:bg-green-700"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {open ? "SELL TO OPEN" : "BUY TO CLOSE"}
                </Badge>
                {strategy && (
                  <Badge variant="outline" className="text-[10px] px-1.5">{strategy}</Badge>
                )}
                <span className={`text-xs ${log.status === "filled" ? "text-green-500" : log.status === "new" ? "text-yellow-500" : "text-muted-foreground"}`}>
                  {log.status}
                </span>
              </div>
              {detail && (
                <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
              )}
            </div>

            {/* Timestamp */}
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatTime(log.timestamp)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function TradeHistory({ data, orderLogs, equityCurve }: Props) {
  const [tab, setTab] = useState<string>("activity");

  if (!data) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Trades</h2>
        <Skeleton className="h-48 w-full rounded-xl" />
      </section>
    );
  }

  const tabs = [
    { key: "activity", label: "Activity", count: orderLogs?.length ?? 0 },
    { key: "positions", label: "Open", count: data.open.length },
    { key: "closed", label: "Closed", count: data.closed.length },
  ];

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Trades</h2>

      {/* Daily P&L + chart + tab bar */}
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center">
        <Card size="sm" className="w-fit">
          <CardContent className="px-4 py-2">
            <span className="text-xs text-muted-foreground mr-2">Daily P&L</span>
            <span className={`text-lg font-bold ${pnlColor(data.daily_pnl)}`}>
              {formatCurrency(data.daily_pnl)}
            </span>
          </CardContent>
        </Card>

        {equityCurve && equityCurve.length > 0 && (
          <Card size="sm" className="w-fit min-w-[200px]">
            <CardContent className="px-4 py-2">
              <DailyPnlChart equityCurve={equityCurve} />
            </CardContent>
          </Card>
        )}

        {/* Tab bar */}
        <div className="flex rounded-lg border bg-muted/50 p-1">
          {tabs.map(({ key, label, count }) => (
            <button
              key={key}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-all sm:px-4 sm:py-2 ${
                tab === key
                  ? "bg-background text-foreground shadow-sm border"
                  : "text-muted-foreground hover:text-foreground hover:bg-background/50"
              }`}
              onClick={() => setTab(key)}
            >
              {label}
              <span className={`ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold ${
                tab === key ? "bg-primary text-primary-foreground" : "bg-muted-foreground/20"
              }`}>
                {count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Activity stream */}
      {tab === "activity" && (
        <ActivityStream logs={orderLogs ?? []} />
      )}

      {/* Open positions */}
      {tab === "positions" && (
        <div>
          {data.open.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No open positions.</p>
          ) : (
            <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead>Entry</TableHead>
                  <TableHead>Current</TableHead>
                  <TableHead>Unrealized P&amp;L</TableHead>
                  <TableHead>Opened</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.open.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{field(row, "symbol")}</TableCell>
                    <TableCell><Badge variant="outline">{field(row, "strategy")}</Badge></TableCell>
                    <TableCell>{field(row, "side")}</TableCell>
                    <TableCell>${field(row, "entry_price")}</TableCell>
                    <TableCell>${field(row, "current_price")}</TableCell>
                    <TableCell>
                      {row["unrealized_pnl"] != null ? (
                        <span className={pnlColor(row["unrealized_pnl"] as number)}>
                          {formatCurrency(row["unrealized_pnl"] as number)}
                        </span>
                      ) : "--"}
                    </TableCell>
                    <TableCell>{field(row, "opened_at")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </div>
      )}

      {/* Closed trades */}
      {tab === "closed" && (
        <div>
          {data.closed.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No closed trades.</p>
          ) : (
            <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead>Entry</TableHead>
                  <TableHead>Exit</TableHead>
                  <TableHead>Realized P&amp;L</TableHead>
                  <TableHead>Closed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.closed.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{field(row, "symbol")}</TableCell>
                    <TableCell><Badge variant="outline">{field(row, "strategy")}</Badge></TableCell>
                    <TableCell>{field(row, "side")}</TableCell>
                    <TableCell>${field(row, "entry_price")}</TableCell>
                    <TableCell>${field(row, "exit_price")}</TableCell>
                    <TableCell>
                      {row["realized_pnl"] != null ? (
                        <span className={pnlColor(row["realized_pnl"] as number)}>
                          {formatCurrency(row["realized_pnl"] as number)}
                        </span>
                      ) : "--"}
                    </TableCell>
                    <TableCell>{field(row, "closed_at")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
