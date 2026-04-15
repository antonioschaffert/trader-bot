import { useState, useEffect } from "react";
import type { Account } from "@/lib/api";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function StrategyToggles({
  strategies,
  onChange,
}: {
  strategies: Record<string, boolean>;
  onChange: (strategies: Record<string, boolean>) => void;
}) {
  return (
    <div className="flex items-center gap-4">
      {["swing", "exhaustion", "wheel"].map((s) => (
        <label key={s} className="flex items-center gap-1.5 text-sm">
          <Switch
            checked={strategies[s] ?? false}
            onCheckedChange={(checked: boolean) =>
              onChange({ ...strategies, [s]: checked })
            }
          />
          <span className="capitalize">{s}</span>
        </label>
      ))}
    </div>
  );
}

function AccountCard({
  account,
  onUpdate,
  onDelete,
}: {
  account: Account;
  onUpdate: () => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(account.name);
  const [strategies, setStrategies] = useState(account.strategies);
  const [symbols, setSymbols] = useState(account.symbols.join(", "));
  const [saving, setSaving] = useState(false);

  async function handleToggle() {
    await api.toggleAccount(account.account_id);
    onUpdate();
  }

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateAccount(account.account_id, {
        name,
        strategies,
        symbols: symbols.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setEditing(false);
      onUpdate();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete account "${account.name}"?`)) return;
    await api.deleteAccount(account.account_id);
    onDelete();
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span>{account.name}</span>
            <Badge variant={account.is_paper ? "secondary" : "destructive"}>
              {account.is_paper ? "Paper" : "Live"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Switch checked={account.enabled} onCheckedChange={handleToggle} />
              {account.enabled ? "On" : "Off"}
            </label>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-xs text-muted-foreground">
          ID: {account.account_id} | Key: {account.api_key_masked}
        </div>

        {editing ? (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8" />
            </div>
            <div>
              <label className="text-xs font-medium">Symbols (comma-separated)</label>
              <Input value={symbols} onChange={(e) => setSymbols(e.target.value)} className="h-8" />
            </div>
            <div>
              <label className="text-xs font-medium">Strategies</label>
              <StrategyToggles strategies={strategies} onChange={setStrategies} />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-xs">
              <span className="text-muted-foreground">Symbols: </span>
              {account.symbols.join(", ")}
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Strategies:</span>
              {Object.entries(account.strategies).map(([k, v]) => (
                <Badge key={k} variant={v ? "default" : "outline"} className="text-[10px]">
                  {k}
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button size="sm" variant="destructive" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AddAccountForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    account_id: "",
    name: "",
    api_key: "",
    api_secret: "",
    is_paper: true,
    symbols: "SPY, QQQ",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createAccount({
        account_id: form.account_id,
        name: form.name,
        api_key: form.api_key,
        api_secret: form.api_secret,
        is_paper: form.is_paper,
        enabled: false,
        strategies: { swing: true, exhaustion: true, wheel: false },
        symbols: form.symbols.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setForm({ account_id: "", name: "", api_key: "", api_secret: "", is_paper: true, symbols: "SPY, QQQ" });
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <Button variant="outline" className="w-full" onClick={() => setOpen(true)}>
        + Add Account
      </Button>
    );
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm">Add Account</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-2">
          <Input placeholder="Account ID (e.g. paper1)" value={form.account_id}
            onChange={(e) => setForm({ ...form, account_id: e.target.value })} className="h-8" required />
          <Input placeholder="Display Name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-8" required />
          <Input placeholder="Alpaca API Key" value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })} className="h-8" required />
          <Input placeholder="Alpaca API Secret" type="password" value={form.api_secret}
            onChange={(e) => setForm({ ...form, api_secret: e.target.value })} className="h-8" required />
          <Input placeholder="Symbols (comma-separated)" value={form.symbols}
            onChange={(e) => setForm({ ...form, symbols: e.target.value })} className="h-8" />
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={form.is_paper} onCheckedChange={(checked: boolean) => setForm({ ...form, is_paper: checked })} />
            Paper Account
          </label>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={saving}>{saving ? "Creating..." : "Create"}</Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function AccountsPanel({ open, onOpenChange }: Props) {
  const [accounts, setAccounts] = useState<Account[]>([]);

  async function loadAccounts() {
    try {
      const data = await api.getAccounts();
      setAccounts(data.accounts);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (open) loadAccounts();
  }, [open]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:w-[420px] sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Accounts</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4">
          {accounts.map((acct) => (
            <AccountCard
              key={acct.account_id}
              account={acct}
              onUpdate={loadAccounts}
              onDelete={loadAccounts}
            />
          ))}
          <AddAccountForm onCreated={loadAccounts} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
