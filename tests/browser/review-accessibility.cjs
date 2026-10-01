'use strict';
// Real Chromium + a disposable authenticated backend. No production/SP5 data.
// Run: node --test tests/browser/review-accessibility.cjs
// Needs local playwright/Chromium and Python web dependencies (WEB_TEST_PYTHON).
// Exercises native filechooser events, then injects synthetic files with
// FileChooser.setFiles. Login uses a fixture HTTP request; logout is native.
// Limits: no OS-dialog UI, login-form, screen-reader, physical mobile device,
// or spreadsheet-app coverage; Chromium emulates the touch viewport.
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {randomBytes} = require('node:crypto');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let state, password, server, serverExit, browser, base, serverOutput = '';

before(async () => {
  state = fs.mkdtempSync(path.join(os.tmpdir(), 'generator-review-ui-'));
  // An ephemeral fixture-only credential; never logs or uses a user's secret.
  password = randomBytes(24).toString('hex');
  const passwordFile = path.join(state, 'test-password');
  fs.writeFileSync(passwordFile, password, {mode: 0o600});
  const code = [
    'import os, socket, uvicorn',
    'from sp5generator.webapp import create_app',
    'sock = socket.socket()',
    "sock.bind(('127.0.0.1', 0))",
    "app = create_app(os.environ['WEB_TEST_STATE'], start_worker=False)",
    "print('REVIEW_PORT=' + str(sock.getsockname()[1]), flush=True)",
    "uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='warning')).run(sockets=[sock])"
  ].join('\n');
  server = spawn(process.env.WEB_TEST_PYTHON || 'python3', ['-c', code], {
    cwd: root,
    env: {...process.env, WEB_TEST_STATE: state, SP5_WEB_PASSWORD_FILE: passwordFile},
    stdio: ['ignore', 'pipe', 'pipe']
  });
  serverExit = once(server, 'exit');
  let spawnError;
  server.on('error', error => { spawnError = error; });
  for (const stream of [server.stdout, server.stderr]) stream.on('data', chunk => {
    serverOutput += chunk;
    const port = /REVIEW_PORT=(\d+)/.exec(serverOutput)?.[1];
    if (port) base = `http://127.0.0.1:${port}`;
  });
  let ready = false;
  for (let attempt = 0; attempt < 150; attempt++) {
    if (spawnError) throw spawnError;
    if (server.exitCode !== null) throw Error('Fixture backend exited: ' + serverOutput);
    try { if (base && (await fetch(base + '/healthz')).ok) { ready = true; break; } } catch {}
    await pause(100);
  }
  assert(ready, 'disposable backend starts: ' + serverOutput);
  browser = await chromium.launch({headless: true, args: ['--no-sandbox'],
    ...(process.env.WEB_TEST_CHROMIUM ? {executablePath: process.env.WEB_TEST_CHROMIUM} : {})});
});

after(async () => {
  try { if (browser) await browser.close(); }
  finally {
    if (server && server.exitCode === null && server.signalCode === null) {
      server.kill('SIGTERM');
      let timer;
      const stopped = await Promise.race([serverExit.then(() => true),
        new Promise(resolve => { timer = setTimeout(() => resolve(false), 10000); })]);
      clearTimeout(timer);
      if (!stopped) { server.kill('SIGKILL'); await serverExit; }
      assert(stopped, 'fixture backend stops gracefully');
    }
    if (state) fs.rmSync(state, {recursive: true, force: true});
  }
});

async function authenticatedPage(t, viewport = {width: 1440, height: 1000}, options = {}) {
  const context = await browser.newContext({...options, viewport});
  t.after(() => context.close());
  const login = await context.request.post(base + '/login', {
    form: {password}, headers: {Origin: base}, maxRedirects: 0
  });
  assert.equal(login.status(), 303, 'real fixture login obtains the session cookie');
  const page = await context.newPage();
  // Keep native chooser interception enabled before any keyboard event. A
  // one-shot listener immediately followed by keyboard.press can race the
  // asynchronous CDP interception toggle (unlike a locator's waited click).
  page.on('filechooser', () => {});
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.dismiss());
  await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
  await page.goto(base);
  await page.waitForFunction(() => /^Version \d/.test(document.querySelector('#version').textContent));
  assert.equal(await page.locator('#logout').getAttribute('hidden'), null, 'real authenticated mode enables logout');
  t.after(() => assert.deepEqual(errors, [], 'no uncaught browser errors'));
  return {page, context};
}

