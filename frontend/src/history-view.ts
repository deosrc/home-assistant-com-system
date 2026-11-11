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
      .entry {
        margin-bottom: 16px;
      }
      .head {
        display: flex;
        justify-content: space-between;
        gap: 8px;
      }
      ul {
        margin: 8px 0 0;
        padding-left: 20px;
      }
      .failed {
        color: var(--error-color, #db4437);
      }
      .warning {
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
        <button @click=${() => void this.load()}>Refresh</button>
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
              <ul>
                ${r.results.map(
                  (x) =>
                    html`<li>
                      ${x.name}:
                      <span class=${x.result === "failed" ? "failed" : ""}
                        >${x.result}</span
                      >${x.reason ? html`<span> (${x.reason})</span>` : ""}
                      ${x.warnings.map(
                        (w) => html`<div class="warning">${w}</div>`,
                      )}
                    </li>`,
                )}
              </ul>
            </div>
          `,
        )}
      </div>
    `;
  }
}

customElements.define("com-system-history", ComSystemHistory);
