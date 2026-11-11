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
  entity_id: "switch.office_notifications_enabled",
  receiver_entity_id: "notification_receiver.office",
  device_id: "dev1",
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
      case "com_system/scripts/check":
        return {
          entity_id: "script.speaker",
          checks: [
            { id: "exists", ok: true, message: "The script exists." },
            { id: "fields", ok: true, message: "It has one object field." },
          ],
          can_rescan: true,
        };
      case "com_system/scripts/rescan":
        return {};
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
              reasons: [
                { kind: "area", id: "office" },
                { kind: "receiver", id: "e1" },
              ],
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
      case "com_system/history/list":
        return {
          notifications: [
            {
              id: "h1",
              time: "2026-11-11T10:00:00+00:00",
              notification: { title: "Laundry", message: "Done" },
              results: [
                {
                  entry_id: "e1",
                  name: "Office",
                  type: "Custom",
                  result: "failed",
                  reason: "Boom",
                  warnings: ["dropped"],
                  reasons: [
                    { kind: "person", id: "person.alice" },
                    { kind: "area", id: "office" },
                    { kind: "receiver", id: "e1" },
                  ],
                },
              ],
            },
          ],
        };
      default:
        return null;
    }
  });
  const hass = {
    callWS,
    states: {
      "switch.office_notifications_enabled": { state: "on" },
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

  it("shows recent notifications with results and warnings", async () => {
    const { hass } = makeHass();
    const panel = await mount("/history", hass);
    const view = panel.shadowRoot!.querySelector("com-system-history")!;
    await settle(view);
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("Laundry");
    expect(text).toContain("Done");
    expect(text).toContain("Office");
    expect(text).toContain("failed");
    expect(text).toContain("Boom");
    const why = [...view.shadowRoot!.querySelectorAll("td .badge")];
    expect(why.map((b) => b.textContent!.trim())).toEqual([
      "Office",
      "Alice",
      "Named",
    ]);
    const badges = [...view.shadowRoot!.querySelectorAll("summary .count")];
    expect(badges.map((b) => b.textContent!.trim())).toEqual(["1 failed"]);
    expect(text).toContain("dropped");
  });

  it("lists receivers and discoveries and toggles enabled", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("Office");
    expect(text).toContain("Custom");
    // Discoveries are an alert with a link, not a list.
    expect(text).not.toContain("Pixel");
    const alert = view.shadowRoot!.querySelector("#discoveries")!;
    expect(alert.textContent).toContain("1 receiver is waiting");
    expect(alert.querySelector("a")!.getAttribute("href")).toBe(
      "/config/integrations/integration/com_system",
    );
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

  it("opens the device page when a row is clicked", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    expect(view.shadowRoot!.querySelector(".edit")).toBeNull();
    expect(view.shadowRoot!.querySelector(".remove")).toBeNull();

    // Using the switch does not open the page.
    const listener = vi.fn();
    window.addEventListener("location-changed", listener);
    (view.shadowRoot!.querySelector("td.switch") as HTMLElement).click();
    expect(listener).not.toHaveBeenCalled();

    (view.shadowRoot!.querySelector("tr.link") as HTMLElement).click();
    expect(location.pathname).toBe("/config/devices/device/dev1");
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("location-changed", listener);
    expect(callWS).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "com_system/receivers/remove" }),
    );
  });

  it("checks a script and offers a rescan", async () => {
    const { hass, callWS } = makeHass();
    hass.states["script.speaker"] = {
      state: "off",
      attributes: { friendly_name: "Speaker" },
    };
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    const select = view.shadowRoot!.querySelector(
      "#script",
    ) as HTMLSelectElement;
    select.value = "script.speaker";
    select.dispatchEvent(new Event("change"));
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/scripts/check",
      entity_id: "script.speaker",
    });
    expect(view.shadowRoot!.querySelectorAll(".checks li.ok").length).toBe(2);
    (view.shadowRoot!.querySelector("#rescan") as HTMLButtonElement).click();
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({ type: "com_system/scripts/rescan" });
    expect(view.shadowRoot!.querySelector("#script-message")).not.toBeNull();
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
    expect(panel.shadowRoot!.querySelector("h1")!.textContent).toBe(
      "Com System",
    );
  });
});

