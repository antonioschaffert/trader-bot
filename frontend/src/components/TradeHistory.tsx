import type { TradesResponse } from "@/lib/api";
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
  data: TradesResponse | null;
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

/** Best-effort field extraction from a generic record. */
function field(row: Record<string, unknown>, key: string): string {
  const v = row[key];
  if (v == null) return "--";
  if (typeof v === "number") return v.toFixed(2);
  return String(v);
}

export function TradeHistory({ data }: Props) {
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
      <Card size="sm" className="mb-6 w-fit">
        <CardHeader>
          <CardTitle>Daily P&amp;L</CardTitle>
        </CardHeader>
        <CardContent>
          <span className={`text-2xl font-bold ${pnlColor(data.daily_pnl)}`}>
            {formatCurrency(data.daily_pnl)}
          </span>
        </CardContent>
      </Card>

      {/* Open positions */}
      <div className="mb-6">
        <h3 className="mb-2 text-base font-medium">
          Open Positions{" "}
          <Badge variant="secondary">{data.open.length}</Badge>
        </h3>
        {data.open.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No open positions.
          </p>
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
                  <TableCell className="font-medium">
                    {field(row, "symbol")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{field(row, "strategy")}</Badge>
                  </TableCell>
                  <TableCell>{field(row, "side")}</TableCell>
                  <TableCell>${field(row, "entry_price")}</TableCell>
                  <TableCell>${field(row, "current_price")}</TableCell>
                  <TableCell>
                    {row["unrealized_pnl"] != null ? (
                      <span
                        className={pnlColor(
                          row["unrealized_pnl"] as number,
                        )}
                      >
                        {formatCurrency(row["unrealized_pnl"] as number)}
                      </span>
                    ) : (
                      "--"
                    )}
                  </TableCell>
                  <TableCell>{field(row, "opened_at")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Closed trades */}
      <div>
        <h3 className="mb-2 text-base font-medium">
          Closed Trades{" "}
          <Badge variant="secondary">{data.closed.length}</Badge>
        </h3>
        {data.closed.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            No closed trades today.
          </p>
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
                  <TableCell className="font-medium">
                    {field(row, "symbol")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{field(row, "strategy")}</Badge>
                  </TableCell>
                  <TableCell>{field(row, "side")}</TableCell>
                  <TableCell>${field(row, "entry_price")}</TableCell>
                  <TableCell>${field(row, "exit_price")}</TableCell>
                  <TableCell>
                    {row["realized_pnl"] != null ? (
                      <span
                        className={pnlColor(
                          row["realized_pnl"] as number,
                        )}
                      >
                        {formatCurrency(row["realized_pnl"] as number)}
                      </span>
                    ) : (
                      "--"
                    )}
                  </TableCell>
                  <TableCell>{field(row, "closed_at")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}
