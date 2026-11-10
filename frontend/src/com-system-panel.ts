import { LitElement, css, html } from "lit";
import "./dashboard-view";
import "./receivers-view";
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
] as const;

/** The admin-only Com System panel: navigation and the active view. */
export class ComSystemPanel extends LitElement {
  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare route: PanelRoute;
  declare panel: unknown;

  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
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
      header {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 12px 16px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, #fff);
      }
      h1 {
        margin: 0;
        font-size: 1.25rem;
        font-weight: 400;
      }
      nav a {
        color: inherit;
        text-decoration: none;
        padding: 8px 12px;
        border-bottom: 2px solid transparent;
      }
      nav a.active {
        border-bottom-color: currentColor;
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
    return html`
      <header>
        <h1>Com System</h1>
        <nav>
          ${VIEWS.map(
            (v) => html`<a
              class=${v.path === active ? "active" : ""}
              href="${prefix}/${v.path}"
              @click=${(ev: Event) => this.navigate(ev, v.path)}
              >${v.label}</a
            >`,
          )}
        </nav>
      </header>
      <main>
        ${active === "receivers"
          ? html`<com-system-receivers .hass=${this.hass}></com-system-receivers>`
          : html`<com-system-dashboard .hass=${this.hass}></com-system-dashboard>`}
      </main>
    `;
  }
}

customElements.define("com-system-panel", ComSystemPanel);
