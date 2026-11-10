/** The part of Home Assistant's `hass` object the panel uses. */
export interface HomeAssistant {
  callWS<T>(msg: { type: string; [key: string]: unknown }): Promise<T>;
  states: Record<string, { state: string }>;
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
  people: string[];
  areas: string[];
}

export interface DiscoveryInfo {
  flow_id: string;
  name: string;
  type: string;
}
