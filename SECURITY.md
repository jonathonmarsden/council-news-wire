# Security policy

## Reporting a vulnerability

Please report security issues privately to **hello@councilnewswire.au**.

Include what you found, how to reproduce it, and any impact you can see. You
will get an acknowledgement within 72 hours and an assessment within seven
days. Please give a reasonable window for a fix before public disclosure.

This is a small public-interest project maintained by one person, so there is
no bug bounty — but credit is offered gladly to anyone who reports something
real.

## Scope

In scope: this repository's code and configuration, the published site at
`councilnewswire.au`, and the crawler's behaviour toward council
websites.

Out of scope: the council websites themselves, Bluesky/AT Protocol
infrastructure, and denial-of-service testing against any third party.

## Design notes relevant to security

The service is deliberately built with a small attack surface:

- **No inbound network exposure for the collector.** It makes outbound
  requests only and listens on no ports. Content from council websites is
  untrusted: only public `http(s)` addresses are fetched.
- **Public edge service.** The website, RSS and Bluesky feed endpoints run as a
  Cloudflare Worker with its own database (`edge/`). Its one write endpoint
  requires a secret token; every query is parameterised and every output
  escaped. It counts feed use with an identifier that changes daily and cannot
  link a reader across days; no IP address or account name is stored.
- **Minimal data.** The collector's database stores article headline, URL,
  publication date, excerpt, link-card details and posting state. No personal
  information is collected or stored by design.
- **Credentials.** Publishing uses scoped, individually revocable application
  passwords supplied via environment variables. Secrets are never committed;
  `.env.example` contains placeholders only.
- **Isolation.** Application and database run in separate containers on a
  dedicated host with no inbound exposure. (Scraping and posting currently
  share one environment; separating them is planned.)
- **Integrity.** Publishing uses an atomic claim so an article is posted at
  most once, even across concurrent runs or a crash mid-operation.
- **Supply chain.** Dependency alerts and secret scanning are enabled, GitHub
  Actions are pinned to commits, and CI runs the test suite on every change.
  Python dependencies are not yet pinned to exact versions; that is planned.

## Responsible crawling

The collector fetches each council's public news listing roughly once per day.
Until November 2026 it presented as an ordinary browser to most councils and
identified itself by name only where councils had asked. It is moving to
identifying itself by name wherever a council's website accepts it. Details,
including request volumes and how to allow it, are published at
<https://councilnewswire.au/bot.html>.

If you administer a council website and have a concern about the crawler,
email the address above and it will be actioned promptly.
