import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { renderReasons, reasonStyles } from "./reasons";
import { sharedStyles } from "./styles";
import type {
  HomeAssistant,
  NotifyContent,
  NotifyTargets,
  SelectedTarget,
  PreviewEntry,
  SendResponse,
} from "./types";

/** The choices of the people and receivers fields. */
const EVERYONE = "Everyone";
const INDIVIDUALS = "Individuals";
const SELECT = "Select";
const ALL_AREAS = "All Areas";

const ACTION = "notify.com_system";

interface ActionValue {
  action: string;
  data?: Record<string, unknown>;
}

/** Home Assistant's own Actions form; loaded lazily, so it may be absent. */
const CONTROL = "ha-service-control";

const PRIORITIES = ["low", "normal", "high", "critical"] as const;

/** The action fields the form edits; the content card edits the others. */
const FORM_FIELDS = ["title", "message", "people", "receivers"];

/** Whether a receiver type supports a typed field or any `data` key. */
function supports(entry: PreviewEntry, field: string): boolean {
  if (entry.accepts_any_content) return true;
  const caps = entry.capabilities ?? [];
  return field === "data"
    ? caps.some((c) => c === "data" || c.startsWith("data."))
    : caps.includes(field);
}

function ensureList(value: unknown): string[] {
  if (value === undefined || value === null || value === "") return [];
  return (Array.isArray(value) ? value : [value]).map(String);
}

/**
 * The testing tool: fill in the `notify.com_system` action, preview which
 * receivers it reaches, and send a test through it.
 *
 * The form is Home Assistant's `ha-service-control` with its action picker
 * hidden, so it matches Developer tools > Actions. It starts from the action
 * alone, with no data, so Home Assistant fills in the defaults from the
 * action's description as it does when an action is picked. The page keeps
 * no defaults of its own; it only follows what the form reports. The element
 * is loaded lazily by Home Assistant, so if it is not defined shortly after
 * the view opens, an error is shown.
 */
export class ComSystemTest extends LitElement {
  declare hass: HomeAssistant;
  /** The form's value; without data until the form has applied defaults. */
  declare private value: ActionValue;
  declare private preview?: PreviewEntry[];
  declare private priority: string;
  declare private image: string;
  /** JSON text of each receiver type's data block, by type id. */
  declare private dataText: Record<string, string>;
  declare private response?: SendResponse;
  declare private sending: boolean;
  declare private error?: string;
  /** Whether Home Assistant's Actions form is available (undefined: waiting). */
  declare private haControl?: boolean;

  /** How long to wait for `ha-service-control` before using the fallback. */
  static controlTimeoutMs = 1500;

  static properties = {
    hass: { attribute: false },
    value: { state: true },
    preview: { state: true },
    priority: { state: true },
    image: { state: true },
    dataText: { state: true },
    response: { state: true },
    sending: { state: true },
    error: { state: true },
    haControl: { state: true },
  };

