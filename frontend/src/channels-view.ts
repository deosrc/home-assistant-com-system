import { LitElement, css, html, nothing } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { ChannelDefaults, ChannelInfo, HomeAssistant } from "./types";

/** Home Assistant's own Actions form; loaded lazily, so it may be absent. */
const CONTROL = "ha-service-control";
/** Home Assistant's dialog element, used for the delete confirmation. */
const DIALOG = "ha-dialog";
const DOMAIN = "com_system";
const CREATE = "create_channel";
const UPDATE = "update_channel";
const DELETE = "delete_channel";

interface ActionValue {
  action: string;
  data?: Record<string, unknown>;
}

/** What the open form is doing. */
interface Editing {
  /** The channel being edited; absent while creating. */
  channel?: ChannelInfo;
  value: ActionValue;
}

/** The update form starts from the channel's current values. */
function updateValue(channel: ChannelInfo): ActionValue {
  const { image, ...rest }: ChannelDefaults = channel.defaults;
  return {
    action: `${DOMAIN}.${UPDATE}`,
    data: {
      channel: channel.entity_id,
      name: channel.name,
      ...rest,
      ...(image ? { image: imageChoice(image) } : {}),
    },
  };
}

/** The image field is a choose selector (as on notify.com_system), so the
 * stored string becomes its `{active_choice, <choice>: value}` form. */
function imageChoice(image: string): Record<string, string> {
  const isEntity = /^(image|camera)\.[^/]*$/.test(image);
  const choice = isEntity ? "Entity" : "URL";
  return { active_choice: choice, [choice]: image };
}

/**
 * Channels: named default content, each a `notification_channel` entity.
 *
 * Channels are read over websocket and written through the
 * `com_system.create_channel`, `update_channel` and `delete_channel`
 * actions. The forms are Home Assistant's `ha-service-control`, so the
 * fields, selectors and descriptions come from the actions' own
 * descriptions. As on the Test page, the create form starts from the action
 * alone so Home Assistant applies its defaults; the update form is seeded
 * with the channel's current values.
 */
export class ComSystemChannels extends LitElement {
  declare hass: HomeAssistant;
  declare private channels?: ChannelInfo[];
  declare private editing?: Editing;
  declare private error?: string;
  declare private formError?: string;
  declare private saving: boolean;
  /** The channel whose delete confirmation dialog is open. */
  declare private confirming?: ChannelInfo;
  /** Whether Home Assistant's Actions form is available (undefined: waiting). */
  declare private haControl?: boolean;

  /** How long to wait for `ha-service-control` before giving up. */
  static controlTimeoutMs = 1500;

