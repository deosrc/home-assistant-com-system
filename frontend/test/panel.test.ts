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
  conditions: 2,
};

function makeHass(): {
  hass: HomeAssistant;
  callWS: ReturnType<typeof vi.fn>;
  callService: ReturnType<typeof vi.fn>;
} {
  const callWS = vi.fn(async (msg: { type: string }) => {
    switch (msg.type) {
      case "com_system/dashboard":
        return {
          total: 3,
          enabled: 2,
          disabled: 1,
          unavailable: 1,
          pending_discoveries: 2,
          history: {
            notifications: 4,
            rate: 0.1,
            rate_unit: "day",
            notification_success_rate: 0.75,
            receiver_success_rate: 1,
            stopped_by_condition_rate: 0.25,
          },
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
              outcome: "targeted",
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
              responses: [
                {
                  time: "2026-11-11T10:05:00+00:00",
                  receiver_id: "e1",
                  receiver: "Office",
                  person: "person.alice",
                  action: "OPEN",
                  reply_text: null,
                },
              ],
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
      case "com_system/channels/list":
        return {
          channels: [
            {
              channel_id: "c1",
              name: "Doors",
              entity_id: "notification_channel.doors",
              defaults: {
                priority: "high",
                image: "/local/d.jpg",
                data: { mobile_app: { tag: "d" } },
              },
            },
          ],
        };
      default:
        return null;
    }
  });
  const callService = vi.fn(async () => undefined);
  const hass = {
    callWS,
    callService,
    states: {
      "switch.office_notifications_enabled": { state: "on" },
      "person.alice": { state: "home", attributes: { friendly_name: "Alice" } },
      "person.zed": { state: "home", attributes: { friendly_name: "Zed" } },
    },
    areas: { office: { name: "Office" } },
  } as unknown as HomeAssistant;
  return { hass, callWS, callService };
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
    expect(view.shadowRoot!.textContent).not.toContain("Pending discoveries");
    expect(
      view.shadowRoot!.querySelector("#discoveries")!.textContent,
    ).toContain("2 receivers are waiting to be added.");
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("2/3");
    expect(text).not.toContain("Unavailable");
    expect(text).toContain("0.1/day");
    expect(text).toContain("75%");
    expect(text).toContain("25%");
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
    const active = panel.shadowRoot!.querySelector(".tabs a.active")!;
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
    // The response is shown on the row of the receiver that sent it.
    const headers = [...view.shadowRoot!.querySelectorAll("th")].map((th) =>
      th.textContent!.trim(),
    );
    expect(headers).toContain("Response");
    const row = view.shadowRoot!.querySelector("tbody tr")!;
    expect(
      row.querySelector(".response")!.textContent!.replace(/\s+/g, " "),
    ).toContain("OPEN by Alice");
    expect(view.shadowRoot!.querySelector(".responses")).toBeNull();
  });

  it("lists receivers and discoveries and toggles enabled", async () => {
    const { hass, callWS } = makeHass();
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("Office");
    expect(text).toContain("Custom");
    expect(
      view.shadowRoot!.querySelector("td.conditions")!.textContent!.trim(),
    ).toBe("2 conditions");
    expect(
      view.shadowRoot!.querySelector("td.conditions a")!.getAttribute("href"),
    ).toBe("/config/integrations/integration/com_system#config_entry=e1");
    // Discoveries are an alert with a link, not a list.
    expect(text).not.toContain("Pixel");
    const alert = view.shadowRoot!.querySelector("#discoveries")!;
    expect(alert.textContent).toContain("1 receiver is waiting");
    expect(alert.querySelector("a")!.getAttribute("href")).toBe(
      "/config/integrations/integration/com_system",
    );
    // Areas first, then people, each sorted by name (the API order is not
    // the name order); unknown ids fall back to the id.
    const badges = [
      ...view.shadowRoot!.querySelectorAll("tbody td:nth-child(5) .badge"),
    ];
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
  async function mountWith(receiver: object) {
    const { hass, callWS } = makeHass();
    const base = callWS.getMockImplementation()!;
    callWS.mockImplementation(async (msg: { type: string }) =>
      msg.type === "com_system/receivers/list"
        ? { receivers: [{ ...RECEIVER, ...receiver }] }
        : base(msg),
    );
    const panel = await mount("/receivers", hass);
    const view = panel.shadowRoot!.querySelector("com-system-receivers")!;
    await settle(view);
    return view;
  }

  it("is disabled when the state cannot be read", async () => {
    const view = await mountWith({ available: false, enabled: null });
    const control = view.shadowRoot!.querySelector("ha-switch")!;
    expect(control.hasAttribute("disabled")).toBe(true);
    expect(view.shadowRoot!.querySelector("tr.unavailable")).not.toBeNull();
  });

  it("can be changed for an unavailable receiver", async () => {
    const view = await mountWith({ available: false, enabled: true });
    const control = view.shadowRoot!.querySelector("ha-switch")!;
    expect(control.hasAttribute("disabled")).toBe(false);
  });

  it("shows Disabled, Unavailable or Available as the status", async () => {
    const status = async (receiver: object) =>
      [
        ...(await mountWith(receiver)).shadowRoot!.querySelectorAll(
          "tbody td:nth-child(3) .badge",
        ),
      ].map((b) => b.textContent!.trim());
    expect(await status({})).toEqual(["Available"]);
    const ok = await mountWith({});
    expect(
      ok.shadowRoot!.querySelector(".badge.success")!.textContent,
    ).toContain("Available");
    expect(await status({ enabled: false })).toEqual(["Disabled"]);
    expect(await status({ available: false })).toEqual(["Unavailable"]);
    expect(await status({ enabled: false, available: false })).toEqual([
      "Disabled",
      "Unavailable",
    ]);
  });
});

