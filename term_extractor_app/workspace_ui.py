"""Shared toolkit design tokens, component roles and per-column language selection."""
THEME_CSS = r'''

/* One semantic palette for every toolkit page, state and dialog. */
:root {
  color-scheme: dark;
  --font-ui: "Segoe UI", "Microsoft YaHei UI", sans-serif;
  --bg:#212121; --panel:#252525; --panel-soft:#2c2c2c; --sidebar-bg:#191919;
  --ink:#ededed; --text:var(--ink); --muted:#adadad;
  --line:#424242; --line-strong:#707070;
  --primary:#ededed; --primary-strong:#fff; --button-ink:#202020;
  --selected-bg:#383838; --selected-border:#888;
  --danger:#f2a29c; --danger-bg:#372827; --danger-line:#77504d;
  --success:#9bceae; --success-bg:#26362c; --success-line:#4a7057;
  --warning:#dfc48b; --warning-bg:#393225; --warning-line:#776441;
  --focus:#6393bd; --selection:#b6d4ed;
  --radius-sm:6px; --radius-md:8px; --radius-lg:12px;
  --shadow:0 18px 50px #0004;
  --surface-inset:var(--panel-soft); --surface-raised:var(--panel); --surface-hover:var(--selected-bg);
  --panel-solid:var(--panel); --panel-subtle:var(--panel-soft); --primary-soft:var(--selected-bg);
  --selected-line:var(--selected-border); --accent:var(--ink);
  --glass:var(--panel); --glass-strong:var(--panel); --glass-border:var(--line);
}
html.light-theme {
  color-scheme:light;
  --bg:#fff; --panel:#fff; --panel-soft:#f6f6f5; --sidebar-bg:#f6f6f5;
  --ink:#252525; --muted:#666; --line:#dededb; --line-strong:#999;
  --primary:#262626; --primary-strong:#111; --button-ink:#fff;
  --selected-bg:#eeedeb; --selected-border:#888;
  --danger:#a52e29; --danger-bg:#fbefed; --danger-line:#dcb6b3;
  --success:#28623e; --success-bg:#eef6f0; --success-line:#b7d1c0;
  --warning:#775315; --warning-bg:#faf4e7; --warning-line:#dcc995;
}
html:root body{background:var(--bg);color:var(--ink);font-family:var(--font-ui);font-size:14px;line-height:1.5}
html:root body::before,html:root body::after,html:root button::before{display:none}
html:root .shell{grid-template-columns:222px minmax(0,1fr)}
html:root .sidebar{background:var(--sidebar-bg);padding:24px 16px;box-shadow:none}
html:root .brand{margin:0 8px 24px}html:root .brand strong{font-size:18px;font-weight:600}
html:root .brand-mark{background:var(--panel);border-color:var(--line);box-shadow:none;border-radius:8px}
html:root .brand-version,html:root .brand small{color:var(--muted);background:transparent}
html:root .main{background:var(--bg);padding:28px 32px;min-width:0}
html:root .hero{background:none;box-shadow:none;padding:0 0 20px;margin-bottom:22px;border-color:var(--line)}
html:root .hero h1{font-size:27px;font-weight:600;letter-spacing:-.02em}
html:root .hero-context,html:root .hero .eyebrow,html:root .hero-topline{display:none}
html:root .lede{color:var(--muted);font-size:14px}
html:root :is(.sidebar-nav,.nav-group,.nav-accordion,.nav-accordion[open],.sidebar-footer){background:transparent;box-shadow:none;border-color:var(--line)}
html:root .nav-accordion{border:0}
html:root .nav-link,html:root .nav-accordion-summary{color:var(--ink);background:transparent;border:0;border-radius:8px;font-weight:400}
html:root .nav-link.active,html:root .nav-link:hover,html:root .nav-accordion-summary:hover{background:var(--selected-bg);color:var(--ink);box-shadow:none}
/* Neutral is the default action. Only explicit primary actions receive an inverse fill. */
html:root body button{font-family:var(--font-ui);font-size:13px;font-weight:500;min-height:36px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);box-shadow:none;transform:none;transition:background-color .12s,border-color .12s}
html:root body button:hover:not(:disabled){background:var(--selected-bg);border-color:var(--line-strong);color:var(--ink);box-shadow:none;transform:none}
html:root body button.primary{background:var(--primary);border-color:var(--primary);color:var(--button-ink)}
html:root body button.primary:hover:not(:disabled){background:var(--primary-strong);border-color:var(--primary-strong);color:var(--button-ink)}
html:root body button.primary :where(*){color:inherit}
html:root body :is(button.danger,button.danger-text,.scope-delete){background:var(--panel);color:var(--danger);border-color:var(--danger-line)}
html:root body :is(button.danger,button.danger-text,.scope-delete):hover:not(:disabled){background:var(--danger-bg);color:var(--danger)}
html:root body :is(button.active,button.selected,button[aria-pressed=true]){background:var(--selected-bg);border-color:var(--selected-border);color:var(--ink)}
html:root body :is(button.nav-link,button.review-session-item,button.review-session-rename,button.review-attachment-open,button.review-attachment-remove){background:transparent;border:0;color:var(--ink)}
html:root body button.nav-link.active{background:var(--selected-bg)}
html:root body :is(.theme-toggle-button,.feedback-entry-button){background:transparent;color:var(--ink);border-color:var(--line)}
html:root body :is(input,select,textarea){font-family:var(--font-ui);font-size:13px;border-color:var(--line-strong);border-radius:8px;background:var(--panel);color:var(--ink);box-shadow:none;caret-color:var(--ink);min-width:0}
html:root body :is(input,select){min-height:36px}
html:root body :is(input,textarea)::placeholder{color:var(--muted);opacity:1}
html:root body :is(input[type=checkbox],input[type=radio]){min-height:16px;width:16px;height:16px;accent-color:var(--primary);flex:0 0 auto}
html:root body :is(input[type=range],input[type=color]){min-height:28px}
html:root body :is(button,input,select,textarea):disabled{color:var(--muted)!important;background:var(--panel-soft)!important;border-color:var(--line)!important;opacity:.65;cursor:not-allowed;box-shadow:none}
html:root body :is(button,input,select,textarea,summary,a):focus-visible{outline:2px solid var(--focus);outline-offset:3px;box-shadow:none}
html:root :is(.card,.advanced-card,.stats-panel,.stage-panel,.result-box,.file-card,.review-result-preview,.review-detail-group,.cross-file-card,.diff-file-card){background:var(--panel);border-color:var(--line);border-radius:12px;box-shadow:none}
html:root :is(.card,.compact-card){padding:22px}
html:root :is(.card-title h2,.card-title h3,.section-header h2){font-size:17px;font-weight:600;color:var(--ink)}
html:root :is(.card-title p,.section-header p,.hint,label,.field-label,.stats-title){color:var(--muted)}
html:root :is(.check-line,.check){background:transparent;border-color:var(--line);color:var(--ink);border-radius:8px}
html:root :is(.inline-notice,.sticky-actions,.summary-line,.metrics>div,.compact-metrics>div,.result-file,.prompt-card,.scope-card,.cross-summary-box,.cross-result-card,.review-request-queue,.review-request-lane,.review-request-item,.preprocess-progress-overview>div,.preprocess-progress-metrics>div,.preprocess-events,.feedback-attachment-card,.feedback-log-card,.update-release-notes){background:var(--panel-soft);border-color:var(--line);color:var(--ink);box-shadow:none;border-radius:8px}
html:root :is(.inline-notice-icon,.tool-guide-arrow,.mapping-col-id,.review-language-check,.review-term-base-option-check){color:var(--ink)}
html:root :is(.metrics span,.result-file span,.result-file small,.prompt-card small,.cross-summary-box span,.cross-summary-box small,.preprocess-progress-overview span,.preprocess-progress-metrics span,.preprocess-events-head span,.preprocess-event,.preprocess-events-empty,.review-request-queue-head span,.review-request-item span,.review-request-more,.review-request-empty){color:var(--muted)}
html:root :is(.metrics strong,.compact-metrics strong,.preprocess-progress-overview strong,.preprocess-progress-metrics strong,.preprocess-events-head strong,.review-request-item strong){color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
html:root :is(.preprocess-progress-overview,.preprocess-events-head,.review-request-queue-head,.review-request-lane-head,.cross-result-meta){background:var(--panel-soft);color:var(--ink);border-color:var(--line)}
html:root .preprocess-progress-overview>div{border-radius:0}
html:root :is(.progress,.progress-track,.progress-bar-wrap,.preprocess-progress-track,.review-learning-progress-track){background:var(--line);border-radius:6px}
html:root :is(.progress>span,.progress-fill,.progress-bar,.preprocess-progress-fill,.review-learning-progress-track>span){background:var(--ink);box-shadow:none;transition:none}
html:root .preprocess-event.is-latest{background:var(--selected-bg);color:var(--ink)}
html:root .preprocess-event-marker{background:var(--muted);box-shadow:none}
html:root :is(.pill,.sidebar-local-badge,.preprocess-status-pill,.prompt-badge,.tool-guide-badge,.review-workspace-total,.review-workspace-language,.summary-line span,.cross-result-meta span){background:var(--panel-soft);color:var(--muted)!important;border-color:var(--line);border-radius:6px;box-shadow:none}
/* Large navigation cards are surfaces, never inverse action buttons. */
html:root body .tool-guide-card{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:12px;text-align:left;padding:24px;box-shadow:none;min-height:180px;align-items:stretch;justify-content:stretch;justify-items:stretch}
html:root body .tool-guide-card:hover,html:root body .tool-guide-card:focus-visible{background:var(--panel-soft);border-color:var(--line-strong);color:var(--ink);transform:none}
html:root .tool-guide-card :is(strong,.tool-guide-icon,.tool-guide-arrow){color:var(--ink)}
html:root .tool-guide-card :is(small,.tool-guide-card-footer,.tool-guide-badge){color:var(--muted)}
html:root .tool-guide-icon{background:var(--panel-soft);border-color:var(--line);box-shadow:none;border-radius:8px}
html:root .tool-guide-card-footer{border-color:var(--line)}
html:root :is(.pattern-table-wrap,.review-input-table-wrap,.review-result-table-wrap,.review-detail-table-wrap,.diff-preview-table-wrap){background:var(--panel);border-color:var(--line);box-shadow:none;border-radius:8px}
html:root :is(table,th,td){border-color:var(--line);color:var(--ink)}
html:root th{background:var(--panel-soft);color:var(--muted);font-weight:600}
html:root tbody tr:hover{background:var(--panel-soft)}
html:root :is(.log-box,pre,.review-stream-output,.review-thinking-details,.followup-message.assistant){background:var(--panel-soft);color:var(--ink);border-color:var(--line);box-shadow:none}
/* Conversation, generated previews and learning cards share the same surface family. */
html:root .review-conversation-shell{border:0;grid-template-columns:190px minmax(0,1fr);gap:0;background:var(--bg);box-shadow:none}
html:root .review-session-sidebar{background:var(--sidebar-bg);padding:16px;border:0;border-right:1px solid var(--line);border-radius:0}
html:root .review-session-row{border:0;background:transparent;box-shadow:none}
html:root .review-session-row.active,html:root .review-session-row:hover{background:var(--selected-bg);box-shadow:none}
html:root .review-conversation-main{background:var(--bg)}
html:root .review-conversation-head{background:transparent;border-color:var(--line);padding:16px 24px}
html:root .review-conversation-head h3{color:var(--ink)}html:root .review-conversation-head p{color:var(--muted)}
html:root .review-conversation-messages{padding:24px clamp(18px,5%,64px)}
html:root .review-chat-message{background:transparent;color:var(--ink);border:0;box-shadow:none}
html:root :is(.review-chat-message.user,.followup-message.user){background:var(--panel-soft);border-radius:12px;color:var(--ink);border:0}
html:root .review-chat-message.workspace-report{background:var(--panel);border:1px solid var(--line);border-radius:12px}
html:root :is(.review-workspace-preview,.review-workspace-file-card,.review-workspace-endpoint,.review-workspace-note,.review-workspace-sample,.review-learning-question,.review-memory-rule,.review-followup-context,.review-followup-messages){background:var(--panel);border-color:var(--line);color:var(--ink);box-shadow:none;border-radius:8px}
html:root :is(.review-workspace-sample-source,.review-workspace-sample-target){border-color:var(--line-strong);color:var(--ink)}
html:root :is(.review-workspace-file-icon,.review-mapping-file-icon,.review-import-mode-icon,.review-term-base-action-icon,.review-message-file){background:var(--panel-soft);color:var(--ink);border-color:var(--line);box-shadow:none}
html:root .review-composer{background:var(--panel);border:1px solid var(--line-strong);box-shadow:none;border-radius:14px;margin:10px clamp(18px,5%,64px) 20px;padding:14px}
html:root .review-composer textarea{background:transparent;border:0;color:var(--ink)}
html:root .review-composer.dragging{background:var(--selected-bg);border-color:var(--selected-border)}
html:root :is(.composer-chip,.review-attachment-chip,.sheet-tab,.review-target-tab){font-size:12px;background:var(--panel);color:var(--ink);border-color:var(--line);border-radius:8px;max-width:100%;overflow-wrap:anywhere}
/* Every native dialog and overlay uses the same title, content and action treatment. */
html:root :is(dialog.modal,dialog.dialog){position:fixed;inset:0;margin:auto;width:min(760px,calc(100vw - 32px));max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px);padding:0;border:0;background:transparent;overflow:auto;color:var(--ink)}
html:root dialog.wide-dialog{width:min(1120px,calc(100vw - 32px))}html:root dialog.compact-dialog{width:min(460px,calc(100vw - 32px))}html:root #reviewAttachmentMappingDialog{width:min(640px,calc(100vw - 32px))}
html:root .modal-overlay,html:root dialog::backdrop{background:#0006;backdrop-filter:none}
html:root .modal-overlay{display:grid;place-items:center;padding:16px}html:root .modal-overlay[hidden]{display:none}
html:root :is(.modal-card,.dialog-body,.tool-guide-dialog .dialog-card){background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);max-width:100%}
html:root dialog :is(.modal-card,.dialog-body,.dialog-card){width:100%;max-height:calc(100dvh - 32px);margin:0;overflow:auto}
html:root :is(.modal-header,.dialog-head,.dialog-header,.dialog-actions,.modal-footer){background:transparent;border-color:var(--line)}
html:root :is(.modal-header h3,.dialog-head h2,.dialog-header h3,.review-mapping-file-copy h2){color:var(--ink);font-size:21px;font-weight:600}
html:root :is(.modal-header p,.dialog-head p,.review-mapping-lead,.review-mapping-preset-panel>small){color:var(--muted)}
html:root .review-mapping-file-copy h2{white-space:normal;overflow-wrap:anywhere}
html:root :is(.dialog-kicker,.review-mapping-file-copy>span){color:var(--muted)}
html:root :is(.review-language-popover,.review-term-base-popover){background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);color:var(--ink)}
html:root :is(.review-language-option,.review-term-base-action,.review-term-base-option){color:var(--ink);background:transparent;border-color:var(--line);border-radius:8px}
html:root :is(.review-language-option,.review-term-base-option):is(:hover,.selected){background:var(--selected-bg);color:var(--ink)}
html:root :is(.review-language-search-wrap,.review-language-popover-head span,.review-term-base-option small){color:var(--muted)}
html:root :is(.review-import-mode-option,.review-mapping-preset-panel,.mapping-template-bar){background:var(--panel-soft);border-color:var(--line);color:var(--ink);box-shadow:none;border-radius:8px}
html:root .review-import-mode-option.selected{background:var(--selected-bg);border-color:var(--selected-border)}
html:root .review-import-mode-option>i{background:var(--primary);color:var(--button-ink)}
html:root .review-import-mode-option strong{color:var(--ink)}html:root .review-import-mode-option small{color:var(--muted)}
html:root .review-import-mode-option strong em{background:var(--panel);color:var(--muted);border-radius:4px}
html:root .mapping-row{grid-template-columns:32px minmax(120px,1fr) 75px minmax(135px,1fr) minmax(135px,1fr) 100px;align-items:center;padding:12px 0;gap:10px;background:transparent;border-radius:0;border:0;border-bottom:1px solid var(--line)}
html:root .mapping-column-language{grid-column:3/-1;justify-self:start;width:auto;max-width:100%;overflow-wrap:anywhere}
html:root .mapping-header{color:var(--ink);font-weight:600}
html:root .column-language-options{display:grid;grid-template-columns:1fr 1fr;gap:6px;max-height:300px;overflow:auto}
html:root .column-language-options button{text-align:left}html:root .column-language-search{width:100%}
.custom-language-action{grid-column:1/-1;white-space:normal;overflow-wrap:anywhere;text-align:left}
html:root .tool-guide-dialog :is(.markdown-guide,.markdown-guide h4,.markdown-guide p,.markdown-guide ul,.markdown-guide ol){background:transparent;color:var(--ink)}
html:root .tool-guide-dialog .markdown-guide code{background:var(--panel-soft);color:var(--ink)}
html:root :is(.feedback-dropzone,.update-leaving-card){background:var(--panel-soft);color:var(--ink);border-color:var(--line);box-shadow:none}
html:root .feedback-dropzone:hover{background:var(--selected-bg);border-color:var(--line-strong)}
/* Semantic color is reserved for task states and actual text differences. */
html:root :is(.pill.failed,.preprocess-status-pill.is-failed,.error-panel,.diff-inline-delete){background:var(--danger-bg);color:var(--danger)!important;border-color:var(--danger-line)}
html:root :is(.pill.completed,.preprocess-status-pill.is-completed,.diff-inline-add){background:var(--success-bg);color:var(--success)!important;border-color:var(--success-line)}
html:root :is(.pill.running,.preprocess-status-pill.is-paused,.prompt-badge.modified,.cross-cell.matched){background:var(--warning-bg);color:var(--warning)!important;border-color:var(--warning-line)}
html:root :is(.preprocess-status-pill.is-running,.preprocess-file-item.active){background:var(--selected-bg);border-color:var(--selected-border);color:var(--ink)!important}
html:root :is(.diff-token-delete,.diff-inline-delete .diff-inline-label,.inline-task-hint.is-error,.review-log-list li.error){color:var(--danger)}
html:root :is(.diff-token-add,.diff-inline-add .diff-inline-label){color:var(--success)}
html:root .review-request-item em{color:var(--warning)}
html:root .diff-inline-text{color:var(--ink)}
html:root .diff-token-delete{background:var(--danger-bg)}html:root .diff-token-add{background:var(--success-bg)}
html:root body .preset-color-btn{min-height:24px;border:2px solid var(--line-strong);border-radius:6px}
html:root ::selection{background:var(--selection);color:#111}
html:root *{scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}
html:root *::-webkit-scrollbar-thumb{background:var(--line-strong);border-color:transparent}
@media(max-width:1100px){html:root .shell{grid-template-columns:190px minmax(0,1fr)}html:root .main{padding:22px}html:root .review-conversation-shell{grid-template-columns:160px minmax(0,1fr)}html:root .mapping-row{grid-template-columns:28px 1fr 75px}html:root .mapping-column-language{grid-column:2/-1}}
@media(max-width:760px){html:root .shell{grid-template-columns:1fr}html:root .main{padding:18px 14px}html:root .sidebar{position:static;width:100%;padding:16px}html:root .review-conversation-shell{grid-template-columns:1fr}html:root .review-session-sidebar{max-height:170px;border-right:0;border-bottom:1px solid var(--line)}html:root .review-conversation-messages{padding:18px 14px}html:root .review-composer{margin:10px 12px 16px}html:root .review-conversation-head{padding:14px}html:root .dialog-body{padding:18px}html:root .review-import-mode-grid,html:root .review-mapping-preset-row,html:root .mapping-default-languages{grid-template-columns:1fr}html:root .dialog-actions,html:root .modal-footer{flex-wrap:wrap}html:root .mapping-template-bar{grid-template-columns:1fr auto}html:root .mapping-template-bar label{grid-column:1/-1}html:root .mapping-row{grid-template-columns:28px minmax(80px,1fr) 75px}html:root .mapping-row .mapping-target,html:root .mapping-row .mapping-info,html:root .mapping-row .mapping-info-category,html:root .mapping-column-language{grid-column:2/-1}}

html:root .mapping-row.preprocess-column-row{grid-template-columns:32px minmax(0,1fr) auto}
html:root .preprocess-progress-stage,html:root .preprocess-progress-percent{border-color:var(--line)}
@media(max-width:1100px){html:root .preprocess-task-grid{grid-template-columns:1fr;gap:20px}}
@media(max-width:760px){
  html:root .grid.two,html:root .preprocess-task-grid{grid-template-columns:minmax(0,1fr)}
  html:root .preprocess-file-list{grid-template-columns:minmax(0,1fr)}
  html:root .secret-field{grid-template-columns:minmax(0,1fr);width:100%}
  html:root .secret-field>*{width:100%;min-width:0}
  html:root .review-conversation-list{display:grid;grid-template-columns:minmax(0,1fr);grid-auto-flow:row;overflow:auto;max-height:110px;gap:4px}
  html:root .review-session-row{grid-template-columns:minmax(0,1fr) 32px;min-width:0;width:100%}
  html:root .review-session-item{min-width:0}
  html:root .review-session-sidebar{overflow:auto;max-height:200px}
  html:root .review-request-columns{grid-template-columns:1fr}
  html:root .review-memory-example{grid-template-columns:1fr}
  html:root .modal-card{max-width:calc(100vw - 32px)}
}

@media(prefers-reduced-motion:reduce){html:root *{animation:none!important;transition:none!important}}

'''

