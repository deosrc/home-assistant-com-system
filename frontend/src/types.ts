/** The part of Home Assistant's `hass` object the panel uses. */
export interface HomeAssistant {
  callWS<T>(msg: { type: string; [key: string]: unknown }): Promise<T>;
  states: Record<
    string,
    { state: string; attributes?: { friendly_name?: string } }
  >;
  areas?: Record<string, { name: string }>;
  services?: Record<string, unknown>;
  user?: { is_admin: boolean };
}

export interface PanelRoute {
  prefix: string;
  path: string;
}

export interface DashboardData {
  total: number;
  enabled: number;
  disabled: number;
  unavailable: number;
  pending_discoveries: number;
  by_type: Record<string, number>;
}

export interface ReceiverInfo {
  entry_id: string;
  name: string;
  type_id: string;
  type: string;
  type_known: boolean;
  /** The enabled switch; null when it cannot be read. */
  enabled: boolean | null;
  available: boolean;
  entity_id: string | null;
  /** The read-only `notification_receiver` entity; the action's target. */
  receiver_entity_id: string | null;
  /** The device page is where a receiver is edited. */
  device_id: string | null;
  people: string[];
  areas: string[];
}

export interface DiscoveryInfo {
  flow_id: string;
  name: string;
  type: string;
}

/** The target fields shared by the preview and the test send. */
export type PersonTarget =
  { active_choice: "Everyone"; Everyone: true } | string[];

/** The values of a target selector; only the keys with a selection. */
export type SelectedTarget = Record<string, string[]>;

export type ReceiversTarget =
  | { active_choice: "All Areas"; "All Areas": true }
  | { active_choice: "Select"; Select: SelectedTarget };

export interface NotifyTargets {
  /** Everyone, or the listed `person.*` entities. */
  people?: PersonTarget;
  /** Every receiver with an area, or a selection of receivers. */
  receivers?: ReceiversTarget;
}

/** Why a receiver was included: its own area or person that matched, or
 * that it was named (`id` is then its entry id). */
export interface MatchReason {
  kind: "everyone" | "all_areas" | "area" | "person" | "receiver";
  id?: string;
}

export interface PreviewEntry {
  entry_id: string;
  name: string;
  type: string;
  outcome: "reached" | "skipped";
  reason: string | null;
  reasons?: MatchReason[];
  /** The receiver type id, the key of its block in `data`. */
  type_id?: string;
  /** What the type supports: title, priority, image, data, data.<key>. */
  capabilities?: string[];
  accepts_any_content?: boolean;
}

/** Content beyond the message and title. */
export interface NotifyContent {
  priority?: "low" | "normal" | "high" | "critical";
  image?: string;
  /** Objects keyed by receiver type id. */
  data?: Record<string, Record<string, unknown>>;
}

export interface SendResult {
  entry_id: string;
  name: string;
  type: string;
  result: "delivered" | "failed" | "skipped";
  reason: string | null;
  warnings: string[];
  reasons?: MatchReason[];
}

export interface SendResponse {
  results: SendResult[];
  counts: { delivered: number; failed: number; skipped: number };
}

export interface ScriptCheck {
  id: string;
  ok: boolean;
  message: string;
}

export interface ScriptCheckResult {
  entity_id: string;
  checks: ScriptCheck[];
  /** True when a rescan would offer the script as a receiver. */
  can_rescan: boolean;
}

export interface HistoryRecord {
  id: string;
  /** ISO timestamp (UTC). */
  time: string;
  notification: {
    title?: string;
    message?: string;
    priority?: string;
    image?: string;
    data?: Record<string, unknown>;
  };
  results: SendResult[];
}
