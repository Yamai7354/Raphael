"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { SettingDefinition, SettingValue } from "@/lib/settings-schema";

interface SettingRowProps {
  setting: SettingDefinition;
  value: SettingValue;
  onChange: (key: string, value: SettingValue) => void;
}

const riskVariant: Record<NonNullable<SettingDefinition["risk"]>, "outline" | "secondary" | "destructive"> = {
  low: "secondary",
  medium: "outline",
  high: "destructive",
};

export function SettingRow({ setting, value, onChange }: SettingRowProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-white/10 bg-white/5 p-4 md:flex-row md:items-center md:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <p className="text-sm font-bold">{setting.label}</p>
          {setting.risk && (
            <Badge variant={riskVariant[setting.risk]} className="uppercase tracking-wide">
              {setting.risk} risk
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{setting.description}</p>
      </div>

      <div className="w-full md:w-64 md:flex-none">
        {setting.control === "toggle" && (
          <Button
            type="button"
            variant="outline"
            onClick={() => onChange(setting.key, !Boolean(value))}
            role="switch"
            aria-checked={Boolean(value)}
            className={cn(
              "w-full justify-between rounded-xl border-white/20 bg-black/30 text-xs font-bold uppercase tracking-wider",
              Boolean(value) && "border-primary/40 bg-primary/10 text-primary"
            )}
          >
            <span>{Boolean(value) ? "Enabled" : "Disabled"}</span>
            <span
              className={cn(
                "h-2.5 w-2.5 rounded-full bg-zinc-500 transition-colors",
                Boolean(value) && "bg-primary"
              )}
            />
          </Button>
        )}

        {setting.control === "number" && (
          <Input
            type="number"
            min={setting.min}
            max={setting.max}
            step={setting.step ?? 1}
            value={typeof value === "number" ? value : Number(value) || 0}
            onChange={(event) => onChange(setting.key, Number(event.target.value))}
            className="rounded-xl border-white/20 bg-black/30 font-mono text-sm"
          />
        )}

        {setting.control === "select" && (
          <Select
            value={String(value)}
            onValueChange={(newValue) => onChange(setting.key, newValue)}
          >
            <SelectTrigger className="w-full rounded-xl border-white/20 bg-black/30">
              <SelectValue placeholder="Choose value" />
            </SelectTrigger>
            <SelectContent>
              {setting.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  );
}
