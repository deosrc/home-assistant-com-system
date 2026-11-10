import { css } from "lit";

export const sharedStyles = css`
  .card {
    background: var(--card-background-color, #fff);
    border-radius: var(--ha-card-border-radius, 12px);
    border: 1px solid var(--divider-color, #e0e0e0);
    padding: 16px;
  }
  .error {
    color: var(--error-color, #db4437);
  }
  .muted {
    color: var(--secondary-text-color);
  }
  a {
    color: var(--primary-color);
  }
  button {
    font: inherit;
    cursor: pointer;
  }
`;
