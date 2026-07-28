import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const docs = join(root, "docs");
const output = join(docs, "data", "search-index.json");

const pages = [
  ["index.html", "Home"],
  ["getting-started.html", "Start"],
  ["install.html", "Start"],
  ["video.html", "Playback"],
  ["audio.html", "Playback"],
  ["pictures.html", "Playback"],
  ["subtitles.html", "Playback"],
  ["devices.html", "Devices"],
  ["usb.html", "Devices"],
  ["mx4sio.html", "Devices"],
  ["hdd.html", "Devices"],
  ["ilink.html", "Devices"],
  ["mmce.html", "Devices"],
  ["smb.html", "Devices"],
  ["cd-dvd.html", "Devices"],
  ["settings.html", "Setup"],
  ["network.html", "Setup"],
  ["themes.html", "Setup"],
  ["converter.html", "Setup"],
  ["troubleshooting.html", "Reference"],
  ["building.html", "Reference"],
  ["releases.html", "Reference"],
  ["credits.html", "Reference"],
];

const namedEntities = {
  amp: "&",
  apos: "'",
  gt: ">",
  hellip: "…",
  le: "≤",
  lt: "<",
  mdash: "—",
  nbsp: " ",
  ndash: "–",
  quot: '"',
  times: "×",
};

function decodeEntities(value) {
  return value.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (entity, code) => {
    if (code[0] === "#") {
      const radix = code[1]?.toLowerCase() === "x" ? 16 : 10;
      const digits = radix === 16 ? code.slice(2) : code.slice(1);
      return String.fromCodePoint(Number.parseInt(digits, radix));
    }
    return namedEntities[code.toLowerCase()] ?? entity;
  });
}

function textContent(html) {
  return decodeEntities(
    html
      .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
      .replace(/<[^>]+>/g, " ")
  )
    .replace(/\s+/g, " ")
    .trim();
}

function slug(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "sec";
}

const index = [];

for (const [file, category] of pages) {
  const html = await readFile(join(docs, file), "utf8");
  const main = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/i)?.[1];
  if (!main) throw new Error(`${file}: missing <main>`);

  const title = textContent(main.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/i)?.[1] ?? "");
  const meta = html.match(/<meta\s+name=["']description["']\s+content=(["'])([\s\S]*?)\1/i);
  const description = decodeEntities(meta?.[2] ?? "");
  if (!title || !description) throw new Error(`${file}: missing h1 or meta description`);

  index.push({ title, cat: category, url: file, text: description });

  const headings = [...main.matchAll(/<h([23])\b([^>]*)>([\s\S]*?)<\/h\1>/gi)];
  const used = new Set();

  for (let i = 0; i < headings.length; i += 1) {
    const heading = headings[i];
    const headingTitle = textContent(heading[3]);
    if (!headingTitle) continue;

    const explicitId = heading[2].match(/\bid=["']([^"']+)["']/i)?.[1];
    let id = explicitId;
    if (!id) {
      id = slug(headingTitle);
      while (used.has(id)) id += "-x";
    }
    used.add(id);

    const start = (heading.index ?? 0) + heading[0].length;
    const end = headings[i + 1]?.index ?? main.length;
    const sectionText = textContent(main.slice(start, end)).slice(0, 700);
    index.push({
      title: headingTitle,
      cat: category,
      url: `${file}#${id}`,
      text: sectionText || description,
    });
  }
}

await writeFile(output, `${JSON.stringify(index)}\n`, "utf8");
console.log(`Wrote ${index.length} entries to ${output}`);
