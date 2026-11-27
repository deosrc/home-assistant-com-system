import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { NO_RECEIVERS, noReceiversStyles } from "./no-receivers";
import { renderReasons, reasonStyles } from "./reasons";
import { sharedStyles } from "./styles";
import type { ActionResponse, HistoryRecord, HomeAssistant } from "./types";

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
    reasonStyles,
    noReceiversStyles,
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
        padding-bottom: 12px;
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
      .counts {
        display: inline-flex;
        gap: 4px;
      }
      .count {
        padding: 2px 10px;
        border-radius: 16px;
        font-size: 12px;
        white-space: nowrap;
        background: var(--secondary-background-color, #f0f0f0);
      }
      .count.delivered {
        color: var(--success-color, #43a047);
      }
      .count.failed {
        color: var(--error-color, #db4437);
      }
      .count.skipped {
        color: var(--warning-color, #ffa600);
      }
      .responses {
        margin: 8px 0 0;
        padding-left: 20px;
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

  /** Who responded: the person's name if known, else the receiver. */
  private responder(x: ActionResponse): string {
    const person = x.person ? this.hass.states?.[x.person] : undefined;
    const name = person?.attributes?.friendly_name ?? x.person;
    return name ?? x.receiver ?? "an unknown receiver";
  }

  /** The responses from one receiver, or an empty string. */
  private renderResponses(r: HistoryRecord, entryId: string) {
    const own = (r.responses ?? []).filter((x) => x.receiver_id === entryId);
    return own.map(
      (x) =>
        html`<div class="response">
          <strong>${x.action}</strong>${
            x.reply_text ? html` “${x.reply_text}”` : ""
          }
          ${x.person ? html`by <span>${this.responder(x)}</span>` : ""}
          <span class="muted">${new Date(x.time).toLocaleString()}</span>
        </div>`,
    );
  }

  /** Responses from a receiver that is not in the results (for example one
   * that was removed), so none is lost. */
  private renderOrphans(r: HistoryRecord) {
    const known = new Set(r.results.map((x) => x.entry_id));
    const orphans = (r.responses ?? []).filter(
      (x) => !x.receiver_id || !known.has(x.receiver_id),
    );
    if (!orphans.length) return "";
    return html`<ul class="responses">
      ${orphans.map(
        (x) =>
          html`<li>
            <strong>${x.action}</strong> from ${this.responder(x)}
            <span class="muted">${new Date(x.time).toLocaleString()}</span>
          </li>`,
      )}
    </ul>`;
  }

  private renderCounts(r: HistoryRecord) {
    const counts = (["delivered", "failed", "skipped"] as const)
      .map((k) => [k, r.results.filter((x) => x.result === k).length] as const)
      .filter(([, n]) => n > 0);
    return html`<span class="counts"
      >${counts.map(
        ([k, n]) => html`<span class="count ${k}" title=${k}>${n} ${k}</span>`,
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
                ${
                  r.notification.title
                    ? html`<strong>${r.notification.title}</strong>`
                    : html`<span class="muted">(No title)</span>`
                }
                <span class="muted">${new Date(r.time).toLocaleString()}</span>
              </div>
              <div class="body">${r.notification.message}</div>
              ${this.renderOrphans(r)}
              <hr />
              ${r.results.length ? this.renderResults(r) : NO_RECEIVERS}
            </div>
          `,
        )}
      </div>
    `;
  }

  private renderResults(r: HistoryRecord) {
    return html`<details>
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
            <th>Why</th>
            <th>Outcome</th>
            ${r.responses?.length ? html`<th>Response</th>` : ""}
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          ${r.results.map(
            (x) =>
              html`<tr>
                <td>${x.name}</td>
                <td>${x.type}</td>
                <td>${renderReasons(this.hass, x.reasons)}</td>
                <td class=${x.result}>${x.result}</td>
                ${
                  r.responses?.length
                    ? html`<td>${this.renderResponses(r, x.entry_id)}</td>`
                    : ""
                }
                <td>
                  ${[x.reason, ...x.warnings.map((w) => `Warning: ${w}`)]
                    .filter(Boolean)
                    .join("; ")}
                </td>
              </tr>`,
          )}
        </tbody>
      </table>
    </details>`;
  }
}

customElements.define("com-system-history", ComSystemHistory);
