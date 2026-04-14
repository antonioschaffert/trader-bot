import type { AccountStatus } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface Props {
  accounts: AccountStatus[];
  activeAccountId: string;
  onSelect: (accountId: string) => void;
  onManageAccounts: () => void;
}

export function AccountSwitcher({ accounts, activeAccountId, onSelect, onManageAccounts }: Props) {
  if (accounts.length === 0) {
    return null;
  }

  const active = accounts.find((a) => a.account_id === activeAccountId);

  return (
    <div className="relative inline-block">
      <select
        value={activeAccountId}
        onChange={(e) => {
          if (e.target.value === "__manage__") {
            onManageAccounts();
          } else {
            onSelect(e.target.value);
          }
        }}
        className="h-8 rounded-md border border-input bg-background px-3 pr-8 text-sm font-medium shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">All Accounts</option>
        {accounts.map((acct) => (
          <option key={acct.account_id} value={acct.account_id}>
            {acct.name} ({acct.is_paper ? "Paper" : "Live"})
            {!acct.enabled ? " [off]" : ""}
          </option>
        ))}
        <option value="__manage__">Manage Accounts...</option>
      </select>
      {active && (
        <div className="mt-1 flex items-center gap-1.5">
          <Badge variant={active.is_paper ? "secondary" : "destructive"} className="text-[10px] px-1.5 py-0">
            {active.is_paper ? "Paper" : "Live"}
          </Badge>
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              active.running ? "bg-green-500" : "bg-gray-400"
            }`}
          />
          <span className="text-[10px] text-muted-foreground">
            {active.running ? "Running" : "Stopped"}
          </span>
        </div>
      )}
    </div>
  );
}
