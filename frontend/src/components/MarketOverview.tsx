import { useState, useEffect } from "react";
import type { MarketData, IvPoint } from "@/lib/api";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface Props {
  market: MarketData[] | null;
}

function computeBias(
  price: number,
  sma50: number | null,
  rsi: number | null,
): "bullish" | "bearish" | "neutral" {
  if (sma50 != null && rsi != null) {
    if (price > sma50 && rsi < 70) return "bullish";
    if (price < sma50 && rsi > 30) return "bearish";
  }
  return "neutral";
}

function rsiColor(rsi: number | null): string {
  if (rsi == null) return "text-muted-foreground";
  if (rsi > 70) return "text-red-500";
  if (rsi < 30) return "text-green-500";
  return "text-foreground";
}

function biasVariant(
  bias: "bullish" | "bearish" | "neutral",
): "default" | "secondary" | "destructive" {
  if (bias === "bullish") return "default";
  if (bias === "bearish") return "destructive";
  return "secondary";
}

function adxLabel(adx: number | null): string {
  if (adx == null) return "N/A";
  if (adx < 20) return `${adx.toFixed(0)} (Range)`;
  if (adx < 25) return `${adx.toFixed(0)} (Trans.)`;
  if (adx < 40) return `${adx.toFixed(0)} (Trend)`;
  return `${adx.toFixed(0)} (Strong)`;
}

function IvSparkline({ symbol }: { symbol: string }) {
  const [data, setData] = useState<IvPoint[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getIvHistory(symbol, 7).then((result) => {
      if (!cancelled) setData(result);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [symbol]);

  if (!data || data.length < 2) return null;

  const chartData = data.map((d) => ({ iv: d.iv }));

  return (
    <div className="mt-2 border-t pt-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">IV (7d)</span>
        <span className="text-[10px] font-medium">
          {(data[data.length - 1].iv * 100).toFixed(1)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={30}>
        <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`ivGrad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-chart-amber)" stopOpacity={0.4} />
              <stop offset="95%" stopColor="var(--color-chart-amber)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="iv"
            stroke="var(--color-chart-amber)"
            strokeWidth={1.5}
            fill={`url(#ivGrad-${symbol})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MarketOverview({ market }: Props) {
  if (!market) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Market Overview</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-40 w-full rounded-xl" />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Market Overview</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {market.map((m) => {
          const bias = computeBias(m.price, m.sma_50, m.rsi);
          return (
            <Card key={m.symbol} size="sm">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{m.symbol}</span>
                  <div className="flex gap-1">
                    <Badge variant={biasVariant(bias)}>{bias}</Badge>
                    {m.regime && (
                      <Badge variant="outline" className="text-[10px]">
                        {m.regime.phase === "mean_reverting" ? "RNG" : m.regime.phase === "trending" ? "TRD" : "TRS"}
                      </Badge>
                    )}
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-y-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Price</span>
                    <p className="font-medium">${m.price.toFixed(2)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">RSI</span>
                    <p className={`font-medium ${rsiColor(m.rsi)}`}>
                      {m.rsi != null ? m.rsi.toFixed(1) : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">IV Rank</span>
                    <p className="font-medium">
                      {m.iv_rank != null ? `${m.iv_rank.toFixed(0)}%` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">IV %ile</span>
                    <p className="font-medium">
                      {m.iv_percentile != null ? `${m.iv_percentile.toFixed(0)}%` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">ADX</span>
                    <p className="font-medium">{adxLabel(m.adx)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">ATR</span>
                    <p className="font-medium">
                      {m.atr != null ? `$${m.atr.toFixed(2)}` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Support</span>
                    <p className="font-medium text-green-500">
                      {m.support != null ? `$${m.support.toFixed(2)}` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Resistance</span>
                    <p className="font-medium text-red-500">
                      {m.resistance != null ? `$${m.resistance.toFixed(2)}` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">SMA 50</span>
                    <p className="font-medium">
                      {m.sma_50 != null ? `$${m.sma_50.toFixed(2)}` : "N/A"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">SMA 20</span>
                    <p className="font-medium">
                      {m.sma_20 != null ? `$${m.sma_20.toFixed(2)}` : "N/A"}
                    </p>
                  </div>
                </div>
                <IvSparkline symbol={m.symbol} />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
