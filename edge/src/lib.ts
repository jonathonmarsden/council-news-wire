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

// ---- Readable feed page (for people who open a feed in a browser) ----------

/** Shared look for the edge's HTML pages, matching lgnews.jonathonmarsden.com. */
export const PAGE_CSS = `:root{--bg:#f7f4ef;--surface:#fff;--border:#e5ded3;--text:#141414;--text-2:#4a4a4a;--text-3:#7a766f;--accent:#c0711f;--h:Georgia,'Times New Roman',serif}
@media(prefers-color-scheme:dark){:root{--bg:#0e0d0b;--surface:#1a1814;--border:#302c25;--text:#eeece8;--text-2:#a8a59f;--text-3:#8a867f;--accent:#e8902f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 ui-sans-serif,-apple-system,'Segoe UI',system-ui,sans-serif}
a{color:var(--accent)}main{max-width:46rem;margin:0 auto;padding:1.5rem 1rem 3rem}
.top{font-family:var(--h);font-weight:700;color:var(--accent);text-decoration:none}
h1{font-family:var(--h);font-size:1.7rem;line-height:1.2;margin:1rem 0 .3rem}.lead{color:var(--text-2);margin:0 0 1.25rem}
.box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1.75rem}
.box h2{font-family:var(--h);font-size:1.05rem;margin:0 0 .35rem}.box p{margin:.2rem 0 .8rem;color:var(--text-2);font-size:.92rem}
.row{display:flex;gap:.5rem;flex-wrap:wrap}.row input{flex:1 1 16rem;min-width:0;font:inherit;font-size:.85rem;padding:.45rem .55rem;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
.btn{display:inline-block;font:inherit;font-size:.88rem;font-weight:600;padding:.45rem .8rem;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:#fff;text-decoration:none;cursor:pointer}
.btn.alt{background:transparent;color:var(--accent)}.apps{margin-top:.7rem}
.ways{padding-left:1.1rem;margin:.9rem 0 0;font-size:.92rem;color:var(--text-2)}.ways li{margin:.55rem 0}.ways b{color:var(--text)}.ways .apps{margin-top:.5rem}
details{margin-top:.8rem;font-size:.9rem;color:var(--text-2)}summary{cursor:pointer;color:var(--text)}details li{margin:.35rem 0}
ol{list-style:none;padding:0;margin:0}ol li{padding:.85rem 0;border-top:1px solid var(--border)}
.t{font-family:var(--h);font-size:1.05rem;font-weight:700;text-decoration:none;color:var(--text)}.t:hover{color:var(--accent)}
.m{font-size:.8rem;color:var(--text-3);margin-top:.15rem}ol p{margin:.35rem 0 0;font-size:.92rem;color:var(--text-2)}
footer{margin-top:2rem;font-size:.85rem;color:var(--text-3)}

.st{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1rem}
.st h2{font-family:var(--h);font-size:1.15rem;margin:0 0 .6rem}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:0;padding:0;list-style:none}
.chips a{display:inline-block;font-size:.85rem;padding:.28rem .7rem;border-radius:999px;border:1px solid var(--border);color:var(--text);text-decoration:none;background:var(--bg)}
.chips a:hover{border-color:var(--accent);color:var(--accent)}.chips a.all{border-color:var(--accent);color:var(--accent);font-weight:600}
.st details{margin-top:.75rem}.cl{columns:2 14rem;font-size:.88rem;padding-left:1.1rem;margin:.5rem 0 0}.cl a{color:var(--text)}
`;

/** True when a person is opening the address in a browser tab. Browsers mark
 *  page navigations with Sec-Fetch-Dest: document; feed readers fetch from
 *  their own servers and never send it, so they keep getting RSS. ?view=html
 *  and ?view=rss force either. */
export function wantsFeedPage(headers: { get(name: string): string | null }, view: string | null): boolean {
  if (view === "html") return true;
  if (view === "rss") return false;
  return headers.get("sec-fetch-dest") === "document" && headers.get("sec-fetch-mode") === "navigate";
}

