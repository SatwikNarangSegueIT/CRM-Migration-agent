// End-to-end smoke test against a running stack (API + worker + Vite or nginx).
//   BASE_URL=http://localhost:5173 SHOTS=/tmp/shots node e2e/smoke.mjs
// Requires the demo users (`python -m app.cli seed-demo`) and MFA_REQUIRED_FOR_STAFF=false.
// Uses the `playwright` package (installed globally in CI images: NODE_PATH=$(npm root -g)).
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL ?? "http://localhost:5173";
const SHOTS = process.env.SHOTS ?? "e2e-shots";
const PASSWORD = "Demo-Password-2026!";
const RUN = Date.now().toString(36);
mkdirSync(SHOTS, { recursive: true });

const results = [];
const consoleErrors = [];
let browserRef = null;

async function step(name, fn) {
  const started = Date.now();
  try {
    await fn();
    results.push({ name, ok: true, ms: Date.now() - started });
    console.log(`  ✓ ${name}`);
  } catch (err) {
    results.push({ name, ok: false, error: String(err).split("\n")[0] });
    console.log(`  ✗ ${name}: ${String(err).split("\n")[0]}`);
    let n = 0;
    for (const ctx of browserRef?.contexts() ?? [])
      for (const pg of ctx.pages())
        await pg.screenshot({ path: `${SHOTS}/FAILED-${n++}.png` }).catch(() => {});
    throw err;
  }
}

async function newPage(browser, viewport = { width: 1440, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  page.on("console", (m) => {
    // Expected: /auth/me answers 401 before sign-in.
    if (m.type() === "error" && !m.text().includes("401")) consoleErrors.push(`${page.url()}: ${m.text()}`);
  });
  page.on("pageerror", (e) => consoleErrors.push(`${page.url()}: ${e.message}`));
  return { context, page };
}

async function signIn(page, email, password = PASSWORD) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel(/E-mail/).fill(email);
  await page.getByLabel(/Password/).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
}

async function api(page, method, path, body) {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie
        .split("; ")
        .find((c) => c.startsWith("crm_csrf="))
        ?.split("=")[1];
      const res = await fetch(`/api/v1${path}`, {
        method,
        headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return {
        status: res.status,
        json: res.headers.get("content-type")?.includes("json") ? await res.json() : null,
      };
    },
    { method, path, body },
  );
}

const shot = (page, name) => page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false });

