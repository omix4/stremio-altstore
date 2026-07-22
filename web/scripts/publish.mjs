import { copyFile, mkdir } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const repositoryRoot = path.resolve(webRoot, "..")

const outputs = ["index.html", "assets/site.css", "assets/site.js"]

for (const output of outputs) {
  const destination = path.join(repositoryRoot, output)
  await mkdir(path.dirname(destination), { recursive: true })
  await copyFile(path.join(webRoot, "dist", output), destination)
}

console.log("Published GitHub Pages assets to the repository root.")
