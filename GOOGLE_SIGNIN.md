# Getting the Google client ID

You need **one** value: `GOOGLE_CLIENT_ID`. There is no client secret in this
flow — the browser returns a signed ID token and the API verifies it against
Google's public keys, so there is nothing to keep out of the repo.

The client ID is public by design. It ships in the frontend bundle and
identifies the application; it does not authorise anything.

---

## 1 · Create a project

[console.cloud.google.com](https://console.cloud.google.com) → project dropdown
(top left) → **New Project** → name it `SANKHYA` → Create.

Select it before continuing. Everything below is per-project, and configuring
the wrong one is the most common way to lose twenty minutes here.

## 2 · Configure the consent screen

**Google Auth Platform** → **Overview**, and fill in the branding prompt it
opens with. (On the older console this lived under *APIs & Services → OAuth
consent screen*; Google has since split it across **Branding**, **Audience** and
**Data access** in the left nav.)

| Field | Value |
|---|---|
| User type | **External** |
| App name | `SANKHYA` |
| User support email | your address |
| Developer contact | your address |

Then **Data access** → *Add or remove scopes* → tick
`.../auth/userinfo.email`, `.../auth/userinfo.profile`, `openid`. Nothing else:
this only needs to know who signed in.

### The bit that catches people

A new app sits in **Testing** status, where **only accounts you list as test
users can sign in**. Everyone else gets "access blocked" with no useful
explanation.

Open **Audience** in the left nav:

- **Demo or hackathon** → stay in Testing and add the accounts that will be
  demoing under **Test users**. Up to 100.
- **Real users** → **Publish app**. An app requesting only email and profile is
  not subject to Google's verification review, so this takes effect immediately.

## 3 · Create the credential

**Clients** in the left nav → **Create OAuth client** → Application type:
**Web application**. (Older console: *APIs & Services → Credentials → Create
Credentials → OAuth client ID*.)

Under **Authorised JavaScript origins**, add every origin the sign-in page is
served from:

```
https://sankhya-two.vercel.app
http://localhost:3000
```

Leave **Authorised redirect URIs empty**. This flow never redirects — Google
Identity Services returns the token to JavaScript on the page.

Create, then copy the **Client ID**. It looks like:

```
123456789012-abc123def456ghi789.apps.googleusercontent.com
```

Ignore the client secret. Nothing here uses it.

### Origins must match exactly

Scheme, host and port, with **no path and no trailing slash**. Each of these is
a different origin as far as Google is concerned:

| | |
|---|---|
| `https://sankhya-two.vercel.app` | ✅ |
| `https://sankhya-two.vercel.app/` | ❌ trailing slash |
| `http://sankhya-two.vercel.app` | ❌ wrong scheme |
| `https://sankhya-two.vercel.app/login` | ❌ has a path |

A mismatch shows as `origin_mismatch` or a button that does nothing.

**Vercel preview deployments each get their own URL** and none of them are
listed, so Google sign-in will not work on a preview branch unless you add that
URL too. Password sign-in still does.

---

## 4 · Set it on the API

Render → `sankhya-api` → **Environment**:

```
GOOGLE_CLIENT_ID = 123456789012-abc....apps.googleusercontent.com
```

Save. Render restarts automatically.

Nothing to change on Vercel: the frontend asks `GET /auth/config` at runtime and
shows the button only when the server reports a client ID. So turning Google
sign-in on or off is a restart, not a rebuild.

## 5 · Check it

```bash
curl -s https://sankhya-api-amdu.onrender.com/auth/config
```

```json
{
  "google_client_id": "1234...apps.googleusercontent.com",
  "registration_open": false,
  "allowed_email_domains": ["gov.in", "nic.in"]
}
```

Reload the sign-in page and the Google button appears above the method tabs.

---

## Who is allowed in

Google sign-in respects the same domain rule as registration. With the default
`ALLOWED_EMAIL_DOMAINS=gov.in,nic.in`, a `@gmail.com` account is refused — this
platform holds officers' competency records, so an arbitrary address must not be
able to create one.

**To let any Google account in** (a demo, most likely), set on Render:

```
ALLOWED_EMAIL_DOMAINS=
```

Empty means no restriction. It is an explicit opt-out rather than something that
happens by accident.

Two further controls:

- `GOOGLE_AUTO_PROVISION=false` — existing officers may sign in with Google, but
  a Google account with no record is refused rather than creating one.
- An account created this way is always a **learner with no division and no FRAC
  role**. Every competency figure is measured against a role, and the premise of
  the platform is that competency is never self-declared — so an administrator
  assigns it, not the person signing up.

## Local development

Same client ID, with `http://localhost:3000` in the origins list:

```bash
# backend/.env or the repo-root .env
GOOGLE_CLIENT_ID=1234...apps.googleusercontent.com
ALLOWED_EMAIL_DOMAINS=
```

Restart the API. The Vite dev server proxies `/api`, so the browser stays on
`localhost:3000` and that is the origin Google checks.

## When it does not work

| What you see | Cause |
|---|---|
| No button at all | `GOOGLE_CLIENT_ID` unset, or the API restart has not finished. Check `/auth/config`. |
| Button renders, nothing happens on click | Origin not in **Authorised JavaScript origins**. Check the browser console for `origin_mismatch`. |
| "Access blocked: app not verified" | Consent screen is in Testing and this account is not a test user. |
| 401 "This Google sign-in was not issued for SANKHYA" | `aud` mismatch — the API's `GOOGLE_CLIENT_ID` differs from the one the button used. |
| 403 "limited to official government addresses" | Domain rule. Clear `ALLOWED_EMAIL_DOMAINS` to allow any. |
| Button never loads, console shows a blocked request | An ad blocker is blocking `accounts.google.com/gsi/client`. The page says so and falls back to the other methods. |

## A note on this being a government platform

The sign-in page already says these methods are the interim path, and that
production would authenticate against **Parichay**, the Government of India
single sign-on. Google sign-in is a convenience for demos and development, not a
proposal for how officers would really authenticate. The adapter seam is at
`/auth/parichay/authorize`, which is deliberately a documented stub rather than
a faked integration.
