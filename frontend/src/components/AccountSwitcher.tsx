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
    <div className="flex items-center gap-2">
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
            {acct.name}
            {!acct.enabled ? " [off]" : ""}
          </option>
        ))}
        <option value="__manage__">Manage Accounts...</option>
      </select>
      {active && (
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            active.running ? "bg-green-500" : "bg-gray-400"
          }`}
          title={active.running ? "Running" : "Stopped"}
        />
      )}
    </div>
  );
}