const browser = await chromium.launch();
browserRef = browser;
try {
  console.log("Administrator");
  const { page } = await newPage(browser);

  await step("sign in and see the home page with apps in the rail", async () => {
    await signIn(page, "admin@demo.example.com");
    await page.getByRole("heading", { name: /Good (morning|afternoon|evening), Alex/ }).waitFor();
    const rail = page.getByRole("navigation", { name: "Apps" });
    for (const app of ["Home", "Sales", "Service", "Marketing", "Setup"])
      await rail.getByText(app, { exact: true }).waitFor();
    await shot(page, "01-home");
  });

  await step("create an account from the Accounts list view", async () => {
    await page.goto(`${BASE}/o/account`);
    await page.getByRole("button", { name: "New" }).click();
    const dialog = page.getByRole("dialog", { name: "New Account" });
    await dialog.getByLabel(/Name/).first().fill(`Acme ${RUN}`);
    await dialog.getByRole("button", { name: "Save" }).click();
    await page.waitForURL(/\/o\/account\/[0-9a-f-]{36}$/);
    await page.getByRole("heading", { name: `Acme ${RUN}` }).waitFor();
    await shot(page, "02-account-record");
  });

  await step("Object Manager: create a custom object with a picklist field", async () => {
    await page.goto(`${BASE}/setup/objects`);
    await page.getByRole("button", { name: /New Custom Object/ }).click();
    const dialog = page.getByRole("dialog", { name: "New custom object" });
    await dialog.getByLabel(/^Label/).fill(`Vehicle ${RUN}`);
    await dialog.getByRole("button", { name: "Save" }).click();
    await page.waitForURL(/\/setup\/objects\/vehicle_.*__c$/);
    await page.getByRole("button", { name: /New Field/ }).click();
    const field = page.getByRole("dialog", { name: /New field on/ });
    await field.getByLabel(/Data type/).selectOption("picklist");
    await field.getByLabel(/Field label/).fill("Fuel");
    await field.getByLabel(/Default access/).selectOption("edit");
    await field.getByLabel(/Add values/).fill("Petrol\nDiesel\nElectric");
    await field.getByRole("button", { name: "Add", exact: true }).click();
    await field.getByRole("button", { name: "Save" }).click();
    await page.getByRole("cell", { name: "Fuel", exact: true }).waitFor();
    await shot(page, "03-object-manager");
  });

  const objectApi = new URL(page.url()).pathname.split("/").pop();

  await step("App Manager: add an app with the new object's tab", async () => {
    await page.goto(`${BASE}/setup/apps`);
    await page.getByRole("button", { name: /New App/ }).click();
    const dialog = page.getByRole("dialog", { name: "New app" });
    await dialog.getByLabel(/App name/).fill(`Fleet ${RUN}`);
    await dialog.getByLabel("Add tab").selectOption(`object:${objectApi}`);
    await dialog.getByRole("button", { name: "Add", exact: true }).click();
    await dialog.getByRole("button", { name: "Save" }).click();
    await page.getByText("App created.").waitFor();
    await page.goto(`${BASE}/`);
    await page.getByRole("navigation", { name: "Apps" }).getByText(`Fleet ${RUN}`).waitFor();
  });

  await step("create a record of the custom object with the picklist", async () => {
    await page.goto(`${BASE}/o/${objectApi}`);
    await page.getByRole("button", { name: "New" }).click();
    const dialog = page.getByRole("dialog", { name: /^New Vehicle/ });
    await dialog.getByLabel(/Name/).first().fill("Hilux 01");
    await dialog.getByLabel("Fuel").selectOption("Diesel");
    await dialog.getByRole("button", { name: "Save" }).click();
    await page.waitForURL(new RegExp(`/o/${objectApi}/[0-9a-f-]{36}$`));
    await page.getByText("Diesel").first().waitFor();
    await shot(page, "04-custom-record");
  });

  await step("settings: save billing payment terms", async () => {
    await page.goto(`${BASE}/setup/settings/billing`);
    await page.getByLabel("Payment terms (days)").fill("30");
    await page.getByRole("button", { name: "Save" }).click();
    await page.getByText("Invoices saved.").waitFor();
    await shot(page, "05-settings-billing");
  });

  await step("industry packs: install the Migration Agency pack", async () => {
    await page.goto(`${BASE}/setup/packs`);
    await page.getByRole("heading", { name: /Migration Agency/ }).waitFor();
    const install = page.getByRole("button", { name: /^(Install|Upgrade)$/ });
    if (await install.count()) {
      await install.first().click();
      await page.getByRole("dialog").getByRole("button", { name: "Continue" }).click();
      await page.getByText(/installed\.$/).waitFor({ timeout: 60_000 });
    }
    await page.getByText("Enabled").first().waitFor();
    await shot(page, "06-packs");
  });

  await step("reports and dashboards open", async () => {
    await page.goto(`${BASE}/reports`);
    await page
      .getByRole("heading", { name: /Reports/ })
      .first()
      .waitFor();
    await page.goto(`${BASE}/dashboards`);
    await page
      .getByRole("heading", { name: /Dashboards/ })
      .first()
      .waitFor();
    await shot(page, "07-dashboards");
  });

  await step("global search finds the new account", async () => {
    await page.goto(`${BASE}/search?q=${encodeURIComponent(`Acme ${RUN}`)}`);
    await page
      .getByRole("link", { name: `Acme ${RUN}` })
      .first()
      .waitFor();
  });

  // ----------------------------------------------------------- customer portal
  console.log("Customer portal");
  let portalEmail = `priya.${RUN}@example.com`;
  let inviteToken = "";

  await step("invite a contact to the portal (Setup → Portal Users)", async () => {
    const acct = await api(page, "POST", "/objects/account/records/query", {
      limit: 1,
      search: `Acme ${RUN}`,
    });
    const accountId = acct.json.items?.[0]?.id;
    if (acct.json.items?.[0]?.name !== `Acme ${RUN}`)
      throw new Error("account search returned the wrong record");
    const contact = await api(page, "POST", "/objects/contact/records", {
      fields: { first_name: "Priya", last_name: `Client ${RUN}`, email: portalEmail, account: accountId },
    });
    if (contact.status !== 201 && contact.status !== 200)
      throw new Error(`contact create ${contact.status} ${JSON.stringify(contact.json)}`);
    await page.goto(`${BASE}/setup/portal-users`);
    await page.getByRole("button", { name: /Invite contact/ }).click();
    const dialog = page.getByRole("dialog", { name: /Invite a contact/ });
    await dialog.getByPlaceholder("Search contacts…").fill(`Client ${RUN}`);
    await page
      .getByRole("option", { name: new RegExp(`Client ${RUN}`) })
      .first()
      .click();
    await dialog.getByRole("button", { name: "Send invitation" }).click();
    await page.getByText(`Invitation sent to ${portalEmail}.`).waitFor();
    await shot(page, "08-portal-users");
  });

  await step("read the invitation e-mail from the worker log", async () => {
    const { readFileSync } = await import("node:fs");
    const log = process.env.WORKER_LOG;
    if (!log) throw new Error("WORKER_LOG not set");
    for (let i = 0; i < 40 && !inviteToken; i++) {
      const text = readFileSync(log, "utf8");
      const at = text.lastIndexOf(`To: ${portalEmail}`);
      const m = at >= 0 ? /accept-invitation#token=([A-Za-z0-9_-]+)/.exec(text.slice(at)) : null;
      if (m) inviteToken = m[1];
      else await new Promise((r) => setTimeout(r, 500));
    }
    if (!inviteToken) throw new Error("no invitation e-mail found");
  });

  const portal = await newPage(browser, { width: 390, height: 844 });
  const p = portal.page;
  await step("accept the invitation and sign in to the portal (phone width)", async () => {
    await p.goto(`${BASE}/accept-invitation#token=${inviteToken}`);
    await p.getByLabel(/^Password/).fill("Portal-Passphrase-2026");
    await p.getByLabel(/Confirm password/).fill("Portal-Passphrase-2026");
    await p.getByRole("button", { name: "Create account" }).click();
    await p
      .getByText(/ready|Sign in/i)
      .first()
      .waitFor();
    await signIn(p, portalEmail, "Portal-Passphrase-2026");
    await p.waitForURL(/\/portal$/);
    await p.getByRole("heading", { name: "Hello, Priya" }).waitFor();
    await shot(p, "09-portal-home");
  });

  await step("raise a case in the portal and add a message", async () => {
    await p.getByRole("link", { name: /Get help/ }).click();
    await p.getByLabel(/Subject/).fill(`Printer jam ${RUN}`);
    await p.getByLabel(/Description/).fill("The printer in reception is jammed.");
    await p.getByRole("button", { name: "Submit" }).click();
    await p.waitForURL(/\/portal\/o\/case\/[0-9a-f-]{36}$/);
    await p.getByText(`Printer jam ${RUN}`).first().waitFor();
    await p.getByLabel("Add a message").fill("Any update?");
    await p.getByRole("button", { name: "Send" }).click();
    // The message must appear in the conversation (not just remain in the textarea).
    await p.getByRole("listitem").filter({ hasText: "Any update?" }).waitFor();
    if ((await p.getByLabel("Add a message").inputValue()) !== "") throw new Error("message box not cleared");
    await shot(p, "10-portal-case");
  });

  await step("staff see the portal case", async () => {
    const found = await api(page, "POST", "/objects/case/records/query", {
      limit: 5,
      search: `Printer jam ${RUN}`,
    });
    if (found.json.items?.length !== 1)
      throw new Error(`expected exactly this run's case, got ${found.json.items?.length}`);
    await page.goto(`${BASE}/o/case/${found.json.items[0].id}`);
    await page.getByText(`Printer jam ${RUN}`).first().waitFor();
    await shot(page, "11-staff-case");
  });
  await portal.context.close();

  // ----------------------------------------------------------- read-only auditor
  console.log("Read-only auditor");
  const aud = await newPage(browser);
  await step("auditor can browse but not change data or reach user admin", async () => {
    await signIn(aud.page, "auditor@demo.example.com");
    await aud.page.goto(`${BASE}/o/account`);
    await aud.page
      .getByRole("link", { name: `Acme ${RUN}` })
      .first()
      .waitFor();
    if (await aud.page.getByRole("button", { name: "New" }).count()) throw new Error("auditor sees New");
    await aud.page.goto(`${BASE}/admin/users`);
    await aud.page.getByRole("heading", { name: "Access denied" }).waitFor();
    await aud.page.goto(`${BASE}/setup/objects`);
    await aud.page.getByRole("link", { name: `Vehicle ${RUN}` }).waitFor();
    if (await aud.page.getByRole("button", { name: /New Custom Object/ }).count())
      throw new Error("auditor can create objects");
    await shot(aud.page, "12-auditor-object-manager");
  });
  await aud.context.close();
} finally {
  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} steps passed`);
  if (consoleErrors.length)
    console.log("Console errors:\n" + consoleErrors.map((e) => `  - ${e}`).join("\n"));
  process.exitCode = failed.length || consoleErrors.length ? 1 : 0;
}
