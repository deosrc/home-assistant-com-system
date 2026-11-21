/** The part of Home Assistant's `hass` object the panel uses. */
export interface HomeAssistant {
  callWS<T>(msg: { type: string; [key: string]: unknown }): Promise<T>;
  callService(
    domain: string,
    service: string,
    serviceData?: Record<string, unknown>,
  ): Promise<unknown>;
  states: Record<
    string,
    { state: string; attributes?: { friendly_name?: string } }
  >;
  areas?: Record<string, { name: string }>;
  user?: { is_admin: boolean };
}

export interface PanelRoute {
  prefix: string;
  path: string;
}

export interface HistoryStats {
  notifications: number;
  /** Notifications per `rate_unit`; null when there is no basis for one. */
  rate: number | null;
  rate_unit: "day" | "hour";
  /** Fractions from 0 to 1; null when the history is empty. */
  notification_success_rate: number | null;
  receiver_success_rate: number | null;
  stopped_by_condition_rate: number | null;
}

export interface DashboardData {
  total: number;
  enabled: number;
  disabled: number;
  unavailable: number;
  pending_discoveries: number;
  by_type: Record<string, number>;
  history: HistoryStats;
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
  /** How many notification conditions the receiver has. */
  conditions: number;
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
  outcome: "targeted" | "skipped";
  reason: string | null;
  reasons?: MatchReason[];
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

export interface ChannelDefaults {
  title?: string;
  priority?: string;
  image?: string;
  click_action?: string;
  actions?: { id: string; label: string; uri?: string }[];
  tag?: string;
  car_ui?: boolean;
  data?: Record<string, unknown>;
}

export interface ChannelInfo {
  channel_id: string;
  name: string;
  /** The `notification_channel` entity the action's channel field takes. */
  entity_id: string | null;
  defaults: ChannelDefaults;
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
  /** Responses to notification actions, oldest first. */
  responses?: ActionResponse[];
}

export interface ActionResponse {
  /** ISO timestamp (UTC). */
  time: string;
  receiver_id: string | null;
  receiver: string | null;
  /** The `person.*` entity of the device's owner, if it is personal. */
  person: string | null;
  action: string;
  reply_text?: string | null;
}
