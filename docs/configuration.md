# Postmarked configuration guide

This guide covers optional imports, single sign-on, and legal policy pages.
The complete list of deployment settings and defaults is in
[`.env.example`](../.env.example).

## RV Trip Wizard import

Use the admin **Import** page to upload an RV Trip Wizard `.xlsx` export. Review
the preview diff before applying it. Imported stops are created as private
drafts.

## OpenID Connect single sign-on

Postmarked supports generic OpenID Connect alongside email and password
authentication.

1. Create an OAuth/OIDC client in Keycloak, Authentik, Azure AD, or another
   compatible identity provider.
2. Set its redirect URI to `{APP_BASE_URL}/api/auth/oidc/callback`. The value
   must match exactly.
3. Enable the `openid` and `email` scopes. The `profile` scope is recommended
   for display names.
4. Add the OIDC variables from [`.env.example`](../.env.example) to `.env` and
   set `OIDC_ENABLED=true`.
5. Restart the stack.

Signed-in users can connect and disconnect an SSO identity from their account
page. This is the recommended way to link an existing password account because
the active session proves ownership.

`OIDC_ASSOCIATE_BY_EMAIL` automatically links a matching local account on the
first SSO sign-in. It defaults to `false` and should remain disabled unless
registration is closed and the identity provider verifies email addresses.
Postmarked does not verify password-account email addresses itself. If the
provider reports an address as unverified, Postmarked refuses to link it.

`OIDC_PROVIDER_NAME` controls the login-button label and can be reworded.
`OIDC_PROVIDER_KEY` is the stable identifier stored with linked accounts.
Changing the key after accounts are linked orphans those links.

Postmarked creates its own seven-day session after a successful SSO login and
does not continuously re-check the provider. Disabling a provider account
blocks future logins but does not end active sessions. Deactivate the user in
Postmarked's admin UI to end access immediately.

### Google sign-in

Google works through the standard OpenID Connect settings:

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a
   project and open **APIs & Services → Credentials**.
2. Configure an **External** OAuth consent screen with links to the instance's
   privacy policy and terms pages.
3. Create a **Web application** OAuth client.
4. Add `{APP_BASE_URL}/api/auth/oidc/callback` as an authorized redirect URI.
5. Set `OIDC_DISCOVERY_URL` to
   `https://accounts.google.com/.well-known/openid-configuration` and add the
   client ID and secret to `.env`.
6. Publish the consent screen and restart Postmarked. While the consent screen
   remains in Testing, only listed test users can sign in.

The default `openid email profile` scopes are non-sensitive Google scopes.

Existing subscribers connect Google from their account page after signing in
with their password. Connecting adds a sign-in method; it does not remove the
password. This is safer than automatic email matching because the current
session proves account ownership.

SSO registrations follow the same approval rules as password registrations.
When user approval is required, a new SSO user enters the pending queue.

## Privacy policy and terms pages

Postmarked serves `/privacy` and `/terms` with generic placeholder content.
Place `privacy.md` and `terms.md` in `MEDIA_DIR` to replace it. The repository
includes [`privacy.md.example`](../privacy.md.example) and
[`terms.md.example`](../terms.md.example) as starting points.

Set the support contact shown in the built-in pages with:

```env
SUPPORT_EMAIL=support@example.com
```

When `SUPPORT_EMAIL` is unset, the contact section directs readers to the site
administrator.
