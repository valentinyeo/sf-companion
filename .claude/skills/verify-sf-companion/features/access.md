# Anonymous access gate

The deployed site sits behind Cloudflare Access, so an anonymous request reaches the Access login before any factory data. The gate is a property of the deployed Website resource, not of the page renderer.

Covers: deploy:website

Code paths: apps/web/src/website.ts, apps/web/src/entry.server.ts

## Sub-features

- `access-anonymous` redirects an unauthenticated request to the Access login.

## How to get to it (user POV)

- Open `https://yeoux.net/factory/` in a browser without an authenticated session.

## Driving it with Playwright

Preconditions:

- Run `../run.sh --live`. Network access to yeoux.net must be available. Do not supply cookies or tokens.

- Request. Use a fresh `request.newContext()` and `context.get('https://yeoux.net/factory/', {maxRedirects: 0})`.
- Verify. Require HTTP 301, 302, 303, 307, or 308. Require Location to have a hostname ending in `.cloudflareaccess.com` and a path starting with `/cdn-cgi/access/login`.
- Proof. `result.json` records the redirect status and destination origin/path. Without `--live`, it records `live: "skipped"`.

## Gotchas

- Never follow the redirect or save signed query parameters.
- This is a read-only anonymous boundary check. It does not prove login success or authenticated page content.
- A network failure is a failed requested check, not a verified gate.
