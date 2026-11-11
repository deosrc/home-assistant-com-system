import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { HistoryRecord, HomeAssistant } from "./types";

/** The recent notifications, newest first, with each receiver's result. */
export class ComSystemHistory extends LitElement {
  declare hass: HomeAssistant;
  declare private records?: HistoryRecord[];
  declare private error?: string;

  static properties = {
    hass: { attribute: false },
    records: { state: true },
    error: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        justify-content: flex-end;
        padding-bottom: 16px;
      }
      button.refresh {
        padding: 8px 16px;
        font-weight: 500;
        color: var(--text-primary-color, #fff);
        background: var(--primary-color);
        border: none;
        border-radius: var(--ha-button-border-radius, 9999px);
      }
      .entry {
        margin-bottom: 16px;
      }
      .head {
        display: flex;
        justify-content: space-between;
        gap: 8px;
      }
      summary {
        display: flex;
        align-items: center;
        gap: 12px;
        cursor: pointer;
        padding: 4px 0;
      }
      summary::-webkit-details-marker {
        display: none;
      }
      summary::marker {
        content: "";
      }
      .chevron {
        display: inline-flex;
        color: var(--secondary-text-color);
        transition: transform 0.2s;
        transform: rotate(-90deg);
      }
      details[open] .chevron {
        transform: none;
      }
      .badges {
        display: inline-flex;
        gap: 4px;
      }
      .badge {
        padding: 2px 10px;
        border-radius: 16px;
        font-size: 12px;
        white-space: nowrap;
        background: var(--secondary-background-color, #f0f0f0);
      }
      .badge.delivered {
        color: var(--success-color, #43a047);
      }
      .badge.failed {
        color: var(--error-color, #db4437);
      }
      .badge.skipped {
        color: var(--warning-color, #ffa600);
      }
      hr {
        border: none;
        border-top: 1px solid var(--divider-color, #e0e0e0);
        margin: 16px 0 8px;
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
      td.delivered {
        color: var(--success-color, #43a047);
      }
      td.failed {
        color: var(--error-color, #db4437);
      }
      td.skipped {
        color: var(--warning-color, #ffa600);
      }
    `,
  ];

  private loaded = false;

  protected updated(): void {
    if (this.hass && !this.loaded) {
      this.loaded = true;
      void this.load();
    }
  }

  private async load(): Promise<void> {
    try {
      this.records = await new ComSystemApi(this.hass).history();
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  /** HA's button when it is loaded, otherwise a styled native one. */
  private renderRefresh() {
    return customElements.get("ha-button")
      ? html`<ha-button @click=${() => void this.load()}>Refresh</ha-button>`
      : html`<button class="refresh" @click=${() => void this.load()}>
          Refresh
        </button>`;
  }

  private renderCounts(r: HistoryRecord) {
    const counts = (["delivered", "failed", "skipped"] as const)
      .map((k) => [k, r.results.filter((x) => x.result === k).length] as const)
      .filter(([, n]) => n > 0);
    return html`<span class="badges"
      >${counts.map(
        ([k, n]) => html`<span class="badge ${k}" title=${k}>${n} ${k}</span>`,
      )}</span
    >`;
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.records) {
      return html`<p class="muted">Loading…</p>`;
    }
    if (!this.records.length) {
      return html`<p class="muted">No notifications yet.</p>`;
    }
    return html`
      <div>
        <div class="toolbar">${this.renderRefresh()}</div>
        ${this.records.map(
          (r) => html`
            <div class="card entry">
              <div class="head">
                <strong
                  >${r.notification.title ?? r.notification.message}</strong
                >
                <span class="muted">${new Date(r.time).toLocaleString()}</span>
              </div>
              ${
                r.notification.title
                  ? html`<div>${r.notification.message}</div>`
                  : ""
              }
              <hr />
              <details>
                <summary>
                  <ha-icon class="chevron" icon="mdi:chevron-down"></ha-icon>
                  <span>Receivers (${r.results.length})</span>
                  ${this.renderCounts(r)}
                </summary>
                <table>
                  <thead>
                    <tr>
                      <th>Receiver</th>
                      <th>Type</th>
                      <th>Outcome</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${r.results.map(
                      (x) =>
                        html`<tr>
                          <td>${x.name}</td>
                          <td>${x.type}</td>
                          <td class=${x.result}>${x.result}</td>
                          <td>
                            ${[
                              x.reason,
                              ...x.warnings.map((w) => `Warning: ${w}`),
                            ]
                              .filter(Boolean)
                              .join("; ")}
                          </td>
                        </tr>`,
                    )}
                  </tbody>
                </table>
              </details>
            </div>
          `,
        )}
      </div>
    `;
  }
}

customElements.define("com-system-history", ComSystemHistory);