LANGUAGE_JS = r'''
function openColumnLanguageDialog(sheetName, columnIndex) {
  let dialog = document.getElementById('columnLanguageDialog');
  if (!dialog) {
    dialog = document.createElement('dialog'); dialog.id = 'columnLanguageDialog'; dialog.className = 'dialog compact-dialog';
    dialog.setAttribute('aria-labelledby', 'columnLanguageTitle');
    dialog.innerHTML = `<form method="dialog" class="dialog-body"><div class="dialog-head"><div><h2 id="columnLanguageTitle">设置语种</h2><p>自动检测、选择已有语种，或输入自定义名称。</p></div><button class="secondary" value="cancel" aria-label="关闭">×</button></div><input class="column-language-search" aria-label="搜索或输入自定义语种" placeholder="搜索或输入自定义语种"><div class="column-language-options"></div><p class="hint" aria-live="polite"></p><div class="dialog-actions"><button class="primary column-language-apply" type="button">确认语种</button><button class="secondary" value="cancel">取消</button></div></form>`;
    document.body.appendChild(dialog);
  }
  const state = aiReviewExcelMappingState[sheetName];
  const isSource = state.sources.includes(columnIndex);
  let selected = state.languages?.[columnIndex] || (isSource ? $('mappingSourceLanguageInput').value : $('mappingTargetLanguageInput').value) || 'auto';
  const search = dialog.querySelector('input');
  const list = dialog.querySelector('.column-language-options');
  const hint = dialog.querySelector('.hint');
  $('columnLanguageTitle').textContent = `${aiReviewColumnLabel(sheetName, columnIndex)} · ${isSource ? '原文' : '译文'}语种`;
  search.value = '';
  function choose(value) { selected = value; render(); }
  function render() {
    const query = search.value.trim(); list.innerHTML = '';
    const names = [...new Set([...reviewLanguages, ...Object.values(state.languages || {}), reviewConversationState.sourceLanguage, ...reviewConversationState.targetLanguages])].filter(x => x && !['none','无源文','auto'].includes(x));
    names.filter(x => !query || x.toLowerCase().includes(query.toLowerCase())).forEach(name => {
      const value = name === '自动检测' ? 'auto' : name;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary';
      button.textContent = name + (value === selected ? ' ✓' : ''); button.setAttribute('aria-pressed', value === selected ? 'true' : 'false'); button.onclick = () => choose(value); list.appendChild(button);
    });
    if (query && !names.includes(query)) {
      const add = document.createElement('button'); add.type = 'button'; add.className = 'secondary custom-language-action'; add.textContent = `使用自定义语种“${query}”`;
      add.onclick = () => choose(query); list.appendChild(add);
    }
    hint.textContent = '已选：' + (selected === 'auto' ? '自动检测' : selected);
  }
  search.oninput = render;
  search.onkeydown = event => { if (event.key === 'Enter') { event.preventDefault(); if (search.value.trim()) choose(search.value.trim()); } };
  dialog.querySelector('.column-language-apply').onclick = () => {
    state.languages ||= {}; state.languages[columnIndex] = selected; dialog.close(); renderAiReviewExcelMappingDialog();
  };
  render(); dialog.showModal(); search.focus();
}
'''
