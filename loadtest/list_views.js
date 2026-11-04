// k6 load test for plan v3 section 14: list view p95 < 400 ms with 1M records per object at 50 users.
//
//   cd backend && uv run python -m app.cli seed-demo && uv run python -m app.cli seed-load --count 1000000
//   psql "$DATABASE_URL" -c "ANALYZE records"
//   k6 run -e BASE_URL=http://localhost:8000 -e EMAIL=sales@demo.example.com -e PASSWORD='Demo-Password-2026!' loadtest/list_views.js
//
// Run against a disposable database with MFA_REQUIRED_FOR_STAFF=false and RATE_LIMIT_ENABLED=false.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = `${__ENV.BASE_URL || "http://localhost:8000"}/api/v1`;

export const options = {
  scenarios: {
    users: { executor: "constant-vus", vus: 50, duration: __ENV.DURATION || "3m" },
  },
  thresholds: {
    "http_req_duration{name:list}": ["p(95)<400"],
    "http_req_duration{name:filtered}": ["p(95)<400"],
    "http_req_duration{name:next_page}": ["p(95)<400"],
    "http_req_duration{name:search}": ["p(95)<800"],
    http_req_failed: ["rate<0.01"],
  },
};

// Each virtual user signs in once; k6 keeps the session cookie per VU.
export function setup() {
  return { email: __ENV.EMAIL || "sales@demo.example.com", password: __ENV.PASSWORD || "Demo-Password-2026!" };
}

let csrf = null;

function login(creds) {
  const res = http.post(`${BASE}/auth/login`, JSON.stringify(creds), { headers: { "Content-Type": "application/json" } });
  check(res, { "signed in": (r) => r.status === 200 });
  const jar = http.cookieJar();
  csrf = jar.cookiesForURL(BASE).crm_csrf?.[0] ?? null;
}

function query(body, name) {
  return http.post(`${BASE}/objects/account/records/query`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf ?? "" },
    tags: { name },
  });
}

export default function (creds) {
  if (!csrf) login(creds);
  const list = query({ limit: 50, sort: [{ field: "name", direction: "asc" }] }, "list");
  check(list, { "list ok": (r) => r.status === 200 });
  const cursor = list.status === 200 ? list.json("next_cursor") : null;
  if (cursor) check(query({ limit: 50, cursor, sort: [{ field: "name", direction: "asc" }] }, "next_page"), { "page 2 ok": (r) => r.status === 200 });
  const filtered = query(
    { limit: 50, filters: { logic: "and", conditions: [{ field: "industry", op: "equals", value: "Retail" }] }, sort: [{ field: "annual_revenue", direction: "desc" }] },
    "filtered",
  );
  check(filtered, { "filter ok": (r) => r.status === 200 });
  const search = http.get(`${BASE}/search?q=Load%20account%2000012`, { tags: { name: "search" } });
  check(search, { "search ok": (r) => r.status === 200 });
  sleep(1);
}
