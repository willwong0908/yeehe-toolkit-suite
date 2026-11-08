const transfer = (() => {
  const base = "/api/feishu-transfer";
  const drafts = new Map();
  let groups = [], selected = null, busy = false, returning = false, generation = 0;
  let prepared = null, waiting = false, cancelled = false;
  async function call(path, options = {}) {
    const response = await fetch(base + path, options);
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 401) gate(body.detail, true);
      throw new Error(body.detail || "文件传输失败");
    }
    return body;
  }
  function gate(text, login) {
    $("ftIdentity").textContent = "";
    $("ftDesk").hidden = true;
    $("ftGate").hidden = false;
    $("ftGateHint").textContent = text;
    $("ftLogin").hidden = !login;
    $("ftReload").hidden = false;
    if (login) { drafts.clear(); selected = null; groups = []; }
  }
  async function enter() {
    if (busy) return;
    const version = ++generation;
    gate("正在读取群聊…", false);
    try {
      const data = await call("/groups");
      if (version !== generation) return;
      groups = data.groups;
      $("ftIdentity").textContent = data.username ? "memoQ · "+data.username : "";
      selected = groups.find(g => g.id === selected?.id) || null;
      $("ftDesk").hidden = false; $("ftGate").hidden = true;
      render();
    } catch (error) { if (version === generation) gate(error.message, !$("ftLogin").hidden); }
  }
  const rows = () => drafts.get(selected?.id) || [];
  const eligible = r => r.state !== "已发送";
  function render() {
    const list = $("ftGroups"); list.replaceChildren();
    const matches = groups.filter(g => g.name.toLocaleLowerCase().includes($("ftSearch").value.trim().toLocaleLowerCase()));
    if (!matches.length) list.textContent = groups.length ? "未找到匹配的群聊" : "传输账号尚未加入群聊";
    for (const group of matches) {
      const btn = document.createElement("button"); btn.className = "secondary";
      btn.textContent = group.name; btn.setAttribute("aria-pressed", String(group.id === selected?.id));
      if (groups.some(g => g.id !== group.id && g.name === group.name)) {
        const detail = document.createElement("small");
        detail.textContent = [group.external ? "外部群" : "内部群",group.description || "",group.members_hint || ""].filter(Boolean).join(" · ");
        btn.append(detail);
      }
      btn.disabled = busy; btn.onclick = () => {selected = group; $("ftStatus").textContent = ""; render();}; list.append(btn);
    }
    $("ftTitle").textContent = selected?.name || "选择一个群聊";
    $("ftCompose").hidden = !selected; $("ftSender").textContent = selected ? "发送身份 · 信鸽" : "";
    const box = $("ftRows"); box.replaceChildren();
    for (const row of rows()) {
      const el = document.createElement("div"); el.className = "ft-row";
      const info = document.createElement("div"), name = document.createElement("strong"), note = document.createElement("small");
      name.textContent = row.file.name;
      note.textContent = formatSize(row.file.size) + (row.file.size > 30*1048576 ? " · 群云文档" : " · 群附件") + " · " + (row.error || row.state);
      info.append(name,note);
      if (row.state === "发送中") {
        const meter = document.createElement("progress");
        meter.className = "ft-progress"; meter.max = row.file.size; meter.value = row.uploaded || 0;
        meter.setAttribute("aria-label", name.textContent + "上传进度");
        const detail = document.createElement("small");
        const amount = row.uploaded || 0;
        detail.textContent = row.phase === "finalizing" ? "上传完成，正在处理并发送…" :
          "已上传 " + formatSize(amount) + " / " + formatSize(row.file.size) + " · " +
          (amount / row.file.size * 100).toFixed(1) + "% · " + (row.speed ? formatSize(row.speed) + "/s" : "计算速率中");
        info.append(meter, detail);
      }
      el.append(info);
      if (!busy) {
        const remove = document.createElement("button"); remove.className = "secondary"; remove.textContent = "移除";
        remove.setAttribute("aria-label","移除 " + row.file.name);
        remove.onclick = () => { drafts.set(selected.id,rows().filter(r=>r!==row)); render(); }; el.append(remove);
      }
      box.append(el);
    }
    const pending = rows().filter(eligible);
    $("ftCount").textContent = rows().length ? "共 " + rows().length + " 个文件" : "";
    $("ftSend").disabled = busy || !pending.length; $("ftRefresh").disabled = busy; $("ftPick").disabled = busy;
    $("ftSend").textContent = pending.length ? (pending.every(r=>r.error) ? "重试失败文件" : "发送 " + pending.length + " 个文件") : "发送文件";
  }
  function formatSize(bytes) {return bytes < 1048576 ? Math.ceil(bytes/1024)+" KB" : (bytes/1048576).toFixed(1)+" MB";}
  function add(files) {
    if (!selected || busy) return;
    const batch = rows().slice(), messages = [];
    for (const f of files) {
      if (!f.size) {messages.push(f.name+"：不能发送空文件"); continue;}
      if (batch.some(r=>r.file.name===f.name && r.file.size===f.size && r.file.lastModified===f.lastModified)) continue;
      batch.push({file:f, id:crypto.randomUUID(), state:"待发送"});
    }
    drafts.set(selected.id,batch); $("ftStatus").textContent = messages.join("；"); render();
  }
  function progress(msg) {
    $("ftStatus").textContent = msg;
    setTaskStatus("feishuTransferPage",{taskLabel:"飞书文件传输",stageLabel:msg,pill:busy?"进行中":"就绪",message:msg,active:busy});
    if (currentPageId==="feishuTransferPage") renderCurrentTaskStatus();
  }
  async function confirm() {
    if (busy || !selected) return;
    prepared = {group:selected, files:rows().filter(eligible)};
    if (!prepared.files.length) return;
    busy = true; render();
    try {
      const result = await call("/groups/"+selected.id+"/membership");
      $("ftConfirmTitle").textContent = "发送到「"+prepared.group.name+"」？";
      $("ftConfirmBody").textContent = "将由信鸽发送 "+prepared.files.length+" 个文件。"+(prepared.files.some(r=>r.file.size>30*1048576)?"大文件将追加到本群云文档，由信鸽发送链接。":"")+(result.member?"":"确认后会先邀请信鸽加入该群。");
      $("ftConfirm").showModal();
    } catch (e) {busy=false; progress(e.message); render();}
  }
  async function send() {
    const {group,files} = prepared, path = "/groups/"+group.id;
    cancelled=false;
    $("ftConfirm").close("send");
    let finalMessage = "";
    try {
      progress("正在确认信鸽入群…");
      let status = await call(path+"/prepare",{method:"POST"});
      while (!status.ready) {
        waiting=true; $("ftStop").hidden=false;
        progress(status.pending ? "等待群管理员批准入群…" : "正在等待飞书确认入群…");
        await new Promise(resolve=>setTimeout(resolve,10000));
        if (cancelled) throw new Error("已停止等待，文件仍在待发送列表中");
        const membership = await call(path+"/membership");
        status = {...status, ready:membership.member};
      }
      waiting=false; $("ftStop").hidden=true;
      for (const [i,row] of files.entries()) {
        row.state="发送中"; row.error=""; row.uploaded=0; row.speed=0; row.phase="uploading"; render();
        progress("正在发送第 "+(i+1)+" 个文件，共 "+files.length+" 个");
        try {
          let polling = true;
          const poll = async () => {
            while (polling) {
              await new Promise(resolve=>setTimeout(resolve, 800));
              if (!polling) break;
              try {
                const state = await call("/progress/"+row.id);
                if (state.state !== "waiting") {
                  row.uploaded=state.uploaded; row.speed=state.speed; row.phase=state.state;
                  if (currentPageId === "feishuTransferPage") render();
                }
              } catch (_) {}
            }
          };
          poll();
          let reply;
          try { reply = await call(path+"/files/"+row.id+"?filename="+encodeURIComponent(row.file.name),{method:"PUT",body:row.file}); }
          finally { polling=false; }
          if (!reply.message_id) throw new Error("未收到飞书回执");
          row.state="已发送";
        } catch (e) {row.state="发送失败"; row.error="发送失败 · "+e.message; if ($("ftDesk").hidden) break;}
      }
      finalMessage = "本次已发送 "+files.filter(r=>r.state==="已发送").length+" / "+files.length+" 个文件";
    } catch(e) {finalMessage = e.message;}
    finally {waiting=false; $("ftStop").hidden=true; busy=false; progress(finalMessage); render();}
  }
  $("ftStop").onclick=()=>{if (waiting) {cancelled=true; progress("正在停止等待…");}};
  $("ftLogin").onclick = () => {returning=true;setPage("modelSettingsPage");$("memoqUsername").focus();};
  $("ftReload").onclick = $("ftRefresh").onclick = enter;
  $("ftSearch").oninput=render;
  $("ftPick").onclick=()=>$("ftInput").click();
  $("ftInput").onchange=e=>{add(e.target.files);e.target.value="";};
  for(const event of ["dragover","dragleave","drop"]) $("ftDrop").addEventListener(event,e=>{
    e.preventDefault(); $("ftDrop").classList.toggle("dragging",event==="dragover" && !busy);
    if(event==="drop") add(e.dataTransfer.files);
  });
  $("ftSend").onclick=confirm;
  $("ftCancel").onclick=()=>$("ftConfirm").close("cancel");
  $("ftConfirm").addEventListener("close",()=>{if ($("ftConfirm").returnValue!=="send"){busy=false;render();} $("ftConfirm").returnValue="";});
  $("ftAccept").onclick=send;
  return {enter,afterLogin(){if(returning){returning=false;setPage("feishuTransferPage");}},logout(){generation++;drafts.clear();selected=null;groups=[];gate("请先登录 memoQ",true);}};
})();

