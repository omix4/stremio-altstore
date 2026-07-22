import { describe, expect, it } from "vitest"

import { formatBytes, latestVersion, sortedVersions, validateSource, type AltSource } from "@/lib/source"

const source: AltSource = {
  name: "Test",
  sourceURL: "https://example.com/source.json",
  apps: [
    {
      name: "App",
      bundleIdentifier: "example.app",
      versions: [
        { version: "2.0.1", buildVersion: "15", date: "2026-01-01", downloadURL: "https://example.com/15.ipa" },
        { version: "2.0.1", buildVersion: "16", date: "2026-01-02", downloadURL: "https://example.com/16.ipa" },
        { version: "2.0.0", buildVersion: "20", date: "2025-12-31", downloadURL: "https://example.com/20.ipa" },
      ],
    },
  ],
}

describe("source helpers", () => {
  it("sorts semantic versions and builds newest first", () => {
    expect(sortedVersions(source.apps[0]).map((version) => version.buildVersion)).toEqual(["16", "15", "20"])
    expect(latestVersion(source)?.buildVersion).toBe("16")
  })

  it("formats byte sizes without overstating precision", () => {
    expect(formatBytes(76_237_174)).toBe("72.7 MB")
    expect(formatBytes()).toBe("Unknown size")
  })

  it("rejects malformed source roots", () => {
    expect(() => validateSource({ apps: [] })).toThrow("missing required fields")
    expect(validateSource(source)).toBe(source)
  })
})
