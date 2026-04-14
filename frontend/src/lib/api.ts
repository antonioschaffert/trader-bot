export interface RegimeData {
  volatility_regime: "low" | "normal" | "elevated" | "crisis";
  trend_regime: "strong_bull" | "bull" | "neutral" | "bear" | "strong_bear";
  market_phase: "trending" | "mean_reverting" | "transitioning";
  vix_current: number;
  vix_sma_10: number;
  vix_percentile_30d: number;
  vix_term_structure: string;
  trend_score: number;
  adx: number;
  weekly_trend: string;
  daily_trend: string;
  intraday_trend: string;
  position_size_multiplier: number;
  spread_width_multiplier: number;
  delta_adjustment: number;
  premium_threshold_multiplier: number;
  should_trade: boolean;
}

export interface DrawdownData {
  peak_equity: number;
  current_equity: number;
  drawdown_pct: number;
  max_drawdown_pct: number;
  consecutive_losses: number;
  consecutive_wins: number;
  longest_losing_streak: number;
  cooldown_until: string | null;
  is_in_cooldown: boolean;
  size_reduction_factor: number;
  total_trades: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
}

export interface AccountStatus {
  account_id: string;
  name: string;
  is_paper: boolean;
  enabled: boolean;
  running: boolean;
  strategies: Record<string, boolean>;
}

export interface Account {
  account_id: string;
  name: string;
  is_paper: boolean;
  enabled: boolean;
  strategies: Record<string, boolean>;
  symbols: string[];
  api_key_masked?: string;
  api_secret_masked?: string;
  created_at?: string;
  updated_at?: string;
}

export interface OrderLog {
  _id: string;
  order_id: string;
  action: string;
  symbol?: string;
  signal?: Record<string, unknown>;
  status: string;
  timestamp: string;
  limit_price?: number;
  account_id?: string;
}

export interface StatusData {
  running: boolean;
  scanning: boolean;
  market_hours: boolean;
  paper_mode: boolean;
  last_scan_time: string | null;
  symbols: string[];
  regime: RegimeData | null;
  drawdown: DrawdownData | null;
  accounts: AccountStatus[];
}

export interface MarketData {
  symbol: string;
  price: number;
  iv_rank: number | null;
  iv_percentile: number | null;
  rsi: number | null;
  sma_50: number | null;
  sma_20: number | null;
  current_iv: number | null;
  adx: number | null;
  atr: number | null;
  support: number | null;
  resistance: number | null;
  timestamp: string;
  regime?: {
    volatility: string;
    trend: string;
    phase: string;
    vix: number;
  };
}

export interface Rejection {
  strategy: string;
  reason: string;
  spread_type?: string;
  variables: Record<string, unknown>;
}

export interface ScanRejection {
  _id: string;
  symbol: string;
  timestamp: string;
  market_snapshot: Record<string, unknown>;
  rejections: Rejection[];
}

export interface RejectionsResponse {
  items: ScanRejection[];
  total: number;
}

export interface TradesResponse {
  open: Record<string, unknown>[];
  closed: Record<string, unknown>[];
  daily_pnl: number;
}

export interface IvPoint {
  timestamp: string;
  iv: number;
}

export interface Settings {
  symbols: string[];
  swing: Record<string, unknown>;
  exhaustion: Record<string, unknown>;
  risk: Record<string, unknown>;
  execution: Record<string, unknown>;
  schedule: Record<string, unknown>;
  notifications: Record<string, unknown>;
  regime?: Record<string, unknown>;
  updated_at?: string;
}

export interface PortfolioGreeksData {
  net_delta: number;
  net_gamma: number;
  net_theta: number;
  net_vega: number;
  total_premium_at_risk: number;
  theta_to_delta_ratio: number;
  per_symbol: Record<string, Record<string, number>>;
}

export interface StrategyMetrics {
  strategy: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  total_pnl: number;
  profit_factor: number;
  expectancy: number;
}

export interface EquityCurvePoint {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
}

