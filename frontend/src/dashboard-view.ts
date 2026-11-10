import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { DashboardData, HomeAssistant } from "./types";

/** Receiver counts and state. */
export class ComSystemDashboard extends LitElement {
  declare hass: HomeAssistant;
  declare private data?: DashboardData;
  declare private error?: string;

  static properties = {
    hass: { attribute: false },
    data: { state: true },
    error: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      .tiles {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }
      .value {
        font-size: 2rem;
        font-weight: 500;
      }
      ul {
        margin: 8px 0 0;
        padding-left: 20px;
      }
    `,
  ];

  private lastSignature = "";

  protected updated(): void {
    // Refetch when a receiver's state changes, and on first connection.
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
    try {
      this.data = await new ComSystemApi(this.hass).dashboard();
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    const data = this.data;
    if (!data) {
      return html`<p class="muted">Loading…</p>`;
    }
    const tiles: [string, number][] = [
      ["Receivers", data.total],
      ["Enabled", data.enabled],
      ["Disabled", data.disabled],
      ["Unavailable", data.unavailable],
      ["Pending discoveries", data.pending_discoveries],
    ];
    const types = Object.entries(data.by_type);
    return html`
      <div class="tiles">
        ${tiles.map(
          ([label, value]) => html`
            <div class="card">
              <div class="value">${value}</div>
              <div class="muted">${label}</div>
            </div>
          `,
        )}
      </div>
      <div class="card">
        <strong>Receivers by type</strong>
        ${types.length
          ? html`<ul>
              ${types.map(([t, n]) => html`<li>${t}: ${n}</li>`)}
            </ul>`
          : html`<p class="muted">No receivers yet.</p>`}
      </div>
    `;
  }
}

customElements.define("com-system-dashboard", ComSystemDashboard);
