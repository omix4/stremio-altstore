import { ChevronDown, Copy, ExternalLink } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { INSTALLERS } from "@/lib/installers"

async function copyText(value: string, message: string) {
  try {
    await navigator.clipboard.writeText(value)
    toast.success(message)
  } catch {
    toast.error("Could not copy the link. Press and hold the download button instead.")
  }
}

interface InstallerMenuProps {
  url: string
}

export function InstallerMenu({ url }: InstallerMenuProps) {
  const openFlareStore = () => {
    window.open("https://flarestore.app/signer/", "_blank", "noopener,noreferrer")
    void copyText(url, "IPA link copied. Paste it into FlareStore's File URL field.")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          Install with
          <ChevronDown className="size-3.5" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {INSTALLERS.map((installer) => (
          <DropdownMenuItem key={installer.id} asChild>
            <a href={installer.installLink(url)}>
              {installer.name}
              <ExternalLink className="ml-auto size-3.5 text-muted-foreground" aria-hidden="true" />
            </a>
          </DropdownMenuItem>
        ))}
        <DropdownMenuItem onSelect={openFlareStore}>
          FlareStore
          <Copy className="ml-auto size-3.5 text-muted-foreground" aria-hidden="true" />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void copyText(url, "IPA link copied.")}>
          Copy IPA link
          <Copy className="ml-auto size-3.5 text-muted-foreground" aria-hidden="true" />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { copyText }
