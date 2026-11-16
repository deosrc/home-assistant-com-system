import { LitElement, css, html, nothing } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { ChannelDefaults, ChannelInfo, HomeAssistant } from "./types";

const PRIORITIES = ["", "low", "normal", "high", "critical"];

interface Draft {
  /** Absent while adding a new channel. */
  channelId?: string;
  name: string;
  title: string;
  priority: string;
  image: string;
  /** The `data` object as JSON text. */
  data: string;
}

function toDraft(channel?: ChannelInfo): Draft {
  const d = channel?.defaults ?? {};
  return {
    channelId: channel?.channel_id,
    name: channel?.name ?? "",
    title: d.title ?? "",
    priority: d.priority ?? "",
    image: d.image ?? "",
    data: d.data ? JSON.stringify(d.data, null, 2) : "",
  };
}

/** Parses a draft into defaults, or throws a message for the form. */
export function toDefaults(draft: Draft): ChannelDefaults {
  const defaults: ChannelDefaults = {};
  if (draft.title.trim()) defaults.title = draft.title.trim();
  if (draft.priority) defaults.priority = draft.priority;
  if (draft.image.trim()) defaults.image = draft.image.trim();
  if (draft.data.trim()) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft.data);
    } catch {
      throw new Error("Data must be valid JSON");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Data must be an object keyed by receiver type");
    }
    defaults.data = parsed as Record<string, unknown>;
  }
  return defaults;
}

/** Channels: named default content, each a `notification_channel` entity. */
export class ComSystemChannels extends LitElement {
  declare hass: HomeAssistant;
  declare private channels?: ChannelInfo[];
  declare private draft?: Draft;
  declare private error?: string;
  declare private formError?: string;

  static properties = {
    hass: { attribute: false },
    channels: { state: true },
    draft: { state: true },
    error: { state: true },
    formError: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
      .toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
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
      .actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 12px;
      }
      code {
        font-size: 12px;
      }
      label {
        display: block;
        margin-bottom: 12px;
      }
      label span {
        display: block;
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-bottom: 4px;
      }
      input,
      select,
      textarea {
        box-sizing: border-box;
        width: 100%;
        padding: 8px;
        font: inherit;
        color: var(--primary-text-color);
        background: var(--secondary-background-color, #f5f5f5);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
      }
      textarea {
        min-height: 96px;
        font-family: monospace;
      }
      button {
        padding: 8px 16px;
        font-weight: 500;
        border: none;
        border-radius: var(--ha-button-border-radius, 9999px);
        color: var(--text-primary-color, #fff);
        background: var(--primary-color);
      }
      button.secondary {
        color: var(--primary-color);
        background: transparent;
      }
      button.danger {
        color: var(--error-color, #db4437);
        background: transparent;
      }
      ul.defaults {
        margin: 8px 0 0;
        padding-left: 18px;
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
      this.channels = await new ComSystemApi(this.hass).channels();
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private async save(): Promise<void> {
    const draft = this.draft;
    if (!draft) return;
    try {
      await new ComSystemApi(this.hass).saveChannel(
        draft.name,
        toDefaults(draft),
        draft.channelId,
      );
    } catch (err) {
      this.formError = errorMessage(err);
      return;
    }
    this.draft = undefined;
    this.formError = undefined;
    await this.load();
  }

  private async deleteChannel(channel: ChannelInfo): Promise<void> {
    if (
      !window.confirm(
        `Delete the channel ${channel.name}? Android devices are told to remove it.`,
      )
    ) {
      return;
    }
    try {
      await new ComSystemApi(this.hass).removeChannel(channel.channel_id);
    } catch (err) {
      this.error = errorMessage(err);
      return;
    }
    await this.load();
  }

  private edit(key: keyof Draft, ev: Event): void {
    const value = (ev.target as HTMLInputElement).value;
    this.draft = { ...this.draft!, [key]: value };
  }

  private renderForm(draft: Draft) {
    return html`
      <div class="card">
        <label
          ><span>Name</span
          ><input
            .value=${draft.name}
            @input=${(ev: Event) => this.edit("name", ev)}
        /></label>
        <label
          ><span>Title</span
          ><input
            .value=${draft.title}
            @input=${(ev: Event) => this.edit("title", ev)}
        /></label>
        <label
          ><span>Priority</span
          ><select
            .value=${draft.priority}
            @change=${(ev: Event) => this.edit("priority", ev)}
          >
            ${PRIORITIES.map(
              (p) =>
                html`<option value=${p} ?selected=${p === draft.priority}>
                  ${p || "(none)"}
                </option>`,
            )}
          </select></label
        >
        <label
          ><span>Image (URL, /local/ path, media source or entity)</span
          ><input
            .value=${draft.image}
            @input=${(ev: Event) => this.edit("image", ev)}
        /></label>
        <label
          ><span>Data (JSON, keyed by receiver type)</span
          ><textarea
            .value=${draft.data}
            @input=${(ev: Event) => this.edit("data", ev)}
          ></textarea>
        </label>
        ${
          this.formError
            ? html`<p class="error">${this.formError}</p>`
            : nothing
        }
        <div class="actions">
          <button
            class="secondary"
            @click=${() => {
              this.draft = undefined;
              this.formError = undefined;
            }}
          >
            Cancel
          </button>
          <button @click=${() => void this.save()}>Save</button>
        </div>
      </div>
    `;
  }

  private renderDefaults(d: ChannelDefaults) {
    const rows = Object.entries(d).map(
      ([k, v]) =>
        html`<li>
          ${k}: <code>${typeof v === "string" ? v : JSON.stringify(v)}</code>
        </li>`,
    );
    return rows.length
      ? html`<ul class="defaults">
          ${rows}
        </ul>`
      : html`<p class="muted">No defaults.</p>`;
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.channels) {
      return html`<p class="muted">Loading…</p>`;
    }
    return html`
      <div>
        <div class="toolbar">
          <span class="muted"
            >Select a channel in the channel field of notify.com_system. Its
            defaults fill anything the call leaves out.</span
          >
          <button @click=${() => (this.draft = toDraft())}>Add channel</button>
        </div>
        ${this.draft && !this.draft.channelId ? this.renderForm(this.draft) : nothing}
        ${
          !this.channels.length && !this.draft
            ? html`<p class="muted">No channels yet.</p>`
            : nothing
        }
        ${this.channels.map((c) =>
          this.draft?.channelId === c.channel_id
            ? this.renderForm(this.draft)
            : html`<div class="card">
                <div class="head">
                  <strong>${c.name}</strong>
                  <code>${c.entity_id ?? ""}</code>
                </div>
                ${this.renderDefaults(c.defaults)}
                <div class="actions">
                  <button
                    class="secondary"
                    @click=${() => (this.draft = toDraft(c))}
                  >
                    Edit
                  </button>
                  <button
                    class="danger"
                    @click=${() => void this.deleteChannel(c)}
                  >
                    Delete
                  </button>
                </div>
              </div>`,
        )}
      </div>
    `;
  }
}

customElements.define("com-system-channels", ComSystemChannels);
