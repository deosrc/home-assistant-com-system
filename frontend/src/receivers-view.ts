import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type {
  Audience,
  DiscoveryInfo,
  HomeAssistant,
  ReceiverInfo,
  ScriptCheckResult,
} from "./types";

/** Configured receivers, a script checker and a pending discoveries alert. */
export class ComSystemReceivers extends LitElement {
  declare hass: HomeAssistant;
  declare private receivers?: ReceiverInfo[];
  declare private discoveries: DiscoveryInfo[];
  declare private error?: string;
  declare private scriptId: string;
  declare private scriptResult?: ScriptCheckResult;
  declare private scriptMessage?: string;

  static properties = {
    hass: { attribute: false },
    receivers: { state: true },
    discoveries: { state: true },
    error: { state: true },
    scriptId: { state: true },
    scriptResult: { state: true },
    scriptMessage: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      /* Copies the cards of Developer tools > Actions. ha-card styles the
         slotted .card-header, .card-content and .card-actions itself. */
      ha-card {
        display: block;
        margin-bottom: 16px;
      }
      .card-header {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .secondary {
        margin: 0;
        font-size: 14px;
        font-weight: normal;
        letter-spacing: normal;
        line-height: normal;
        color: var(--secondary-text-color);
      }
      .card-content {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 16px;
        margin: 8px;
      }
      .card-content > * {
        margin: 0;
      }
      .card-actions {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 8px;
      }
      .alert {
        display: block;
        margin-bottom: 16px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th,
      td {
        text-align: left;
        padding: 8px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .switch {
        width: 1%;
      }
      tr.link {
        cursor: pointer;
      }
      tr.link:hover {
        background: var(--secondary-background-color, #f0f0f0);
      }
      tr.unavailable td:not(.switch) {
        opacity: 0.6;
      }
      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 10px 2px 6px;
        border-radius: 16px;
        font-size: 12px;
        white-space: nowrap;
        background: var(--secondary-background-color, #f0f0f0);
        color: var(--primary-text-color);
      }
      .badge ha-icon {
        --mdc-icon-size: 16px;
        display: inline-flex;
        color: var(--secondary-text-color);
      }
      .checks {
        list-style: none;
        padding: 0;
      }
      .checks .ok {
        color: var(--success-color, #43a047);
      }
      .checks .problem {
        color: var(--error-color, #db4437);
      }
      select.audience {
        font: inherit;
        color: var(--primary-text-color);
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 4px 8px;
      }
    `,
  ];

  private lastSignature?: string;

  constructor() {
    super();
    this.discoveries = [];
    this.scriptId = "";
  }

  protected updated(): void {
    if (!this.hass) return;
    // Load once hass is set, then refetch when a switch state changes.
    const signature = Object.entries(this.hass.states)
      .filter(([id]) => id.startsWith("switch.") || id.startsWith("select."))
      .map(([id, s]) => `${id}=${s.state}`)
      .join(",");
    if (signature !== this.lastSignature) {
      this.lastSignature = signature;
      void this.load();
    }
  }

  private async load(): Promise<void> {
    const api = new ComSystemApi(this.hass);
    try {
      [this.receivers, this.discoveries] = await Promise.all([
        api.receivers(),
        api.discoveries(),
      ]);
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private async changeAudience(receiver: ReceiverInfo, ev: Event) {
    const control = ev.target as HTMLSelectElement;
    try {
      await new ComSystemApi(this.hass).setAudience(
        receiver.entry_id,
        control.value as Audience,
      );
      await this.load();
    } catch (err) {
      control.value = receiver.audience ?? "";
      this.error = errorMessage(err);
    }
  }

  private renderAudience(r: ReceiverInfo) {
    if (r.audience === null) {
      return html`<span class="muted">–</span>`;
    }
    return html`<select
      class="audience"
      .value=${r.audience}
      ?disabled=${!r.available}
      @change=${(ev: Event) => this.changeAudience(r, ev)}
    >
      <option value="personal" ?selected=${r.audience === "personal"}>
        Personal
      </option>
      <option value="shared" ?selected=${r.audience === "shared"}>
        Shared
      </option>
    </select>`;
  }

  private async toggle(receiver: ReceiverInfo, ev: Event) {
    const control = ev.target as HTMLInputElement;
    try {
      await new ComSystemApi(this.hass).setEnabled(
        receiver.entry_id,
        control.checked,
      );
      await this.load();
    } catch (err) {
      // Put the switch back; the state did not change.
      control.checked = receiver.enabled === true;
      this.error = errorMessage(err);
    }
  }

  private async checkScript(entityId: string) {
    this.scriptId = entityId;
    this.scriptResult = undefined;
    this.scriptMessage = undefined;
    if (!entityId) return;
    try {
      this.scriptResult = await new ComSystemApi(this.hass).checkScript(
        entityId,
      );
    } catch (err) {
      this.scriptMessage = errorMessage(err);
    }
  }

  private async rescan() {
    try {
      await new ComSystemApi(this.hass).rescanScripts();
      await this.load();
      // Check again: the script is now waiting to be added.
      await this.checkScript(this.scriptId);
      this.scriptMessage =
        "Rescan finished. The script is waiting to be added.";
    } catch (err) {
      this.scriptMessage = errorMessage(err);
    }
  }

  /** Home Assistant's entity picker when it is loaded, else a plain select. */
  private renderScriptPicker() {
    if (customElements.get("ha-entity-picker")) {
      return html`<ha-entity-picker
        id="script"
        label="Script"
        .hass=${this.hass}
        .value=${this.scriptId}
        .includeDomains=${["script"]}
        @value-changed=${(e: CustomEvent<{ value?: string }>) =>
          this.checkScript(e.detail.value ?? "")}
      ></ha-entity-picker>`;
    }
    const scripts = Object.keys(this.hass.states)
      .filter((id) => id.startsWith("script."))
      .sort();
    return html`<select
      id="script"
      @change=${(e: Event) =>
        this.checkScript((e.target as HTMLSelectElement).value)}
    >
      <option value="">Choose a script…</option>
      ${scripts.map(
        (id) =>
          html`<option value=${id} ?selected=${id === this.scriptId}>
            ${this.hass.states[id]?.attributes?.friendly_name ?? id}
          </option>`,
      )}
    </select>`;
  }

  private renderScriptCheck() {
    const result = this.scriptResult;
    return html`<ha-card>
      <div class="card-header">
        Check a script
        <p class="secondary">
          Pick a script to see whether it can be a custom receiver. It needs one
          object field named notification; other fields must be optional.
        </p>
      </div>
      <div class="card-content">
        ${this.renderScriptPicker()}
        ${
          result
            ? html`<ul class="checks">
                ${result.checks.map(
                  (c) =>
                    html`<li class=${c.ok ? "ok" : "problem"}>
                      ${c.ok ? "✓" : "✗"} ${c.message}
                    </li>`,
                )}
              </ul>`
            : ""
        }
        ${
          this.scriptMessage
            ? html`<p id="script-message">${this.scriptMessage}</p>`
            : ""
        }
      </div>
      <div class="card-actions">
        ${
          result?.can_rescan
            ? html`<button id="rescan" @click=${() => this.rescan()}>
                Rescan scripts
              </button>`
            : ""
        }
      </div>
    </ha-card>`;
  }

  /** The areas and people a receiver is linked to: by type, then name. */
  private targets(r: ReceiverInfo): { icon: string; name: string }[] {
    const areas = r.areas.map((id) => ({
      icon: "mdi:texture-box",
      name: this.hass.areas?.[id]?.name ?? id,
    }));
    const people = r.people.map((id) => ({
      icon: "mdi:account",
      name: this.hass.states[id]?.attributes?.friendly_name ?? id,
    }));
    const byName = (a: { name: string }, b: { name: string }) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    return [...areas.sort(byName), ...people.sort(byName)];
  }

  private renderTargets(r: ReceiverInfo) {
    const targets = this.targets(r);
    if (!targets.length) {
      return html`<span class="muted">None</span>`;
    }
    return html`<div class="badges">
      ${targets.map(
        (t) =>
          html`<span class="badge">
            <ha-icon icon=${t.icon}></ha-icon>${t.name}
          </span>`,
      )}
    </div>`;
  }

  /** Open the receiver's device page, where it is edited. */
  private openDevice(r: ReceiverInfo): void {
    if (!r.device_id) return;
    history.pushState(null, "", `/config/devices/device/${r.device_id}`);
    window.dispatchEvent(new CustomEvent("location-changed"));
  }

  private renderTable(receivers: ReceiverInfo[]) {
    return html`<table>
      <thead>
        <tr>
          <th class="switch" aria-label="Enabled"></th>
          <th>Name</th>
          <th>Type</th>
          <th>Use</th>
          <th>Targets</th>
        </tr>
      </thead>
      <tbody>
        ${receivers.map(
          (r) => html`
            <tr
              class=${[
                r.available ? "" : "unavailable",
                r.device_id ? "link" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              tabindex=${r.device_id ? "0" : "-1"}
              @click=${() => this.openDevice(r)}
              @keydown=${(ev: KeyboardEvent) => {
                if (ev.key === "Enter") this.openDevice(r);
              }}
            >
              <td class="switch" @click=${(ev: Event) => ev.stopPropagation()}>
                <ha-switch
                  .checked=${r.enabled === true}
                  ?disabled=${!r.available || r.enabled === null}
                  title=${r.available ? "" : "Unavailable"}
                  @change=${(ev: Event) => this.toggle(r, ev)}
                ></ha-switch>
              </td>
              <td>${r.name}</td>
              <td>${r.type}</td>
              <td @click=${(ev: Event) => ev.stopPropagation()}>
                ${this.renderAudience(r)}
              </td>
              <td>${this.renderTargets(r)}</td>
            </tr>
          `,
        )}
      </tbody>
    </table>`;
  }

  /** An alert, with no list, when receivers are waiting to be added. */
  private renderDiscoveryAlert() {
    const count = this.discoveries.length;
    if (!count) return html``;
    return html`<ha-alert class="alert" alert-type="info" id="discoveries">
      ${
        count === 1
          ? "1 receiver is waiting to be added."
          : `${count} receivers are waiting to be added.`
      }
      <a href="/config/integrations/integration/com_system"
        >Review in Devices &amp; services</a
      >
    </ha-alert>`;
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.receivers) {
      return html`<p class="muted">Loading…</p>`;
    }
    return html`
      <div>${this.renderDiscoveryAlert()}</div>
      <ha-card>
        <div class="card-header">Receivers</div>
        <div class="card-content">
          ${
            this.receivers.length
              ? this.renderTable(this.receivers)
              : html`<p class="muted">No receivers yet.</p>`
          }
        </div>
      </ha-card>
      <div>${this.renderScriptCheck()}</div>
    `;
  }
}

customElements.define("com-system-receivers", ComSystemReceivers);
