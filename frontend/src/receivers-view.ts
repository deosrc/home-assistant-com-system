import { LitElement, css, html } from "lit";
import { ComSystemApi, errorMessage } from "./api";
import { sharedStyles } from "./styles";
import type { DiscoveryInfo, HomeAssistant, ReceiverInfo } from "./types";

/** The receiver being edited. */
interface Draft {
  entryId: string;
  name: string;
  people: string[];
  error?: string;
}

/** Messages for the error codes the update command returns. */
const ERRORS: Record<string, string> = {
  name_required: "Enter a name.",
};

/** Configured receivers with enable/disable, plus pending discoveries. */
export class ComSystemReceivers extends LitElement {
  declare hass: HomeAssistant;
  declare private receivers?: ReceiverInfo[];
  declare private discoveries: DiscoveryInfo[];
  declare private error?: string;
  declare private draft?: Draft;

  static properties = {
    hass: { attribute: false },
    receivers: { state: true },
    discoveries: { state: true },
    error: { state: true },
    draft: { state: true },
  };

  static styles = [
    sharedStyles,
    css`
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
      .switch {
        width: 1%;
      }
      tr.unavailable td:not(.switch) {
        opacity: 0.6;
      }
      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 10px 2px 6px;
        border-radius: 16px;
        font-size: 12px;
        white-space: nowrap;
        background: var(--secondary-background-color, #f0f0f0);
        color: var(--primary-text-color);
      }
      .badge ha-icon {
        --mdc-icon-size: 16px;
        display: inline-flex;
        color: var(--secondary-text-color);
      }
      .editor {
        display: grid;
        gap: 12px;
        max-width: 560px;
      }
      .editor label {
        display: grid;
        gap: 4px;
      }
      .editor input {
        font: inherit;
        padding: 8px;
        color: var(--primary-text-color);
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
      }
      .people {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }
      .actions {
        display: flex;
        gap: 8px;
      }
      .card + .card {
        margin-top: 16px;
      }
    `,
  ];

  private lastSignature?: string;