describe("panel layout", () => {
  it("puts the tabs in a bottom bar when narrow", async () => {
    const { hass } = makeHass();
    const panel = await mount("", hass);
    expect(panel.hasAttribute("narrow")).toBe(false);
    // Wide screens have the tabs in the toolbar instead of a title.
    expect(panel.shadowRoot!.querySelector("h1")).toBeNull();
    panel.narrow = true;
    await panel.updateComplete;
    expect(panel.hasAttribute("narrow")).toBe(true);
    expect(
      panel.shadowRoot!.querySelectorAll(".tabs .tab ha-icon"),
    ).toHaveLength(5);
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
      notification: {},
    });
    const everyone = { active_choice: "Everyone", Everyone: true };
    const allAreas = { active_choice: "All Areas", "All Areas": true };
    callWS.mockClear();
    await change({ people: everyone, receivers: allAreas });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      people: everyone,
      receivers: allAreas,
      notification: {},
    });
    const rows = [...root.querySelectorAll(".preview tbody tr")];
    expect(rows.map((r) => r.textContent!.replace(/\s+/g, " ").trim())).toEqual(
      [
        "Office Custom OfficeNamed targeted",
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
      priority: "high",
      data: { pushover: { sound: "siren" } },
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
      notification: {
        message: "Hello",
        title: "Hi",
        priority: "high",
        data: { pushover: { sound: "siren" } },
      },
    });
    expect(send().disabled).toBe(false);

    send().click();
    await settle(view);
    // The action's data goes through exactly as the form built it, so a
    // field added to the action needs no change in the panel.
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/test",
      service_data: {
        message: "Hello",
        title: "Hi",
        priority: "high",
        data: { pushover: { sound: "siren" } },
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
      },
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
      notification: { message: "Hello" },
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

