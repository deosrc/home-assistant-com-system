import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { DiscoveryInfo, HomeAssistant, ReceiverInfo } from "./types";

/** Configured receivers with enable/disable, plus pending discoveries. */
export class ComSystemReceivers extends LitElement {
  declare hass: HomeAssistant;
  declare private receivers?: ReceiverInfo[];
  declare private discoveries: DiscoveryInfo[];
  declare private error?: string;

  static properties = {
    hass: { attribute: false },
    receivers: { state: true },
    discoveries: { state: true },
    error: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
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
      .card + .card {
        margin-top: 16px;
      }
    `,
  ];

  private lastSignature?: string;

  constructor() {
    super();
    this.discoveries = [];
  }

  protected updated(): void {
    if (!this.hass) return;
    // Load once hass is set, then refetch when a switch state changes.
    const signature = Object.entries(this.hass.states)
      .filter(([id]) => id.startsWith("switch."))
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

  private async toggle(receiver: ReceiverInfo, enabled: boolean) {
    try {
      await new ComSystemApi(this.hass).setEnabled(receiver.entry_id, enabled);
      await this.load();
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private status(r: ReceiverInfo): string {
    if (!r.available) return "Unavailable";
    if (r.enabled === null) return "Unknown";
    return r.enabled ? "Enabled" : "Disabled";
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.receivers) {
      return html`<p class="muted">Loading…</p>`;
    }
    return html`
      <div class="card">
        <strong>Receivers</strong>
        ${this.receivers.length
          ? html`<table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Enabled</th>
                </tr>
              </thead>
              <tbody>
                ${this.receivers.map(
                  (r) => html`
                    <tr>
                      <td>${r.name}</td>
                      <td>${r.type}</td>
                      <td>${this.status(r)}</td>
                      <td>
                        <button
                          ?disabled=${r.enabled === null}
                          @click=${() => this.toggle(r, !r.enabled)}
                        >
                          ${r.enabled ? "Disable" : "Enable"}
                        </button>
                      </td>
                    </tr>
                  `,
                )}
              </tbody>
            </table>`
          : html`<p class="muted">No receivers yet.</p>`}
      </div>
      <div class="card">
        <strong>Pending discoveries</strong>
        ${this.discoveries.length
          ? html`<ul>
                ${this.discoveries.map(
                  (d) => html`<li>${d.name} (${d.type})</li>`,
                )}
              </ul>
              <p>
                <a href="/config/integrations/integration/com_system"
                  >Review in Devices &amp; services</a
                >
              </p>`
          : html`<p class="muted">Nothing waiting to be added.</p>`}
      </div>
    `;
  }
}

customElements.define("com-system-receivers", ComSystemReceivers);
