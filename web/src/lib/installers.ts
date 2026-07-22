export type InstallerId = "altstore" | "sidestore" | "feather"

export interface Installer {
  id: InstallerId
  name: string
  sourceLink: (url: string) => string
  installLink: (url: string) => string
}

const queryLink = (scheme: string, action: string, url: string) =>
  `${scheme}://${action}?url=${encodeURIComponent(url)}`

const pathLink = (scheme: string, action: string, url: string) =>
  `${scheme}://${action}/${encodeURIComponent(url)}`

export const INSTALLERS: Installer[] = [
  {
    id: "altstore",
    name: "AltStore Classic",
    sourceLink: (url) => queryLink("altstore", "source", url),
    installLink: (url) => queryLink("altstore", "install", url),
  },
  {
    id: "sidestore",
    name: "SideStore",
    sourceLink: (url) => queryLink("sidestore", "source", url),
    installLink: (url) => queryLink("sidestore", "install", url),
  },
  {
    id: "feather",
    name: "Feather",
    sourceLink: (url) => pathLink("feather", "source", url),
    installLink: (url) => pathLink("feather", "install", url),
  },
]
