# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x (`main`) | yes |
| 1.x | no |

## Reporting a vulnerability

Please report suspected vulnerabilities privately through
[GitHub security advisories](https://github.com/SatvikPraveen/FlaskVerseHub/security/advisories/new)
rather than a public issue. Include reproduction steps, the affected
endpoint or module, and the impact you believe is possible. You should
receive an acknowledgement within a few days; fixes are released as patch
versions with credit unless you prefer otherwise.

## Security design

* Passwords are hashed with Werkzeug's scrypt; accounts lock for 15 minutes
  after 5 failed attempts.
* Password-reset and verification links are signed, time-limited and bound
  to the current password hash (single use).
* API keys are stored as SHA-256 hashes with a display prefix and scopes.
* JWTs are short-lived access tokens with refresh tokens; inactive users are
  rejected on every request.
* CSRF protection on all browser forms; the JSON API is CSRF-exempt and
  token-authenticated.
* User-supplied HTML is sanitised with `nh3` using an allow-list.
* Responses carry CSP, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy` and HSTS (when cookies are secure).
* Rate limits on authentication and API routes; audit trail of security
  events (`user.login_failed`, `user.login_blocked`, key issuance/revocation).
* Dependencies are monitored by Dependabot; code is scanned by CodeQL and
  bandit on every push.
