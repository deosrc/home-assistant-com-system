import { describe, expect, it, vi } from "vitest";
import { ComSystemApi, errorMessage } from "../src/api";
import type { HomeAssistant } from "../src/types";

function fakeHass(result: unknown) {
  const callWS = vi.fn().mockResolvedValue(result);
  return { hass: { callWS, states: {} } as unknown as HomeAssistant, callWS };
}

describe("ComSystemApi", () => {
  it("pings", async () => {
    const { hass, callWS } = fakeHass({ pong: true });
    expect(await new ComSystemApi(hass).ping()).toEqual({ pong: true });
    expect(callWS).toHaveBeenCalledWith({ type: "com_system/ping" });
  });

  it("unwraps the receivers list", async () => {
    const { hass, callWS } = fakeHass({ receivers: [{ name: "Office" }] });
    expect(await new ComSystemApi(hass).receivers()).toEqual([
      { name: "Office" },
    ]);
    expect(callWS).toHaveBeenCalledWith({ type: "com_system/receivers/list" });
  });

  it("unwraps the discoveries list", async () => {
    const { hass } = fakeHass({ discoveries: [{ name: "Pixel" }] });
    expect(await new ComSystemApi(hass).discoveries()).toEqual([
      { name: "Pixel" },
    ]);
  });

  it("sets enabled", async () => {
    const { hass, callWS } = fakeHass(null);
    await new ComSystemApi(hass).setEnabled("abc", false);
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/receivers/set_enabled",
      entry_id: "abc",
      enabled: false,
    });
  });

  it("previews and sends tests with only the chosen targets", async () => {
    const { hass, callWS } = fakeHass({ receivers: [] });
    await new ComSystemApi(hass).previewNotify({
      receivers: { active_choice: "Select", Select: { area_id: ["kitchen"] } },
    });
    expect(callWS).toHaveBeenCalledWith({
      type: "com_system/notify/preview",
      receivers: { active_choice: "Select", Select: { area_id: ["kitchen"] } },
    });
    await new ComSystemApi(hass).sendTest("Hi", "", {});
    expect(callWS).toHaveBeenLastCalledWith({
      type: "com_system/notify/test",
      message: "Hi",
    });
  });

  it("formats errors", () => {
    expect(errorMessage({ code: "x", message: "Nope" })).toBe("Nope");
    expect(errorMessage("plain")).toBe("plain");
  });
});