async function tabTo(page, selector, maxTabs = 75) {
  const seen = [];
  for (let count = 0; count < maxTabs; count++) {
    await page.keyboard.press('Tab');
    if (await page.locator(selector).evaluate(element => element === document.activeElement)) return;
    seen.push(await page.evaluate(() => document.activeElement.id || document.activeElement.tagName));
  }
  assert.fail('Native Tab navigation must reach ' + selector + '; visited: ' + seen.join(', '));
}

async function assertAccessibleFileFocus(page, selector, name) {
  const focus = await page.locator(selector).evaluate(input => {
    const label = input.closest('label'), style = getComputedStyle(label);
    return {focused: document.activeElement === input, display: getComputedStyle(input).display,
      outlineStyle: style.outlineStyle, outlineWidth: parseFloat(style.outlineWidth),
      labelWidth: label.getBoundingClientRect().width};
  });
  assert(focus.focused);
  assert.notEqual(focus.display, 'none');
  assert(focus.outlineStyle !== 'none' && focus.outlineWidth >= 2 && focus.labelWidth > 20,
    'visible focus is on the label, not only on the visually hidden input');
  const cdp = await page.context().newCDPSession(page);
  try {
    const {root: document} = await cdp.send('DOM.getDocument');
    const {nodeId} = await cdp.send('DOM.querySelector', {nodeId: document.nodeId, selector});
    const {node} = await cdp.send('DOM.describeNode', {nodeId});
    const {nodes} = await cdp.send('Accessibility.getPartialAXTree', {backendNodeId: node.backendNodeId, fetchRelatives: false});
    assert(nodes.some(item => !item.ignored && item.role?.value === 'button' && item.name?.value === name),
      'native file input remains a named control in Chromium accessibility tree');
  } finally { await cdp.detach(); }
}

async function chooseFileWithKey(page, selector, key, file) {
  const [chooser] = await Promise.all([page.waitForEvent('filechooser', {timeout: 3000}), page.keyboard.press(key)]);
  assert.equal(await chooser.element().getAttribute('id'), selector.slice(1), 'the keyboard opened the intended native chooser');
  await chooser.setFiles(file);
}

async function screenshot(page, name) {
  if (process.env.WEB_TEST_SCREENSHOT_DIR) {
    fs.mkdirSync(process.env.WEB_TEST_SCREENSHOT_DIR, {recursive: true});
    await page.screenshot({path: path.join(process.env.WEB_TEST_SCREENSHOT_DIR, name), fullPage: true});
  }
}

test('UI-009: keyboard opens both native file choosers and imports their selected files', async t => {
  const {page, context} = await authenticatedPage(t);
  const response = await context.request.get(base + '/api/demo');
  assert.equal(response.status(), 200);
  const project = await response.json();
  project.id = 'review-keyboard-file';
  project.metadata.name = 'Keyboard project import';
  await page.locator('#openImport').focus();
  await page.keyboard.press('Enter');
  await tabTo(page, '#file');
  await assertAccessibleFileFocus(page, '#file', 'Projektdatei öffnen');

  await screenshot(page, 'review-project-file-focus.png');
  assert(await page.locator('#file').evaluate(input => input === document.activeElement && !input.disabled),
    'project file input remains ready after inspecting visible focus');
  const [checked] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/snapshots/check') && r.request().method() === 'POST'),
    chooseFileWithKey(page, '#file', 'Enter', {
      name: 'synthetic-project.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(project))
    })
  ]);
  assert.equal(checked.status(), 200);
  await page.waitForFunction(id => snapshot?.id === id, project.id);
  assert.equal(await page.evaluate(() => snapshot.metadata.name), project.metadata.name);
  assert.equal(await page.locator('#file').inputValue(), '', 'input resets after actual import');

  await page.locator('.main-nav [data-navigate="team"]').focus();
  await page.keyboard.press('Enter');
  await page.locator('#teamTransfer > summary').focus();
  await page.keyboard.press('Enter');
  await tabTo(page, '#teamImport', 5);
  await assertAccessibleFileFocus(page, '#teamImport', 'Bearbeitete CSV prüfen');
  await screenshot(page, 'review-team-file-focus.png');
  const before = await page.evaluate(() => structuredClone(snapshot.employees));
  const newName = "  '=Keyboard CSV;\"quote\"";
  const csv = await page.evaluate(name => {
    const edited = structuredClone(currentSnapshot()); edited.employees[0].name = name;
    return TeamTransfer.toCsv(edited);
  }, newName);
  await chooseFileWithKey(page, '#teamImport', 'Space', {
    name: 'synthetic-team.csv', mimeType: 'text/csv', buffer: Buffer.from(csv)
  });
  await page.waitForFunction(() => document.querySelector('#teamTransferPreview').textContent.includes('1 Personen zu ändern'));
  assert.match(await page.locator('#teamTransferPreview').innerText(), /0 zu korrigieren/);
  assert.deepEqual(await page.evaluate(() => snapshot.employees), before, 'CSV selection only previews, never silently applies');
  const apply = page.locator('#teamTransferPreview').getByRole('button', {name: /übernehmen/});
  await apply.focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(name => snapshot.employees[0].name === name, newName);
  const expected = structuredClone(before); expected[0].name = newName;
  assert.deepEqual(await page.evaluate(() => snapshot.employees), expected, 'actual CSV apply preserves all other settings');
  assert.equal(await page.locator('#teamImport').inputValue(), '');
});

