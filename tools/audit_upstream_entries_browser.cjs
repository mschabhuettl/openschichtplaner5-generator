/* Synthetic source-contract browser check. Requires a prepared isolated frontend,
 * a loopback Vite server, and JSON fixtures from the candidate's local ASGI tests.
 * No production API, credentials, or personal data. Not a full OSP5 app test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const [frontend, fixturePath, base = 'http://127.0.0.1:5189'] = process.argv.slice(2);
assert.equal(new URL(base).hostname, '127.0.0.1');
const {chromium} = createRequire(path.resolve(frontend, 'package.json'))('playwright');
const fixtures = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({viewport: {width, height: 900}, timezoneId: 'Europe/Vienna'});
      const errors = [];
      const requests = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route(base + '/api/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/api/v1/groups') return route.fulfill({json: []});
        assert.equal(url.pathname, '/api/v1/schedule/week');
        requests.push(url.searchParams.get('date'));
        const plan = url.searchParams.get('plan');
        assert.ok(fixtures[plan], 'explicit known plan required');
        return route.fulfill({json: fixtures[plan]});
      });
      await page.goto(base + '/entries-audit.html');
      await page.getByText('10:00–11:00', {exact: true}).waitFor();
      assert.equal(await page.getByText('Ist · im Ist ersetzt · 08:00-16:00', {exact: true}).count(), 2);
      await page.getByText('Sonderdienst · 0800-1000', {exact: true}).waitFor();
      await page.getByText('Sonderdienst · 1600-1900', {exact: true}).waitFor();
      await page.getByLabel('Plansicht').focus();
      await page.keyboard.press('s');
      await page.getByLabel('Plansicht').selectOption('soll');
      await page.getByText('Soll · 08:00-16:00', {exact: true}).waitFor();
      assert.equal(await page.getByText('Ist · im Ist ersetzt · 08:00-16:00', {exact: true}).count(), 0);
      await page.getByLabel('Plansicht').selectOption('both');
      await page.getByText('Ist · im Ist ersetzt · 08:00-16:00', {exact: true}).first().waitFor();
      assert.equal(await page.getByText('Ist · im Ist ersetzt · 08:00-16:00', {exact: true}).count(), 2);
      assert.equal(await page.getByText('Soll · 08:00-16:00', {exact: true}).count(), 1);
      assert.equal(await page.getByText('10:00–11:00', {exact: true}).count(), 1);
      const requestAfter = async action => {
        await Promise.all([
          page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/schedule/week'),
          action(),
        ]);
        return requests.at(-1);
      };
      assert.equal(await requestAfter(() => page.locator('input[type="date"]').fill('2027-01-01')),
        '2026-12-28', 'Vienna date selection must request the ISO Monday, not UTC Sunday');
      assert.equal(await requestAfter(() => page.getByRole('button', {name: 'Vor →', exact: true}).click()),
        '2027-01-04', 'next week advances exactly seven calendar dates');
      assert.equal(await requestAfter(() => page.locator('input[type="date"]').fill('2026-10-25')),
        '2026-10-19', 'DST transition Sunday remains in its local ISO week');
      assert.equal(await requestAfter(() => page.getByRole('button', {name: 'Vor →', exact: true}).click()),
        '2026-10-26', 'next week crosses DST without UTC date drift');
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`PASS: ${width}px source rows, explicit Ist/Soll/Both, replacement/absence details, Vienna year/DST navigation`);
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
