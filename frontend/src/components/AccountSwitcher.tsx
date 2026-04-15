import { useState, useRef, useEffect } from "react";
import type { AccountStatus } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface Props {
  accounts: AccountStatus[];
  activeAccountId: string;
  onSelect: (accountId: string) => void;
  onManageAccounts: () => void;
}

export function AccountSwitcher({ accounts, activeAccountId, onSelect, onManageAccounts }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (accounts.length === 0) return null;

  const active = accounts.find((a) => a.account_id === activeAccountId);
  const label = active ? active.name : "All Accounts";

  return (
    <div className="relative" ref={ref}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium shadow-sm transition-colors hover:bg-muted"
      >
        <span>{label}</span>
        {active && (
          <Badge variant={active.is_paper ? "secondary" : "destructive"} className="text-[10px] px-1.5 py-0">
            {active.is_paper ? "Paper" : "Live"}
          </Badge>
        )}
        {active && (
          <span className={`inline-block h-2 w-2 rounded-full ${active.running ? "bg-green-500" : "bg-gray-400"}`} />
        )}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-muted-foreground">
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border bg-background p-1 shadow-lg">
          {/* All accounts option */}
          <button
            onClick={() => { onSelect(""); setOpen(false); }}
            className={`flex w-full items-center rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted ${activeAccountId === "" ? "bg-muted font-medium" : ""}`}
          >
            All Accounts
          </button>

          {/* Account items */}
          {accounts.map((acct) => (
            <button
              key={acct.account_id}
              onClick={() => { onSelect(acct.account_id); setOpen(false); }}
              className={`flex w-full flex-col rounded-md px-3 py-2 text-left transition-colors hover:bg-muted ${activeAccountId === acct.account_id ? "bg-muted" : ""}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{acct.name}</span>
                <div className="flex items-center gap-1.5">
                  <Badge variant={acct.is_paper ? "secondary" : "destructive"} className="text-[10px] px-1.5 py-0">
                    {acct.is_paper ? "Paper" : "Live"}
                  </Badge>
                  <span className={`inline-block h-2 w-2 rounded-full ${acct.running ? "bg-green-500" : "bg-gray-400"}`} />
                </div>
              </div>
              <div className="mt-1 flex items-center gap-1.5">
                {Object.entries(acct.strategies).map(([k, v]) => (
                  <Badge key={k} variant={v ? "default" : "outline"} className="text-[9px] px-1 py-0">
                    {k}
                  </Badge>
                ))}
                {!acct.enabled && (
                  <span className="text-[10px] text-muted-foreground">[disabled]</span>
                )}
              </div>
            </button>
          ))}

          {/* Manage link */}
          <div className="mt-1 border-t pt-1">
            <button
              onClick={() => { onManageAccounts(); setOpen(false); }}
              className="flex w-full items-center rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              Manage Accounts...
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
