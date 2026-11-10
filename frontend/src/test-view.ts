import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type {
  HomeAssistant,
  NotifyTargets,
  SelectedTarget,
  PreviewEntry,
  ReceiverInfo,
  SendResponse,
} from "./types";

/** The people field is a choice: everyone, or individual people. */
const EVERYONE = "Everyone";
const INDIVIDUALS = "Individuals";
type PersonChoice = typeof EVERYONE | typeof INDIVIDUALS;

/** The receivers field is a choice: a selection, or all areas. */
const NONE = "None";
const SELECT = "Select";
const ALL_AREAS = "All Areas";
type ReceiversChoice = typeof SELECT | typeof ALL_AREAS;

/** The lists the built-in form edits. */
type TargetKey = "person" | "area_id" | "entity_id";

const ACTION = "notify.com_system";

/** Home Assistant's own Actions form; loaded lazily, so it may be absent. */
const CONTROL = "ha-service-control";

function ensureList(value: unknown): string[] {
  if (value === undefined || value === null || value === "") return [];
  return (Array.isArray(value) ? value : [value]).map(String);
}

/**
 * The testing tool: choose targets, preview which receivers they reach, and
 * send a test through the `notify.com_system` action.
 *
 * The form is Home Assistant's `ha-service-control` with its action picker
 * hidden, so it matches Developer tools > Actions. The element is loaded
 * lazily by Home Assistant, so if it is not defined shortly after the view
 * opens, a built-in form with the same fields is used instead. Both edit the
 * same state, which feeds the preview and the send.
 */
export class ComSystemTest extends LitElement {
  declare hass: HomeAssistant;
  declare private receivers: ReceiverInfo[];
  declare private message: string;
  declare private subject: string;
  /** The individuals chosen when `personChoice` is Individuals. */
  declare private people: string[];
  /** Undefined: the field is not given, so people are not targeted. */
  declare private personChoice?: PersonChoice;
  /** The selection (area_id, entity_id, ...) when `receiversChoice` is Select. */
  declare private selection: SelectedTarget;
  /** Undefined: the field is not given, so receivers are not targeted. */
  declare private receiversChoice?: ReceiversChoice;
  declare private preview?: PreviewEntry[];
  declare private response?: SendResponse;
  declare private sending: boolean;
  declare private error?: string;
  /** Whether Home Assistant's Actions form is available (undefined: waiting). */
  declare private haControl?: boolean;

  /** How long to wait for `ha-service-control` before using the fallback. */
  static controlTimeoutMs = 1500;