  static styles = [
    sharedStyles,
    reasonStyles,
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
        font-weight: 500;
        color: var(--text-primary-color, #fff);
        background: var(--primary-color);
        border: none;
        border-radius: var(--ha-button-border-radius, 9999px);
      }
      button.send[disabled] {
        opacity: 0.5;
        cursor: default;
      }
    `,
  ];

  constructor() {
    super();
    this.value = { action: ACTION };
    this.priority = "";
    this.image = "";
    this.dataText = {};
    this.sending = false;
  }

  private loaded = false;

  protected updated(): void {
    if (this.hass && !this.loaded) {
      this.loaded = true;
      void this.init();
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (customElements.get(CONTROL)) {
      this.haControl = true;
      return;
    }
    const timeout = new Promise<boolean>((resolve) =>
      setTimeout(() => resolve(false), ComSystemTest.controlTimeoutMs),
    );
    const defined = customElements.whenDefined(CONTROL).then(() => true);
    void Promise.race([defined, timeout]).then((ok) => (this.haControl = ok));
  }

  /** The action data the form reports (empty until it has any). */
  private get data(): Record<string, unknown> {
    return this.value.data ?? {};
  }

  private get message(): string {
    const message = this.data.message;
    return message === undefined ? "" : String(message);
  }

  private get subject(): string {
    const title = this.data.title;
    return title === undefined ? "" : String(title);
  }

  private controlChanged(ev: CustomEvent<{ value: ActionValue }>): void {
    ev.stopPropagation();
    this.value = ev.detail.value;
    // The previous send no longer describes the selection.
    this.response = undefined;
    void this.refreshPreview();
  }

  private async init(): Promise<void> {
    await this.refreshPreview();
  }

  /**
   * `hass` as the form sees it: the action without the content fields, which
   * the content card shows only for the receivers they apply to. Cached.
   */
  private formHassSource?: HomeAssistant;
  private formHassValue?: HomeAssistant;
  private get formHass(): HomeAssistant {
    if (this.formHassSource === this.hass) return this.formHassValue!;
    this.formHassSource = this.hass;
    const services = this.hass?.services as
      | Record<string, Record<string, { fields?: Record<string, unknown> }>>
      | undefined;
    const action = services?.notify?.com_system;
    if (!action?.fields) {
      this.formHassValue = this.hass;
      return this.hass;
    }
    const fields = Object.fromEntries(
      Object.entries(action.fields).filter(([k]) => FORM_FIELDS.includes(k)),
    );
    this.formHassValue = {
      ...this.hass,
      services: {
        ...services,
        notify: { ...services!.notify, com_system: { ...action, fields } },
      },
    } as HomeAssistant;
    return this.formHassValue;
  }

  /** The distinct types of the receivers that would be reached. */
  private get reachedTypes(): PreviewEntry[] {
    const seen = new Map<string, PreviewEntry>();
    for (const p of this.preview ?? []) {
      if (p.outcome === "reached" && !seen.has(p.type_id ?? p.type)) {
        seen.set(p.type_id ?? p.type, p);
      }
    }
    return [...seen.values()];
  }

  /** The content fields that apply, parsed; `error` when a block is invalid. */
  private get content(): { content: NotifyContent; error?: string } {
    const content: NotifyContent = {};
    const types = this.reachedTypes;
    if (this.priority && types.some((t) => supports(t, "priority"))) {
      content.priority = this.priority as NotifyContent["priority"];
    }
    if (this.image.trim() && types.some((t) => supports(t, "image"))) {
      content.image = this.image.trim();
    }
    const data: Record<string, Record<string, unknown>> = {};
    for (const t of types) {
      const text = (this.dataText[t.type_id ?? ""] ?? "").trim();
      if (!text || !supports(t, "data")) continue;
      try {
        const value = JSON.parse(text);
        if (!value || typeof value !== "object" || Array.isArray(value)) {
          throw new Error("not an object");
        }
        data[t.type_id!] = value;
      } catch {
        return { content, error: `The ${t.type} data is not a JSON object` };
      }
    }
    if (Object.keys(data).length) content.data = data;
    return { content };
  }

  /** Only the fields the form gives are sent. */
  private get targets(): NotifyTargets {
    const targets: NotifyTargets = {};
    const people = this.data.people as Record<string, unknown> | undefined;
    if (people?.active_choice === EVERYONE) {
      targets.people = { active_choice: EVERYONE, [EVERYONE]: true };
    } else if (ensureList(people?.[INDIVIDUALS]).length) {
      targets.people = ensureList(people?.[INDIVIDUALS]);
    }
    const receivers = this.data.receivers as
      Record<string, unknown> | undefined;
    if (receivers?.active_choice === ALL_AREAS) {
      targets.receivers = { active_choice: ALL_AREAS, [ALL_AREAS]: true };
    } else if (receivers?.active_choice === SELECT) {
      const selection: SelectedTarget = {};
      for (const [key, v] of Object.entries(
        (receivers[SELECT] ?? {}) as Record<string, unknown>,
      )) {
        if (ensureList(v).length) selection[key] = ensureList(v);
      }
      if (Object.keys(selection).length) {
        targets.receivers = { active_choice: SELECT, [SELECT]: selection };
      }
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

  private async send(): Promise<void> {
    this.sending = true;
    this.response = undefined;
    try {
      this.response = await new ComSystemApi(this.hass).sendTest(
        this.message,
        this.subject,
        this.targets,
        this.content.content,
      );
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    } finally {
      this.sending = false;
    }
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
          <th>Why</th>
          <th>Would be</th>
        </tr>
      </thead>
      <tbody>
        ${this.preview.map(
          (p) =>
            html`<tr>
              <td>${p.name}</td>
              <td>${p.type}</td>
              <td>${renderReasons(this.hass, p.reasons)}</td>
              <td class=${p.outcome}>
                ${p.reason ? `${p.outcome} (${p.reason})` : p.outcome}
              </td>
            </tr>`,
        )}
      </tbody>
    </table>`;
  }

  private setContent(change: () => void): void {
    change();
    this.response = undefined;
  }

  /** Names of the reached receiver types that lack a capability. */
  private lacking(field: string) {
    const names = this.reachedTypes
      .filter((t) => !supports(t, field))
      .map((t) => t.type);
    return names.length
      ? html`<span class="muted"
          >Not supported by ${names.join(", ")}: it is dropped, with a
          warning.</span
        >`
      : "";
  }

