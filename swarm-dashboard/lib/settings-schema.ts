export type SettingControl = "toggle" | "number" | "select";
export type SettingValue = boolean | number | string;

export interface SettingOption {
  label: string;
  value: string;
}

export interface SettingDefinition {
  key: string;
  label: string;
  description: string;
  control: SettingControl;
  defaultValue: SettingValue;
  min?: number;
  max?: number;
  step?: number;
  options?: SettingOption[];
  risk?: "low" | "medium" | "high";
}

export interface SettingSection {
  id: string;
  title: string;
  description: string;
  settings: SettingDefinition[];
}

export const settingsSections: SettingSection[] = [
  {
    id: "agent-lifecycle",
    title: "Agent Lifecycle",
    description: "Configure how the swarm scales, retires, and recovers agents.",
    settings: [
      {
        key: "autonomousScaling",
        label: "Autonomous Scaling",
        description: "Allow the swarm to create agents based on workload pressure.",
        control: "toggle",
        defaultValue: true,
        risk: "medium",
      },
      {
        key: "autoRecycling",
        label: "Automatic Recycling",
        description: "Recycle low-fitness agents without manual intervention.",
        control: "toggle",
        defaultValue: true,
        risk: "low",
      },
      {
        key: "recycleThreshold",
        label: "Recycle Threshold",
        description: "Minimum fitness score before an agent is eligible for recycling.",
        control: "number",
        defaultValue: 8,
        min: 1,
        max: 100,
        step: 1,
        risk: "high",
      },
    ],
  },
  {
    id: "execution-limits",
    title: "Execution Limits",
    description: "Bound throughput and latency-sensitive operations.",
    settings: [
      {
        key: "triggerCooldownSeconds",
        label: "Trigger Cooldown (seconds)",
        description: "Cooldown period before an agent can be manually triggered again.",
        control: "number",
        defaultValue: 5,
        min: 0,
        max: 120,
        step: 1,
        risk: "low",
      },
      {
        key: "maxConcurrentTasks",
        label: "Max Concurrent Tasks",
        description: "Upper bound of active tasks executed by the swarm at once.",
        control: "number",
        defaultValue: 12,
        min: 1,
        max: 200,
        step: 1,
        risk: "medium",
      },
      {
        key: "telemetryIntervalSeconds",
        label: "Telemetry Interval",
        description: "How frequently the swarm updates telemetry snapshots.",
        control: "select",
        defaultValue: "5",
        options: [
          { label: "Every 2 seconds", value: "2" },
          { label: "Every 5 seconds", value: "5" },
          { label: "Every 10 seconds", value: "10" },
          { label: "Every 30 seconds", value: "30" },
        ],
        risk: "low",
      },
    ],
  },
  {
    id: "integrations",
    title: "Integrations",
    description: "Control external provider and model behavior.",
    settings: [
      {
        key: "modelRoutingMode",
        label: "Model Routing Mode",
        description: "Choose whether to use local-only models or hybrid routing.",
        control: "select",
        defaultValue: "hybrid",
        options: [
          { label: "Local Only", value: "local" },
          { label: "Hybrid", value: "hybrid" },
          { label: "Cloud Preferred", value: "cloud" },
        ],
        risk: "medium",
      },
      {
        key: "strictSafetyChecks",
        label: "Strict Safety Checks",
        description: "Block high-risk task payloads before execution.",
        control: "toggle",
        defaultValue: true,
        risk: "high",
      },
    ],
  },
];

export const settingDefinitions: SettingDefinition[] = settingsSections.flatMap(
  (section) => section.settings
);

export function createDefaultSettings(): Record<string, SettingValue> {
  const defaults: Record<string, SettingValue> = {};
  for (const setting of settingDefinitions) {
    defaults[setting.key] = setting.defaultValue;
  }
  return defaults;
}

export function getSettingLabel(key: string): string {
  const match = settingDefinitions.find((setting) => setting.key === key);
  return match?.label ?? key;
}
