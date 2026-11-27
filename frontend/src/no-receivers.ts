import { css, html } from "lit";

/** Shown for a notification whose targets matched no receiver. */
export const NO_RECEIVERS = html`<ha-alert
  class="no-receivers"
  alert-type="warning"
  >No receiver matched the targets, so none was notified.</ha-alert
>`;

export const noReceiversStyles = css`
  .no-receivers {
    display: block;
  }
`;
