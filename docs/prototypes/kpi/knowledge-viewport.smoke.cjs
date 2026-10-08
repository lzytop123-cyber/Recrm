const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
let browser;
(async () => {
  browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const url = pathToFileURL(path.join(__dirname, 'frontend.html')).href;
  async function fits(label) {
    const dimensions = await page.evaluate(() => {
      const pager = document.querySelector('.kb-pager').getBoundingClientRect();
      const rows = [...document.querySelectorAll('[data-document-id]')].map(node => node.getBoundingClientRect());
      const scrollers = [...document.querySelectorAll('.kb-shell, .kb-workspace, .kb-directory, .kb-dir-list, .kb-global-nav, .kb-library, .kb-results, .kb-table-wrap, .kb-cards')]
        .filter(node => node.getClientRects().length && (node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1)).map(node => node.className);
      return { height: innerHeight, width: innerWidth, scrollHeight: document.documentElement.scrollHeight, scrollWidth: document.documentElement.scrollWidth,
        pagerTop: pager.top, pagerBottom: pager.bottom, rows: rows.map(row => ({ top: row.top, bottom: row.bottom, right: row.right })), scrollers };
    });
    assert.ok(dimensions.scrollHeight <= dimensions.height + 1, label + ' page vertical overflow: ' + JSON.stringify(dimensions));
    assert.ok(dimensions.scrollWidth <= dimensions.width + 1, label + ' page horizontal overflow');
    assert.ok(dimensions.pagerBottom <= dimensions.height && dimensions.pagerTop >= 0, label + ' pagination outside viewport');
    assert.ok(dimensions.rows.every(row => row.bottom <= dimensions.pagerTop + 1 && row.top >= 0 && row.right <= dimensions.width), label + ' documents clipped');
    assert.deepEqual(dimensions.scrollers, [], label + ' nested scrolling or hidden overflow');
  }
  for (const [name, width, height] of [['desktop', 1920, 919], ['laptop', 1366, 768], ['tablet', 820, 1000], ['mobile', 390, 844], ['short-mobile', 390, 667]]) {
    await page.setViewportSize({ width, height });
    await page.goto(url);
    await page.locator('[data-document-id]').first().waitFor();
    if (name === 'desktop' || name === 'laptop') {
      assert.equal(await page.locator('[data-document-id]').count(), 10, name + ' displays ten documents');
    }
    await fits(name);
    await page.screenshot({ path: path.join(__dirname, 'knowledge-one-screen-' + name + '.png') });
    const seen = new Set();
    for (let i = 0; i < 30; i++) {
      await fits(name + ' page ' + (i + 1));
      for (const id of await page.locator('[data-document-id]').evaluateAll(rows => rows.map(row => row.dataset.documentId))) seen.add(id);
      const next = page.getByRole('button', { name: '下一页', exact: true });
      if (await next.isDisabled()) break;
      await next.click();
    }
    assert.equal(seen.size, 22, name + ' all documents remain reachable');
    await page.getByRole('navigation', { name: '知识库页面' }).getByRole('button', { name: /^审核管理/ }).click();
    await fits(name + ' audit');
    if (width > 700) {
      await page.getByRole('button', { name: '卡片视图', exact: true }).click();
      await fits(name + ' cards');
    }
    console.log(name + ': one-screen layout, all-document pagination and audit/cards passed');
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(url);
  await page.getByRole('button', { name: '下一页', exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.waitForTimeout(100);
  await fits('resize');
  assert.deepEqual(errors, []);
  await browser.close();
})().catch(async error => { console.error(error); await browser?.close(); process.exitCode = 1; });
