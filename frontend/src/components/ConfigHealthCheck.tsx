import { useState } from "react";
import type { Settings } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  settings: Settings | null;
}

type Severity = "error" | "warning" | "info";

interface CheckResult {
  severity: Severity;
  label: string;
  message: string;
  value: string;
}

function runChecks(settings: Settings): CheckResult[] {
  const results: CheckResult[] = [];
  const risk = (settings.risk ?? {}) as Record<string, unknown>;
  const drawdown = ((risk.drawdown as Record<string, unknown>) ?? {}) as Record<string, unknown>;
  const swing = (settings.swing ?? {}) as Record<string, unknown>;
  const exhaustion = (settings.exhaustion ?? {}) as Record<string, unknown>;
  const settingsAny = settings as unknown as Record<string, unknown>;
  const wheel = settingsAny.wheel as Record<string, unknown> | undefined;

  // Symbols
  if (!settings.symbols || settings.symbols.length === 0) {
    results.push({ severity: "error", label: "Symbols", message: "No symbols configured", value: "none" });
  }

  // Daily loss limit
  if (!risk.daily_loss_limit || Number(risk.daily_loss_limit) <= 0) {
    results.push({ severity: "error", label: "Daily Loss Limit", message: "No daily loss limit configured", value: "$0" });
  }

  // Stop loss
  if (!risk.stop_loss_multiplier || Number(risk.stop_loss_multiplier) <= 0) {
    results.push({ severity: "error", label: "Stop Loss", message: "No stop loss multiplier set", value: "0x" });
  }

  // Drawdown halt
  if (!drawdown.drawdown_halt_pct || Number(drawdown.drawdown_halt_pct) <= 0) {
    results.push({ severity: "error", label: "Drawdown Halt", message: "Drawdown halt not configured", value: "off" });
  }

  // Strategies enabled
  const hasSwing = swing.target_dte != null;
  const hasExhaustion = exhaustion.enabled !== false;
  const hasWheel = wheel?.enabled === true;
  if (!hasSwing && !hasExhaustion && !hasWheel) {
    results.push({ severity: "error", label: "Strategies", message: "No strategies appear to be enabled", value: "none" });
  }

  // Risk per trade
  const riskPct = Number(risk.max_risk_per_trade_pct ?? 0);
  if (riskPct > 10) {
    results.push({ severity: "warning", label: "Risk Per Trade", message: `Risk per trade is ${riskPct}% (>10%)`, value: `${riskPct}%` });
  }

  // Buying power
  const bpPct = Number(risk.max_buying_power_usage_pct ?? 0);
  if (bpPct > 80) {
    results.push({ severity: "warning", label: "Buying Power", message: `BP usage limit is ${bpPct}% (>80%)`, value: `${bpPct}%` });
  }

  // Concurrent spreads
  const maxSpreads = Number(risk.max_concurrent_spreads ?? 0);
  if (maxSpreads > 20) {
    results.push({ severity: "warning", label: "Concurrent Spreads", message: `Max concurrent spreads is ${maxSpreads} (>20)`, value: `${maxSpreads}` });
  }

  // Income target
  if (!risk.daily_income_target || Number(risk.daily_income_target) <= 0) {
    results.push({ severity: "info", label: "Income Target", message: "No daily income target set", value: "$0" });
  }

  // Contracts cap
  if (!risk.max_contracts_per_trade || Number(risk.max_contracts_per_trade) <= 0) {
    results.push({ severity: "info", label: "Contract Limit", message: "No per-trade contract limit set", value: "none" });
  }

  return results;
}

function severityIcon(severity: Severity): string {
  switch (severity) {
    case "error": return "\u2716";
    case "warning": return "\u26A0";
    case "info": return "\u24D8";
  }
}

function severityColor(severity: Severity): string {
  switch (severity) {
    case "error": return "text-red-500";
    case "warning": return "text-amber-500";
    case "info": return "text-blue-400";
  }
}

function severityBorder(severity: Severity): string {
  switch (severity) {
    case "error": return "border-l-red-500";
    case "warning": return "border-l-amber-500";
    case "info": return "border-l-blue-400";
  }
}

export function ConfigHealthCheck({ settings }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!settings) return null;

  const checks = runChecks(settings);
  const errors = checks.filter((c) => c.severity === "error").length;
  const warnings = checks.filter((c) => c.severity === "warning").length;

  if (checks.length === 0) {
    return (
      <section>
        <Card size="sm" className="border-l-4 border-l-green-500">
          <CardContent className="flex items-center gap-2 py-3">
            <span className="text-green-500">{"\u2714"}</span>
            <span className="text-sm font-medium">All config checks passed</span>
          </CardContent>
        </Card>
      </section>
    );
  }

  return (
    <section>
      <Card size="sm">
        <CardHeader className="cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <CardTitle className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span>Config Health</span>
              {errors > 0 && (
                <Badge variant="destructive" className="text-[10px]">{errors} error{errors > 1 ? "s" : ""}</Badge>
              )}
              {warnings > 0 && (
                <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500">{warnings} warning{warnings > 1 ? "s" : ""}</Badge>
              )}
            </div>
            <span className="text-muted-foreground text-xs">
              {expanded ? "collapse" : `${checks.length} issue${checks.length > 1 ? "s" : ""}`}
            </span>
          </CardTitle>
        </CardHeader>
        {expanded && (
          <CardContent className="space-y-2 pt-0">
            {checks.map((check, i) => (
              <div
                key={i}
                className={`flex items-center justify-between rounded-md border-l-4 bg-muted/50 px-3 py-2 ${severityBorder(check.severity)}`}
              >
                <div className="flex items-center gap-2 text-sm">
                  <span className={severityColor(check.severity)}>{severityIcon(check.severity)}</span>
                  <span>{check.message}</span>
                </div>
                <span className="text-xs font-mono text-muted-foreground">{check.value}</span>
              </div>
            ))}
          </CardContent>
        )}
      </Card>
    </section>
  );
}
