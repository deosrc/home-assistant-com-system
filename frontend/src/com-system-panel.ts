import { LitElement, css, html, nothing } from "lit";
import "./dashboard-view";
import "./receivers-view";
import "./test-view";
import { sharedStyles } from "./styles";
import type { HomeAssistant, PanelRoute } from "./types";

// In development Home Assistant imports this module straight from the Vite
// dev server, so the HMR client has to be loaded explicitly, from the dev
// server's origin. Vite removes this block from production builds.
if (import.meta.env.MODE === "development") {
  void import(/* @vite-ignore */ new URL("/@vite/client", import.meta.url).href);
}

const VIEWS = [
  { path: "dashboard", label: "Dashboard" },
  { path: "receivers", label: "Receivers" },
  { path: "test", label: "Test" },
] as const;

/** The admin-only Com System panel: navigation and the active view. */
export class ComSystemPanel extends LitElement {
  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare route: PanelRoute;
  declare panel: unknown;

  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean, reflect: true },
    route: { attribute: false },
    panel: { attribute: false },
  };

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        min-height: 100vh;
        background: var(--primary-background-color);
        color: var(--primary-text-color);
      }
      /* Copies the toolbar and tabs of Home Assistant's own pages
         (hass-tabs-subpage and ha-tab). */
      :host([narrow]) {
        padding-bottom: var(--header-height, 56px);
      }
      .toolbar {
        box-sizing: border-box;
        height: var(--header-height, 56px);
        font-size: 20px;
        font-weight: 400;
        background-color: var(--sidebar-background-color);
        border-bottom: 1px solid var(--divider-color);
      }
      .toolbar-content {
        display: flex;
        align-items: center;
        box-sizing: border-box;
        height: 100%;
        padding: 8px 12px;
      }
      :host([narrow]) .toolbar-content {
        padding: 4px;
      }
      ha-menu-button {
        flex-shrink: 0;
        color: var(--sidebar-icon-color);
        margin-inline-end: 24px;
      }
      h1 {
        flex: 1;
        min-width: 0;
        margin: 0;
        font-size: inherit;
        font-weight: inherit;
        line-height: 1.5;
        color: var(--sidebar-text-color);
        white-space: nowrap;
      }
      nav {
        display: flex;
        flex: 1;
        justify-content: center;
        overflow: hidden;
        font-size: 14px;
      }
      nav.bottom-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        z-index: 2;
        width: 100%;
        box-sizing: border-box;
        padding: 0 16px;
        justify-content: space-around;
        font-size: 12px;
        background-color: var(--sidebar-background-color);
        border-top: 1px solid var(--divider-color);
      }
      nav a {
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        height: var(--header-height, 56px);
        padding: 0 32px;
        max-width: 45%;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        text-decoration: none;
        color: var(--sidebar-text-color);
        outline: none;
      }
      nav.bottom-bar a {
        width: 25%;
        padding: 0 4px;
      }
      nav a.active {
        color: var(--primary-color);
      }
      nav:not(.bottom-bar) a.active {
        border-bottom: 2px solid var(--primary-color);
      }
      nav a:focus-visible {
        background-color: rgba(127, 127, 127, 0.08);
      }
      main {
        padding: 16px;
        max-width: 1000px;
        margin: 0 auto;
      }
    `,
  ];

  private get activePath(): string {
    const segment = this.route?.path.split("/").filter(Boolean)[0];
    return VIEWS.some((v) => v.path === segment) ? segment! : "dashboard";
  }

  private navigate(ev: Event, path: string): void {
    ev.preventDefault();
    const prefix = this.route?.prefix ?? "/com-system";
    history.pushState(null, "", `${prefix}/${path}`);
    // Home Assistant listens for this to update the panel's route.
    window.dispatchEvent(new CustomEvent("location-changed"));
    this.requestUpdate();
  }

  protected render() {
    const active = this.activePath;
    const prefix = this.route?.prefix ?? "/com-system";
    const tabs = html`
      <nav class=${this.narrow ? "bottom-bar" : ""}>
        ${VIEWS.map(
          (v) => html`<a
            class=${v.path === active ? "active" : ""}
            href="${prefix}/${v.path}"
            @click=${(ev: Event) => this.navigate(ev, v.path)}
            >${v.label}</a
          >`,
        )}
      </nav>
    `;
    return html`
      <div class="toolbar">
        <div class="toolbar-content">
          <ha-menu-button
            .hass=${this.hass}
            .narrow=${this.narrow}
          ></ha-menu-button>
          ${this.narrow ? html`<h1>Com System</h1>` : nothing}
          ${tabs}
        </div>
      </div>
      <main>
        ${active === "receivers"
          ? html`<com-system-receivers .hass=${this.hass}></com-system-receivers>`
          : active === "test"
            ? html`<com-system-test .hass=${this.hass}></com-system-test>`
            : html`<com-system-dashboard .hass=${this.hass}></com-system-dashboard>`}
      </main>
    `;
  }
}

customElements.define("com-system-panel", ComSystemPanel);
