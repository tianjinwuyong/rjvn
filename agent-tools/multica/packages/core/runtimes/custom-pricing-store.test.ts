import { describe, expect, it, beforeEach } from "vitest";
import {
  getCustomPricing,
  useCustomPricingStore,
  type CustomModelPricing,
} from "./custom-pricing-store";

const rate: CustomModelPricing = {
  input: 1.0,
  output: 2.0,
  cacheRead: 0.1,
  cacheWrite: 0.2,
};

// This is a global (singleton) zustand store, so reset it before every test
// to keep tests isolated and deterministic.
beforeEach(() => {
  useCustomPricingStore.setState({ pricings: {} });
});

describe("useCustomPricingStore / getCustomPricing", () => {
  it("starts with an empty pricings map", () => {
    expect(useCustomPricingStore.getState().pricings).toEqual({});
  });

  it("setCustomPricing adds a model and getCustomPricing reads it back", () => {
    useCustomPricingStore.getState().setCustomPricing("gpt-5.5-mini", rate);
    expect(useCustomPricingStore.getState().pricings["gpt-5.5-mini"]).toEqual(
      rate,
    );
    expect(getCustomPricing("gpt-5.5-mini")).toEqual(rate);
  });

  it("setCustomPricing overwrites an existing model's rates", () => {
    useCustomPricingStore.getState().setCustomPricing("m-1", rate);
    const updated: CustomModelPricing = {
      input: 9.0,
      output: 8.0,
      cacheRead: 0.9,
      cacheWrite: 0.8,
    };
    useCustomPricingStore.getState().setCustomPricing("m-1", updated);
    expect(useCustomPricingStore.getState().pricings["m-1"]).toEqual(updated);
    expect(Object.keys(useCustomPricingStore.getState().pricings)).toEqual([
      "m-1",
    ]);
  });

  it("removeCustomPricing removes an existing model", () => {
    useCustomPricingStore.getState().setCustomPricing("m-1", rate);
    useCustomPricingStore.getState().setCustomPricing("m-2", rate);
    useCustomPricingStore.getState().removeCustomPricing("m-1");
    const state = useCustomPricingStore.getState();
    expect(state.pricings["m-1"]).toBeUndefined();
    expect(state.pricings["m-2"]).toEqual(rate);
  });

  it("removeCustomPricing on an unknown model is a no-op", () => {
    useCustomPricingStore.getState().setCustomPricing("m-1", rate);
    useCustomPricingStore.getState().removeCustomPricing("does-not-exist");
    expect(useCustomPricingStore.getState().pricings).toEqual({ "m-1": rate });
  });

  it("getCustomPricing returns undefined for an unknown model", () => {
    expect(getCustomPricing("no-such-model")).toBeUndefined();
  });

  it("keeps multiple models independent", () => {
    const a: CustomModelPricing = { input: 1, output: 2, cacheRead: 0, cacheWrite: 0 };
    const b: CustomModelPricing = { input: 3, output: 4, cacheRead: 5, cacheWrite: 6 };
    useCustomPricingStore.getState().setCustomPricing("model-a", a);
    useCustomPricingStore.getState().setCustomPricing("model-b", b);
    const state = useCustomPricingStore.getState();
    expect(state.pricings["model-a"]).toEqual(a);
    expect(state.pricings["model-b"]).toEqual(b);
    expect(Object.keys(state.pricings).sort()).toEqual(["model-a", "model-b"]);
  });
});
