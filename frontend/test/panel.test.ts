import { beforeAll, describe, expect, it, vi } from "vitest";
import type { ComSystemPanel } from "../src/com-system-panel";
import type { HomeAssistant } from "../src/types";

const RECEIVER = {
  entry_id: "e1",
  name: "Office",
  type_id: "custom",
  type: "Custom",
  type_known: true,
  enabled: true,
  available: true,
  entity_id: "switch.office_enabled",
  people: [],
  areas: [],
};

function makeHass(): { hass: HomeAssistant; callWS: ReturnType<typeof vi.fn> } {
  const callWS = vi.fn(async (msg: { type: string }) => {
    switch (msg.type) {
      case "com_system/dashboard":
        return {
          total: 1,
          enabled: 1,
          disabled: 0,
          unavailable: 0,
          pending_discoveries: 2,
          by_type: { Custom: 1 },
        };
      case "com_system/receivers/list":
        return { receivers: [RECEIVER] };
      case "com_system/discoveries/list":
        return {
          discoveries: [{ flow_id: "f1", name: "Pixel", type: "Mobile app" }],
        };
      default:
        return null;
    }
  });
  const hass = {
    callWS,
    states: { "switch.office_enabled": { state: "on" } },
  } as unknown as HomeAssistant;
  return { hass, callWS };
}

async function mount(path: string, hass: HomeAssistant) {
  const el = document.createElement("com-system-panel") as ComSystemPanel;
  el.hass = hass;
  el.route = { prefix: "/com-system", path };
  document.body.append(el);
  await el.updateComplete;
  return el;
}

async function settle(el: Element) {
  // Let the view's fetch resolve and re-render.
  await new Promise((r) => setTimeout(r, 0));
  await (el as unknown as { updateComplete: Promise<unknown> }).updateComplete;
}

beforeAll(async () => {
  await import("../src/com-system-panel");
});

describe("panel", () => {
  it("shows the dashboard by default with receiver counts", async () => {
    const { hass } = makeHass();
    const panel = await mount("", hass);
    const view = panel.shadowRoot!.querySelector("com-system-dashboard")!;
    await settle(view);
    expect(view.shadowRoot!.textContent).toContain("Pending discoveries");
    expect(view.shadowRoot!.textContent).toContain("Custom: 1");
  });

  it("marks the active navigation entry", async () => {
    const { hass } = makeHass();
    const panel = await mount("/receivers", hass);
    const active = panel.shadowRoot!.querySelector("nav a.active")!;
    expect(active.textContent).toBe("Receivers");
  });

  it("lists receivers and discoveries and toggles enabled", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("Office");
    expect(text).toContain("Custom");
    expect(text).toContain("Pixel");

    view.shadowRoot!.querySelector("button")!.click();
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/receivers/set_enabled",
      entry_id: "e1",
      enabled: false,
    });
  });

  it("shows an error when a command fails", async () => {
    const { hass, callWS } = makeHass();
    callWS.mockRejectedValue({ code: "unauthorized", message: "Unauthorized" });
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    expect(view.shadowRoot!.querySelector(".error")!.textContent).toBe(
      "Unauthorized",
    );
  });
});
