# Security policy

## Reporting a vulnerability

Please report security issues privately to **hello@jonathonmarsden.com**.

Include what you found, how to reproduce it, and any impact you can see. You
will get an acknowledgement within 72 hours and an assessment within seven
days. Please give a reasonable window for a fix before public disclosure.

This is a small public-interest project maintained by one person, so there is
no bug bounty — but credit is offered gladly to anyone who reports something
real.

## Scope

In scope: this repository's code and configuration, the published site at
`lgnews.jonathonmarsden.com`, and the crawler's behaviour toward council
websites.

Out of scope: the council websites themselves, Bluesky/AT Protocol
infrastructure, and denial-of-service testing against any third party.

## Design notes relevant to security

The service is deliberately built with a small attack surface:

- **No inbound network exposure.** The collector makes outbound HTTPS requests
  only. It listens on no ports, exposes no API, accepts no user input, and has
  no accounts or sessions. The public website is a static page behind a CDN.
- **Minimal data.** The database stores article headline, URL, publication
  date, excerpt, and posting state. No personal information is collected or
  stored by design.
- **Credentials.** Publishing uses scoped, individually revocable application
  passwords supplied via environment variables. Secrets are never committed;
  `.env.example` contains placeholders only.
- **Isolation.** Application and database run in separate containers on a
  dedicated host with no inbound exposure.
- **Integrity.** Publishing uses an atomic claim so an article is posted at
  most once, even across concurrent runs or a crash mid-operation.
- **Supply chain.** Dependencies are pinned, dependency alerts are enabled,
  and CI runs the test suite on every change across supported Python versions.

## Responsible crawling

The collector fetches each council's public news listing roughly once per day
and identifies itself where councils have asked it to. Details, including
request volumes and how to allow or block it, are published at
<https://lgnews.jonathonmarsden.com/bot.html>.

If you administer a council website and have a concern about the crawler,
email the address above and it will be actioned promptly.
