import { CheckCircle2, Copy, ExternalLink, Smartphone, Tv } from "lucide-react"

import { copyText } from "@/components/installer-menu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { INSTALLERS } from "@/lib/installers"
import { type AltSource, type FeedDefinition, formatDate, latestVersion } from "@/lib/source"

interface SourceCardProps {
  definition: FeedDefinition
  source: AltSource
}

export function SourceCard({ definition, source }: SourceCardProps) {
  const latest = latestVersion(source)
  const releaseCount = source.apps.reduce((total, app) => total + app.versions.length, 0)
  const PlatformIcon = definition.id === "ios" ? Smartphone : Tv

  const useFlareStore = () => {
    window.open("https://flarestore.app/guide/ios/", "_blank", "noopener,noreferrer")
    void copyText(source.sourceURL, "Source URL copied. Add it in FlareStore's Repositories tab.")
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="pb-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg border bg-muted/60">
            <PlatformIcon className="size-5 text-primary" aria-hidden="true" />
          </div>
          <Badge variant="secondary">
            <CheckCircle2 className="mr-1 size-3" aria-hidden="true" />
            Live source
          </Badge>
        </div>
        <CardTitle className="text-lg">{definition.label}</CardTitle>
        <CardDescription>
          {source.apps.length} apps · {releaseCount} IPAs
          {latest ? ` · Updated ${formatDate(latest.date)}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="flex items-center gap-2 rounded-md border bg-muted/30 p-2.5">
          <code className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{source.sourceURL}</code>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 shrink-0"
            onClick={() => void copyText(source.sourceURL, `${definition.shortLabel} source URL copied.`)}
            aria-label={`Copy ${definition.label} source URL`}
          >
            <Copy className="size-3.5" aria-hidden="true" />
          </Button>
        </div>

        <div className="mt-auto grid grid-cols-2 gap-2">
          {INSTALLERS.map((installer) => (
            <Button key={installer.id} variant="outline" size="sm" asChild>
              <a href={installer.sourceLink(source.sourceURL)}>
                {installer.name}
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            </Button>
          ))}
          <Button variant="outline" size="sm" onClick={useFlareStore}>
            FlareStore
            <Copy className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
