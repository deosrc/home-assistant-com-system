import type {
  DashboardData,
  DiscoveryInfo,
  HistoryRecord,
  HomeAssistant,
  NotifyContent,
  NotifyTargets,
  PreviewEntry,
  ReceiverInfo,
  ScriptCheckResult,
  SendResponse,
} from "./types";

/**
 * Typed wrappers for the integration's websocket commands. Every command
 * requires an admin user; Home Assistant answers others with `unauthorized`.
 */
export class ComSystemApi {
  constructor(private readonly hass: HomeAssistant) {}

  ping(): Promise<{ pong: boolean }> {
    return this.hass.callWS({ type: "com_system/ping" });
  }

  dashboard(): Promise<DashboardData> {
    return this.hass.callWS({ type: "com_system/dashboard" });
  }

  async receivers(): Promise<ReceiverInfo[]> {
    const result = await this.hass.callWS<{ receivers: ReceiverInfo[] }>({
      type: "com_system/receivers/list",
    });
    return result.receivers;
  }

  async discoveries(): Promise<DiscoveryInfo[]> {
    const result = await this.hass.callWS<{ discoveries: DiscoveryInfo[] }>({
      type: "com_system/discoveries/list",
    });
    return result.discoveries;
  }

  async previewNotify(targets: NotifyTargets): Promise<PreviewEntry[]> {
    const result = await this.hass.callWS<{ receivers: PreviewEntry[] }>({
      type: "com_system/notify/preview",
      ...targets,
    });
    return result.receivers;
  }

  /** Sends through the `notify.com_system` action itself. */
  sendTest(
    message: string,
    title: string | undefined,
    targets: NotifyTargets,
    content: NotifyContent = {},
  ): Promise<SendResponse> {
    return this.hass.callWS({
      type: "com_system/notify/test",
      message,
      ...(title ? { title } : {}),
      ...content,
      ...targets,
    });
  }

  async history(limit?: number): Promise<HistoryRecord[]> {
    const result = await this.hass.callWS<{ notifications: HistoryRecord[] }>({
      type: "com_system/history/list",
      ...(limit ? { limit } : {}),
    });
    return result.notifications;
  }

  checkScript(entityId: string): Promise<ScriptCheckResult> {
    return this.hass.callWS({
      type: "com_system/scripts/check",
      entity_id: entityId,
    });
  }

  rescanScripts(): Promise<void> {
    return this.hass.callWS({ type: "com_system/scripts/rescan" });
  }

  setEnabled(entryId: string, enabled: boolean): Promise<void> {
    return this.hass.callWS({
      type: "com_system/receivers/set_enabled",
      entry_id: entryId,
      enabled,
    });
  }
}

export function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}
