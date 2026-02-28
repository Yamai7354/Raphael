import { NextResponse } from "next/server";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  createDefaultSettings,
  settingDefinitions,
  SettingValue,
} from "@/lib/settings-schema";

const settingsFilePath = path.join(process.cwd(), "data", "settings.json");

function sanitizeSettings(payload: unknown): Record<string, SettingValue> {
  const defaults = createDefaultSettings();
  if (!payload || typeof payload !== "object") return defaults;

  const input = payload as Record<string, unknown>;
  const sanitized: Record<string, SettingValue> = { ...defaults };

  for (const definition of settingDefinitions) {
    const raw = input[definition.key];
    const expectedType = typeof definition.defaultValue;

    if (raw === undefined) continue;
    if (expectedType === "boolean" && typeof raw === "boolean") {
      sanitized[definition.key] = raw;
    } else if (expectedType === "number" && typeof raw === "number" && Number.isFinite(raw)) {
      sanitized[definition.key] = raw;
    } else if (expectedType === "string" && typeof raw === "string") {
      sanitized[definition.key] = raw;
    }
  }

  return sanitized;
}

function validateSettings(payload: unknown): {
  settings: Record<string, SettingValue>;
  errors: string[];
} {
  const settings = sanitizeSettings(payload);
  const input = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  const errors: string[] = [];

  for (const definition of settingDefinitions) {
    const value = settings[definition.key];
    const raw = input[definition.key];

    if (raw === undefined) continue;

    if (definition.control === "number" && typeof value === "number") {
      if (definition.min !== undefined && value < definition.min) {
        errors.push(`${definition.label} must be >= ${definition.min}`);
      }
      if (definition.max !== undefined && value > definition.max) {
        errors.push(`${definition.label} must be <= ${definition.max}`);
      }
    }

    if (definition.control === "select" && typeof value === "string") {
      const allowed = new Set((definition.options ?? []).map((option) => option.value));
      if (!allowed.has(value)) {
        errors.push(`${definition.label} has an unsupported value`);
      }
    }

    if (typeof raw !== typeof definition.defaultValue) {
      errors.push(`${definition.label} has invalid value type`);
    }
  }

  return { settings, errors };
}

async function readSettingsFromDisk(): Promise<Record<string, SettingValue>> {
  const defaults = createDefaultSettings();
  try {
    const raw = await readFile(settingsFilePath, "utf-8");
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return defaults;
  }
}

export async function GET() {
  const settings = await readSettingsFromDisk();
  return NextResponse.json({ settings });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { settings?: unknown };
    const { settings, errors } = validateSettings(body?.settings);
    if (errors.length > 0) {
      return NextResponse.json(
        { ok: false, error: "Settings validation failed", details: errors },
        { status: 400 }
      );
    }
    await mkdir(path.dirname(settingsFilePath), { recursive: true });
    await writeFile(settingsFilePath, JSON.stringify(settings, null, 2), "utf-8");
    return NextResponse.json({ ok: true, settings });
  } catch {
    return NextResponse.json(
      { ok: false, error: "Failed to save settings" },
      { status: 500 }
    );
  }
}