export interface AnalyticsData {
  total_trades: number;
  total_pnl: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  avg_trade_duration_hours: number;
  pnl_7d: number;
  pnl_30d: number;
  trades_7d: number;
  trades_30d: number;
  win_rate_7d: number;
  win_rate_30d: number;
  by_strategy: StrategyMetrics[];
  by_symbol: Record<string, { trades: number; pnl: number; win_rate: number }>;
  equity_curve: EquityCurvePoint[];
  best_day: number;
  worst_day: number;
  avg_daily_pnl: number;
}

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

const BASE = `${import.meta.env.VITE_API_URL ?? ""}/api`;

let _authHeader: string | null = sessionStorage.getItem("auth");

export function setCredentials(user: string, pass: string) {
  _authHeader = "Basic " + btoa(`${user}:${pass}`);
  sessionStorage.setItem("auth", _authHeader);
}

export function clearCredentials() {
  _authHeader = null;
  sessionStorage.removeItem("auth");
}

export function hasCredentials() {
  return _authHeader !== null;
}

function authHeaders(): HeadersInit {
  return _authHeader ? { Authorization: _authHeader } : {};
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (res.status === 401) {
    clearCredentials();
    throw new Error("unauthorized");
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { clearCredentials(); throw new Error("unauthorized"); }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { clearCredentials(); throw new Error("unauthorized"); }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function deleteJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.status === 401) { clearCredentials(); throw new Error("unauthorized"); }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

/** Append ?account_id=X if non-empty */
function acctParam(accountId: string): string {
  return accountId ? `account_id=${encodeURIComponent(accountId)}` : "";
}

function withAcct(path: string, accountId: string): string {
  const p = acctParam(accountId);
  if (!p) return path;
  return path.includes("?") ? `${path}&${p}` : `${path}?${p}`;
}

export const api = {
  // Account-aware endpoints (pass accountId="" for all)
  getStatus: (accountId = "") => fetchJson<StatusData>(withAcct("/status", accountId)),
  getMarket: () => fetchJson<MarketData[]>("/market"),
  getRejections: (limit = 50, symbol = "", strategy = "", accountId = "") => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (symbol) params.set("symbol", symbol);
    if (strategy) params.set("strategy", strategy);
    if (accountId) params.set("account_id", accountId);
    return fetchJson<RejectionsResponse>(`/rejections?${params}`);
  },
  getTrades: (accountId = "") => fetchJson<TradesResponse>(withAcct("/trades", accountId)),
  getOrderLogs: (accountId = "", limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (accountId) params.set("account_id", accountId);
    return fetchJson<{ logs: OrderLog[] }>(`/order-logs?${params}`);
  },
  getIvHistory: (symbol: string, days = 30) =>
    fetchJson<IvPoint[]>(`/iv-history?symbol=${symbol}&days=${days}`),
  getSettings: () => fetchJson<Settings>("/settings"),
  putSettings: async (settings: Partial<Settings>): Promise<Settings> => {
    return putJson("/settings", settings);
  },
  getRegime: () => fetchJson<RegimeData>("/regime"),
  getAnalytics: (accountId = "") => fetchJson<AnalyticsData>(withAcct("/analytics", accountId)),
  getPortfolioGreeks: (accountId = "") => fetchJson<PortfolioGreeksData>(withAcct("/portfolio-greeks", accountId)),
  getDrawdown: (accountId = "") => fetchJson<DrawdownData>(withAcct("/drawdown", accountId)),
  getWheel: (accountId = "") => fetchJson<WheelData>(withAcct("/wheel", accountId)),

  // Account management
  getAccounts: () => fetchJson<{ accounts: Account[] }>("/accounts"),
  createAccount: (data: Partial<Account> & { api_key: string; api_secret: string }) =>
    postJson<{ account: Account }>("/accounts", data),
  updateAccount: (accountId: string, data: Partial<Account>) =>
    putJson<{ account: Account }>(`/accounts/${accountId}`, data),
  deleteAccount: (accountId: string) =>
    deleteJson<{ deleted: boolean }>(`/accounts/${accountId}`),
  toggleAccount: (accountId: string) =>
    postJson<{ account_id: string; enabled: boolean }>(`/accounts/${accountId}/toggle`, {}),
};
