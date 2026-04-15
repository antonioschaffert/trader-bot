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
import { WheelStatus } from "@/components/WheelStatus";
import { AccountsPanel } from "@/components/AccountsPanel";
import { LoginGate } from "@/components/LoginGate";
import { ConfigHealthCheck } from "@/components/ConfigHealthCheck";
import { DailyRiskControl } from "@/components/DailyRiskControl";

function Dashboard() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [accountsOpen, setAccountsOpen] = useState(false);
  const [activeAccountId, setActiveAccountId] = useState("");
  const [rejSymbol, setRejSymbol] = useState("");
  const [rejStrategy, setRejStrategy] = useState("");

  // Account-filtered data fetchers
  const statusFetcher = useCallback(() => api.getStatus(activeAccountId), [activeAccountId]);
  const tradesFetcher = useCallback(() => api.getTrades(activeAccountId), [activeAccountId]);
  const analyticsFetcher = useCallback(() => api.getAnalytics(activeAccountId), [activeAccountId]);
  const greeksFetcher = useCallback(() => api.getPortfolioGreeks(activeAccountId), [activeAccountId]);
  const wheelFetcher = useCallback(() => api.getWheel(activeAccountId), [activeAccountId]);
  const orderLogsFetcher = useCallback(() => api.getOrderLogs(activeAccountId, 100), [activeAccountId]);

  const { data: status, refresh: refreshStatus } = usePolling(statusFetcher);
  const { data: market } = usePolling(api.getMarket);
  const { data: trades } = usePolling(tradesFetcher);
  const { data: orderLogsData } = usePolling(orderLogsFetcher);
  const { data: settings, refresh: refreshSettings } = usePolling(api.getSettings);
  const { data: analytics } = usePolling(analyticsFetcher);
  const { data: greeks } = usePolling(greeksFetcher);
  const { data: wheel } = usePolling(wheelFetcher);

  const rejFetcher = useCallback(
    () => api.getRejections(50, rejSymbol, rejStrategy, activeAccountId),
    [rejSymbol, rejStrategy, activeAccountId],
  );
  const { data: rejections } = usePolling(rejFetcher);

  const handleFilterChange = (symbol: string, strategy: string) => {
    setRejSymbol(symbol);
    setRejStrategy(strategy);
  };

  const orderLogs = orderLogsData?.logs ?? null;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <StatusBar
        status={status}
        market={market}
        activeAccountId={activeAccountId}
        onSelectAccount={setActiveAccountId}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenAccounts={() => setAccountsOpen(true)}
      />
      <main className="mx-auto max-w-7xl space-y-8 px-6 py-6">
        <ConfigHealthCheck settings={settings} />
        <MarketRegime
          regime={status?.regime ?? null}
          drawdown={status?.drawdown ?? null}
        />
        <DailyRiskControl
          dailyPnl={trades?.daily_pnl ?? 0}
          settings={settings}
          onSaved={() => {
            refreshSettings();
            refreshStatus();
          }}
        />
        <MarketOverview market={market} />
        <WheelStatus data={wheel} />
        <PerformancePanel analytics={analytics} greeks={greeks} />
        <TradeHistory
          data={trades}
          orderLogs={orderLogs}
          equityCurve={analytics?.equity_curve}
        />
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
      <AccountsPanel
        open={accountsOpen}
        onOpenChange={setAccountsOpen}
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
