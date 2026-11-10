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
  receiver_entity_id: "notification_receiver.office",
  people: ["person.zed", "person.alice"],
  areas: ["unknown_area", "office"],
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
      case "com_system/notify/preview":
        return {
          receivers: [
            {
              entry_id: "e1",
              name: "Office",
              type: "Custom",
              outcome: "reached",
              reason: null,
            },
            {
              entry_id: "e2",
              name: "Den",
              type: "Custom",
              outcome: "skipped",
              reason: "Receiver is disabled",
            },
          ],
        };
      case "com_system/notify/test":
        return {
          results: [
            {
              entry_id: "e1",
              name: "Office",
              type: "Custom",
              result: "failed",
              reason: "Not implemented",
              warnings: ["dropped"],
            },
          ],
          counts: { delivered: 0, failed: 1, skipped: 0 },
        };
      default:
        return null;
    }
  });
  const hass = {
    callWS,
    states: {
      "switch.office_enabled": { state: "on" },
      "person.alice": { state: "home", attributes: { friendly_name: "Alice" } },
      "person.zed": { state: "home", attributes: { friendly_name: "Zed" } },
    },
    areas: { office: { name: "Office" } },
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

  it("loads when there are no switch entities", async () => {
    const { hass } = makeHass();
    hass.states = {};
    const panel = await mount("", hass);
    const view = panel.shadowRoot!.querySelector("com-system-dashboard")!;
    await settle(view);
    expect(view.shadowRoot!.textContent).not.toContain("Loading");
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
    // Areas first, then people, each sorted by name (the API order is not
    // the name order); unknown ids fall back to the id.
    const badges = [...view.shadowRoot!.querySelectorAll(".badge")];
    expect(badges.map((b) => b.textContent!.trim())).toEqual([
      "Office",
      "unknown_area",
      "Alice",
      "Zed",
    ]);
    expect(
      badges.map((b) => b.querySelector("ha-icon")!.getAttribute("icon")),
    ).toEqual([
      "mdi:texture-box",
      "mdi:texture-box",
      "mdi:account",
      "mdi:account",
    ]);

    const control = view.shadowRoot!.querySelector(
      "ha-switch",
    ) as HTMLElement & { checked: boolean };
    expect(control.checked).toBe(true);
    control.checked = false;
    control.dispatchEvent(new Event("change"));
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

describe("receivers switch", () => {
  it("is off and disabled for an unavailable receiver", async () => {
    const { hass, callWS } = makeHass();
    const base = callWS.getMockImplementation()!;
    callWS.mockImplementation(async (msg: { type: string }) =>
      msg.type === "com_system/receivers/list"
        ? { receivers: [{ ...RECEIVER, available: false, enabled: null }] }
        : base(msg),
    );
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    const control = view.shadowRoot!.querySelector("ha-switch")!;
    expect(control.hasAttribute("disabled")).toBe(true);
    expect(view.shadowRoot!.querySelector("tr.unavailable")).not.toBeNull();
  });
});

describe("panel layout", () => {
  it("puts the tabs in a bottom bar when narrow", async () => {
    const { hass } = makeHass();
    const panel = await mount("", hass);
    expect(panel.shadowRoot!.querySelector("nav.bottom-bar")).toBeNull();
    // Wide screens have the tabs in the toolbar instead of a title.
    expect(panel.shadowRoot!.querySelector("h1")).toBeNull();
    panel.narrow = true;
    await panel.updateComplete;
    expect(panel.hasAttribute("narrow")).toBe(true);
    expect(panel.shadowRoot!.querySelector("nav.bottom-bar")).not.toBeNull();
    expect(panel.shadowRoot!.querySelector("h1")!.textContent).toBe("Com System");
  });
});

describe("testing tool", () => {
  // jsdom has no Home Assistant frontend, so the fallback form is used.
  beforeAll(async () => {
    const { ComSystemTest } = await import("../src/test-view");
    ComSystemTest.controlTimeoutMs = 0;
  });

  it("previews receivers and sends a test through the action", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/test", hass);
    const view = panel.shadowRoot!.querySelector("com-system-test")!;
    await settle(view);
    const root = view.shadowRoot!;
    // The default preview has no targets.
    expect(callWS).toHaveBeenCalledWith({ type: "com_system/notify/preview" });
    const rows = [...root.querySelectorAll(".preview tbody tr")];
    expect(rows.map((r) => r.textContent!.replace(/\s+/g, " ").trim())).toEqual([
      "Office Custom reached",
      "Den Custom skipped (Receiver is disabled)",
    ]);

    const send = root.querySelector<HTMLButtonElement>("button.send")!;
    expect(send.disabled).toBe(true); // no message yet
    const message = root.querySelector("textarea")!;
    message.value = "Hello";
    message.dispatchEvent(new Event("input"));
    await settle(view);
    expect(send.disabled).toBe(false);

    // Choosing a person re-runs the preview with that target.
    const person = [...root.querySelectorAll<HTMLInputElement>("input[type=checkbox]")]
      .find((c) => c.parentElement!.textContent!.includes("Alice"))!;
    person.checked = true;
    person.dispatchEvent(new Event("change"));
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      person: ["person.alice"],
    });

    send.click();
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/test",
      message: "Hello",
      person: ["person.alice"],
    });
    await settle(view);
    const result = root.querySelector(".results")!.textContent!;
    expect(result).toContain("failed");
    expect(result).toContain("Not implemented");
    expect(result).toContain("Warning: dropped");
    expect(root.textContent!.replace(/\s+/g, " ")).toContain(
      "0 delivered, 1 failed, 0 skipped",
    );
  });

  it("shows an error when the send is rejected", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/test", hass);
    const view = panel.shadowRoot!.querySelector("com-system-test")!;
    await settle(view);
    const impl = callWS.getMockImplementation()!;
    callWS.mockImplementation(async (msg: { type: string }) => {
      if (msg.type === "com_system/notify/test") {
        throw { message: "No receiver matches the targets" };
      }
      return impl(msg);
    });
    const root = view.shadowRoot!;
    const message = root.querySelector("textarea")!;
    message.value = "Hello";
    message.dispatchEvent(new Event("input"));
    await settle(view);
    root.querySelector<HTMLButtonElement>("button.send")!.click();
    await settle(view);
    expect(root.querySelector(".error")!.textContent).toContain(
      "No receiver matches the targets",
    );
  });
});

