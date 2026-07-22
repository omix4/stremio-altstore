import { Download, ShieldCheck } from "lucide-react"

import { InstallerMenu } from "@/components/installer-menu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { type FeedDefinition, formatBytes, formatDate, type SourceVersion } from "@/lib/source"
import { cn } from "@/lib/utils"

interface VersionRowProps {
  version: SourceVersion
  definition: FeedDefinition
  featured?: boolean
}

export function VersionRow({ version, definition, featured = false }: VersionRowProps) {
  return (
    <div className={cn("flex flex-col gap-4", featured && "rounded-lg border bg-muted/20 p-4 sm:p-5")}>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className={cn("font-semibold", featured ? "text-lg" : "text-sm")}>
              Version {version.version}
            </span>
            <Badge variant="outline">Build {version.buildVersion}</Badge>
            {version.sha256 ? (
              <Badge variant="secondary">
                <ShieldCheck className="mr-1 size-3" aria-hidden="true" />
                SHA-256
              </Badge>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {formatDate(version.date)} · {formatBytes(version.size)}
            {version.minOSVersion ? ` · ${definition.minimumLabel} ${version.minOSVersion}+` : ""}
          </p>
          {featured && version.localizedDescription ? (
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{version.localizedDescription}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button size="sm" asChild>
            <a href={version.downloadURL} target="_blank" rel="noreferrer">
              <Download className="size-3.5" aria-hidden="true" />
              Download IPA
            </a>
          </Button>
          <InstallerMenu url={version.downloadURL} />
        </div>
      </div>
      {version.sha256 ? (
        <details className="group text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none font-medium hover:text-foreground">Integrity hash</summary>
          <code className="mt-2 block break-all rounded-md bg-muted px-3 py-2">{version.sha256}</code>
        </details>
      ) : null}
    </div>
  )
}