  static properties = {
    hass: { attribute: false },
    channels: { state: true },
    editing: { state: true },
    error: { state: true },
    formError: { state: true },
    saving: { state: true },
    confirming: { state: true },
    haControl: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        padding-bottom: 16px;
      }
      .card {
        margin-bottom: 16px;
      }
      .head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 8px;
      }
      .channel-name {
        font-size: 20px;
        font-weight: 500;
      }
      /* As in Home Assistant's dialog-box: the header sizes the title, so the
         heading must not bring its own size and margin. */
      .confirm-title {
        font-weight: inherit;
        font-size: inherit;
        margin: inherit;
      }
      #confirm-text p {
        color: var(--primary-text-color);
        margin: 0;
      }
      .form-title {
        margin: 0 0 16px;
        font-size: 20px;
        font-weight: 400;
      }
      .actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 12px;
      }
      code {
        font-size: 12px;
      }
      button {
        padding: 8px 16px;
        font-weight: 500;
        border: none;
        border-radius: var(--ha-button-border-radius, 9999px);
        color: var(--text-primary-color, #fff);
        background: var(--primary-color);
      }
      button.add {
        flex-shrink: 0;
        white-space: nowrap;
      }
      button:disabled {
        opacity: 0.5;
        cursor: default;
      }
      button.secondary {
        color: var(--primary-color);
        background: transparent;
      }
      button.danger {
        color: var(--error-color, #db4437);
        background: transparent;
      }
      dl {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 4px 16px;
        margin: 8px 0 0;
      }
      dt {
        color: var(--secondary-text-color);
      }
      dd {
        margin: 0;
        min-width: 0;
        overflow-wrap: anywhere;
      }
      dd dl {
        margin: 0;
      }
      .data-block {
        margin-top: 12px;
      }
      .receiver-type {
        font-weight: 500;
      }
    `,
  ];

  constructor() {
    super();
    this.saving = false;
  }

  private loaded = false;

  protected updated(): void {
    if (this.hass && !this.loaded) {
      this.loaded = true;
      void this.load();
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (customElements.get(CONTROL)) {
      this.haControl = true;
      return;
    }
    const timeout = new Promise<boolean>((resolve) =>
      setTimeout(() => resolve(false), ComSystemChannels.controlTimeoutMs),
    );
    const defined = customElements.whenDefined(CONTROL).then(() => true);
    void Promise.race([defined, timeout]).then((ok) => (this.haControl = ok));
  }

  private async load(): Promise<void> {
    try {
      this.channels = await new ComSystemApi(this.hass).channels();
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  /** Opens Home Assistant's "More info" dialog for the channel's entity. */
  private showMoreInfo(entityId: string): void {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private open(editing: Editing): void {
    this.editing = editing;
    this.formError = undefined;
  }

  private close(): void {
    this.editing = undefined;
    this.formError = undefined;
  }

  private controlChanged(ev: CustomEvent<{ value: ActionValue }>): void {
    ev.stopPropagation();
    if (this.editing) {
      this.editing = { ...this.editing, value: ev.detail.value };
    }
  }

  /** Calls the open form's action with the data the form reports. */
  private async save(): Promise<void> {
    const editing = this.editing;
    if (!editing) return;
    this.saving = true;
    try {
      await this.hass.callService(
        DOMAIN,
        editing.channel ? UPDATE : CREATE,
        editing.value.data ?? {},
      );
    } catch (err) {
      this.formError = errorMessage(err);
      return;
    } finally {
      this.saving = false;
    }
    this.close();
    await this.load();
  }

  private confirmText(channel: ChannelInfo): string {
    return `Delete the channel ${channel.name}? Android devices are told to remove it.`;
  }

  /** Asks first, in Home Assistant's dialog style when it is available. */
  private requestDelete(channel: ChannelInfo): void {
    if (customElements.get(DIALOG)) {
      this.confirming = channel;
    } else if (window.confirm(this.confirmText(channel))) {
      void this.deleteChannel(channel);
    }
  }

  private async deleteChannel(channel: ChannelInfo): Promise<void> {
    try {
      await this.hass.callService(DOMAIN, DELETE, {
        channel: channel.entity_id,
      });
    } catch (err) {
      this.error = errorMessage(err);
      return;
    }
    await this.load();
  }

  /** The delete confirmation, laid out like Home Assistant's own
   * confirmation dialog (`dialog-box`): a titled `ha-dialog` with a plain
   * Cancel and a danger Delete button in the footer. */
  private renderConfirm(channel: ChannelInfo) {
    const close = () => (this.confirming = undefined);
    return html`<ha-dialog
      .open=${true}
      type="standard"
      .preventScrimClose=${true}
      aria-describedby="confirm-text"
      @closed=${close}
    >
      <ha-dialog-header slot="header">
        <h1 slot="title" class="confirm-title">Delete channel</h1>
      </ha-dialog-header>
      <div id="confirm-text"><p>${this.confirmText(channel)}</p></div>
      <ha-dialog-footer slot="footer">
        <ha-button
          slot="secondaryAction"
          class="confirm-cancel"
          appearance="plain"
          @click=${close}
        >
          Cancel
        </ha-button>
        <ha-button
          slot="primaryAction"
          class="confirm-delete"
          variant="danger"
          @click=${() => {
            close();
            void this.deleteChannel(channel);
          }}
        >
          Delete
        </ha-button>
      </ha-dialog-footer>
    </ha-dialog>`;
  }

  private renderForm(editing: Editing) {
    return html`
      <div class="card">
        <h2 class="form-title">
          ${editing.channel ? "Edit channel" : "Add a channel"}
        </h2>
        ${
          this.haControl
            ? html`<ha-service-control
                hide-picker
                hide-description
                .hass=${this.hass}
                .value=${editing.value}
                @value-changed=${(ev: CustomEvent<{ value: ActionValue }>) =>
                  this.controlChanged(ev)}
              ></ha-service-control>`
            : this.haControl === false
              ? html`<p class="error">
                  Home Assistant's action form is not available.
                </p>`
              : html`<p class="muted">Loading…</p>`
        }
        ${
          this.formError
            ? html`<p class="error">${this.formError}</p>`
            : nothing
        }
        <div class="actions">
          <button class="secondary" @click=${() => this.close()}>Cancel</button>
          <button
            class="save"
            ?disabled=${this.saving || !this.haControl}
            @click=${() => void this.save()}
          >
            ${editing.channel ? "Save" : "Create"}
          </button>
        </div>
      </div>
    `;
  }

  /** A value for the cards: objects broken down by key, lists joined. */
  private renderValue(value: unknown): unknown {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return html`<dl>
        ${Object.entries(value).map(
          ([k, v]) =>
            html`<dt>${k}</dt>
              <dd>${this.renderValue(v)}</dd>`,
        )}
      </dl>`;
    }
    if (Array.isArray(value)) {
      return value.every((v) => v === null || typeof v !== "object")
        ? value.join(", ")
        : html`<code>${JSON.stringify(value)}</code>`;
    }
    return String(value);
  }

  /** The defaults: Title, Priority, Image and the mobile app fields as labelled rows, then one
   * list of properties per receiver type in `data`. */
  private renderDefaults(d: ChannelDefaults) {
    const labels: [keyof ChannelDefaults, string][] = [
      ["title", "Title"],
      ["priority", "Priority"],
      ["image", "Image"],
      ["click_action", "Click action"],
      ["actions", "Actions"],
      ["tag", "Tag"],
      ["car_ui", "Car UI"],
    ];
    const rows = labels
      .filter(([key]) => d[key] !== undefined)
      .map(
        ([key, label]) =>
          html`<dt>${label}</dt>
            <dd>${this.renderValue(d[key])}</dd>`,
      );
    const blocks = Object.entries(d.data ?? {});
    if (!rows.length && !blocks.length) {
      return html`<p class="muted">No defaults.</p>`;
    }
    return html`<div class="defaults-wrap">
      ${rows.length ? html`<dl class="defaults">${rows}</dl>` : nothing}
      ${blocks.map(
        ([type, block]) =>
          html`<div class="data-block">
            <div class="receiver-type">${type}</div>
            ${this.renderValue(block)}
          </div>`,
      )}
    </div>`;
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.channels) {
      return html`<p class="muted">Loading…</p>`;
    }
    const editing = this.editing;
    return html`
      <div>
        <div class="toolbar">
          <span class="muted"
            >Notification Channels provide defaults such as priority when
            sending notifications. For receivers such as the Home Assistant
            Companion App, the Channel is also used for the Android Notification
            Channel.</span
          >
          <button
            class="add"
            @click=${() => this.open({ value: { action: `${DOMAIN}.${CREATE}` } })}
          >
            Add channel
          </button>
        </div>
        ${editing ? this.renderForm(editing) : nothing}
        ${
          !this.channels.length && !editing
            ? html`<p class="muted">No channels yet.</p>`
            : nothing
        }
        ${this.channels.map(
          (c) =>
            html`<div class="card">
              <div class="head">
                <strong class="channel-name">${c.name}</strong>
                <code>${c.entity_id ?? ""}</code>
              </div>
              ${this.renderDefaults(c.defaults)}
              <div class="actions">
                ${
                  c.entity_id
                    ? html`<button
                        class="secondary more-info"
                        @click=${() => this.showMoreInfo(c.entity_id!)}
                      >
                        More info
                      </button>`
                    : nothing
                }
                <button
                  class="secondary edit"
                  @click=${() =>
                    this.open({ channel: c, value: updateValue(c) })}
                >
                  Edit
                </button>
                <button
                  class="danger delete"
                  @click=${() => this.requestDelete(c)}
                >
                  Delete
                </button>
              </div>
            </div>`,
        )}
        ${this.confirming ? this.renderConfirm(this.confirming) : nothing}
      </div>
    `;
  }
}

customElements.define("com-system-channels", ComSystemChannels);
