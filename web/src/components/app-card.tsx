import { Box, History } from "lucide-react"

import { VersionRow } from "@/components/version-row"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { type FeedDefinition, type SourceApp, sortedVersions } from "@/lib/source"

interface AppCardProps {
  app: SourceApp
  definition: FeedDefinition
}

export function AppCard({ app, definition }: AppCardProps) {
  const versions = sortedVersions(app)
  const latest = versions[0]
  const older = versions.slice(1)

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-start gap-4">
          <img
            src={app.iconURL || "./assets/stremio-icon.png"}
            alt=""
            className="size-14 rounded-xl border bg-muted object-cover"
          />
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <CardTitle className="text-xl">{app.name}</CardTitle>
              {app.bundleIdentifier === "com.stremio.ios" ? <Badge variant="secondary">Legacy</Badge> : null}
            </div>
            <CardDescription>{app.subtitle || app.localizedDescription}</CardDescription>
            <div className="mt-2 flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
              <Box className="size-3" aria-hidden="true" />
              <code className="min-w-0 break-all">{app.bundleIdentifier}</code>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {latest ? <VersionRow version={latest} definition={definition} featured /> : <p>No releases listed.</p>}
        {older.length ? (
          <Accordion type="single" collapsible className="mt-4">
            <AccordionItem value="history">
              <AccordionTrigger>
                <span className="flex items-center gap-2">
                  <History className="size-4 text-muted-foreground" aria-hidden="true" />
                  {older.length} older {older.length === 1 ? "release" : "releases"}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="divide-y rounded-lg border px-4">
                  {older.map((version) => (
                    <div key={`${version.version}-${version.buildVersion}`} className="py-4">
                      <VersionRow version={version} definition={definition} />
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : null}
      </CardContent>
    </Card>
  )
}
