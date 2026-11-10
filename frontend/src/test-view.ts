import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type {
  HomeAssistant,
  NotifyTargets,
  PreviewEntry,
  ReceiverInfo,
  SendResponse,
} from "./types";

type TargetKey = keyof NotifyTargets;

/**
 * The testing tool: choose targets, preview which receivers they reach, and
 * send a test through the `notify.com_system` action.
 */
export class ComSystemTest extends LitElement {
  declare hass: HomeAssistant;
  declare private receivers: ReceiverInfo[];
  declare private message: string;
  declare private subject: string;
  declare private selected: Record<TargetKey, string[]>;
  declare private preview?: PreviewEntry[];
  declare private response?: SendResponse;
  declare private sending: boolean;
  declare private error?: string;

  static properties = {
    hass: { attribute: false },
    receivers: { state: true },
    message: { state: true },
    subject: { state: true },
    selected: { state: true },
    preview: { state: true },
    response: { state: true },
    sending: { state: true },
    error: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      .card + .card {
        margin-top: 16px;
      }
      label.field {
        display: block;
        margin: 8px 0;
      }
      label.field span {
        display: block;
        font-size: 12px;
        color: var(--secondary-text-color);
      }
      input[type="text"],
      textarea {
        box-sizing: border-box;
        width: 100%;
        font: inherit;
        padding: 8px;
        color: var(--primary-text-color);
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
      }
      fieldset {
        margin: 8px 0;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
      }
      legend {
        font-size: 12px;
        color: var(--secondary-text-color);
      }
      fieldset label {
        display: inline-block;
        margin-inline-end: 16px;
        white-space: nowrap;
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
      .delivered,
      .reached {
        color: var(--success-color, #43a047);
      }
      .failed {
        color: var(--error-color, #db4437);
      }
      .skipped {
        color: var(--warning-color, #ffa600);
      }
      .counts {
        margin: 8px 0;
      }
      button.send {
        padding: 8px 16px;
        color: var(--text-primary-color, #fff);
        background: var(--primary-color);
        border: none;
        border-radius: 4px;
      }
      button.send[disabled] {
        opacity: 0.5;
        cursor: default;
      }
    `,
  ];

  constructor() {
    super();
    this.receivers = [];
    this.message = "";
    this.subject = "";
    this.selected = { person: [], area_id: [], entity_id: [] };
    this.sending = false;
  }

  private loaded = false;

  protected updated(): void {
    if (this.hass && !this.loaded) {
      this.loaded = true;
      void this.init();
    }
  }

  private async init(): Promise<void> {
    try {
      this.receivers = await new ComSystemApi(this.hass).receivers();
    } catch (err) {
      this.error = errorMessage(err);
    }
    await this.refreshPreview();
  }

  /** Only the fields with a selection are sent, so none means the default. */
  private get targets(): NotifyTargets {
    const targets: NotifyTargets = {};
    for (const key of Object.keys(this.selected) as TargetKey[]) {
      if (this.selected[key].length) targets[key] = this.selected[key];
    }
    return targets;
  }

  private async refreshPreview(): Promise<void> {
    try {
      this.preview = await new ComSystemApi(this.hass).previewNotify(
        this.targets,
      );
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private toggle(key: TargetKey, id: string, checked: boolean): void {
    const current = this.selected[key].filter((x) => x !== id);
    this.selected = {
      ...this.selected,
      [key]: checked ? [...current, id] : current,
    };
    // The previous send no longer describes the selection.
    this.response = undefined;
    void this.refreshPreview();
  }

  private async send(): Promise<void> {
    this.sending = true;
    this.response = undefined;
    try {
      this.response = await new ComSystemApi(this.hass).sendTest(
        this.message,
        this.subject,
        this.targets,
      );
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    } finally {
      this.sending = false;
    }
  }

  private options(key: TargetKey): { id: string; name: string }[] {
    const byName = (a: { name: string }, b: { name: string }) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    if (key === "area_id") {
      return Object.entries(this.hass.areas ?? {})
        .map(([id, a]) => ({ id, name: a.name }))
        .sort(byName);
    }
    if (key === "person") {
      return Object.entries(this.hass.states)
        .filter(([id]) => id.startsWith("person."))
        .map(([id, s]) => ({ id, name: s.attributes?.friendly_name ?? id }))
        .sort(byName);
    }
    return this.receivers
      .filter((r) => r.receiver_entity_id)
      .map((r) => ({ id: r.receiver_entity_id!, name: r.name }))
      .sort(byName);
  }

  private renderTargets(key: TargetKey, legend: string) {
    const options = this.options(key);
    return html`<fieldset>
      <legend>${legend}</legend>
      ${options.length
        ? options.map(
            (o) => html`<label
              ><input
                type="checkbox"
                .checked=${this.selected[key].includes(o.id)}
                @change=${(ev: Event) =>
                  this.toggle(key, o.id, (ev.target as HTMLInputElement).checked)}
              />
              ${o.name}</label
            >`,
          )
        : html`<span class="muted">None available</span>`}
    </fieldset>`;
  }

  private renderPreview() {
    if (!this.preview) return html`<p class="muted">Loading…</p>`;
    if (!this.preview.length) {
      return html`<p class="muted">No receiver matches these targets.</p>`;
    }
    return html`<table class="preview">
      <thead>
        <tr>
          <th>Receiver</th>
          <th>Type</th>
          <th>Would be</th>
        </tr>
      </thead>
      <tbody>
        ${this.preview.map(
          (p) => html`<tr>
            <td>${p.name}</td>
            <td>${p.type}</td>
            <td class=${p.outcome}>
              ${p.reason ? `${p.outcome} (${p.reason})` : p.outcome}
            </td>
          </tr>`,
        )}
      </tbody>
    </table>`;
  }

  private renderResponse() {
    const r = this.response;
    if (!r) return "";
    return html`<div class="card">
      <strong>Result</strong>
      <p class="counts">
        ${r.counts.delivered} delivered, ${r.counts.failed} failed,
        ${r.counts.skipped} skipped
      </p>
      <table class="results">
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
            (x) => html`<tr>
              <td>${x.name}</td>
              <td>${x.type}</td>
              <td class=${x.result}>${x.result}</td>
              <td>
                ${[x.reason, ...x.warnings.map((w) => `Warning: ${w}`)]
                  .filter(Boolean)
                  .join("; ")}
              </td>
            </tr>`,
          )}
        </tbody>
      </table>
    </div>`;
  }

  protected render() {
    const canSend =
      !this.sending &&
      this.message.trim() !== "" &&
      (this.preview?.some((p) => p.outcome === "reached") ?? false);
    return html`
      <div class="card">
        <strong>Send a test notification</strong>
        <label class="field"
          ><span>Message</span
          ><textarea
            rows="2"
            .value=${this.message}
            @input=${(ev: Event) =>
              (this.message = (ev.target as HTMLTextAreaElement).value)}
          ></textarea
        ></label>
        <label class="field"
          ><span>Title (optional)</span
          ><input
            type="text"
            .value=${this.subject}
            @input=${(ev: Event) =>
              (this.subject = (ev.target as HTMLInputElement).value)}
        /></label>
        ${this.renderTargets("person", "People")}
        ${this.renderTargets("area_id", "Areas")}
        ${this.renderTargets("entity_id", "Receivers")}
        <p class="muted">
          With nothing selected the notification goes to all people and
          areas, as it does from an automation.
        </p>
        ${this.error ? html`<p class="error">${this.error}</p>` : ""}
        <button
          class="send"
          ?disabled=${!canSend}
          @click=${() => this.send()}
        >
          Send test
        </button>
      </div>
      <div class="card">
        <strong>Receivers reached</strong>
        ${this.renderPreview()}
      </div>
      <div class="response">${this.renderResponse()}</div>
    `;
  }
}

customElements.define("com-system-test", ComSystemTest);
