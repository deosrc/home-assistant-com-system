import { css, html } from "lit";
import type { HomeAssistant, MatchReason } from "./types";

/** Badge styles, the same look as the targets on the Receivers page. */
export const reasonStyles = css`
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
`;

const ORDER = { all_areas: 0, area: 1, everyone: 2, person: 3, receiver: 4 };

/**
 * Why a receiver was included, as badges: "All Areas" or "Everyone" when
 * those choices matched it, otherwise the area and person it is linked to
 * that matched, and "Named" when it was selected explicitly. A receiver
 * can have all three.
 */
export function renderReasons(
  hass: HomeAssistant,
  reasons: MatchReason[] | undefined,
) {
  if (!reasons?.length) {
    return html`<span class="muted">None</span>`;
  }
  const badges = reasons
    .map((r) => {
      const id = r.id ?? "";
      switch (r.kind) {
        case "all_areas":
          return {
            order: ORDER.all_areas,
            icon: "mdi:texture-box",
            name: "All Areas",
          };
        case "everyone":
          return {
            order: ORDER.everyone,
            icon: "mdi:account-group",
            name: "Everyone",
          };
        case "area":
          return {
            order: ORDER.area,
            icon: "mdi:texture-box",
            name: hass.areas?.[id]?.name ?? id,
          };
        case "person":
          return {
            order: ORDER.person,
            icon: "mdi:account",
            name: hass.states[id]?.attributes?.friendly_name ?? id,
          };
        default:
          return {
            order: ORDER.receiver,
            icon: "mdi:bell-ring",
            name: "Named",
          };
      }
    })
    .sort(
      (a, b) =>
        a.order - b.order ||
        a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
    );
  return html`<div class="badges">
    ${badges.map(
      (b) =>
        html`<span class="badge"
          ><ha-icon icon=${b.icon}></ha-icon>${b.name}</span
        >`,
    )}
  </div>`;
}
