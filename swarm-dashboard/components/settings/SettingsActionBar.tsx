"use client";

import { Button } from "@/components/ui/button";

interface SettingsActionBarProps {
  dirty: boolean;
  saving?: boolean;
  onDiscard: () => void;
  onResetDefaults: () => void;
  onSave: () => void;
  saveLabel?: string;
}

export function SettingsActionBar({
  dirty,
  saving = false,
  onDiscard,
  onResetDefaults,
  onSave,
  saveLabel = "Save Changes",
}: SettingsActionBarProps) {
  return (
    <div className="sticky bottom-4 z-30 mt-8 rounded-2xl border border-white/10 bg-black/40 p-4 backdrop-blur-xl">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          {dirty ? "Unsaved Changes" : "No Pending Changes"}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" onClick={onDiscard} disabled={!dirty || saving}>
            Discard
          </Button>
          <Button type="button" variant="destructive" onClick={onResetDefaults} disabled={saving}>
            Reset Defaults
          </Button>
          <Button type="button" onClick={onSave} disabled={!dirty || saving}>
            {saving ? "Saving..." : saveLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