async function assertLogoutReachable(page, width) {
  const button = page.getByRole('button', {name: 'Abmelden', exact: true});
  assert.equal(await page.locator('form[action="/logout"]').count(), 1, 'one existing native logout form, no duplicate handler');
  assert(await button.isVisible(), 'authenticated logout remains visible at ' + width + 'px');
  assert(await button.isEnabled());
  const bounds = await button.boundingBox();
  assert(bounds && bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= width,
    'logout is within the viewport, not offscreen in the navigation strip');
  assert(await button.evaluate(element => {
    const rect = element.getBoundingClientRect();
    return element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
  }), 'logout is not clipped or covered by another element');
  const layout = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    overflowing: [...document.body.querySelectorAll('*')].filter(element => {
      const rect = element.getBoundingClientRect(); return rect.width && rect.right > innerWidth;
    }).slice(0, 12).map(element => ({id: element.id, tag: element.tagName, className: element.getAttribute('class'),
      right: element.getBoundingClientRect().right, width: element.getBoundingClientRect().width}))
  }));
  assert(layout.scrollWidth <= layout.width, 'no whole-page horizontal overflow at ' + width + ': ' + JSON.stringify(layout));
  return button;
}

async function assertLogoutRevokesSession(page, context, activate) {
  const session = (await context.cookies()).find(cookie => cookie.name === 'sp5_session');
  assert(session, 'a real authenticated session exists before logout');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url() === base + '/logout' && r.request().method() === 'POST'),
    activate()
  ]);
  assert.equal((await response.request().allHeaders()).origin, base,
    'native logout must retain its same-origin Origin header instead of null');
  assert.equal(response.status(), 303, 'native form submits to the actual logout endpoint');
  await page.waitForURL(base + '/login');
  assert.equal((await context.request.get(base + '/api/version')).status(), 401, 'session cookie is gone');
  const replay = await context.request.get(base + '/api/version', {headers: {Cookie: session.name + '=' + session.value}});
  assert.equal(replay.status(), 401, 'the old server-side session is revoked, not merely hidden');
}

test('UI-010: authenticated narrow views retain keyboard and touch logout with real session revocation', async t => {
  const {page, context} = await authenticatedPage(t, {width: 390, height: 844});
  await page.evaluate(async () => load(await api('/api/demo'), true));
  for (const width of [320, 390, 768, 900, 901]) {
    await page.setViewportSize({width, height: 900});
    await assertLogoutReachable(page, width);
  }
  await page.setViewportSize({width: 320, height: 900});
  await page.locator('.main-nav [data-navigate="projects"]').focus();
  await tabTo(page, '#logout button', 15);
  assert(await page.locator('#logout button').evaluate(button => button.matches(':focus-visible')),
    'keyboard focus reaches the visible logout control');
  await screenshot(page, 'review-mobile-keyboard-logout.png');
  await assertLogoutRevokesSession(page, context, () => page.keyboard.press('Enter'));

  const touch = await authenticatedPage(t, {width: 390, height: 844}, {isMobile: true, hasTouch: true});
  await touch.page.evaluate(async () => load(await api('/api/demo'), true));
  const button = await assertLogoutReachable(touch.page, 390);
  await screenshot(touch.page, 'review-mobile-touch-logout.png');
  await assertLogoutRevokesSession(touch.page, touch.context, () => button.tap());
});

test('Existing team-transfer browser contract stays compatible with the versioned export', async t => {
  const {page} = await authenticatedPage(t);
  await require('./team-transfer.cjs')({page, base});
});
