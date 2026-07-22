import { describe, expect, it } from "vitest"

import { INSTALLERS } from "@/lib/installers"

const url = "https://repo.example/source file.json?channel=stable"

describe("installer links", () => {
  it("uses encoded query parameters for AltStore and SideStore", () => {
    expect(INSTALLERS[0].sourceLink(url)).toBe(
      "altstore://source?url=https%3A%2F%2Frepo.example%2Fsource%20file.json%3Fchannel%3Dstable",
    )
    expect(INSTALLERS[1].installLink(url)).toContain("sidestore://install?url=https%3A%2F%2F")
  })

  it("uses Feather's path-based handlers", () => {
    expect(INSTALLERS[2].sourceLink(url)).toBe(
      "feather://source/https%3A%2F%2Frepo.example%2Fsource%20file.json%3Fchannel%3Dstable",
    )
    expect(INSTALLERS[2].installLink(url)).toContain("feather://install/https%3A%2F%2F")
  })
})