// Microsoft's Power Automate template that emails each new item of an RSS
// feed to the signed-in Microsoft 365 user.
const PA_RSS_EMAIL = "https://make.powerautomate.com/templates/details/abd158fa332542ea89f822a590a75a9c";

export function renderFeedPage(ch: Channel, posts: Post[], site: string, now: Date = new Date()): string {
  const enc = encodeURIComponent(ch.selfUrl);
  const fmt = (d: Date) => d.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "Australia/Sydney" });
  const items = posts.map((p) => `
      <li><a class="t" href="${xmlEscape(p.url)}">${xmlEscape(p.title)}</a>
        <div class="m">${xmlEscape(p.council_name)} · ${fmt(itemDate(p, now))}</div>
        ${p.excerpt ? `<p>${xmlEscape(p.excerpt.length > 220 ? p.excerpt.slice(0, 217).trimEnd() + "…" : p.excerpt)}</p>` : ""}</li>`).join("");
  return `<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${xmlEscape(ch.title)} · RSS feed</title>
<meta name="description" content="${xmlEscape(ch.description)}">
<link rel="alternate" type="application/rss+xml" title="${xmlEscape(ch.title)}" href="${xmlEscape(ch.selfUrl)}">
<style>${PAGE_CSS}</style></head><body><main>
<a class="top" href="${xmlEscape(site)}">Local Government News</a>
<h1>${xmlEscape(ch.title)}</h1>
<p class="lead">${xmlEscape(ch.description)}</p>
<section class="box" aria-labelledby="sub">
  <h2 id="sub">Get these stories automatically</h2>
  <p>Copy the feed address, then pick the place you already read. New stories arrive as councils publish them. No account with us, no tracking.</p>
  <div class="row"><input id="u" value="${xmlEscape(ch.selfUrl)}" readonly aria-label="Feed address" onclick="this.select()">
    <button class="btn" id="c" type="button">Copy address</button></div>
  <ul class="ways">
    <li><b>Email at work (Microsoft 365):</b> open Microsoft's <a href="${PA_RSS_EMAIL}">RSS feed to send e-mail</a> template, sign in with your work account and paste the address. Each new story lands in your Outlook inbox. Some organisations need IT to allow Power Automate first.</li>
    <li><b>A Teams channel:</b> in the channel, open Workflows, choose “Post to a channel when an RSS feed is updated” and paste the address.</li>
    <li><b>Email anywhere (Gmail, iCloud, Outlook.com and others):</b> <a href="https://feedrabbit.com/subscriptions/new?url=${enc}">Feedrabbit</a> emails you each new story and has a free plan. It is a separate service with its own terms.</li>
    <li><b>A feed reader:</b> on iPhone or Mac, NetNewsWire is free; on the web, use the buttons below.
      <div class="row apps"><a class="btn alt" href="https://feedly.com/i/subscription/feed%2F${enc}">Add to Feedly</a>
      <a class="btn alt" href="https://www.inoreader.com/?add_feed=${enc}">Add to Inoreader</a></div></li>
  </ul>
  <details><summary>More ways to follow</summary><ul>
    <li><b>Slack:</b> type <code>/feed subscribe</code> followed by the address in the channel.</li>
    <li><b>Outlook (classic, Windows):</b> right-click RSS Subscriptions, choose Add a New RSS Feed, and paste the address. The new Outlook does not read feeds; use the email option above instead.</li>
    <li><b>Media monitoring tools:</b> most accept an RSS address as a source.</li>
    <li><b>Any other feed reader</b> (Reeder, Feeder, Thunderbird and others): add a new feed and paste the address.</li>
  </ul></details>
</section>
<h2 style="font-family:var(--h);font-size:1.15rem">Latest stories</h2>
<ol>${items || "<li>No stories in the last few months.</li>"}</ol>
<footer><a href="/rss/">All RSS feeds</a> · <a href="${xmlEscape(site)}">Back to the news site</a></footer>
</main>
<script>document.getElementById("c").onclick=function(){var b=this,i=document.getElementById("u");(navigator.clipboard?navigator.clipboard.writeText(i.value):Promise.reject()).then(function(){b.textContent="Copied"},function(){i.select();document.execCommand("copy");b.textContent="Copied"})}</script>
</body></html>
`;
}