  constructor() {
    super();
    this.discoveries = [];
  }

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
    const api = new ComSystemApi(this.hass);
    try {
      [this.receivers, this.discoveries] = await Promise.all([
        api.receivers(),
        api.discoveries(),
      ]);
      this.error = undefined;
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private async toggle(receiver: ReceiverInfo, ev: Event) {
    const control = ev.target as HTMLInputElement;
    try {
      await new ComSystemApi(this.hass).setEnabled(
        receiver.entry_id,
        control.checked,
      );
      await this.load();
    } catch (err) {
      // Put the switch back; the state did not change.
      control.checked = receiver.enabled === true;
      this.error = errorMessage(err);
    }
  }

  private startEdit(r: ReceiverInfo) {
    this.draft = { entryId: r.entry_id, name: r.name, people: [...r.people] };
  }

  private async save() {
    const d = this.draft;
    if (!d) return;
    try {
      await new ComSystemApi(this.hass).updateReceiver(d.entryId, {
        name: d.name,
        people: d.people,
      });
      this.draft = undefined;
      await this.load();
    } catch (err) {
      const code = (err as { code?: string })?.code ?? "";
      this.draft = { ...d, error: ERRORS[code] ?? errorMessage(err) };
    }
  }

  private async removeReceiver(r: ReceiverInfo) {
    if (!confirm(`Remove the receiver ${r.name}?`)) return;
    try {
      await new ComSystemApi(this.hass).removeReceiver(r.entry_id);
      await this.load();
    } catch (err) {
      this.error = errorMessage(err);
    }
  }

  private renderEditor(d: Draft) {
    const update = (changes: Partial<Draft>) =>
      (this.draft = { ...d, ...changes, error: undefined });
    const persons = Object.keys(this.hass.states).filter((id) =>
      id.startsWith("person."),
    );
    return html`<div class="card editor">
      <strong>Edit receiver</strong>
      <label
        >Name
        <input
          id="name"
          .value=${d.name}
          @input=${(e: Event) =>
            update({ name: (e.target as HTMLInputElement).value })}
      /></label>
      <div>
        People
        <div class="people">
          ${
            persons.length
              ? persons.map(
                  (id) =>
                    html`<label
                      ><input
                        type="checkbox"
                        .checked=${d.people.includes(id)}
                        @change=${(e: Event) =>
                          update({
                            people: (e.target as HTMLInputElement).checked
                              ? [...d.people, id]
                              : d.people.filter((p) => p !== id),
                          })}
                      />
                      ${
                        this.hass.states[id]?.attributes?.friendly_name ?? id
                      }</label
                    >`,
                )
              : html`<span class="muted">No people</span>`
          }
        </div>
      </div>
      ${d.error ? html`<p class="error">${d.error}</p>` : html``}
      <div class="actions">
        <button id="save" @click=${() => this.save()}>Save</button>
        <button id="cancel" @click=${() => (this.draft = undefined)}>
          Cancel
        </button>
      </div>
    </div>`;
  }

  /** The areas and people a receiver is linked to: by type, then name. */
  private targets(r: ReceiverInfo): { icon: string; name: string }[] {
    const areas = r.areas.map((id) => ({
      icon: "mdi:texture-box",
      name: this.hass.areas?.[id]?.name ?? id,
    }));
    const people = r.people.map((id) => ({
      icon: "mdi:account",
      name: this.hass.states[id]?.attributes?.friendly_name ?? id,
    }));
    const byName = (a: { name: string }, b: { name: string }) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    return [...areas.sort(byName), ...people.sort(byName)];
  }

  private renderTargets(r: ReceiverInfo) {
    const targets = this.targets(r);
    if (!targets.length) {
      return html`<span class="muted">None</span>`;
    }
    return html`<div class="badges">
      ${targets.map(
        (t) =>
          html`<span class="badge">
            <ha-icon icon=${t.icon}></ha-icon>${t.name}
          </span>`,
      )}
    </div>`;
  }

  protected render() {
    if (this.error) {
      return html`<p class="error">${this.error}</p>`;
    }
    if (!this.receivers) {
      return html`<p class="muted">Loading…</p>`;
    }
    return html`
      <div>${this.draft ? this.renderEditor(this.draft) : html``}</div>
      <div class="card">
        <strong>Receivers</strong>
        ${
          this.receivers.length
            ? html`<table>
                <thead>
                  <tr>
                    <th class="switch" aria-label="Enabled"></th>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Targets</th>
                    <th aria-label="Actions"></th>
                  </tr>
                </thead>
                <tbody>
                  ${this.receivers.map(
                    (r) => html`
                      <tr class=${r.available ? "" : "unavailable"}>
                        <td class="switch">
                          <ha-switch
                            .checked=${r.enabled === true}
                            ?disabled=${!r.available || r.enabled === null}
                            title=${r.available ? "" : "Unavailable"}
                            @change=${(ev: Event) => this.toggle(r, ev)}
                          ></ha-switch>
                        </td>
                        <td>${r.name}</td>
                        <td>${r.type}</td>
                        <td>${this.renderTargets(r)}</td>
                        <td class="actions">
                          <button
                            class="edit"
                            @click=${() => this.startEdit(r)}
                          >
                            Edit
                          </button>
                          <button
                            class="remove"
                            @click=${() => this.removeReceiver(r)}
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    `,
                  )}
                </tbody>
              </table>`
            : html`<p class="muted">No receivers yet.</p>`
        }
      </div>
      <div class="card">
        <strong>Pending discoveries</strong>
        ${
          this.discoveries.length
            ? html`<ul>
                  ${this.discoveries.map(
                    (d) => html`<li>${d.name} (${d.type})</li>`,
                  )}
                </ul>
                <p>
                  <a href="/config/integrations/integration/com_system"
                    >Review in Devices &amp; services</a
                  >
                </p>`
            : html`<p class="muted">Nothing waiting to be added.</p>`
        }
      </div>
    `;
  }
}

customElements.define("com-system-receivers", ComSystemReceivers);
