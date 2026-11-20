import { chromium } from 'playwright';
import assert from 'node:assert/strict';

const ARTIFACT_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

async function main() {
  console.log('--- 1. Launching real Chromium browser ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  console.log('--- 2. Checking Favicon directly ---');
  const faviconRes = await page.goto('http://127.0.0.1:5173/assets/brand/favicon-64.png');
  assert.equal(faviconRes.status(), 200, 'Favicon must return 200');
  console.log('Favicon 64x64 loaded successfully with status 200!');

  console.log('--- 3. Navigating to Home ---');
  await page.goto('http://127.0.0.1:5173/');
  await page.waitForLoadState('networkidle');

  // Verify favicon link in document head
  const faviconHref = await page.$eval('link[rel~="icon"]', el => el.getAttribute('href'));
  console.log('Favicon href in index.html:', faviconHref);
  assert.equal(faviconHref, '/assets/brand/favicon-64.png');

  console.log('--- 4. Logging in as qa_user1 via /login ---');
  await page.goto('http://127.0.0.1:5173/login');
  await page.waitForSelector('#loginForm');
  await page.fill('#identifier', 'qa_user1@example.com');
  await page.fill('#password', 'QaUserPass2026!');
  await page.click('button[type="submit"]');

  // Wait for login redirection to home
  await page.waitForURL('http://127.0.0.1:5173/');
  await page.waitForTimeout(1500);

  console.log('--- 5. Checking Header Bell and Badge ---');
  const bellButton = await page.waitForSelector('.notification-trigger, #site-notifications-button', { timeout: 5000 });
  assert(bellButton, 'Notifications bell button must be visible in header');

  const unreadBadge = await page.$('.notification-badge');
  if (unreadBadge) {
    const badgeText = await unreadBadge.innerText();
    console.log(`Unread badge text in header: ${badgeText}`);
  } else {
    console.log('No unread badge (unread count is 0 or all read)');
  }

  console.log('--- 6. Clicking Notifications Bell to open popover ---');
  await bellButton.click();
  await page.waitForTimeout(1000);

  const dropdown = await page.waitForSelector('.notifications-dropdown, #site-notifications-menu', { timeout: 5000 });
  assert(dropdown, 'Notifications dropdown popover must open upon clicking bell');

  // Check items in dropdown
  const notifItems = await page.$$('.notifications-item');
  console.log(`Found ${notifItems.length} notification items in the dropdown`);

  // Take screenshot 1: Open popup with unread items
  const screenshotPath = `${ARTIFACT_DIR}/browser_bell_notifications.png`;
  await page.screenshot({ path: screenshotPath, fullPage: false });
  console.log(`Saved screenshot to: ${screenshotPath}`);

  console.log('--- 7. Clicking Mark All As Read ---');
  const markAllBtn = await page.waitForSelector('.notifications-mark-all-btn', { timeout: 3000 });
  await markAllBtn.click();
  await page.waitForTimeout(1000);

  // Take screenshot 2: After mark all read
  const screenshotPath2 = `${ARTIFACT_DIR}/browser_bell_all_read.png`;
  await page.screenshot({ path: screenshotPath2, fullPage: false });
  console.log(`Saved screenshot 2 to: ${screenshotPath2}`);

  await browser.close();
  console.log('--- BROWSER VERIFICATION COMPLETE & SUCCESSFUL! ---');
}

main().catch(err => {
  console.error('Browser check failed:', err);
  process.exit(1);
});
