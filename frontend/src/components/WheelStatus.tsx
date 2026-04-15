import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export interface WheelPosition {
  symbol: string;
  phase: string;
  shares_held: number;
  cost_basis: number;
  total_premium_collected: number;
  current_option_symbol: string;
  current_option_strike: number;
  current_option_expiration: string | null;
  current_option_entry_premium: number;
  current_option_entry_delta: number;
  current_option_quantity: number;
  cycles_completed: number;
  started_at: string | null;
  last_updated: string | null;
}

export interface WheelData {
  positions: WheelPosition[];
}

interface Props {
  data: WheelData | null;
}

function phaseBadge(phase: string) {
  const config: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
    idle: { label: "IDLE", variant: "secondary" },
    selling_csp: { label: "SELLING CSP", variant: "default" },
    holding_shares: { label: "HOLDING SHARES", variant: "outline" },
    selling_cc: { label: "SELLING CC", variant: "default" },
  };
  const c = config[phase] ?? { label: phase.toUpperCase(), variant: "secondary" as const };
  return <Badge variant={c.variant}>{c.label}</Badge>;
}

function phaseStep(phase: string): number {
  const steps: Record<string, number> = {
    idle: 0,
    selling_csp: 1,
    holding_shares: 2,
    selling_cc: 3,
  };
  return steps[phase] ?? 0;
}

function PhaseIndicator({ phase }: { phase: string }) {
  const step = phaseStep(phase);
  const labels = ["Idle", "CSP", "Shares", "CC"];
  return (
    <div className="flex flex-wrap items-center gap-1">
      {labels.map((label, i) => (
        <div key={label} className="flex items-center">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
              i === step
                ? "bg-primary text-primary-foreground"
                : i < step
                  ? "bg-primary/20 text-primary"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {i + 1}
          </div>
          <span className={`ml-1 text-xs ${i === step ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
            {label}
          </span>
          {i < labels.length - 1 && (
            <div className={`mx-1 h-px w-4 ${i < step ? "bg-primary" : "bg-muted"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

function WheelPositionCard({ pos }: { pos: WheelPosition }) {
  const hasOption = pos.current_option_symbol && pos.phase !== "idle" && pos.phase !== "holding_shares";

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{pos.symbol}</span>
          <div className="flex items-center gap-2">
            {pos.cycles_completed > 0 && (
              <Badge variant="outline">{pos.cycles_completed} cycle{pos.cycles_completed !== 1 ? "s" : ""}</Badge>
            )}
            {phaseBadge(pos.phase)}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <PhaseIndicator phase={pos.phase} />

          <div className="grid grid-cols-2 gap-y-2 text-sm">
            {/* Shares info */}
            {pos.shares_held > 0 && (
              <>
                <div>
                  <span className="text-muted-foreground">Shares</span>
                  <p className="font-medium">{pos.shares_held}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Cost Basis</span>
                  <p className="font-medium">${pos.cost_basis.toFixed(2)}</p>
                </div>
              </>
            )}

            {/* Active option info */}
            {hasOption && (
              <>
                <div>
                  <span className="text-muted-foreground">Strike</span>
                  <p className="font-medium">${pos.current_option_strike.toFixed(0)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Premium</span>
                  <p className="font-medium text-green-500">${pos.current_option_entry_premium.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Delta</span>
                  <p className="font-medium">{pos.current_option_entry_delta.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Expiration</span>
                  <p className="font-medium">{pos.current_option_expiration ?? "-"}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Qty</span>
                  <p className="font-medium">{pos.current_option_quantity}</p>
                </div>
              </>
            )}

            {/* Premium collected */}
            <div>
              <span className="text-muted-foreground">Total Premium</span>
              <p className={`font-medium ${pos.total_premium_collected > 0 ? "text-green-500" : ""}`}>
                ${pos.total_premium_collected.toFixed(2)}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function WheelStatus({ data }: Props) {
  if (!data) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Wheel Strategy</h2>
        <Skeleton className="h-48 w-full rounded-xl" />
      </section>
    );
  }

  if (data.positions.length === 0) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold">Wheel Strategy</h2>
        <Card size="sm">
          <CardContent className="py-6">
            <p className="text-center text-sm text-muted-foreground">
              No wheel positions active. The wheel strategy will automatically start selling CSPs when enabled.
            </p>
          </CardContent>
        </Card>
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold">Wheel Strategy</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {data.positions.map((pos) => (
          <WheelPositionCard key={pos.symbol} pos={pos} />
        ))}
      </div>
    </section>
  );
}
