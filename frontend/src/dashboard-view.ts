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
      .alert {
        display: block;
        margin-bottom: 16px;
      }
      .value {
        font-size: 2rem;
        font-weight: 500;
      }
    `,
  ];

  private lastSignature?: string;

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
    const h = data.history;
    const pct = (v: number | null) =>
      v === null ? "–" : `${Math.round(v * 1000) / 10}%`;
    const rateWarning = h.rate === null && h.rate_unit === "hour";
    const rate =
      h.rate === null ? "–" : `${Math.round(h.rate * 10) / 10}/${h.rate_unit}`;
    const tiles: [string, string | number, string?][] = [
      ["Receivers", `${data.total - data.unavailable}/${data.total}`],
      [
        "Notifications per " + h.rate_unit,
        rateWarning ? "⚠" : rate,
        rateWarning
          ? "History is full but covers less than one whole hour."
          : undefined,
      ],
      ["Notification success", pct(h.notification_success_rate)],
      ["Receiver success", pct(h.receiver_success_rate)],
      ["Filtered by condition", pct(h.stopped_by_condition_rate)],
    ];
    const pending = data.pending_discoveries;
    return html`
      <div>
        ${
          pending
            ? html`<ha-alert class="alert" alert-type="info" id="discoveries">
                ${
                  pending === 1
                    ? "1 receiver is waiting to be added."
                    : `${pending} receivers are waiting to be added.`
                }
                <a href="/config/integrations/integration/com_system"
                  >Review in Devices &amp; services</a
                >
              </ha-alert>`
            : html``
        }
      </div>
      <div class="tiles">
        ${tiles.map(
          ([label, value, title]) => html`
            <div class="card" title=${title ?? ""}>
              <div class="value">${value}</div>
              <div class="muted">${label}</div>
            </div>
          `,
        )}
      </div>
    `;
  }
}

customElements.define("com-system-dashboard", ComSystemDashboard);
