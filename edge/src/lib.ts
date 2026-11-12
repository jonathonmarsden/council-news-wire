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

/** The edge cache key for a request: the path plus only the parameters that
 *  change the answer. Anything else in the query string is dropped, so adding
 *  made-up parameters cannot skip the cache and force a database read. */
export function cacheKey(url: URL, page: boolean): string {
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const keep = new URLSearchParams();
  if (path === "/xrpc/app.bsky.feed.getFeedSkeleton") {
    const feed = url.searchParams.get("feed");
    const cursor = url.searchParams.get("cursor");
    if (feed) keep.set("feed", feed);
    if (cursor) keep.set("cursor", cursor);
    keep.set("limit", String(clampLimit(url.searchParams.get("limit"))));
  }
  if (page) keep.set("__page", "1");
  const q = keep.toString();
  return `${url.origin}${path}${q ? `?${q}` : ""}`;
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

/** Shared look for the edge's HTML pages, matching councilnewswire.au. */
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
[hidden]{display:none!important}
.keep{font-size:.88rem;color:var(--text-2);margin:-.5rem 0 1.1rem}.keep .btn{margin-left:.3rem;padding:.2rem .6rem;font-size:.8rem}
details.box{margin-top:0;font-size:1rem;color:inherit}details.box>summary{list-style:none;cursor:pointer}details.box>summary::-webkit-details-marker{display:none}
details.box>summary h2{display:inline;margin:0}details.box>summary::after{content:"Show";float:right;font-size:.8rem;color:var(--accent);font-weight:600}details.box[open]>summary::after{content:"Hide"}
details.box[open]>summary{margin-bottom:.35rem}
.latest{font-family:var(--h);font-size:1.15rem;margin:0 0 .6rem}.since{font-size:.85rem;color:var(--text-3);margin:-.3rem 0 .7rem}
.cards{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.85rem}
.card{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--sc,var(--accent));border-radius:6px;padding:.9rem 1.15rem .75rem;box-shadow:0 1px 4px rgba(0,0,0,.05)}
.ch{display:flex;flex-wrap:wrap;align-items:baseline;gap:.4em;font-size:.78rem;color:var(--text-3);line-height:1.3}
.cn{font-family:var(--h);font-weight:700;font-size:.9rem;color:var(--text)}
.new{display:none;margin-left:.2rem;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#fff;background:var(--accent);border-radius:999px;padding:.05rem .5rem}.is-new .new{display:inline-block}
.hl{display:block;margin-top:.5rem;font-family:var(--h);font-size:1.15rem;font-weight:700;line-height:1.3;color:var(--sc,var(--accent));text-decoration:none;text-wrap:balance}.hl:hover{text-decoration:underline}
.ex{margin:.45rem 0 0;font-family:var(--h);font-size:.95rem;line-height:1.55;color:var(--text-2)}
.cf{margin-top:.65rem;padding-top:.55rem;border-top:1px solid var(--border);display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;font-size:.76rem}.cf a{color:var(--text-3);text-decoration:none}.cf a:hover{color:var(--accent)}
@media(prefers-color-scheme:dark){.hl{color:color-mix(in srgb,var(--sc,var(--accent)) 45%,#fff)}}
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

// Each state's colour on councilnewswire.au, used for the card edge.
export const STATE_COLORS: Record<string, string> = {
  nsw: "#2a6b98", vic: "#2a4a6f", qld: "#8a1d30", sa: "#b33829",
  wa: "#b07520", tas: "#24663a", nt: "#b05828", act: "#2a5f92",
};

/** The bsky.app address of a post, from its at:// uri. */
export function bskyWebUrl(uri: string | null): string | null {
  const m = uri ? /^at:\/\/(did:[a-z]+:[A-Za-z0-9._:-]+)\/app\.bsky\.feed\.post\/([A-Za-z0-9]+)$/.exec(uri) : null;
  return m ? `https://bsky.app/profile/${m[1]}/post/${m[2]}` : null;
}

/** Name for a home-screen icon: "Greater Sydney council news" -> "Greater Sydney",
 *  "Wollongong City Council news" -> "Wollongong City Council". Case matters:
 *  group feeds say "council news", council names end in "Council". */
export function shortName(title: string): string {
  return title.replace(/ council news$/, "").replace(/ news$/, "").trim() || title;
}

/** Web app manifest, so a feed page can be added to a phone's home screen
 *  and open straight to that feed. */
export function renderManifest(ch: Channel): string {
  const path = new URL(ch.selfUrl).pathname;
  return JSON.stringify({
    id: path,
    name: ch.title,
    short_name: shortName(ch.title),
    description: ch.description,
    start_url: `${path}?view=html`,
    scope: path,
    display: "standalone",
    background_color: "#f7f4ef",
    theme_color: "#df842b",
    icons: [
      { src: "/rss/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/rss/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/rss/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  });
}

// In-page script: relative times, "New since your last visit" (remembered only
// in this browser), the sign-up box folded away for returning visitors, and an
// Install button where the browser offers one. Every storage call is guarded:
// private windows and blocked storage just skip the extras.
const FEED_PAGE_JS = `(function(){
var d=document,k="lgn-seen:"+location.pathname,last=null,top="";
try{last=localStorage.getItem(k)}catch(e){}
var cards=d.querySelectorAll(".card"),n=0;
cards.forEach(function(c){var a=c.getAttribute("data-at");if(a>top)top=a;
  if(last&&a>last){c.classList.add("is-new");n++}
  var t=c.querySelector("time"),s=(Date.now()-Date.parse(t.getAttribute("datetime")))/1000;
  if(s>=0&&s<604800){t.title=t.textContent;t.textContent=s<3600?Math.max(1,Math.round(s/60))+" min ago":s<86400?Math.round(s/3600)+" h ago":Math.round(s/86400)+" d ago"}});
if(last){var b=d.getElementById("subbox");if(b)b.open=false;
  var w=d.getElementById("since");if(w){w.textContent=n?n+(n==1?" new story":" new stories")+" since your last visit":"Nothing new since your last visit";w.hidden=false}}
try{if(top)localStorage.setItem(k,top)}catch(e){}
var ev,ib=d.getElementById("install");
addEventListener("beforeinstallprompt",function(e){e.preventDefault();ev=e;ib.hidden=false});
ib.onclick=function(){if(ev){ev.prompt();ev=null;ib.hidden=true}};
d.getElementById("c").onclick=function(){var b=this,i=d.getElementById("u");(navigator.clipboard?navigator.clipboard.writeText(i.value):Promise.reject()).then(function(){b.textContent="Copied"},function(){i.select();d.execCommand("copy");b.textContent="Copied"})};
})()`;

export function renderFeedPage(ch: Channel, posts: Post[], site: string, now: Date = new Date()): string {
  const enc = encodeURIComponent(ch.selfUrl);
  const fmt = (d: Date) => d.toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "Australia/Sydney" });
  const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return "council site"; } };
  const cards = posts.map((p) => {
    const d = itemDate(p, now);
    const bsky = bskyWebUrl(p.uri);
    const ex = p.excerpt ? (p.excerpt.length > 260 ? p.excerpt.slice(0, 257).trimEnd() + "…" : p.excerpt) : "";
    return `
      <li class="card" style="--sc:${STATE_COLORS[p.state] ?? "var(--accent)"}" data-at="${xmlEscape(p.posted_at)}">
        <div class="ch"><span class="cn">${xmlEscape(p.council_name)}</span><span class="dot">·</span><time datetime="${d.toISOString()}">${fmt(d)}</time><span class="new">New</span></div>
        <a class="hl" href="${xmlEscape(p.url)}">${xmlEscape(p.title)}</a>
        ${ex ? `<p class="ex">${xmlEscape(ex)}</p>` : ""}
        <div class="cf"><a href="${xmlEscape(p.url)}">Read on ${xmlEscape(host(p.url))}</a>${bsky ? `<a href="${bsky}">View on Bluesky</a>` : ""}</div>
      </li>`;
  }).join("");
  const manifest = `${ch.selfUrl}?view=manifest`;
  return `<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${xmlEscape(ch.title)} · Council News Wire</title>
<meta name="description" content="${xmlEscape(ch.description)}">
<link rel="alternate" type="application/rss+xml" title="${xmlEscape(ch.title)}" href="${xmlEscape(ch.selfUrl)}">
<link rel="manifest" href="${xmlEscape(manifest)}">
<link rel="icon" href="/rss/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/rss/icon-180.png">
<meta name="apple-mobile-web-app-title" content="${xmlEscape(shortName(ch.title))}">
<meta name="theme-color" content="#df842b">
<style>${PAGE_CSS}</style></head><body><main>
<a class="top" href="${xmlEscape(site)}">Council News Wire</a>
<h1>${xmlEscape(ch.title)}</h1>
<p class="lead">${xmlEscape(ch.description)}</p>
<p class="keep">Check back any time: bookmark this page, or add it to your phone's home screen (on iPhone tap Share, then Add to Home Screen; on Android open the ⋮ menu). <button class="btn alt" id="install" type="button" hidden>Install</button></p>
<details class="box" id="subbox" open>
  <summary><h2 id="sub">Get these stories sent to you</h2></summary>
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
</details>
<h2 class="latest">Latest stories</h2>
<p class="since" id="since" hidden></p>
<ol class="cards">${cards || "<li>No stories in the last few months.</li>"}</ol>
<footer><a href="/rss/">All RSS feeds</a> · <a href="${xmlEscape(site)}">Back to the news site</a></footer>
</main>
<script>${FEED_PAGE_JS}</script>
</body></html>
`;
}

// ---- Usage counts ----------------------------------------------------------
// One anonymous data point per feed or RSS request, so we can tell which feeds
// people read. No IP address, account or user agent string is stored: only a
// coarse client class and a keyed hash that cannot be reversed.

const READERS: [RegExp, string][] = [
  [/feedly/i, "feedly"], [/inoreader/i, "inoreader"], [/netnewswire/i, "netnewswire"],
  [/feedbin/i, "feedbin"], [/newsblur/i, "newsblur"], [/old ?reader/i, "theoldreader"],
  [/miniflux/i, "miniflux"], [/freshrss/i, "freshrss"], [/tiny tiny rss|tt-rss/i, "ttrss"],
  [/reeder/i, "reeder"], [/feeder/i, "feeder"], [/feedspot/i, "feedspot"], [/blogtrottr/i, "blogtrottr"],
  [/zapier/i, "zapier"], [/ifttt/i, "ifttt"], [/slack/i, "slack"], [/microsoft|teams|outlook|power ?automate/i, "microsoft"],
  [/thunderbird/i, "thunderbird"], [/feedburner|feedfetcher|feed-fetcher|rss reader|podcast/i, "reader-other"],
];
const BOT = /bot\b|bot\/|crawl|spider|externalhit|meta-|elevenlabs|shapbot|indexer|scrap|python|curl|wget|go-http|node-fetch|axios|okhttp|java\/|httpclient|headless|nginx/i;
const INDEXER = /protoverse|skyfeed/i;

export type Client = { client: string; subscribers: number };

/** A coarse, privacy-safe class for whoever made the request. */
export function classifyClient(ua: string | null): Client {
  const u = (ua || "").trim();
  const subs = /(\d+)\s+subscribers?/i.exec(u);
  const subscribers = subs ? Math.min(Number(subs[1]), 1_000_000) : 0;
  if (!u) return { client: "blank", subscribers };
  if (/^lgnews-/i.test(u)) return { client: "test", subscribers };
  if (/bskyappview/i.test(u)) return { client: "bsky-appview", subscribers };
  if (INDEXER.test(u)) return { client: "indexer", subscribers };
  for (const [re, name] of READERS) if (re.test(u)) return { client: `reader:${name}`, subscribers };
  if (BOT.test(u)) return { client: "bot", subscribers };
  if (/^mozilla\//i.test(u)) return { client: "browser", subscribers };
  return { client: "other", subscribers };
}

/** The Bluesky account asking for a feed, from the service token Bluesky sends
 *  when a signed-in person opens it. Unverified: good enough for counting, never
 *  used for anything else. */
export function viewerDid(authorization: string | null): string | null {
  const m = /^Bearer\s+[\w-]+\.([\w-]+)\.[\w-]*$/.exec(authorization || "");
  if (!m) return null;
  try {
    const b64 = m[1].replace(/-/g, "+").replace(/_/g, "/");
    const iss = JSON.parse(atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4)))?.iss;
    return typeof iss === "string" && /^did:[a-z]+:[\w.:%-]{1,200}(#.*)?$/.test(iss) ? iss.split("#")[0] : null;
  } catch { return null; }
}

/** Keyed hash, truncated: equal inputs give equal ids, but the input cannot be
 *  recovered without the key. */
export async function hashId(key: string, text: string): Promise<string> {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(text)));
  return Array.from(sig.slice(0, 8), (b) => b.toString(16).padStart(2, "0")).join("");
}


/** Where an old-host request should go once the public site has moved, or null.
 *
 * FEED_HOST keeps serving what machines depend on: the Bluesky feed service
 * (did.json and /xrpc), the bot's /ingest and /edge. Everything people read
 * (the site and RSS) moves to PUBLIC_HOST, path and query intact. Only GET and
 * HEAD are redirected: a redirected POST would silently lose its body. */
export function legacyRedirect(url: URL, method: string, feedHost: string, publicHost: string): string | null {
  if (!publicHost || publicHost === feedHost || url.hostname !== feedHost) return null;
  if (method !== "GET" && method !== "HEAD") return null;
  const p = url.pathname;
  if (p === "/.well-known/did.json" || p.startsWith("/xrpc/") || p === "/ingest" || p.startsWith("/edge/")) return null;
  return `https://${publicHost}${p}${url.search}`;
}
