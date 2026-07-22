import { useCallback, useEffect, useState } from "react"
import { AlertCircle, Github, RefreshCw } from "lucide-react"
import { Toaster } from "sonner"

import { AppCard } from "@/components/app-card"
import { SourceCard } from "@/components/source-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { type AltSource, FEEDS, type FeedDefinition, validateSource } from "@/lib/source"

interface FeedState {
  loading: boolean
  source?: AltSource
  error?: string
}

type FeedStates = Record<FeedDefinition["id"], FeedState>

const initialState: FeedStates = {
  ios: { loading: true },
  tvos: { loading: true },
}

async function fetchFeed(definition: FeedDefinition): Promise<AltSource> {
  const response = await fetch(`./${definition.file}`, { cache: "no-store" })
  if (!response.ok) throw new Error(`Request failed with status ${response.status}.`)
  return validateSource(await response.json())
}

function FeedError({ definition, onRetry }: { definition: FeedDefinition; onRetry: () => void }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <AlertCircle className="size-5" aria-hidden="true" />
        </div>
        <div className="flex-1">
          <p className="font-medium">Could not load the {definition.label} source</p>
          <p className="mt-1 text-sm text-muted-foreground">You can retry or open the JSON file directly.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Retry
          </Button>
          <Button variant="outline" size="sm" asChild>
            <a href={`./${definition.file}`}>Open JSON</a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function LoadingCard() {
  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <Skeleton className="size-10" />
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-4 w-52" />
        <Skeleton className="h-10 w-full" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-8" />
          <Skeleton className="h-8" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function App() {
  const [feeds, setFeeds] = useState<FeedStates>(initialState)

  const loadFeed = useCallback(async (definition: FeedDefinition) => {
    setFeeds((current) => ({ ...current, [definition.id]: { loading: true } }))
    try {
      const source = await fetchFeed(definition)
      setFeeds((current) => ({ ...current, [definition.id]: { loading: false, source } }))
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error"
      setFeeds((current) => ({ ...current, [definition.id]: { loading: false, error: message } }))
    }
  }, [])

  useEffect(() => {
    FEEDS.forEach((definition) => void loadFeed(definition))
  }, [loadFeed])

  return (
    <div className="min-h-screen">
      <header className="border-b bg-card/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-3 py-3 sm:gap-4 sm:px-6 sm:py-4 lg:px-8">
          <a href="./" className="flex items-center gap-3" aria-label="Stremio IPA Repository home">
            <img src="./assets/stremio-icon.png" alt="" className="size-9 rounded-lg" />
            <div>
              <p className="text-sm font-semibold leading-tight">Stremio IPA Repository</p>
              <p className="text-xs text-muted-foreground">iOS, iPadOS & tvOS</p>
            </div>
          </a>
          <Button variant="ghost" size="sm" asChild>
            <a href="https://github.com/omix4/stremio-altstore" target="_blank" rel="noreferrer">
              <Github className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">View on GitHub</span>
            </a>
          </Button>
        </div>
      </header>

      <main className="mx-auto min-w-0 max-w-6xl px-3 py-7 sm:px-6 sm:py-14 lg:px-8">
        <section className="max-w-3xl" aria-labelledby="page-title">
          <Badge variant="outline" className="mb-3 sm:mb-4">Unofficial community source</Badge>
          <h1 id="page-title" className="text-2xl font-semibold tracking-tight sm:text-4xl">
            Install Stremio on your Apple devices
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Add a repository to your preferred sideloading app, or download any available IPA directly.
            Release information is loaded live from the source files in this repository.
          </p>
        </section>

        <section className="mt-8 sm:mt-10" aria-labelledby="sources-title">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <h2 id="sources-title" className="text-xl font-semibold tracking-tight">Add a source</h2>
              <p className="mt-1 text-sm text-muted-foreground">Choose the source that matches your device.</p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {FEEDS.map((definition) => {
              const state = feeds[definition.id]
              if (state.loading) return <LoadingCard key={definition.id} />
              if (state.source) return <SourceCard key={definition.id} definition={definition} source={state.source} />
              return <FeedError key={definition.id} definition={definition} onRetry={() => void loadFeed(definition)} />
            })}
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            AltStore links are for AltStore Classic. AltStore PAL uses Apple&apos;s marketplace format and cannot install these plain IPAs.
          </p>
        </section>

        <Separator className="my-8 sm:my-10" />

        <section aria-labelledby="downloads-title">
          <div className="mb-5">
            <h2 id="downloads-title" className="text-xl font-semibold tracking-tight">Apps and downloads</h2>
            <p className="mt-1 text-sm text-muted-foreground">The latest release is shown first. Expand the history for every older IPA.</p>
          </div>
          <Tabs defaultValue="ios">
            <TabsList className="grid w-full grid-cols-2 sm:w-auto">
              {FEEDS.map((definition) => (
                <TabsTrigger key={definition.id} value={definition.id}>{definition.label}</TabsTrigger>
              ))}
            </TabsList>
            {FEEDS.map((definition) => {
              const state = feeds[definition.id]
              return (
                <TabsContent key={definition.id} value={definition.id}>
                  {state.loading ? (
                    <div className="space-y-4">
                      <LoadingCard />
                      <LoadingCard />
                    </div>
                  ) : state.source ? (
                    <div className="space-y-4">
                      {state.source.apps.map((app) => (
                        <AppCard key={app.bundleIdentifier} app={app} definition={definition} />
                      ))}
                    </div>
                  ) : (
                    <FeedError definition={definition} onRetry={() => void loadFeed(definition)} />
                  )}
                </TabsContent>
              )
            })}
          </Tabs>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-3 py-6 text-xs text-muted-foreground sm:px-6 sm:py-8 lg:px-8">
          <p>This is an unofficial community mirror and is not affiliated with or supported by Stremio.</p>
          <p>IPAs are downloaded from Stremio&apos;s public CDN and must be signed before installation.</p>
        </div>
      </footer>
      <Toaster
        position="bottom-center"
        toastOptions={{
          style: {
            background: "var(--popover)",
            color: "var(--popover-foreground)",
            borderColor: "var(--border)",
          },
        }}
      />
    </div>
  )
}
