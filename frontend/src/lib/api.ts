export interface StatusData {
  running: boolean;
  paper_mode: boolean;
  last_scan_time: string | null;
  symbols: string[];
}

export interface MarketData {
  symbol: string;
  price: number;
  iv_rank: number | null;
  rsi: number | null;
  sma_50: number | null;
  sma_20: number | null;
  current_iv: number | null;
  timestamp: string;
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
  updated_at?: string;
}

const BASE = `${import.meta.env.VITE_API_URL ?? ""}/api`;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getStatus: () => fetchJson<StatusData>("/status"),
  getMarket: () => fetchJson<MarketData[]>("/market"),
  getRejections: (limit = 50, symbol = "", strategy = "") => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (symbol) params.set("symbol", symbol);
    if (strategy) params.set("strategy", strategy);
    return fetchJson<RejectionsResponse>(`/rejections?${params}`);
  },
  getTrades: () => fetchJson<TradesResponse>("/trades"),
  getIvHistory: (symbol: string, days = 30) =>
    fetchJson<IvPoint[]>(`/iv-history?symbol=${symbol}&days=${days}`),
  getSettings: () => fetchJson<Settings>("/settings"),
  putSettings: async (settings: Partial<Settings>): Promise<Settings> => {
    const res = await fetch(`${BASE}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
};