  static properties = {
    hass: { attribute: false },
    receivers: { state: true },
    message: { state: true },
    subject: { state: true },
    people: { state: true },
    personChoice: { state: true },
    selection: { state: true },
    receiversChoice: { state: true },
    preview: { state: true },
    response: { state: true },
    sending: { state: true },
    error: { state: true },
    haControl: { state: true },
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
    this.receivers = [];
    this.message = "";
    this.subject = "";
    this.people = [];
    this.personChoice = EVERYONE;
    this.selection = {};
    this.receiversChoice = ALL_AREAS;
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

  /** The action call the form edits: only the fields with a value. */
  private get actionValue() {
    const data: Record<string, unknown> = {};
    if (this.subject) data.title = this.subject;
    if (this.message) data.message = this.message;
    // A field that is not given is left out, which unticks it in the form.
    if (this.personChoice === EVERYONE) {
      data.person = { active_choice: EVERYONE, [EVERYONE]: true };
    } else if (this.personChoice === INDIVIDUALS) {
      data.person = { active_choice: INDIVIDUALS, [INDIVIDUALS]: this.people };
    }
    if (this.receiversChoice === ALL_AREAS) {
      data.receivers = { active_choice: ALL_AREAS, [ALL_AREAS]: true };
    } else if (this.receiversChoice === SELECT) {
      data.receivers = { active_choice: SELECT, [SELECT]: this.selection };
    }
    return { action: ACTION, data };
  }

  private controlChanged(ev: CustomEvent<{ value: { data?: object } }>): void {
    ev.stopPropagation();
    const data = (ev.detail.value.data ?? {}) as Record<string, unknown>;
    this.message = data.message === undefined ? "" : String(data.message);
    this.subject = data.title === undefined ? "" : String(data.title);
    const person = (data.person ?? {}) as Record<string, unknown>;
    this.personChoice =
      data.person === undefined
        ? undefined
        : person.active_choice === INDIVIDUALS
          ? INDIVIDUALS
          : EVERYONE;
    this.people = ensureList(person[INDIVIDUALS]);
    const receivers = (data.receivers ?? {}) as Record<string, unknown>;
    this.receiversChoice =
      data.receivers === undefined
        ? undefined
        : receivers.active_choice === SELECT
          ? SELECT
          : ALL_AREAS;
    // Keep every key of the target selector (areas, devices, floors, ...).
    const selection: SelectedTarget = {};
    for (const [key, value] of Object.entries(
      (receivers[SELECT] ?? {}) as Record<string, unknown>,
    )) {
      if (ensureList(value).length) selection[key] = ensureList(value);
    }
    this.selection = selection;
    // The previous send no longer describes the selection.
    this.response = undefined;
    void this.refreshPreview();
  }

  private async init(): Promise<void> {
    try {
      this.receivers = await new ComSystemApi(this.hass).receivers();
    } catch (err) {
      this.error = errorMessage(err);
    }
    await this.refreshPreview();
  }

  /** Only the fields with a selection are sent. */
  private get targets(): NotifyTargets {
    const targets: NotifyTargets = {};
    if (this.personChoice === EVERYONE) {
      targets.person = { active_choice: EVERYONE, [EVERYONE]: true };
    } else if (this.people.length) {
      targets.person = this.people;
    }
    if (this.receiversChoice === ALL_AREAS) {
      targets.receivers = { active_choice: ALL_AREAS, [ALL_AREAS]: true };
    } else if (
      this.receiversChoice === SELECT &&
      Object.keys(this.selection).length
    ) {
      targets.receivers = { active_choice: SELECT, [SELECT]: this.selection };
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

  private chosen(key: TargetKey): string[] {
    return key === "person" ? this.people : (this.selection[key] ?? []);
  }

  private toggle(key: TargetKey, id: string, checked: boolean): void {
    const current = this.chosen(key).filter((x) => x !== id);
    const next = checked ? [...current, id] : current;
    if (key === "person") {
      this.people = next;
    } else {
      const selection = { ...this.selection, [key]: next };
      if (!next.length) delete selection[key];
      this.selection = selection;
    }
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

  private setPersonChoice(choice: PersonChoice | undefined): void {
    this.personChoice = choice;
    this.response = undefined;
    void this.refreshPreview();
  }

  /** People: everyone, or individuals (listed only when chosen). */
  private renderPeople() {
    return html`<div class="people">
      <fieldset>
        <legend>People</legend>
        ${[INDIVIDUALS, EVERYONE, NONE].map(
          (choice) =>
            html`<label
              ><input
                type="radio"
                name="people"
                .checked=${(this.personChoice ?? NONE) === choice}
                @change=${() =>
                  this.setPersonChoice(
                    choice === NONE ? undefined : (choice as PersonChoice),
                  )}
              />
              ${choice}</label
            >`,
        )}
      </fieldset>
      ${
        this.personChoice === INDIVIDUALS
          ? this.renderTargets("person", "Individuals")
          : ""
      }
    </div>`;
  }

  private setReceiversChoice(choice: ReceiversChoice | undefined): void {
    this.receiversChoice = choice;
    this.response = undefined;
    void this.refreshPreview();
  }

  /** Receivers: a selection (listed only when chosen), or all areas. */
  private renderReceivers() {
    return html`<div class="receivers">
      <fieldset>
        <legend>Receivers</legend>
        ${[SELECT, ALL_AREAS, NONE].map(
          (choice) =>
            html`<label
              ><input
                type="radio"
                name="receivers"
                .checked=${(this.receiversChoice ?? NONE) === choice}
                @change=${() =>
                  this.setReceiversChoice(
                    choice === NONE ? undefined : (choice as ReceiversChoice),
                  )}
              />
              ${choice}</label
            >`,
        )}
      </fieldset>
      ${
        this.receiversChoice === SELECT
          ? html`<div class="select">
              ${this.renderTargets("entity_id", "Receivers")}
              ${this.renderTargets("area_id", "Areas")}
            </div>`
          : ""
      }
    </div>`;
  }

  private renderTargets(key: TargetKey, legend: string) {
    const options = this.options(key);
    return html`<fieldset>
      <legend>${legend}</legend>
      ${
        options.length
          ? options.map(
              (o) =>
                html`<label
                  ><input
                    type="checkbox"
                    .checked=${this.chosen(key).includes(o.id)}
                    @change=${(ev: Event) =>
                      this.toggle(
                        key,
                        o.id,
                        (ev.target as HTMLInputElement).checked,
                      )}
                  />
                  ${o.name}</label
                >`,
            )
          : html`<span class="muted">None available</span>`
      }
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
          (p) =>
            html`<tr>
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

  private renderFallbackForm() {
    return html`
      <label class="field"
        ><span>Title (optional)</span
        ><input
          type="text"
          .value=${this.subject}
          @input=${(ev: Event) =>
            (this.subject = (ev.target as HTMLInputElement).value)}
      /></label>
      <label class="field"
        ><span>Message</span
        ><textarea
          rows="2"
          .value=${this.message}
          @input=${(ev: Event) =>
            (this.message = (ev.target as HTMLTextAreaElement).value)}
        ></textarea>
      </label>
      <div class="targets">
        ${this.renderPeople()} ${this.renderReceivers()}
      </div>
    `;
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
                  .hass=${this.hass}
                  .value=${this.actionValue}
                  @value-changed=${(
                    ev: CustomEvent<{ value: { data?: object } }>,
                  ) => this.controlChanged(ev)}
                ></ha-service-control>`
              : this.haControl === false
                ? this.renderFallbackForm()
                : html`<p class="muted">Loading…</p>`
          }
          ${this.error ? html`<p class="error">${this.error}</p>` : ""}
        </div>
        <div class="card-actions">${this.renderSendButton(canSend)}</div>
      </ha-card>
      <ha-card>
        <div class="card-header">Receivers reached</div>
        <div class="card-content">${this.renderPreview()}</div>
      </ha-card>
      <div class="response">${this.renderResponse()}</div>
    `;
  }
}

customElements.define("com-system-test", ComSystemTest);
