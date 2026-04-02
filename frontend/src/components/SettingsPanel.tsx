import { useState, useEffect } from "react";
import type { Settings } from "@/lib/api";
import { api } from "@/lib/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface Props {
  open: boolean;
  onClose: () => void;
  settings: Settings | null;
  onSaved: () => void;
}

type SectionKey =
  | "symbols"
  | "swing"
  | "exhaustion"
  | "risk"
  | "execution"
  | "notifications";

/** Deep-clone settings into local mutable state. */
function cloneSettings(s: Settings): Settings {
  return JSON.parse(JSON.stringify(s)) as Settings;
}

function SectionFields({
  data,
  onChange,
}: {
  data: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}) {
  return (
    <div className="space-y-4">
      {Object.entries(data).map(([key, value]) => {
        if (typeof value === "boolean") {
          return (
            <div key={key} className="flex items-center justify-between">
              <Label htmlFor={key}>{formatLabel(key)}</Label>
              <Switch
                id={key}
                checked={value}
                onCheckedChange={(val: boolean) => onChange(key, val)}
              />
            </div>
          );
        }
        if (typeof value === "number") {
          return (
            <div key={key} className="space-y-1">
              <Label htmlFor={key}>{formatLabel(key)}</Label>
              <Input
                id={key}
                type="number"
                value={String(value)}
                onChange={(e) => {
                  const parsed = parseFloat(e.target.value);
                  onChange(key, isNaN(parsed) ? 0 : parsed);
                }}
              />
            </div>
          );
        }
        if (typeof value === "string") {
          return (
            <div key={key} className="space-y-1">
              <Label htmlFor={key}>{formatLabel(key)}</Label>
              <Input
                id={key}
                value={value}
                onChange={(e) => onChange(key, e.target.value)}
              />
            </div>
          );
        }
        // Skip nested objects / arrays for simplicity
        return null;
      })}
    </div>
  );
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function SettingsPanel({ open, onClose, settings, onSaved }: Props) {
  const [local, setLocal] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (settings && open) {
      setLocal(cloneSettings(settings));
    }
  }, [settings, open]);

  if (!local) {
    return (
      <Sheet open={open} onOpenChange={(val) => !val && onClose()}>
        <SheetContent side="right" className="w-[420px] overflow-y-auto sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Settings</SheetTitle>
            <SheetDescription>Loading...</SheetDescription>
          </SheetHeader>
        </SheetContent>
      </Sheet>
    );
  }

  const updateSection = (section: SectionKey, key: string, value: unknown) => {
    setLocal((prev) => {
      if (!prev) return prev;
      const next = cloneSettings(prev);
      if (section === "symbols") {
        // symbols is a string[], handle separately
        return next;
      }
      const sectionData = next[section] as Record<string, unknown>;
      sectionData[key] = value;
      return next;
    });
  };

  const saveSection = async (section: SectionKey) => {
    if (!local) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Partial<Settings> = {};
      if (section === "symbols") {
        payload.symbols = local.symbols;
      } else {
        payload[section] = local[section];
      }
      await api.putSettings(payload);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const tabs: { value: SectionKey; label: string }[] = [
    { value: "symbols", label: "General" },
    { value: "swing", label: "Swing" },
    { value: "exhaustion", label: "Exhaustion" },
    { value: "risk", label: "Risk" },
    { value: "execution", label: "Execution" },
    { value: "notifications", label: "Notif." },
  ];

  return (
    <Sheet open={open} onOpenChange={(val) => !val && onClose()}>
      <SheetContent side="right" className="w-[420px] overflow-y-auto sm:max-w-[420px]">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
          <SheetDescription>
            Configure trading bot parameters.
          </SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-6">
          {error && (
            <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <Tabs defaultValue="symbols">
            <TabsList variant="line" className="mb-4 w-full">
              {tabs.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {/* General / Symbols tab */}
            <TabsContent value="symbols">
              <div className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="symbols">
                    Symbols (comma-separated)
                  </Label>
                  <Input
                    id="symbols"
                    value={local.symbols.join(", ")}
                    onChange={(e) => {
                      setLocal((prev) => {
                        if (!prev) return prev;
                        const next = cloneSettings(prev);
                        next.symbols = e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean);
                        return next;
                      });
                    }}
                  />
                </div>
                <Separator />
                <Button
                  onClick={() => saveSection("symbols")}
                  disabled={saving}
                >
                  {saving ? "Saving..." : "Save General"}
                </Button>
              </div>
            </TabsContent>

            {/* Dynamic section tabs */}
            {(
              ["swing", "exhaustion", "risk", "execution", "notifications"] as SectionKey[]
            ).map((section) => (
              <TabsContent key={section} value={section}>
                <SectionFields
                  data={local[section] as Record<string, unknown>}
                  onChange={(key, value) =>
                    updateSection(section, key, value)
                  }
                />
                <Separator className="my-4" />
                <Button
                  onClick={() => saveSection(section)}
                  disabled={saving}
                >
                  {saving ? "Saving..." : `Save ${formatLabel(section)}`}
                </Button>
              </TabsContent>
            ))}
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
}
