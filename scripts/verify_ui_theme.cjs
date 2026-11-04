/* Visual contract checks against a running isolated toolkit host. No model calls or settings writes. */
const { chromium } = require('playwright');
const base = process.env.YEEHE_UI_QA_URL || 'http://127.0.0.1:8895/';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1748, height: 1050 }, reducedMotion: 'reduce' });
  const failures = [], errors = []; let checked = 0;
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base); await page.waitForTimeout(300);
  const ids = await page.locator('[data-page-target]').evaluateAll(nodes => nodes.map(n => n.dataset.pageTarget));
  for (const theme of ['dark', 'light']) {
    await page.evaluate(value => document.documentElement.classList.toggle('light-theme', value === 'light'), theme);
    for (const id of ids) {
      await page.locator('details').evaluateAll(nodes => nodes.forEach(n => n.open = true));
      await page.locator(`[data-page-target="${id}"]`).click();
      await page.waitForTimeout(150);
      const result = await page.locator(`#${id}`).evaluate(root => {
        const failures = []; let checked = 0;
        const rgb = value => (value.match(/[\d.]+/g) || []).map(Number);
        const luminance = color => color.slice(0, 3).map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((s,v,i) => s + v * [.2126,.7152,.0722][i], 0);
        for (const el of root.querySelectorAll('*')) {
          if (!el.checkVisibility() || el.closest(':disabled') || ['SVG','PATH','OPTION'].includes(el.tagName)) continue;
          if (![...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())) continue;
          const style = getComputedStyle(el); const color = rgb(style.color);
          let bg = null;
          for (let p = el; p; p = p.parentElement) { const c = rgb(getComputedStyle(p).backgroundColor); if (c.length >= 3 && (c.length === 3 || c[3] >= .99)) { bg = c; break; } }
          if (!bg || color.length < 3) continue;
          checked++;
          const a = luminance(color), b = luminance(bg), ratio = (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
          const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && +style.fontWeight >= 700);
          if (ratio < (large ? 3 : 4.5)) failures.push({text:el.textContent.trim().slice(0,45),element:el.tagName+'.'+el.className,ratio:+ratio.toFixed(2)});
        }
        for (const el of root.querySelectorAll('.tool-guide-card,.preprocess-progress-overview>div,.preprocess-progress-metrics>div,.preprocess-events')) {
          const c = rgb(getComputedStyle(el).backgroundColor);
          if (Math.max(...c.slice(0,3))-Math.min(...c.slice(0,3)) > 5) failures.push({element:el.className,issue:'Non-neutral structural surface'});
        }
        return {checked,failures};
      });
      checked += result.checked; failures.push(...result.failures.map(f => ({theme,page:id,...f})));
    }
  }
  await browser.close();
  console.log(JSON.stringify({pages:ids.length,themes:2,textChecks:checked,failures,errors},null,2));
  if (failures.length || errors.length) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
