"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SettingRow } from "@/components/settings/SettingRow";
import { SettingsActionBar } from "@/components/settings/SettingsActionBar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  createDefaultSettings,
  getSettingLabel,
  settingsSections,
  SettingValue,
} from "@/lib/settings-schema";

function formatValue(value: SettingValue): string {
  if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
  return String(value);
}

type ToastState = {
  kind: "success" | "error" | "info";
  message: string;
} | null;

export default function SettingsPage() {
  const initialDefaults = useMemo(() => createDefaultSettings(), []);
  const [baseline, setBaseline] = useState<Record<string, SettingValue>>(initialDefaults);
  const [draft, setDraft] = useState<Record<string, SettingValue>>(initialDefaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  const showToast = (kind: "success" | "error" | "info", message: string) => {
    setToast({ kind, message });
  };

  useEffect(() => {
    const fetchSettings = async () => {
      setLoading(true);
      setErrorMessage(null);
      try {
        const res = await fetch("/api/settings", { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Failed to load settings: ${res.status}`);
        }
        const json = await res.json();
        const loaded = json?.settings && typeof json.settings === "object"
          ? { ...initialDefaults, ...json.settings }
          : initialDefaults;
        setBaseline(loaded);
        setDraft(loaded);
      } catch (error) {
        setErrorMessage("Could not load persisted settings. Using local defaults.");
        console.error(error);
        showToast("error", "Using defaults because settings could not be loaded.");
        setBaseline(initialDefaults);
        setDraft(initialDefaults);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, [initialDefaults]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const dirty = useMemo(() => {
    return Object.keys(baseline).some(
      (key) => draft[key] !== baseline[key]
    );
  }, [draft, baseline]);

  const onChangeSetting = (key: string, value: SettingValue) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaveStatus("idle");
  };

  const handleDiscard = () => {
    setDraft(baseline);
    setSaveStatus("idle");
    showToast("info", "Discarded unsaved changes.");
  };

  const handleResetDefaultsConfirmed = () => {
    setDraft(createDefaultSettings());
    setSaveStatus("idle");
    setConfirmResetOpen(false);
    showToast("info", "Draft reset to defaults. Save to persist.");
  };

  const handleSave = async () => {
    setSaving(true);
    setErrorMessage(null);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: draft }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        const detail = Array.isArray(payload?.details) ? payload.details.join(" | ") : `status ${res.status}`;
        throw new Error(`Failed to save settings: ${detail}`);
      }
      const json = await res.json();
      const persisted = json?.settings && typeof json.settings === "object"
        ? { ...initialDefaults, ...json.settings }
        : draft;
      setBaseline(persisted);
      setDraft(persisted);
      setSaveStatus("saved");
      showToast("success", "Settings saved.");
    } catch (error) {
      setSaveStatus("error");
      setErrorMessage("Save failed. Your draft is still in memory.");
      showToast("error", "Save failed. Please review values and retry.");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };

    const onDocumentClick = (event: MouseEvent) => {
      if (!dirty) return;
      const target = event.target as HTMLElement | null;
      const anchor = target?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;

      const next = new URL(anchor.href, window.location.href);
      const currentPath = `${window.location.pathname}${window.location.search}`;
      const nextPath = `${next.pathname}${next.search}`;
      if (nextPath === currentPath) return;

      const shouldLeave = window.confirm(
        "You have unsaved settings. Leave this page and discard draft changes?"
      );
      if (!shouldLeave) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onDocumentClick, true);
    };
  }, [dirty]);

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">
            System Settings
          </h1>
          <p className="text-muted-foreground text-sm font-mono opacity-60">
            Global configuration for the Raphael Swarm Intelligence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">ENV: LOCAL</Badge>
          <Badge variant="secondary">
            {saveStatus === "saved"
              ? "Changes Saved"
              : saveStatus === "error"
                ? "Save Error"
                : loading
                  ? "Loading"
                  : "Draft Mode"}
          </Badge>
        </div>
      </header>

      {errorMessage && (
        <section className="rounded-xl border border-destructive/40 bg-destructive/10 p-3">
          <p className="text-xs font-medium text-destructive">{errorMessage}</p>
        </section>
      )}
      {toast && (
        <section
          className={`fixed right-6 top-6 z-50 rounded-xl border px-4 py-3 text-xs font-semibold shadow-2xl backdrop-blur-xl ${
            toast.kind === "success"
              ? "border-green-500/30 bg-green-500/10 text-green-300"
              : toast.kind === "error"
                ? "border-destructive/40 bg-destructive/15 text-destructive"
                : "border-primary/30 bg-primary/10 text-primary"
          }`}
        >
          {toast.message}
        </section>
      )}

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 space-y-6 lg:col-span-8">
          {settingsSections.map((section) => (
            <section key={section.id} className="glass-card space-y-5">
              <div>
                <h2 className="text-lg font-bold">{section.title}</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  {section.description}
                </p>
              </div>
              <Separator />
              <div className="space-y-4">
                {section.settings.map((setting) => (
                  <SettingRow
                    key={setting.key}
                    setting={setting}
                    value={draft[setting.key]}
                    onChange={onChangeSetting}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>

        <aside className="col-span-12 space-y-6 lg:col-span-4">
          <section className="glass-card space-y-4 lg:sticky lg:top-8">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">
              System Snapshot
            </h2>
            <div className="space-y-3">
              {Object.entries(draft)
                .slice(0, 8)
                .map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2"
                  >
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {getSettingLabel(key)}
                    </span>
                    <span className="text-xs font-mono">{formatValue(value)}</span>
                  </div>
                ))}
            </div>
          </section>
        </aside>
      </div>

      <SettingsActionBar
        dirty={dirty}
        saving={saving}
        onDiscard={handleDiscard}
        onResetDefaults={() => setConfirmResetOpen(true)}
        onSave={handleSave}
        saveLabel={saveStatus === "saved" ? "Saved" : "Save Changes"}
      />

      <AlertDialog open={confirmResetOpen} onOpenChange={setConfirmResetOpen}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Reset to defaults?</AlertDialogTitle>
            <AlertDialogDescription>
              This will replace your current draft settings with safe defaults.
              It does not persist until you press Save Changes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleResetDefaultsConfirmed}>
              Reset Draft
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