describe("testing tool with the Home Assistant Actions form", () => {
  it("drives the preview and send from the form's value", async () => {
    // Defined for the rest of the file; the other tests run before this one.
    customElements.define("ha-service-control", class extends HTMLElement {});
    {
      const { hass, callWS } = makeHass();
      const panel = await mount("/test", hass);
      const view = panel.shadowRoot!.querySelector("com-system-test")!;
      await settle(view);
      const root = view.shadowRoot!;
      const control = root.querySelector("ha-service-control")!;
      expect(control).not.toBeNull();
      expect(control.hasAttribute("hide-picker")).toBe(true);
      // The built-in form is not shown.
      expect(root.querySelector("textarea")).toBeNull();

      callWS.mockClear();
      control.dispatchEvent(
        new CustomEvent("value-changed", {
          detail: {
            value: {
              action: "notify.com_system",
              data: {
                message: "Hello",
                title: "Hi",
                person: "person.alice",
                area_id: ["office"],
                entity_id: [],
              },
            },
          },
        }),
      );
      await settle(view);
      expect(callWS).toHaveBeenCalledWith({
        type: "com_system/notify/preview",
        person: ["person.alice"],
        area_id: ["office"],
      });
      // The form is given back the same selection.
      expect((control as unknown as { value: unknown }).value).toEqual({
        action: "notify.com_system",
        data: {
          message: "Hello",
          title: "Hi",
          person: ["person.alice"],
          area_id: ["office"],
        },
      });

      root.querySelector<HTMLButtonElement>("button.send")!.click();
      await settle(view);
      expect(callWS).toHaveBeenCalledWith({
        type: "com_system/notify/test",
        message: "Hello",
        title: "Hi",
        person: ["person.alice"],
        area_id: ["office"],
      });
    }
  });
});
