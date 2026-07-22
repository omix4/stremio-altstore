export interface SourceVersion {
  version: string
  buildVersion: string
  date: string
  localizedDescription?: string
  downloadURL: string
  size?: number
  sha256?: string
  minOSVersion?: string
  marketingVersion?: string
}

export interface SourceApp {
  name: string
  bundleIdentifier: string
  developerName?: string
  subtitle?: string
  localizedDescription?: string
  iconURL?: string
  tintColor?: string
  versions: SourceVersion[]
}

export interface AltSource {
  name: string
  identifier?: string
  subtitle?: string
  description?: string
  iconURL?: string
  tintColor?: string
  sourceURL: string
  apps: SourceApp[]
}

export interface FeedDefinition {
  id: "ios" | "tvos"
  label: string
  shortLabel: string
  file: string
  minimumLabel: string
}

export const FEEDS: FeedDefinition[] = [
  {
    id: "ios",
    label: "iOS / iPadOS",
    shortLabel: "iOS",
    file: "stremio-ios.json",
    minimumLabel: "iOS",
  },
  {
    id: "tvos",
    label: "Apple TV",
    shortLabel: "tvOS",
    file: "stremio-tvos.json",
    minimumLabel: "tvOS",
  },
]

function numericParts(value: string): number[] {
  return value.split(".").map((part) => {
    const parsed = Number.parseInt(part, 10)
    return Number.isFinite(parsed) ? parsed : -1
  })
}

export function compareVersions(a: SourceVersion, b: SourceVersion): number {
  const aParts = numericParts(a.version)
  const bParts = numericParts(b.version)
  const length = Math.max(aParts.length, bParts.length)

  for (let index = 0; index < length; index += 1) {
    const difference = (bParts[index] ?? 0) - (aParts[index] ?? 0)
    if (difference !== 0) return difference
  }

  return Number.parseInt(b.buildVersion || "0", 10) - Number.parseInt(a.buildVersion || "0", 10)
}

export function sortedVersions(app: SourceApp): SourceVersion[] {
  return [...app.versions].sort(compareVersions)
}

export function latestVersion(source: AltSource): SourceVersion | undefined {
  return source.apps.flatMap((app) => app.versions).sort(compareVersions)[0]
}

export function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "Unknown size"
  const megabytes = bytes / (1024 * 1024)
  return `${megabytes.toFixed(megabytes >= 100 ? 0 : 1)} MB`
}

export function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date)
}

export function validateSource(value: unknown): AltSource {
  if (!value || typeof value !== "object") throw new Error("The source is not an object.")
  const source = value as Partial<AltSource>
  if (!source.name || !source.sourceURL || !Array.isArray(source.apps)) {
    throw new Error("The source is missing required fields.")
  }
  return source as AltSource
}
