// Browser regression using simulated group membership and send responses.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    let signedIn = false, attempts = 0, failedId = "";
    const groups = [{id:"oc_a",name:"交付一组"},{id:"oc_b",name:"交付二组"}];
    await page.route("**/api/feishu-transfer/**", async route => {
      const url = new URL(route.request().url());
      let json = {}, status = 200;
      if (!signedIn) {json={detail:"请先登录公司 memoQ 账号"}; status=401;}
      else if (url.pathname.endsWith("/groups")) json={groups};
      else if (url.pathname.endsWith("/membership")) json={member:false};
      else if (url.pathname.endsWith("/prepare")) json={ready:true};
      else if (url.pathname.includes("/files/")) {
        attempts++;
        assert(url.pathname.includes("oc_a"));
        if(attempts===2){status=409;json={detail:"模拟失败"};failedId=url.pathname;}
        else {if(attempts===3)assert.equal(url.pathname,failedId);json={message_id:"ok"};}
      }
      await route.fulfill({status,json});
    });
    await page.goto(process.env.YEEHE_UI_QA_URL || "http://127.0.0.1:8897");
    await page.locator('[data-page-target="feishuTransferPage"]').click();
    await page.locator("#ftLogin").waitFor({state:"visible"});
    signedIn=true; await page.locator("#ftReload").click();
    await page.getByRole("button",{name:"交付一组"}).click();
    await page.locator("#ftInput").setInputFiles([{name:"第一份.txt",mimeType:"text/plain",buffer:Buffer.from("a")}]);
    await page.locator("#ftDrop").evaluate(el=>{
      const dt=new DataTransfer();dt.items.add(new File(["b"],"第二份.txt",{type:"text/plain"}));
      el.dispatchEvent(new DragEvent("drop",{dataTransfer:dt,bubbles:true,cancelable:true}));
    });
    await page.getByRole("button",{name:"交付二组"}).click();
    assert.equal(await page.locator(".ft-row").count(),0);
    await page.getByRole("button",{name:"交付一组"}).click();
    assert.equal(await page.locator(".ft-row").count(),2);
    await page.locator("#ftSend").click();
    await page.locator("#ftConfirm[open]").waitFor();
    assert.match(await page.locator("#ftConfirmBody").textContent(),/邀请信鸽/);
    await page.locator("#ftCancel").click(); assert.equal(attempts,0);
    await page.locator("#ftSend").click(); await page.locator("#ftAccept").click();
    await page.getByRole("button",{name:"重试失败文件"}).waitFor();
    await page.locator("#ftSend").click(); await page.locator("#ftAccept").click();
    await page.waitForFunction(()=>document.querySelectorAll("#ftRows small").length===2 &&
      [...document.querySelectorAll("#ftRows small")].every(x=>x.textContent.includes("已发送")));
    assert.equal(attempts,3);assert.deepEqual(errors,[]);
    console.log("Passed: login gate, multi-file picker/drop, group drafts, confirmation, receipts and idempotent retry.");
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
