import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { StatusBar } from "@/components/StatusBar";
import { MarketOverview } from "@/components/MarketOverview";
import { RejectionTable } from "@/components/RejectionTable";
import { TradeHistory } from "@/components/TradeHistory";
import { SettingsPanel } from "@/components/SettingsPanel";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [rejSymbol, setRejSymbol] = useState("");
  const [rejStrategy, setRejStrategy] = useState("");

  const { data: status, refresh: refreshStatus } = usePolling(api.getStatus);
  const { data: market } = usePolling(api.getMarket);
  const { data: trades } = usePolling(api.getTrades);
  const { data: settings, refresh: refreshSettings } = usePolling(
    api.getSettings,
  );

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
        <MarketOverview market={market} />
        <RejectionTable
          data={rejections}
          onFilterChange={handleFilterChange}
          symbols={status?.symbols ?? []}
        />
        <TradeHistory data={trades} />
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
