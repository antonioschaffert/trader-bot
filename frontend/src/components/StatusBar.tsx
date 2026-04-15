import type { StatusData, MarketData } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { AccountSwitcher } from "@/components/AccountSwitcher";
import { formatTimeET } from "@/lib/time";

interface Props {
  status: StatusData | null;
  market: MarketData[] | null;
  activeAccountId: string;
  onSelectAccount: (accountId: string) => void;
  onOpenSettings: () => void;
  onOpenAccounts: () => void;
}

export function StatusBar({ status, market, activeAccountId, onSelectAccount, onOpenSettings, onOpenAccounts }: Props) {
  const botAlive = status?.running ?? false;
  const scanning = status?.scanning ?? false;
  const marketHours = status?.market_hours ?? false;
  const paperMode = status?.paper_mode ?? true;
  const lastScan = formatTimeET(status?.last_scan_time);
  const regime = status?.regime;
  const drawdown = status?.drawdown;
  const accounts = status?.accounts ?? [];

  const spyPrice = market?.find((m) => m.symbol === "SPY")?.price;
  const qqqPrice = market?.find((m) => m.symbol === "QQQ")?.price;

  const botLabel = !botAlive
    ? "Offline"
    : scanning
      ? "Scanning"
      : marketHours
        ? "Idle"
        : "Market Closed";
  const dotColor = !botAlive
    ? "bg-red-500"
    : scanning
      ? "bg-green-500 animate-pulse"
      : "bg-yellow-500";

  const shouldTrade = regime?.should_trade ?? true;

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between px-4 py-2 sm:px-6 sm:py-3">
        {/* Top row: status + account + settings */}
        <div className="flex items-center gap-2 sm:gap-4">
          <span className="flex items-center gap-2 text-sm font-medium">
            <span className={`inline-block size-2.5 rounded-full ${dotColor}`} />
            {botLabel}
          </span>

          {/* Paper / Live badge */}
          <Badge variant={paperMode ? "secondary" : "destructive"}>
            {paperMode ? "Paper" : "Live"}
          </Badge>

          {/* Account Switcher (shown when accounts exist) */}
          {accounts.length > 0 && (
            <AccountSwitcher
              accounts={accounts}
              activeAccountId={activeAccountId}
              onSelect={onSelectAccount}
              onManageAccounts={onOpenAccounts}
            />
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          {spyPrice != null && (
            <span className="text-xs font-medium sm:text-sm">
              SPY <span className="text-muted-foreground">${spyPrice.toFixed(2)}</span>
            </span>
          )}
          {qqqPrice != null && (
            <span className="hidden text-sm font-medium sm:inline">
              QQQ <span className="text-muted-foreground">${qqqPrice.toFixed(2)}</span>
            </span>
          )}

          {/* Manage accounts button */}
          <button
            onClick={onOpenAccounts}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Manage accounts"
            title="Manage accounts"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </button>

          {/* Settings gear */}
          <button
            onClick={onOpenSettings}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Open settings"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        </div>
      </div>

      {/* Bottom row: badges + metadata (wraps naturally) */}
      <div className="flex flex-wrap items-center gap-2 border-t border-border/50 px-4 py-1.5 text-xs sm:px-6">
        {regime && (
          <Badge
            variant={
              regime.volatility_regime === "crisis"
                ? "destructive"
                : regime.volatility_regime === "elevated"
                  ? "outline"
                  : "secondary"
            }
          >
            VIX {regime.vix_current.toFixed(0)}
          </Badge>
        )}
        {!shouldTrade && (
          <Badge variant="destructive">HALTED</Badge>
        )}
        {drawdown && drawdown.drawdown_pct > 3 && (
          <Badge variant={drawdown.drawdown_pct > 10 ? "destructive" : "outline"}>
            DD {drawdown.drawdown_pct.toFixed(1)}%
          </Badge>
        )}
        <span className="text-muted-foreground">
          Last scan: {lastScan}
        </span>
      </div>
    </header>
  );
}
