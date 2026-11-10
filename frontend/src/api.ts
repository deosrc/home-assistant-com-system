import type {
  DashboardData,
  DiscoveryInfo,
  HomeAssistant,
  NotifyTargets,
  PreviewEntry,
  ReceiverEdit,
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
  ): Promise<SendResponse> {
    return this.hass.callWS({
      type: "com_system/notify/test",
      message,
      ...(title ? { title } : {}),
      ...targets,
    });
  }

  updateReceiver(entryId: string, edit: ReceiverEdit): Promise<ReceiverInfo> {
    return this.hass.callWS({
      type: "com_system/receivers/update",
      entry_id: entryId,
      ...edit,
    });
  }

  removeReceiver(entryId: string): Promise<void> {
    return this.hass.callWS({
      type: "com_system/receivers/remove",
      entry_id: entryId,
    });
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
