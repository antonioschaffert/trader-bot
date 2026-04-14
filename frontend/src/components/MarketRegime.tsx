import type { RegimeData, DrawdownData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  regime: RegimeData | null;
  drawdown: DrawdownData | null;
}

function volBadge(vol: string) {
  const colors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    low: "secondary",
    normal: "default",
    elevated: "outline",
    crisis: "destructive",
  };
  return <Badge variant={colors[vol] ?? "secondary"}>{vol.toUpperCase()}</Badge>;
}

function trendBadge(trend: string) {
  const colors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    strong_bull: "default",
    bull: "default",
    neutral: "secondary",
    bear: "destructive",
    strong_bear: "destructive",
  };
  const labels: Record<string, string> = {
    strong_bull: "STRONG BULL",
    bull: "BULL",
    neutral: "NEUTRAL",
    bear: "BEAR",
    strong_bear: "STRONG BEAR",
  };
  return <Badge variant={colors[trend] ?? "secondary"}>{labels[trend] ?? trend}</Badge>;
}

function phaseBadge(phase: string) {
  const colors: Record<string, "default" | "secondary" | "outline"> = {
    trending: "outline",
    mean_reverting: "default",
    transitioning: "secondary",
  };
  const labels: Record<string, string> = {
    trending: "TRENDING",
    mean_reverting: "RANGE-BOUND",
    transitioning: "TRANSITIONING",
  };
  return <Badge variant={colors[phase] ?? "secondary"}>{labels[phase] ?? phase}</Badge>;
}

function trendArrow(trend: string): string {
  if (trend === "bullish") return "^";
  if (trend === "bearish") return "v";
  return "-";
}

export function MarketRegime({ regime, drawdown }: Props) {
  if (!regime) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Market Regime</h2>
        <Skeleton className="h-48 w-full rounded-xl" />
      </section>
    );
  }

  const ddPct = drawdown?.drawdown_pct ?? 0;
  const ddColor = ddPct > 10 ? "text-red-500" : ddPct > 5 ? "text-yellow-500" : "text-green-500";

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Market Regime & Risk</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {/* Regime Overview */}
        <Card size="sm">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Regime</span>
              {!regime.should_trade && (
                <Badge variant="destructive">TRADING HALTED</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Volatility</span>
                {volBadge(regime.volatility_regime)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Trend</span>
                {trendBadge(regime.trend_regime)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Phase</span>
                {phaseBadge(regime.market_phase)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">VIX Term Structure</span>
                <Badge variant={regime.vix_term_structure === "backwardation" ? "destructive" : "secondary"}>
                  {regime.vix_term_structure}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* VIX & Trend Details */}
        <Card size="sm">
          <CardHeader>
            <CardTitle>VIX & Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-y-2 text-sm">
              <div>
                <span className="text-muted-foreground">VIX</span>
                <p className="font-medium">{regime.vix_current.toFixed(1)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">VIX SMA(10)</span>
                <p className="font-medium">{regime.vix_sma_10.toFixed(1)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">VIX %ile (30d)</span>
                <p className="font-medium">{regime.vix_percentile_30d.toFixed(0)}%</p>
              </div>
              <div>
                <span className="text-muted-foreground">ADX</span>
                <p className="font-medium">{regime.adx.toFixed(0)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Weekly</span>
                <p className="font-medium">{trendArrow(regime.weekly_trend)} {regime.weekly_trend}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Daily</span>
                <p className="font-medium">{trendArrow(regime.daily_trend)} {regime.daily_trend}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Trend Score</span>
                <p className={`font-medium ${regime.trend_score > 0 ? "text-green-500" : regime.trend_score < 0 ? "text-red-500" : ""}`}>
                  {regime.trend_score > 0 ? "+" : ""}{regime.trend_score.toFixed(0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Risk Adjustments & Drawdown */}
        <Card size="sm">
          <CardHeader>
            <CardTitle>Risk State</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-y-2 text-sm">
              <div>
                <span className="text-muted-foreground">Position Size</span>
                <p className="font-medium">{(regime.position_size_multiplier * 100).toFixed(0)}%</p>
              </div>
              <div>
                <span className="text-muted-foreground">Spread Width</span>
                <p className="font-medium">{(regime.spread_width_multiplier * 100).toFixed(0)}%</p>
              </div>
              <div>
                <span className="text-muted-foreground">Delta Shift</span>
                <p className="font-medium">{regime.delta_adjustment.toFixed(2)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Min Premium</span>
                <p className="font-medium">{(regime.premium_threshold_multiplier * 100).toFixed(0)}%</p>
              </div>
              {drawdown && (
                <>
                  <div>
                    <span className="text-muted-foreground">Drawdown</span>
                    <p className={`font-medium ${ddColor}`}>{ddPct.toFixed(1)}%</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Max DD</span>
                    <p className="font-medium">{drawdown.max_drawdown_pct.toFixed(1)}%</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Streak</span>
                    <p className={`font-medium ${drawdown.consecutive_losses > 2 ? "text-red-500" : "text-green-500"}`}>
                      {drawdown.consecutive_losses > 0
                        ? `${drawdown.consecutive_losses}L`
                        : `${drawdown.consecutive_wins}W`}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Size Factor</span>
                    <p className="font-medium">{(drawdown.size_reduction_factor * 100).toFixed(0)}%</p>
                  </div>
                  {drawdown.is_in_cooldown && (
                    <div className="col-span-2">
                      <Badge variant="destructive">IN COOLDOWN</Badge>
                    </div>
                  )}
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
