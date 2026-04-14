import type { TradesResponse, OrderLog } from "@/lib/api";
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
import { useState } from "react";

interface Props {
  data: TradesResponse | null;
  orderLogs: OrderLog[] | null;
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

function actionBadge(action: string) {
  const config: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
    open: { label: "OPEN", variant: "default" },
    close: { label: "CLOSE", variant: "secondary" },
    wheel_open: { label: "WHEEL OPEN", variant: "default" },
    wheel_close: { label: "WHEEL CLOSE", variant: "secondary" },
  };
  const c = config[action] ?? { label: action.toUpperCase(), variant: "outline" as const };
  return <Badge variant={c.variant} className="text-[10px] px-1.5">{c.label}</Badge>;
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

function ActivityStream({ logs }: { logs: OrderLog[] }) {
  if (logs.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">No order activity yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Time</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Strategy</TableHead>
          <TableHead>Details</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => {
          const signal = log.signal ?? {};
          const symbol = log.symbol || String(signal.symbol ?? "--");
          const strategy = String(signal.strategy_mode ?? signal.phase ?? "--");
          const premium = signal.target_premium != null ? `$${Number(signal.target_premium).toFixed(2)}` : "";
          const spread = signal.spread_type ? String(signal.spread_type) : "";
          const detail = [spread, premium].filter(Boolean).join(" @ ") || (log.limit_price ? `@ $${log.limit_price.toFixed(2)}` : "");

          return (
            <TableRow key={log._id}>
              <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                {formatTime(log.timestamp)}
              </TableCell>
              <TableCell>{actionBadge(log.action)}</TableCell>
              <TableCell className="font-medium">{symbol}</TableCell>
              <TableCell>
                <Badge variant="outline" className="text-[10px]">{strategy}</Badge>
              </TableCell>
              <TableCell className="text-xs">{detail}</TableCell>
              <TableCell>
                <span className={`text-xs ${log.status === "filled" ? "text-green-500" : "text-muted-foreground"}`}>
                  {log.status}
                </span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export function TradeHistory({ data, orderLogs }: Props) {
  const [tab, setTab] = useState<"activity" | "positions" | "closed">("activity");

  if (!data) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Trades</h2>
        <Skeleton className="h-48 w-full rounded-xl" />
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Trades</h2>

      {/* Daily P&L card */}
      <Card size="sm" className="mb-4 w-fit">
        <CardHeader>
          <CardTitle>Daily P&amp;L</CardTitle>
        </CardHeader>
        <CardContent>
          <span className={`text-2xl font-bold ${pnlColor(data.daily_pnl)}`}>
            {formatCurrency(data.daily_pnl)}
          </span>
        </CardContent>
      </Card>

      {/* Tab switcher */}
      <div className="mb-4 flex gap-1 rounded-lg bg-muted p-1 w-fit">
        {([
          ["activity", `Activity (${orderLogs?.length ?? 0})`],
          ["positions", `Open (${data.open.length})`],
          ["closed", `Closed (${data.closed.length})`],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Activity stream */}
      {tab === "activity" && (
        <ActivityStream logs={orderLogs ?? []} />
      )}

      {/* Open positions */}
      {tab === "positions" && (
        <div>
          {data.open.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No open positions.</p>
          ) : (
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
          )}
        </div>
      )}

      {/* Closed trades */}
      {tab === "closed" && (
        <div>
          {data.closed.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No closed trades.</p>
          ) : (
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
          )}
        </div>
      )}
    </section>
  );
}