describe("testing tool", () => {
  beforeAll(async () => {
    const { ComSystemTest } = await import("../src/test-view");
    ComSystemTest.controlTimeoutMs = 0;
  });

  it("says so when Home Assistant's action form is not available", async () => {
    // jsdom has no Home Assistant frontend; this runs before the stub below.
    const { hass } = makeHass();
    const panel = await mount("/test", hass);
    const view = panel.shadowRoot!.querySelector("com-system-test")!;
    await settle(view);
    expect(view.shadowRoot!.querySelector(".error")!.textContent).toContain(
      "action form is not available",
    );
  });

  it("follows the action form: defaults, preview and send", async () => {
    // Defined for the rest of the file.
    customElements.define("ha-service-control", class extends HTMLElement {});
    const { hass, callWS } = makeHass();
    const panel = await mount("/test", hass);
    const view = panel.shadowRoot!.querySelector("com-system-test")!;
    await settle(view);
    const root = view.shadowRoot!;
    const control = root.querySelector("ha-service-control")!;
    expect(control.hasAttribute("hide-picker")).toBe(true);
    const valueOf = () =>
      (control as unknown as { value: { action: string; data?: object } })
        .value;
    const change = async (data: object) => {
      control.dispatchEvent(
        new CustomEvent("value-changed", {
          detail: { value: { action: "notify.com_system", data } },
        }),
      );
      await settle(view);
    };

    // The page starts from the action alone, so the form applies the
    // defaults from the action's description; the page has none of its own.
    expect(valueOf()).toEqual({ action: "notify.com_system" });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
    });
    const everyone = { active_choice: "Everyone", Everyone: true };
    const allAreas = { active_choice: "All Areas", "All Areas": true };
    callWS.mockClear();
    await change({ people: everyone, receivers: allAreas });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      people: everyone,
      receivers: allAreas,
    });
    const rows = [...root.querySelectorAll(".preview tbody tr")];
    expect(rows.map((r) => r.textContent!.replace(/\s+/g, " ").trim())).toEqual(
      [
        "Office Custom OfficeNamed reached",
        "Den Custom None skipped (Receiver is disabled)",
      ],
    );

    const send = () => root.querySelector<HTMLButtonElement>(".send")!;
    expect(send().disabled).toBe(true); // no message yet

    // Other keys of the target selector are kept, empty ones dropped.
    const selected = {
      active_choice: "Select",
      Select: { area_id: ["office"], device_id: ["d1"] },
    };
    callWS.mockClear();
    await change({
      message: "Hello",
      title: "Hi",
      people: {
        active_choice: "Individuals",
        Individuals: ["person.alice"],
        Everyone: true,
      },
      receivers: {
        active_choice: "Select",
        Select: { area_id: ["office"], device_id: ["d1"], entity_id: [] },
        "All Areas": true,
      },
    });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      people: ["person.alice"],
      receivers: selected,
    });
    expect(send().disabled).toBe(false);

    send().click();
    await settle(view);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/test",
      message: "Hello",
      title: "Hi",
      people: ["person.alice"],
      receivers: selected,
    });
    await settle(view);
    const result = root.querySelector(".results")!.textContent!;
    expect(result).toContain("failed");
    expect(result).toContain("Not implemented");
    expect(result).toContain("Warning: dropped");
    expect(root.textContent!.replace(/\s+/g, " ")).toContain(
      "0 delivered, 1 failed, 0 skipped",
    );

    // Unticking people in the form removes the field: not targeted.
    callWS.mockClear();
    await change({ message: "Hello", receivers: allAreas });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      receivers: allAreas,
    });
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
    root.querySelector("ha-service-control")!.dispatchEvent(
      new CustomEvent("value-changed", {
        detail: {
          value: {
            action: "notify.com_system",
            data: {
              message: "Hello",
              people: { active_choice: "Everyone", Everyone: true },
            },
          },
        },
      }),
    );
    await settle(view);
    root.querySelector<HTMLButtonElement>(".send")!.click();
    await settle(view);
    expect(root.querySelector(".error")!.textContent).toContain(
      "No receiver matches the targets",
    );
  });
});
