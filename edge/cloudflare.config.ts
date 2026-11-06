// Cloudflare configuration for the edge service (cf CLI; see README.md).
// The Worker answers only these paths on lgnews.jonathonmarsden.com; every
// other path on that hostname still goes to the static site's origin.
import { bindings, defineConfig, triggers } from "cf/config";

const HOST = "lgnews.jonathonmarsden.com";
const ZONE = "jonathonmarsden.com";
const route = (path: string) => triggers.fetch({ pattern: `${HOST}${path}`, zone: ZONE });

export default defineConfig({
  worker: {
    name: "council-news-edge",
    compatibilityDate: "2026-10-01",
    entrypoint: "./src/index.ts",
    env: {
      DB: bindings.d1({ name: "council-news-edge" }),
      HOSTNAME: bindings.text(HOST),
      // DID of the Bluesky account that publishes the feed records. Set it in
      // the environment when deploying: PUBLISHER_DID=did:plc:... cf deploy
      PUBLISHER_DID: bindings.text(process.env.PUBLISHER_DID ?? ""),
      INGEST_TOKEN: bindings.secret(),
    },
    triggers: [
      route("/.well-known/did.json"),
      route("/xrpc/app.bsky.feed.*"),
      route("/rss"),
      route("/rss/*"),
      route("/ingest"),
      route("/edge/*"),
    ],
  },
});