describe("channels", () => {
  async function open() {
    if (!customElements.get("ha-service-control")) {
      customElements.define("ha-service-control", class extends HTMLElement {});
    }
    const made = makeHass();
    const panel = await mount("/channels", made.hass);
    const view = panel.shadowRoot!.querySelector("com-system-channels")!;
    await settle(view);
    return { ...made, view };
  }
  const button = (view: Element, cls: string) =>
    view.shadowRoot!.querySelector<HTMLButtonElement>(`button.${cls}`)!;
  const report = async (view: Element, value: object) => {
    view
      .shadowRoot!.querySelector("ha-service-control")!
      .dispatchEvent(new CustomEvent("value-changed", { detail: { value } }));
    await settle(view);
  };

  it("lists the channels with their defaults", async () => {
    const { view } = await open();
    const text = view.shadowRoot!.textContent!;
    expect(text).toContain("Doors");
    expect(text).toContain("notification_channel.doors");
    expect(text).toContain("high");
    // JSON is not shown.
    expect(text).not.toContain("{");
  });

  it("shows each receiver type's data as its own list", async () => {
    const { view } = await open();
    const root = view.shadowRoot!;
    const labels = [...root.querySelectorAll("dl.defaults > dt")].map((e) =>
      e.textContent!.trim(),
    );
    expect(labels).toEqual(["Priority", "Image"]);
    const block = root.querySelector(".data-block")!;
    expect(block.querySelector(".receiver-type")!.textContent!.trim()).toBe(
      "mobile_app",
    );
    expect(block.querySelector("dt")!.textContent!.trim()).toBe("tag");
    expect(block.querySelector("dd")!.textContent!.trim()).toBe("d");
  });

  it("opens the more info dialog for the channel's entity", async () => {
    const { view } = await open();
    const events: CustomEvent[] = [];
    document.body.addEventListener("hass-more-info", (ev) =>
      events.push(ev as CustomEvent),
    );
    button(view, "more-info").click();
    expect(events).toHaveLength(1);
    expect(events[0].detail).toEqual({
      entityId: "notification_channel.doors",
    });
  });

  it("creates a channel through the action form", async () => {
    const { view, callService } = await open();
    button(view, "add").click();
    await settle(view);
    const control = view.shadowRoot!.querySelector("ha-service-control")!;
    expect(
      view.shadowRoot!.querySelector(".form-title")!.textContent,
    ).toContain("Add a channel");
    expect(control.hasAttribute("hide-picker")).toBe(true);
    // Starts from the action alone so Home Assistant applies its defaults.
    expect((control as unknown as { value: object }).value).toEqual({
      action: "com_system.create_channel",
    });
    await report(view, {
      action: "com_system.create_channel",
      data: { name: "Alerts", priority: "low" },
    });
    button(view, "save").click();
    await settle(view);
    expect(callService).toHaveBeenCalledWith("com_system", "create_channel", {
      name: "Alerts",
      priority: "low",
    });
    expect(view.shadowRoot!.querySelector("ha-service-control")).toBeNull();
  });

  it("edits a channel starting from its current values", async () => {
    const { view, callService } = await open();
    button(view, "edit").click();
    await settle(view);
    expect(
      view.shadowRoot!.querySelector(".form-title")!.textContent,
    ).toContain("Edit channel");
    // The channel's own card stays in place beside the form.
    expect(view.shadowRoot!.querySelector("button.edit")).not.toBeNull();
    expect(view.shadowRoot!.textContent).toContain(
      "notification_channel.doors",
    );
    const control = view.shadowRoot!.querySelector("ha-service-control")!;
    expect((control as unknown as { value: object }).value).toEqual({
      action: "com_system.update_channel",
      data: {
        channel: "notification_channel.doors",
        name: "Doors",
        priority: "high",
        image: { active_choice: "URL", URL: "/local/d.jpg" },
        data: { mobile_app: { tag: "d" } },
      },
    });
    await report(view, {
      action: "com_system.update_channel",
      data: { channel: "notification_channel.doors", name: "Gates" },
    });
    button(view, "save").click();
    await settle(view);
    expect(callService).toHaveBeenCalledWith("com_system", "update_channel", {
      channel: "notification_channel.doors",
      name: "Gates",
    });
  });

  it("shows the action's error and keeps the form open", async () => {
    const { view, callService } = await open();
    callService.mockRejectedValueOnce({ message: "already exists" });
    button(view, "add").click();
    await settle(view);
    await report(view, {
      action: "com_system.create_channel",
      data: { name: "Doors" },
    });
    button(view, "save").click();
    await settle(view);
    expect(view.shadowRoot!.querySelector(".error")!.textContent).toContain(
      "already exists",
    );
    expect(view.shadowRoot!.querySelector("ha-service-control")).not.toBeNull();
  });

  it("deletes a channel through the action after confirming", async () => {
    const { view, callService } = await open();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    button(view, "delete").click();
    await settle(view);
    expect(confirm).toHaveBeenCalled();
    expect(callService).toHaveBeenCalledWith("com_system", "delete_channel", {
      channel: "notification_channel.doors",
    });
    confirm.mockRestore();
  });

  it("confirms deletes in Home Assistant's dialog when it is available", async () => {
    // Defined from here on, so keep this test last.
    customElements.define("ha-dialog", class extends HTMLElement {});
    const { view, callService } = await open();
    const confirm = vi.spyOn(window, "confirm");
    button(view, "delete").click();
    await settle(view);
    const root = view.shadowRoot!;
    expect(confirm).not.toHaveBeenCalled();
    expect(root.querySelector("ha-dialog")).not.toBeNull();
    expect(root.querySelector(".confirm-title")!.textContent).toContain(
      "Delete channel",
    );
    expect(root.querySelector("ha-dialog")!.textContent).toContain("Doors");
    expect(callService).not.toHaveBeenCalled();

    // Cancel closes it without deleting.
    root.querySelector<HTMLElement>(".confirm-cancel")!.click();
    await settle(view);
    expect(root.querySelector("ha-dialog")).toBeNull();
    expect(callService).not.toHaveBeenCalled();

    // Confirming deletes.
    button(view, "delete").click();
    await settle(view);
    root.querySelector<HTMLElement>(".confirm-delete")!.click();
    await settle(view);
    expect(callService).toHaveBeenCalledWith("com_system", "delete_channel", {
      channel: "notification_channel.doors",
    });
    expect(root.querySelector("ha-dialog")).toBeNull();
    confirm.mockRestore();
  });
});
