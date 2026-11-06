// Pure logic for the edge service: feed lookup, cursors, and RSS rendering.
// No Workers APIs here, so it runs under `node --test` as well.

export type Feed = {
  id: string;
  name: string;
  state: string;
  kind: string;
  description: string;
  council_ids: string[];
};

export type Post = {
  url: string;
  uri: string | null; // Bluesky post at-uri; null if never posted to Bluesky
  council_id: string;
  council_name: string;
  state: string;
  title: string;
  excerpt: string | null;
  published_at: string | null; // the council's own date, ISO
  posted_at: string; // when the bot relayed it, ISO
};

export const STATES = ["nsw", "vic", "qld", "wa", "sa", "tas", "nt", "act"] as const;
export const STATE_NAMES: Record<string, string> = {
  nsw: "New South Wales", vic: "Victoria", qld: "Queensland", wa: "Western Australia",
  sa: "South Australia", tas: "Tasmania", nt: "Northern Territory", act: "Australian Capital Territory",
};

// ---- Bluesky feed generator ------------------------------------------------

export function didDocument(hostname: string) {
  return {
    "@context": ["https://www.w3.org/ns/did/v1"],
    id: `did:web:${hostname}`,
    service: [{ id: "#bsky_fg", type: "BskyFeedGenerator", serviceEndpoint: `https://${hostname}` }],
  };
}

export function feedUri(publisherDid: string, feedId: string): string {
  return `at://${publisherDid}/app.bsky.feed.generator/${feedId}`;
}

/** The feed id from an at-uri, if it names a feed of this publisher. */
export function feedIdFromUri(uri: string, publisherDid: string): string | null {
  const m = /^at:\/\/([^/]+)\/app\.bsky\.feed\.generator\/([a-z0-9-]{1,15})$/.exec(uri || "");
  if (!m || m[1] !== publisherDid) return null;
  return m[2];
}

/** Cursor = "<posted_at>::<uri>", opaque to clients, stable under new posts. */
export function encodeCursor(postedAt: string, uri: string): string {
  return `${postedAt}::${uri}`;
}

export function decodeCursor(cursor: string | null): { postedAt: string; uri: string } | null {
  if (!cursor) return null;
  const i = cursor.indexOf("::");
  if (i <= 0) return null;
  const postedAt = cursor.slice(0, i);
  const uri = cursor.slice(i + 2);
  if (!/^\d{4}-\d{2}-\d{2}T/.test(postedAt) || !uri.startsWith("at://")) return null;
  return { postedAt, uri };
}

export function clampLimit(raw: string | null, dflt = 30, max = 100): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return dflt;
  return Math.min(Math.floor(n), max);
}

// ---- RSS -------------------------------------------------------------------

const XML_ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" };

export function xmlEscape(s: string): string {
  // Drop characters XML 1.0 does not allow, then escape the five specials.
  return String(s ?? "")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g, "")
    .replace(/[&<>"']/g, (c) => XML_ESCAPES[c]);
}

/** The date an item is shown under: the council's own date when it is
 *  plausible (not in the future, not long before it was relayed), otherwise
 *  the time the bot relayed it. */
export function itemDate(p: Post, now: Date = new Date()): Date {
  const posted = new Date(p.posted_at);
  if (p.published_at) {
    const pub = new Date(p.published_at);
    const ok = !isNaN(pub.getTime()) && pub.getTime() <= now.getTime()
      && posted.getTime() - pub.getTime() <= 30 * 86400e3;
    if (ok) return pub;
  }
  return posted;
}

export type Channel = { title: string; description: string; link: string; selfUrl: string };

export function renderRss(ch: Channel, posts: Post[], now: Date = new Date()): string {
  const items = posts.map((p) => {
    const d = itemDate(p, now);
    return [
      "    <item>",
      `      <title>${xmlEscape(p.title)}</title>`,
      `      <link>${xmlEscape(p.url)}</link>`,
      `      <guid isPermaLink="true">${xmlEscape(p.url)}</guid>`,
      `      <pubDate>${d.toUTCString()}</pubDate>`,
      `      <dc:creator>${xmlEscape(p.council_name)}</dc:creator>`,
      `      <category>${xmlEscape(p.council_name)}</category>`,
      p.excerpt ? `      <description>${xmlEscape(p.excerpt)}</description>` : "",
      "    </item>",
    ].filter(Boolean).join("\n");
  });
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">',
    "  <channel>",
    `    <title>${xmlEscape(ch.title)}</title>`,
    `    <link>${xmlEscape(ch.link)}</link>`,
    `    <description>${xmlEscape(ch.description)}</description>`,
    "    <language>en-au</language>",
    `    <lastBuildDate>${now.toUTCString()}</lastBuildDate>`,
    "    <ttl>30</ttl>",
    `    <atom:link href="${xmlEscape(ch.selfUrl)}" rel="self" type="application/rss+xml"/>`,
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}

export type OpmlEntry = { title: string; xmlUrl: string; group: string };

export function renderOpml(title: string, entries: OpmlEntry[]): string {
  const groups = new Map<string, OpmlEntry[]>();
  for (const e of entries) groups.set(e.group, [...(groups.get(e.group) || []), e]);
  const body = [...groups].map(([g, es]) => [
    `    <outline text="${xmlEscape(g)}" title="${xmlEscape(g)}">`,
    ...es.map((e) => `      <outline type="rss" text="${xmlEscape(e.title)}" title="${xmlEscape(e.title)}" xmlUrl="${xmlEscape(e.xmlUrl)}"/>`),
    "    </outline>",
  ].join("\n"));
  return ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">',
    `  <head><title>${xmlEscape(title)}</title></head>`, "  <body>", ...body, "  </body>", "</opml>", ""].join("\n");
}

// ---- Ingest validation -----------------------------------------------------

const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

/** A post as sent by the bot, checked field by field. Returns null if unusable. */
export function cleanPost(x: any): Post | null {
  if (!x || typeof x !== "object") return null;
  const s = (v: any, max: number) => (typeof v === "string" ? v.slice(0, max) : null);
  const url = s(x.url, 2000), title = s(x.title, 500), council_id = s(x.council_id, 100);
  const council_name = s(x.council_name, 200), state = s(x.state, 10)?.toLowerCase() ?? null;
  const posted_at = s(x.posted_at, 40);
  if (!url || !/^https?:\/\//.test(url) || !title || !council_id || !council_name || !state || !posted_at) return null;
  if (!(STATES as readonly string[]).includes(state) || !ISO.test(posted_at)) return null;
  const uri = s(x.uri, 300);
  const published_at = s(x.published_at, 40);
  return {
    url, title, council_id, council_name, state, posted_at,
    uri: uri && uri.startsWith("at://") ? uri : null,
    excerpt: s(x.excerpt, 1000),
    published_at: published_at && ISO.test(published_at) ? published_at : null,
  };
}
