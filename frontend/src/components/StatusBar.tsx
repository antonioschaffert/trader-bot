import type { StatusData, MarketData } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { formatTimeET } from "@/lib/time";

interface Props {
  status: StatusData | null;
  market: MarketData[] | null;
  onOpenSettings: () => void;
}

export function StatusBar({ status, market, onOpenSettings }: Props) {
  const botAlive = status?.running ?? false;
  const scanning = status?.scanning ?? false;
  const marketHours = status?.market_hours ?? false;
  const paperMode = status?.paper_mode ?? true;
  const lastScan = formatTimeET(status?.last_scan_time);

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

  return (
    <header className="sticky top-0 z-40 flex items-center justify-between border-b bg-background/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-4">
        {/* Bot status indicator */}
        <span className="flex items-center gap-2 text-sm font-medium">
          <span
            className={`inline-block size-2.5 rounded-full ${dotColor}`}
          />
          {botLabel}
        </span>

        {/* Paper / Live badge */}
        <Badge variant={paperMode ? "secondary" : "destructive"}>
          {paperMode ? "Paper" : "Live"}
        </Badge>

        {/* Last scan */}
        <span className="text-sm text-muted-foreground">
          Last scan: {lastScan}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Market prices */}
        {spyPrice != null && (
          <span className="text-sm font-medium">
            SPY{" "}
            <span className="text-muted-foreground">
              ${spyPrice.toFixed(2)}
            </span>
          </span>
        )}
        {qqqPrice != null && (
          <span className="text-sm font-medium">
            QQQ{" "}
            <span className="text-muted-foreground">
              ${qqqPrice.toFixed(2)}
            </span>
          </span>
        )}

        {/* Settings gear */}
        <button
          onClick={onOpenSettings}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Open settings"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </div>
    </header>
  );
}