  /**
   * The designer's receiver-specific options. Each field is shown only when
   * a receiver that would be reached supports it.
   */
  private renderContent() {
    const types = this.reachedTypes;
    const priority = types.some((t) => supports(t, "priority"));
    const image = types.some((t) => supports(t, "image"));
    const dataTypes = types.filter((t) => supports(t, "data"));
    if (!priority && !image && !dataTypes.length) return "";
    const { error } = this.content;
    return html`<ha-card class="content">
      <div class="card-header">
        Receiver-specific content
        <p class="secondary">
          Shown for the receiver types that would be reached.
        </p>
      </div>
      <div class="card-content">
        ${
          priority
            ? html`<label class="field priority"
                ><span>Priority</span
                ><select
                  @change=${(ev: Event) =>
                    this.setContent(
                      () =>
                        (this.priority = (
                          ev.target as HTMLSelectElement
                        ).value),
                    )}
                >
                  <option value="">Default (normal)</option>
                  ${PRIORITIES.map(
                    (p) =>
                      html`<option value=${p} ?selected=${this.priority === p}>
                        ${p}
                      </option>`,
                  )}
                </select>
                ${this.lacking("priority")}</label
              >`
            : ""
        }
        ${
          image
            ? html`<label class="field image"
                ><span>Image (URL, /local/ path or media source ID)</span
                ><input
                  type="text"
                  .value=${this.image}
                  @input=${(ev: Event) =>
                    this.setContent(
                      () =>
                        (this.image = (ev.target as HTMLInputElement).value),
                    )}
                />
                ${this.lacking("image")}</label
              >`
            : ""
        }
        ${dataTypes.map((t) => {
          const keys = (t.capabilities ?? [])
            .filter((c) => c.startsWith("data."))
            .map((c) => c.slice(5));
          return html`<label class="field data"
            ><span
              >${t.type} data
              (JSON${keys.length ? `; keys: ${keys.join(", ")}` : ""})</span
            ><textarea
              rows="3"
              data-type=${t.type_id}
              .value=${this.dataText[t.type_id ?? ""] ?? ""}
              @input=${(ev: Event) =>
                this.setContent(
                  () =>
                    (this.dataText = {
                      ...this.dataText,
                      [t.type_id ?? ""]: (ev.target as HTMLTextAreaElement)
                        .value,
                    }),
                )}
            ></textarea>
          </label>`;
        })}
        ${error ? html`<p class="error content-error">${error}</p>` : ""}
      </div>
    </ha-card>`;
  }

  private renderResponse() {
    const r = this.response;
    if (!r) return "";
    return html`<ha-card>
      <div class="card-header">
        Result
        <p class="secondary counts">
          ${r.counts.delivered} delivered, ${r.counts.failed} failed,
          ${r.counts.skipped} skipped
        </p>
      </div>
      <div class="card-content">
        <table class="results">
          <thead>
            <tr>
              <th>Receiver</th>
              <th>Type</th>
              <th>Why</th>
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
                  <td>${renderReasons(this.hass, x.reasons)}</td>
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
      </div>
    </ha-card>`;
  }

  /** HA's raised button when it is loaded, otherwise a styled native one. */
  private renderSendButton(canSend: boolean) {
    return customElements.get("ha-progress-button")
      ? html`<ha-progress-button
          raised
          class="send"
          ?disabled=${!canSend}
          @click=${() => this.send()}
          >Send test</ha-progress-button
        >`
      : html`<button
          class="send"
          ?disabled=${!canSend}
          @click=${() => this.send()}
        >
          Send test
        </button>`;
  }

  protected render() {
    const canSend =
      !this.sending &&
      !this.content.error &&
      this.message.trim() !== "" &&
      (this.preview?.some((p) => p.outcome === "reached") ?? false);
    return html`
      <ha-card>
        <div class="card-header">
          Send a test notification
          <p class="secondary">
            Calls notify.com_system. People and receivers are combined, and one
            that is not given is not targeted.
          </p>
        </div>
        <div class="card-content">
          ${
            this.haControl
              ? html`<ha-service-control
                  hide-picker
                  hide-description
                  .hass=${this.formHass}
                  .value=${this.value}
                  @value-changed=${(ev: CustomEvent<{ value: ActionValue }>) =>
                    this.controlChanged(ev)}
                ></ha-service-control>`
              : this.haControl === false
                ? html`<p class="error">
                    Home Assistant's action form is not available.
                  </p>`
                : html`<p class="muted">Loading…</p>`
          }
          ${this.error ? html`<p class="error">${this.error}</p>` : ""}
        </div>
        <div class="card-actions">${this.renderSendButton(canSend)}</div>
      </ha-card>
      <div class="content-options">${this.renderContent()}</div>
      <ha-card>
        <div class="card-header">Receivers reached</div>
        <div class="card-content">${this.renderPreview()}</div>
      </ha-card>
      <div class="response">${this.renderResponse()}</div>
    `;
  }
}

customElements.define("com-system-test", ComSystemTest);
