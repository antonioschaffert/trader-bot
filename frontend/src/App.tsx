import { useState, useCallback } from "react";
import { api, hasCredentials } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { StatusBar } from "@/components/StatusBar";
import { MarketRegime } from "@/components/MarketRegime";
import { MarketOverview } from "@/components/MarketOverview";
import { PerformancePanel } from "@/components/PerformancePanel";
import { RejectionTable } from "@/components/RejectionTable";
import { TradeHistory } from "@/components/TradeHistory";
import { SettingsPanel } from "@/components/SettingsPanel";
import { LoginGate } from "@/components/LoginGate";

function Dashboard() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [rejSymbol, setRejSymbol] = useState("");
  const [rejStrategy, setRejStrategy] = useState("");

  const { data: status, refresh: refreshStatus } = usePolling(api.getStatus);
  const { data: market } = usePolling(api.getMarket);
  const { data: trades } = usePolling(api.getTrades);
  const { data: settings, refresh: refreshSettings } = usePolling(
    api.getSettings,
  );
  const { data: analytics } = usePolling(api.getAnalytics);
  const { data: greeks } = usePolling(api.getPortfolioGreeks);

  const rejFetcher = useCallback(
    () => api.getRejections(50, rejSymbol, rejStrategy),
    [rejSymbol, rejStrategy],
  );
  const { data: rejections } = usePolling(rejFetcher);

  const handleFilterChange = (symbol: string, strategy: string) => {
    setRejSymbol(symbol);
    setRejStrategy(strategy);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <StatusBar
        status={status}
        market={market}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className="mx-auto max-w-7xl space-y-8 px-6 py-6">
        <MarketRegime
          regime={status?.regime ?? null}
          drawdown={status?.drawdown ?? null}
        />
        <MarketOverview market={market} />
        <PerformancePanel analytics={analytics} greeks={greeks} />
        <TradeHistory data={trades} />
        <RejectionTable
          data={rejections}
          onFilterChange={handleFilterChange}
          symbols={status?.symbols ?? []}
        />
      </main>
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSaved={() => {
          refreshSettings();
          refreshStatus();
        }}
      />
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(hasCredentials());

  if (!authed) {
    return <LoginGate onAuthenticated={() => setAuthed(true)} />;
  }

  return <Dashboard />;
}
