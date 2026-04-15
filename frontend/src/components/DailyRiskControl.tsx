import { useState } from "react";
import type { Settings } from "@/lib/api";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Props {
  dailyPnl: number;
  settings: Settings | null;
  onSaved: () => void;
}

function formatCurrency(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${value.toFixed(0)}`;
}

function ProgressBar({
  value,
  max,
  variant,
  label,
}: {
  value: number;
  max: number;
  variant: "loss" | "income";
  label: string;
}) {
  const pct = max > 0 ? Math.min(Math.abs(value) / max * 100, 100) : 0;
  const bgColor = variant === "loss"
    ? pct > 75 ? "bg-red-500" : pct > 50 ? "bg-amber-500" : "bg-red-400/60"
    : pct > 75 ? "bg-green-500" : "bg-green-400/60";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ${bgColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function DailyRiskControl({ dailyPnl, settings, onSaved }: Props) {
  const [saving, setSaving] = useState(false);

  const risk = (settings?.risk ?? {}) as Record<string, unknown>;
  const lossLimit = Number(risk.daily_loss_limit ?? 0);
  const incomeTarget = Number(risk.daily_income_target ?? 0);
  const riskPerTrade = Number(risk.max_risk_per_trade_pct ?? 0);
  const maxSpreads = Number(risk.max_concurrent_spreads ?? 0);
  const bpUsage = Number(risk.max_buying_power_usage_pct ?? 0);

  const isLoss = dailyPnl < 0;
  const lossUsed = isLoss ? Math.abs(dailyPnl) : 0;
  const incomeUsed = !isLoss ? dailyPnl : 0;

  async function adjustLimit(field: string, delta: number) {
    const current = Number(risk[field] ?? 0);
    const next = Math.max(0, current + delta);
    setSaving(true);
    try {
      await api.putSettings({ risk: { [field]: next } } as Partial<Settings>);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Daily Risk Tolerance</h2>
      <Card size="sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Today&apos;s Risk</span>
            <Badge variant={dailyPnl >= 0 ? "default" : "destructive"} className="text-sm">
              P&L: {formatCurrency(dailyPnl)}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Loss Budget */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Loss Budget</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-medium text-red-500">
                  ${lossLimit.toLocaleString()}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 w-6 p-0 text-xs"
                    onClick={() => adjustLimit("daily_loss_limit", -100)}
                    disabled={saving || lossLimit <= 0}
                  >
                    -
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 w-6 p-0 text-xs"
                    onClick={() => adjustLimit("daily_loss_limit", 100)}
                    disabled={saving}
                  >
                    +
                  </Button>
                </div>
              </div>
            </div>
            <ProgressBar value={lossUsed} max={lossLimit} variant="loss" label={isLoss ? `$${lossUsed.toFixed(0)} lost today` : "No losses today"} />
          </div>

          {/* Income Target */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Income Target</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-medium text-green-500">
                  ${incomeTarget.toLocaleString()}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 w-6 p-0 text-xs"
                    onClick={() => adjustLimit("daily_income_target", -100)}
                    disabled={saving || incomeTarget <= 0}
                  >
                    -
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 w-6 p-0 text-xs"
                    onClick={() => adjustLimit("daily_income_target", 100)}
                    disabled={saving}
                  >
                    +
                  </Button>
                </div>
              </div>
            </div>
            <ProgressBar value={incomeUsed} max={incomeTarget} variant="income" label={!isLoss && dailyPnl > 0 ? `$${incomeUsed.toFixed(0)} earned today` : "No income yet"} />
          </div>

          {/* Quick risk params row */}
          <div className="flex flex-wrap items-center gap-3 border-t pt-3 text-xs text-muted-foreground sm:gap-4">
            <span>Risk/Trade: <span className="font-medium text-foreground">{riskPerTrade}%</span></span>
            <span>Max Spreads: <span className="font-medium text-foreground">{maxSpreads}</span></span>
            <span>BP Limit: <span className="font-medium text-foreground">{bpUsage}%</span></span>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
