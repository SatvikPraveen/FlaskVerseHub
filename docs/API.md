# API guide

Base URL: `/api/v1`. Interactive references: Swagger UI at `/api/v1/docs`,
GraphiQL at `/api/v1/graphql`, machine-readable OpenAPI 3.1 at
`/api/v1/openapi.json`.

## Conventions

| Aspect | Behaviour |
|---|---|
| Envelope | single resource `{"data": {...}}`; collections `{"data": [...], "pagination": {page, per_page, total, pages, has_next, has_prev}}` |
| Errors | `{"error": "<code>", "message": "...", "status": 4xx/5xx, "details"?: {...}, "request_id": "..."}` |
| Validation | `422 validation_error` with `details.fields` mapping field → messages |
| Pagination | `?page=` (1-based) and `?per_page=` (clamped to `MAX_ITEMS_PER_PAGE`, default 100) |
| Identifiers | item routes accept a numeric id or a slug |
| Caching | `Cache-Control: no-store` on every API response |
| Correlation | `X-Request-ID` echoed on every response; send your own to propagate it |
| Rate limits | `RATELIMIT_API` per client (default 120/min); auth endpoints `RATELIMIT_AUTH` (default 10/min); limits are advertised in `X-RateLimit-*` headers |

## Authentication

Two schemes are accepted on every protected route:

1. **JWT bearer token**
   ```http
   POST /api/v1/auth/token
   {"identifier": "alice", "password": "AlicePass123!"}
   → {"access_token", "refresh_token", "token_type": "Bearer", "expires_in", "user"}
   ```
   Send `Authorization: Bearer <access_token>`. Refresh with
   `POST /api/v1/auth/refresh` using the refresh token as the bearer.
   Tokens for inactive accounts are rejected with `401 invalid_token`.
2. **API key** created on `/auth/api-keys`. Send `X-API-Key: fvh_...`.
   Keys carry scopes (`read`, `write`, `admin`); write endpoints require
   `write`, otherwise `403 insufficient_scope`. Only the SHA-256 hash is stored.

Public read endpoints work anonymously and return only items visible to an
anonymous viewer; authenticating widens the result set to the caller's own
and, for administrators, everything.

## REST endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | – | index with endpoint list |
| GET | `/stats` | optional | counts and search-index diagnostics |
| POST | `/auth/token` | – | issue access + refresh tokens |
| POST | `/auth/refresh` | refresh JWT | new access token |
| GET | `/auth/me` | required | the caller's account |
| GET | `/items` | optional | list; filters `q, category, tag, difficulty, status, mine, featured, sort` |
| POST | `/items` | write | create (`201`, `Location` header) |
| GET | `/items/{ident}` | optional | one item with content |
| PATCH/PUT | `/items/{ident}` | write + owner/admin | partial update; `change_note` stored in history |
| DELETE | `/items/{ident}` | write + owner/admin | `204` |
| GET | `/items/{ident}/revisions` | optional | version history |
| GET/POST | `/items/{ident}/comments` | optional / write | threaded comments (`parent_id`) |
| POST | `/items/{ident}/bookmark` | write | toggle; returns `{bookmarked, count}` |
| GET | `/items/{ident}/explain?q=` | optional | per-term score contributions |
| GET | `/search?q=` | optional | ranked search; adds `score` per hit plus `terms`, `ranker`, `elapsed_ms` |
| GET | `/search/suggest?q=` | – | vocabulary completions |
| GET | `/categories` | – | all categories with counts |
| GET | `/tags` | – | tags (paginated) |
| GET | `/users/{username}` | optional | profile and recent items; private fields for self/admin |
| GET | `/activity` | required | audit trail (own events; all for admins) |
| POST | `/graphql` | optional | GraphQL endpoint |

### Item payloads

Create / update accept:

```json
{
  "title": "string (3-200)",
  "content": "HTML string (min 10); sanitised server-side",
  "summary": "string (≤500) | null",
  "tags": "comma-separated string or array of strings",
  "category_id": 1,
  "difficulty": "beginner | intermediate | advanced | expert",
  "status": "draft | published | archived",
  "source_url": "https://...",
  "is_public": true,
  "is_featured": false,
  "change_note": "update only (≤255)"
}
```

`is_featured` is honoured for administrators only. New items default to
private; set `is_public: true` to publish to everyone.

## GraphQL

Schema highlights (camelCase in queries):

```graphql
type Query {
  me: User
  item(slug: String, id: Int): Item
  items(page: Int, perPage: Int, q: String, category: String, tag: String,
        difficulty: String, mine: Boolean, featured: Boolean, sort: String): ItemPage
  search(query: String!, page: Int, perPage: Int): SearchResult
  categories: [Category]
  tags(limit: Int): [Tag]
  user(username: String!): User
}

type Mutation {
  createItem(input: ItemInput!): CreateItem
  updateItem(slug: String!, input: ItemInput!, changeNote: String): UpdateItem
  deleteItem(slug: String!): DeleteItem
  addComment(slug: String!, body: String!, parentId: Int): AddComment
  toggleBookmark(slug: String!): ToggleBookmark
}
```

Authentication uses the same headers as REST. Errors are returned in the
standard `errors` array with the service's message (`Authentication
required.`, `You may not modify this item.`, `Validation failed.`).

## Versioning policy

The path prefix (`/api/v1`) is the major version. Additive changes (new
fields, new endpoints, new optional parameters) ship without a version bump;
removing or renaming a field, or changing a status code, requires `/api/v2`
and a deprecation note in `CHANGELOG.md`.
