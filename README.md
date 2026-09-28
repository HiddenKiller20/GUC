# The Galactic Unification Corps — standalone website

A responsive Republic/Empire VRChat community website with an owner dashboard, a **public status board that requires no login**, and separate pages for High Command, battalions, ranks, Jedi High Council, Bounty Guild, GBC rewards, events, announcements, allies, rules, joining and memorials.

The site is **not connected to ChatGPT**: it has no ChatGPT sign-in, OpenAI API calls, plugin or third-party login. It uses a built-in Node HTTP server, a local SQLite database, and a private owner password. It does **not** require visitors to create accounts.

## What is editable in the dashboard?

The owner can add/change/remove High Command members, units, ranks, events, announcements, Guild tiers, rewards and allied groups; edit public copy for every page; correct/remove public statuses; and change the admin password. Other people can view all public pages and publish/edit/remove their own statuses using a **private edit code**, without accounts. The design and branded images are included as editable source files in `public/`.

The initial owner shown on High Command is `Hidden_Killer20`. No other High Command names are invented; add them from the dashboard.

## Run locally (Windows, Mac or Linux)

1. Install **Node.js 22.16 or newer** from the official Node.js site. No `npm install` or external packages are needed.
2. Unzip this folder. Open a terminal in `GUC_Website`.
3. Optional: copy `.env.example` to `.env` and change the port or host. The default owner email is already set to `bigt1576@gmail.com`.
4. Run `npm run setup`. Enter a strong, private owner password of at least 16 characters. This creates the owner's local account. **Do not send the password to anyone or put it in your website source code.**
5. Run `npm start` and open **http://127.0.0.1:3000**.
6. Open **Owner Login** and sign in with `bigt1576@gmail.com` and the password from setup. Use the dashboard to update your group information.

On Windows PowerShell, step 3 is `Copy-Item .env.example .env`. On macOS/Linux, use `cp .env.example .env`.

**Reset the owner password:** Stop the server, run `npm run setup` again, and choose a new password. This revokes all owner sessions. The email is the owner's account identity, but **no inbox verification, password-reset email or email delivery is configured**; `npm run setup` is the recovery mechanism. If you later want one-time email sign-in, it requires a real SMTP/email provider and verified domain.

## Deploying to a public domain

This is a **server application**, not a static HTML-only site. Deploy to a Node 22+ VPS or host with **persistent disk storage** for `data/guc.db`. Do not use a host that wipes SQLite files on restart. Keep `.env` and the `data/` directory out of public file serving and version control.

Use a trusted HTTPS reverse proxy (for example, Caddy or Nginx), then configure `.env` such as:

```
OWNER_EMAIL=bigt1576@gmail.com
HOST=127.0.0.1
PORT=3000
NODE_ENV=production
SITE_ORIGIN=https://your-domain.example
TRUST_PROXY=1
```

`NODE_ENV=production` enables **Secure** session cookies and HSTS, so HTTPS is required for owner login. Set `TRUST_PROXY=1` **only** if a reverse proxy you control overwrites `X-Forwarded-For`; otherwise leave it as `0`. The server's write endpoints check the browser `Origin`, and authenticated changes also require a private CSRF token.

Run `npm run setup` once on your server, then start `npm start` under a service manager such as systemd/PM2. Restrict who can access the project files, back up your `data/guc.db` regularly, and place the site behind HTTPS. The owner's password is salted and hashed using Node's scrypt function; it is never saved in the public site.

## Public status board

Visitors can publish their VRChat display name, optional rank, designation and unit, duty status and a short message without signing in. The server returns an **entry number and a private edit code** (shown only at submission). Keep that code to update or delete the post later; the owner can moderate every post. Do not post private personal information. The public form is rate-limited to four submissions per IP per hour, includes a honeypot, enforces length limits and renders text as plain text.

This project uses local storage, not cloud email or account provisioning. For a large public deployment, consider adding a managed anti-abuse service, backups, logs and a privacy policy before accepting substantial traffic.

## Edit the look and assets

- `public/styles.css` — all colors, layout and responsive styling.
- `public/app.js` — the full public UI and owner dashboard.
- `public/assets/fused.png`, `republic.png`, `empire.png` — GUC's current fused (blue/red), Republic (blue) and Empire (red) insignias.
- `public/assets/hero.webp`, `republic-art.webp`, `empire-art.webp` — image assets from your GUC banner artwork.
- `db.mjs` — initial text, default units, ranks, GBC store and Guild tiers. Once initialized, use the dashboard; editing initial defaults does not overwrite existing saved data.
- `server.mjs` — API, authentication, status board and security controls.

The Discord invite configured in the UI and server is `https://discord.gg/FuspHdkmEN`. If the invite changes, update both `public/app.js` and `server.mjs`.

## Test

`npm test` runs the included local integration tests: public access, owner login, owner-only edit protection, editable High Command and anonymous status posting/editing/deletion.

## Files that must stay private

Never upload `.env`, the live `data/guc.db` or your setup password to a public repository. Static assets and the website's source code may be published, but the SQLite database and credentials must stay on the private server.

## Deploy to Railway (recommended)

1. Upload this project to GitHub **without** `.env`, `data/*.db`, passwords, private edit codes, or session data.
2. In Railway, create a service from the GitHub repository and use the `main` branch. Node 22.16+ is required.
3. **Before accepting members**, attach a persistent volume to the web service and mount it at `/data`. Set `DB_FILE=/data/guc.db` so posts and admin changes survive redeploys.
4. Set Railway service variables `HOST=0.0.0.0`, `NODE_ENV=production`, `OWNER_EMAIL=bigt1576@gmail.com`, and `DB_FILE=/data/guc.db`. Railway provides `PORT` automatically. Leave `TRUST_PROXY=0` unless you control the proxy and know it overwrites forwarding headers.
5. Set `SETUP_PASSWORD` to a new private 16+ character owner password **in Railway's service Variables screen, not in GitHub or chat**. On first start, the site initializes the owner account if none exists. Once the account is created on the persistent volume, remove `SETUP_PASSWORD` from Railway Variables. Removing it does not change the existing password.
6. In Railway Networking, generate a public Railway domain. HTTPS is provided at the Railway edge. Test `/api/health`, the public status form, and owner login before sharing the domain. You can optionally set `SITE_ORIGIN=https://your-generated-domain.up.railway.app` to restrict write requests to that exact origin.
7. Keep the service at **one replica** with this SQLite database, and back up `/data/guc.db`. Attach the volume *before first production use*.

The `railway.json` file supplies the start command and healthcheck. `scripts/bootstrap.mjs` initializes the owner only if the account doesn't exist; it never resets an established owner password on subsequent deployments.