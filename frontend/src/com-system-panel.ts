import {
  mdiBellRing,
  mdiBullhorn,
  mdiHistory,
  mdiSend,
  mdiViewDashboard,
} from "@mdi/js";
import { LitElement, css, html, nothing } from "lit";
import "./channels-view";
import "./dashboard-view";
import "./history-view";
import "./receivers-view";
import "./test-view";
import { sharedStyles } from "./styles";
import type { HomeAssistant, PanelRoute } from "./types";

// In development Home Assistant imports this module straight from the Vite
// dev server, so the HMR client has to be loaded explicitly, from the dev
// server's origin. Vite removes this block from production builds.
if (import.meta.env.MODE === "development") {
  void import(
    /* @vite-ignore */ new URL("/@vite/client", import.meta.url).href
  );
}

const VIEWS = [
  { path: "dashboard", label: "Dashboard", icon: mdiViewDashboard },
  { path: "receivers", label: "Receivers", icon: mdiBellRing },
  { path: "channels", label: "Channels", icon: mdiBullhorn },
  { path: "history", label: "Recent", icon: mdiHistory },
  { path: "test", label: "Test", icon: mdiSend },
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
      /* Copies the toolbar and tab bar of Home Assistant's own pages
         (hass-tabs-subpage): same structure, ids and classes. */
      :host([narrow]) {
        padding-bottom: calc(
          var(--header-height, 56px) + var(--safe-area-inset-bottom, 0px)
        );
      }
      .toolbar {
        box-sizing: border-box;
        height: calc(
          var(--header-height, 56px) + var(--safe-area-inset-top, 0px)
        );
        padding-top: var(--safe-area-inset-top);
        padding-right: var(--safe-area-inset-right);
        font-size: var(--ha-font-size-xl, 20px);
        font-weight: var(--ha-font-weight-normal, 400);
        background-color: var(--sidebar-background-color);
        border-bottom: 1px solid var(--divider-color);
      }
      :host([narrow]) .toolbar {
        padding-left: var(--safe-area-inset-left);
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
        display: flex;
        flex-shrink: 0;
        color: var(--sidebar-icon-color);
        margin-inline-end: 24px;
        margin-inline-start: initial;
      }
      .main-title {
        min-width: 0;
        flex: 1;
        max-height: var(--header-height);
        line-height: var(--ha-line-height-normal, 1.5);
        color: var(--sidebar-text-color);
        margin-inline-start: var(--main-title-margin, var(--ha-space-6, 24px));
      }
      .narrow .main-title {
        margin-inline-start: var(--main-title-margin, var(--ha-space-2, 8px));
      }
      .main-title h1 {
        margin: 0;
        font: inherit;
      }
      #tabbar a {
        color: var(--sidebar-text-color);
        text-decoration: none;
      }
      .bottom-bar a {
        width: 25%;
      }
      #tabbar {
        display: flex;
        font-size: var(--ha-font-size-m, 14px);
        overflow: hidden;
      }
      #tabbar > a {
        overflow: hidden;
        max-width: 45%;
      }
      #tabbar > a:focus-visible {
        background-color: rgba(127, 127, 127, 0.08);
      }
      #tabbar.bottom-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        padding: 0 calc(16px + var(--safe-area-inset-right, 0px))
          var(--safe-area-inset-bottom, 0px)
          calc(16px + var(--safe-area-inset-left, 0px));
        box-sizing: border-box;
        background-color: var(--sidebar-background-color);
        border-top: 1px solid var(--divider-color);
        justify-content: space-around;
        z-index: 2;
        font-size: var(--ha-font-size-s, 12px);
        width: 100%;
      }
      #tabbar:not(.bottom-bar) {
        flex: 1;
        justify-content: center;
      }
      /* Fallback when Home Assistant has not loaded ha-tab yet. */
      ha-tab:not(:defined) {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: var(--header-height, 56px);
        padding: 0 4px;
      }
      ha-tab:not(:defined)[active] {
        color: var(--primary-color);
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
    const links = VIEWS.map(
      (v) =>
        html`<a
          href="${prefix}/${v.path}"
          aria-current=${v.path === active ? "page" : nothing}
          @click=${(ev: Event) => this.navigate(ev, v.path)}
          ><ha-tab
            .active=${v.path === active}
            .narrow=${this.narrow}
            .name=${v.label}
            ><ha-svg-icon slot="icon" .path=${v.icon}></ha-svg-icon
            ><span class="fallback-name">${v.label}</span></ha-tab
          ></a
        >`,
    );
    const tabs = this.narrow
      ? html`<nav id="tabbar" class="bottom-bar" aria-label="Com System">
          ${links}
        </nav>`
      : html`<div id="tabbar">${links}</div>`;
    const view =
      active === "receivers"
        ? html`<com-system-receivers .hass=${this.hass}></com-system-receivers>`
        : active === "channels"
          ? html`<com-system-channels .hass=${this.hass}></com-system-channels>`
          : active === "history"
            ? html`<com-system-history .hass=${this.hass}></com-system-history>`
            : active === "test"
              ? html`<com-system-test .hass=${this.hass}></com-system-test>`
              : html`<com-system-dashboard
                  .hass=${this.hass}
                ></com-system-dashboard>`;
    return html`
      <div class=${this.narrow ? "toolbar narrow" : "toolbar"}>
        <div class="toolbar-content">
          <ha-menu-button
            .hass=${this.hass}
            .narrow=${this.narrow}
          ></ha-menu-button>
          ${
            this.narrow
              ? html`<div class="main-title"><h1>Com System</h1></div>`
              : nothing
          }
          ${this.narrow ? nothing : tabs}
        </div>
        ${this.narrow ? tabs : nothing}
      </div>
      <main>${view}</main>
    `;
  }
}

customElements.define("com-system-panel", ComSystemPanel);
