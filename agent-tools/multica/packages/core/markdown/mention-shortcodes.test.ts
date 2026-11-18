import { describe, expect, it } from "vitest";
import { preprocessMentionShortcodes } from "./mention-shortcodes";

describe("preprocessMentionShortcodes", () => {
  it("leaves plain text untouched", () => {
    expect(preprocessMentionShortcodes("hello world")).toBe("hello world");
  });

  it("returns an empty string unchanged", () => {
    expect(preprocessMentionShortcodes("")).toBe("");
  });

  it("returns input unchanged when there is no [@  shortcode", () => {
    expect(preprocessMentionShortcodes("just a [@ sign no space")).toBe(
      "just a [@ sign no space",
    );
    expect(preprocessMentionShortcodes("no shortcode here")).toBe(
      "no shortcode here",
    );
  });

  it("converts a complete shortcode to a mention link", () => {
    expect(
      preprocessMentionShortcodes("Hi [@ id=\"u-123\" label=\"Alice\"]"),
    ).toBe("Hi [@Alice](mention://member/u-123)");
  });

  it("converts a shortcode embedded in a sentence", () => {
    expect(
      preprocessMentionShortcodes(
        "Assign to [@ id=\"u-9\" label=\"Bob\"] and [@ id=\"u-3\" label=\"Carol\"]",
      ),
    ).toBe(
      "Assign to [@Bob](mention://member/u-9) and [@Carol](mention://member/u-3)",
    );
  });

  it("leaves a shortcode unchanged when id is missing", () => {
    expect(
      preprocessMentionShortcodes("[@ label=\"NoId\"]"),
    ).toBe("[@ label=\"NoId\"]");
  });

  it("leaves a shortcode unchanged when label is missing", () => {
    expect(
      preprocessMentionShortcodes("[@ id=\"u-1\"]"),
    ).toBe("[@ id=\"u-1\"]");
  });

  it("ignores extra attributes and keeps id + label", () => {
    expect(
      preprocessMentionShortcodes("[@ id=\"u-7\" label=\"Dana\" role=\"member\"]"),
    ).toBe("[@Dana](mention://member/u-7)");
  });

  it("is idempotent: running twice produces the same output", () => {
    const input =
      "See [@ id=\"u-1\" label=\"Alice\"] and [@ id=\"u-2\" label=\"Bob\"]";
    const once = preprocessMentionShortcodes(input);
    expect(preprocessMentionShortcodes(once)).toBe(once);
  });

  it("does not transform [@ without whitespace after the bracket", () => {
    expect(preprocessMentionShortcodes("[@id=\"u-1\" label=\"X\"]")).toBe(
        "[@id=\"u-1\" label=\"X\"]",
      );
  });

  it("preserves surrounding text and spacing", () => {
    expect(
      preprocessMentionShortcodes(
        "prefix [@ id=\"u-5\" label=\"Eve\"] suffix",
      ),
    ).toBe("prefix [@Eve](mention://member/u-5) suffix");
  });
});
