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
import { Badge } from "@/components/ui/badge";

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
  | "wheel"
  | "regime"
  | "execution"
  | "schedule"
  | "notifications";

function cloneSettings(s: Settings): Record<string, unknown> {
  return JSON.parse(JSON.stringify(s)) as Record<string, unknown>;
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Known SMS/email event options for checkbox rendering */
const SMS_EVENTS = ["fill", "stop_loss", "roll", "circuit_breaker", "error", "regime_change", "drawdown_alert"];
const EMAIL_EVENTS = ["daily_summary", "weekly_recap"];

/** Render a 2-element numeric array as min/max range inputs */
function RangeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: [number, number];
  onChange: (val: [number, number]) => void;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          value={String(value[0])}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            onChange([isNaN(v) ? 0 : v, value[1]]);
          }}
          className="h-8"
          step="any"
        />
        <span className="text-xs text-muted-foreground">to</span>
        <Input
          type="number"
          value={String(value[1])}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            onChange([value[0], isNaN(v) ? 0 : v]);
          }}
          className="h-8"
          step="any"
        />
      </div>
    </div>
  );
}

/** Render a string-keyed object as per-key number inputs (e.g. spread_width: {SPY: 5, QQQ: 3}) */
function MapField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Record<string, number>;
  onChange: (val: Record<string, number>) => void;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <div className="space-y-2">
        {Object.entries(value).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <span className="w-12 text-xs font-medium text-muted-foreground">{k}</span>
            <Input
              type="number"
              value={String(v)}
              onChange={(e) => {
                const parsed = parseFloat(e.target.value);
                onChange({ ...value, [k]: isNaN(parsed) ? 0 : parsed });
              }}
              className="h-8"
              step="any"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render array of strings as checkboxes from known options */
function EventCheckboxes({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string[];
  options: string[];
  onChange: (val: string[]) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const checked = value.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => {
                if (checked) {
                  onChange(value.filter((v) => v !== opt));
                } else {
                  onChange([...value, opt]);
                }
              }}
              className={`rounded-md border px-2 py-1 text-xs transition-colors ${
                checked
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {formatLabel(opt)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Render a string array as comma-separated input */
function StringArrayField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string[];
  onChange: (val: string[]) => void;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input
        value={value.join(", ")}
        onChange={(e) => {
          onChange(
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          );
        }}
      />
    </div>
  );
}

/**
 * Recursively render fields for a section, handling:
 * - booleans → Switch
 * - numbers → number Input
 * - strings → text Input
 * - 2-element number arrays → min/max Range
 * - string arrays → comma input or checkboxes
 * - objects with number values → per-key MapField
 * - nested objects → sub-section with heading
 */
function SectionFields({
  data,
  onChange,
  prefix = "",
  eventHints = {},
}: {
  data: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  prefix?: string;
  eventHints?: Record<string, string[]>;
}) {
  return (
    <div className="space-y-4">
      {Object.entries(data).map(([key, value]) => {
        const fullKey = prefix ? `${prefix}.${key}` : key;

        // Boolean → Switch
        if (typeof value === "boolean") {
          return (
            <div key={fullKey} className="flex items-center justify-between">
              <Label htmlFor={fullKey}>{formatLabel(key)}</Label>
              <Switch
                id={fullKey}
                checked={value}
                onCheckedChange={(val: boolean) => onChange(key, val)}
              />
            </div>
          );
        }

        // Number → number input
        if (typeof value === "number") {
          return (
            <div key={fullKey} className="space-y-1">
              <Label htmlFor={fullKey}>{formatLabel(key)}</Label>
              <Input
                id={fullKey}
                type="number"
                value={String(value)}
                onChange={(e) => {
                  const parsed = parseFloat(e.target.value);
                  onChange(key, isNaN(parsed) ? 0 : parsed);
                }}
                step="any"
              />
            </div>
          );
        }

        // String → text input
        if (typeof value === "string") {
          return (
            <div key={fullKey} className="space-y-1">
              <Label htmlFor={fullKey}>{formatLabel(key)}</Label>
              <Input
                id={fullKey}
                value={value}
                onChange={(e) => onChange(key, e.target.value)}
              />
            </div>
          );
        }

        // Array handling
        if (Array.isArray(value)) {
          // 2-element number array → Range (min/max)
          if (
            value.length === 2 &&
            typeof value[0] === "number" &&
            typeof value[1] === "number"
          ) {
            return (
              <RangeField
                key={fullKey}
                label={formatLabel(key)}
                value={value as [number, number]}
                onChange={(val) => onChange(key, val)}
              />
            );
          }

          // String array with known event options → checkboxes
          if (eventHints[key] && value.every((v) => typeof v === "string")) {
            return (
              <EventCheckboxes
                key={fullKey}
                label={formatLabel(key)}
                value={value as string[]}
                options={eventHints[key]}
                onChange={(val) => onChange(key, val)}
              />
            );
          }

          // Generic string array → comma-separated input
          if (value.every((v) => typeof v === "string")) {
            return (
              <StringArrayField
                key={fullKey}
                label={formatLabel(key)}
                value={value as string[]}
                onChange={(val) => onChange(key, val)}
              />
            );
          }

          // Other arrays → show as JSON
          return (
            <div key={fullKey} className="space-y-1">
              <Label>{formatLabel(key)}</Label>
              <Input
                value={JSON.stringify(value)}
                onChange={(e) => {
                  try {
                    onChange(key, JSON.parse(e.target.value));
                  } catch {
                    // ignore invalid JSON while typing
                  }
                }}
                className="font-mono text-xs"
              />
            </div>
          );
        }

        // Object → could be a map (number values) or nested section
        if (value != null && typeof value === "object") {
          const entries = Object.entries(value as Record<string, unknown>);

          // All-number values → per-key MapField (e.g. spread_width: {SPY: 5})
          if (entries.length > 0 && entries.every(([, v]) => typeof v === "number")) {
            return (
              <MapField
                key={fullKey}
                label={formatLabel(key)}
                value={value as Record<string, number>}
                onChange={(val) => onChange(key, val)}
              />
            );
          }

          // Nested object → sub-section with heading
          return (
            <div key={fullKey} className="space-y-3">
              <Separator />
              <h4 className="text-sm font-semibold text-foreground">{formatLabel(key)}</h4>
              <SectionFields
                data={value as Record<string, unknown>}
                prefix={fullKey}
                onChange={(subKey, subVal) => {
                  const updated = { ...(value as Record<string, unknown>), [subKey]: subVal };
                  onChange(key, updated);
                }}
              />
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}

export function SettingsPanel({ open, onClose, settings, onSaved }: Props) {
  const [local, setLocal] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (settings && open) {
      setLocal(cloneSettings(settings));
      setError(null);
      setSuccess(null);
    }
  }, [settings, open]);

  if (!local) {
    return (
      <Sheet open={open} onOpenChange={(val) => !val && onClose()}>
        <SheetContent side="right" className="w-[460px] overflow-y-auto sm:max-w-[460px]">
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
      const next = JSON.parse(JSON.stringify(prev)) as Record<string, unknown>;
      if (section === "symbols") {
        return next;
      }
      const sectionData = (next[section] ?? {}) as Record<string, unknown>;
      sectionData[key] = value;
      next[section] = sectionData;
      return next;
    });
    setSuccess(null);
  };

  const saveSection = async (section: SectionKey) => {
    if (!local) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: Record<string, unknown> = {};
      if (section === "symbols") {
        payload.symbols = local.symbols;
      } else {
        payload[section] = local[section];
      }
      await api.putSettings(payload as Partial<Settings>);
      setSuccess(`${formatLabel(section)} saved`);
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
    { value: "exhaustion", label: "Exhaust." },
    { value: "risk", label: "Risk" },
    { value: "wheel", label: "Wheel" },
    { value: "regime", label: "Regime" },
    { value: "execution", label: "Exec." },
    { value: "schedule", label: "Sched." },
    { value: "notifications", label: "Notif." },
  ];

  // Only show tabs for sections that exist in settings
  const visibleTabs = tabs.filter(
    (t) => t.value === "symbols" || local[t.value] != null,
  );

  return (
    <Sheet open={open} onOpenChange={(val) => !val && onClose()}>
      <SheetContent side="right" className="w-[460px] overflow-y-auto sm:max-w-[460px]">
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
          {success && (
            <div className="mb-4 rounded-md bg-green-500/10 p-3 text-sm text-green-600 dark:text-green-400">
              {success}
            </div>
          )}

          <Tabs defaultValue="symbols">
            <TabsList variant="line" className="mb-4 w-full flex-wrap">
              {visibleTabs.map((t) => (
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
                    value={((local.symbols as string[]) ?? []).join(", ")}
                    onChange={(e) => {
                      setLocal((prev) => {
                        if (!prev) return prev;
                        const next = JSON.parse(JSON.stringify(prev)) as Record<string, unknown>;
                        next.symbols = e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean);
                        return next;
                      });
                      setSuccess(null);
                    }}
                  />
                </div>

                {/* Show last updated timestamp */}
                {typeof local.updated_at === "string" && (
                  <div className="text-xs text-muted-foreground">
                    Last updated: {new Date(local.updated_at).toLocaleString()}
                  </div>
                )}

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
            {visibleTabs
              .filter((t) => t.value !== "symbols")
              .map((t) => {
                const section = t.value;
                const sectionData = (local[section] ?? {}) as Record<string, unknown>;

                // Provide event hints for notifications tab
                const eventHints: Record<string, string[]> = {};
                if (section === "notifications") {
                  eventHints.sms_events = SMS_EVENTS;
                  eventHints.email_events = EMAIL_EVENTS;
                }

                return (
                  <TabsContent key={section} value={section}>
                    {/* Section header with enabled badge if applicable */}
                    {typeof sectionData.enabled === "boolean" && (
                      <div className="mb-3 flex items-center gap-2">
                        <Badge variant={sectionData.enabled ? "default" : "outline"}>
                          {sectionData.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </div>
                    )}

                    <SectionFields
                      data={sectionData}
                      onChange={(key, value) =>
                        updateSection(section, key, value)
                      }
                      eventHints={eventHints}
                    />
                    <Separator className="my-4" />
                    <Button
                      onClick={() => saveSection(section)}
                      disabled={saving}
                    >
                      {saving ? "Saving..." : `Save ${formatLabel(section)}`}
                    </Button>
                  </TabsContent>
                );
              })}
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
}
