// Cloudflare configuration for the edge service (cf CLI; see README.md).
//
// Two hostnames:
// - FEED_HOST serves the Bluesky feed service (did:web:FEED_HOST, which all 89
//   feed records point at, so it must never change), the bot's /ingest and
//   /edge/health.
// - PUBLIC_HOST is where people read the site and RSS.
// While they are the same, the Worker answers only its own paths and every
// other path still goes to the static site's origin. Once PUBLIC_HOST moves,
// FEED_HOST also gets a catch-all route that redirects the site and RSS there.
import { bindings, defineConfig, triggers } from "cf/config";

const FEED_HOST = "lgnews.jonathonmarsden.com";
const FEED_ZONE = "jonathonmarsden.com";
const PUBLIC_HOST = "councilnewswire.au";
const PUBLIC_ZONE = "councilnewswire.au";
const moved = PUBLIC_HOST !== FEED_HOST;

const on = (host: string, zone: string) => (path: string) => triggers.fetch({ pattern: `${host}${path}`, zone });
const feed = on(FEED_HOST, FEED_ZONE);
const pub = on(PUBLIC_HOST, PUBLIC_ZONE);

export default defineConfig({
  worker: {
    name: "council-news-edge",
    compatibilityDate: "2026-10-01",
    entrypoint: "./src/index.ts",
    env: {
      DB: bindings.d1({ name: "council-news-edge" }),
      FEED_HOST: bindings.text(FEED_HOST),
      PUBLIC_HOST: bindings.text(PUBLIC_HOST),
      // DID of the Bluesky account that publishes the feed records. Set it in
      // the environment when deploying: PUBLISHER_DID=did:plc:... cf deploy
      PUBLISHER_DID: bindings.text(process.env.PUBLISHER_DID ?? ""),
      INGEST_TOKEN: bindings.secret(),
      // Anonymous usage counts per feed (see recordUsage in src/index.ts).
      USAGE: bindings.analyticsEngineDataset({ name: "council_news_edge_usage" }),
    },
    triggers: [
      feed("/.well-known/did.json"),
      feed("/xrpc/app.bsky.feed.*"),
      feed("/ingest"),
      feed("/edge/*"),
      ...(moved
        ? [feed("/*"), pub("/rss"), pub("/rss/*"), pub("/edge/*")]
        : [feed("/rss"), feed("/rss/*")]),
    ],
  },
});
