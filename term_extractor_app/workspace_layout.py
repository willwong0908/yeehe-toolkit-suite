"""Toolkit component layouts; all paints reference workspace_ui semantic tokens.

Includes every tool page and dialog. Theme switching changes tokens, never layout.
"""
LAYOUT_CSS = r'''
* { box-sizing: border-box; }
body { margin: 0px; background: var(--panel-soft); color: var(--ink); font-family: var(--font-ui); font-size: 15px; }
.hidden { display: none !important; }
.shell { display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; }
.sidebar { padding: 28px 22px; background: var(--panel-soft); border-right: 1px solid var(--line); backdrop-filter: none; }
.brand { display: flex; gap: 12px; align-items: center; margin-bottom: 36px; }
.brand-mark { width: 38px; height: 38px; border-radius: 13px; object-fit: cover; display: block; box-shadow: none; background: var(--panel-soft); }
.brand-copy { min-width: 0px; display: grid; gap: 2px; }
.brand-version { display: inline-flex; width: fit-content; padding: 2px 8px; border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 11px; font-weight: 600; letter-spacing: 0.03em; }
.brand strong { display: block; font-size: 18px; line-height: 1.2; }
.brand small { color: var(--muted); line-height: 1.3; }
.sidebar-nav { display: grid; gap: 12px; margin-bottom: 22px; }
.nav-group { display: grid; gap: 8px; }
.nav-group-title { padding: 0px; color: var(--ink); font-size: 14px; font-weight: 600; line-height: 1.25; letter-spacing: 0.02em; }
.nav-accordion { border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); overflow: hidden; box-shadow: none; }
.nav-accordion[open] { background: var(--panel-soft); box-shadow: none; }
.nav-accordion-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; cursor: pointer; list-style: none; }
.nav-accordion-summary::-webkit-details-marker { display: none; }
.nav-accordion-summary::after { content: "+"; width: 24px; height: 24px; display: inline-grid; place-items: center; border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 15px; font-weight: 600; line-height: 1; }
.nav-accordion[open] .nav-accordion-summary::after { content: "-"; }
.nav-submenu { display: grid; gap: 6px; padding: 0px 10px 10px; }
.nav-accordion:not([open]) > .nav-submenu { display: none; }
.nav-link { width: 100%; justify-content: flex-start; min-height: 40px; background: transparent; color: var(--ink); border: 0px; text-align: left; padding: 0px 14px; border-radius: 12px; font-weight: 600; transition: background 0.18s, color 0.18s, transform 0.18s; }
.nav-link-top { min-height: 46px; padding: 0px 14px; font-size: 15px; font-weight: 600; color: var(--ink); background: var(--panel-soft); border: 1px solid var(--line); box-shadow: none; }
.nav-link-sub { padding-left: 14px; font-size: 14px; min-height: 38px; }
.nav-link-placeholder { opacity: 0.58; border: 1px dashed var(--line); background: var(--panel-soft); }
.nav-link.active, .nav-link:hover { background: var(--panel-soft); color: var(--ink); }
.nav-link:hover { transform: translateY(-1px); }
.sidebar-status { display: grid; gap: 12px; padding: 14px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: 18px; }
.sidebar-actions-panel { margin-top: 14px; }
.feedback-entry-button { width: 100%; min-height: 44px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); color: var(--ink); font-size: 15px; font-weight: 600; cursor: pointer; transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s; }
.feedback-entry-button:hover { transform: translateY(-1px); border-color: var(--line); box-shadow: none; }
.status-block { display: grid; gap: 6px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }
.status-block:last-of-type { padding-bottom: 0px; border-bottom: 0px; }
.status-caption { color: var(--muted); font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.service-tip { color: var(--muted); line-height: 1.5; }
.service-tip code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }
.content { padding: 28px; max-width: 1280px; width: 100%; }
.hero { display: grid; grid-template-columns: minmax(0px, 1fr) 260px; gap: 20px; align-items: stretch; margin-bottom: 20px; }
.hero h1 { margin: 0px; font-size: clamp(28px, 3vw, 44px); line-height: 1.12; letter-spacing: -0.04em; max-width: 840px; }
.eyebrow { margin: 0px 0px 10px; color: var(--ink); font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }
.lede { color: var(--muted); font-size: 16px; max-width: 760px; }
.hero-card, .card, .advanced-card { background: var(--panel-soft); border: 1px solid var(--line); border-radius: 24px; box-shadow: none; }
.hero-card { padding: 22px; display: grid; align-content: center; gap: 10px; }
.hero-card strong { font-size: 26px; }
.hero-card-label { color: var(--muted); font-weight: 600; }
.hero-card-meta { color: var(--ink); font-size: 13px; line-height: 1.55; padding-top: 2px; }
.pill { width: max-content; padding: 7px 11px; border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-weight: 600; }
.pill.running { background: var(--panel-soft); color: var(--ink); }
.pill.failed { background: var(--panel-soft); color: var(--ink); }
.card { position: relative; padding: 22px; margin-bottom: 18px; }
.card.popover-open { z-index: 80; overflow: visible; }
.advanced-card { padding: 0px; margin-bottom: 18px; overflow: hidden; }
.advanced-card summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 22px; cursor: pointer; list-style: none; }
.advanced-card summary::-webkit-details-marker { display: none; }
.advanced-card summary::after { content: "灞曞紑"; min-height: 34px; padding: 7px 12px; border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-weight: 600; }
.advanced-card[open] summary::after { content: "鏀惰捣"; }
.advanced-card summary strong { display: block; font-size: 20px; }
.advanced-card summary small { display: block; margin-top: 4px; color: var(--muted); }
.advanced-shortcuts { display: flex; gap: 12px; flex-wrap: wrap; padding: 0px 22px 22px; }
.shortcut-button { min-height: 40px; }
.page-section { display: none; }
.page-section.active { display: block; }
.inline-notice { margin-bottom: 14px; padding: 12px 14px; border-radius: 14px; border: 1px solid var(--line); background: var(--panel-soft); color: var(--ink); font-size: 13px; line-height: 1.6; }
.tool-guide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
.tool-guide-card { min-height: 86px; justify-content: center; align-items: center; padding: 16px; border-radius: 18px; background: var(--panel-soft); border: 1px solid var(--line); box-shadow: none; color: var(--ink); font-size: 17px; font-weight: 600; text-align: center; letter-spacing: -0.02em; }
.tool-guide-card:hover, .tool-guide-card:focus-visible { background: var(--panel-soft); color: var(--ink); transform: translateY(-2px); }
.tool-guide-dialog { width: min(760px, -40px + 100vw); max-height: calc(-56px + 100vh); }
.tool-guide-dialog .dialog-card { display: grid; gap: 18px; max-height: calc(-56px + 100vh); overflow: auto; padding: 24px; border: 1px solid var(--line); border-radius: 22px; background: var(--panel-soft); box-shadow: none; }
.tool-guide-dialog .dialog-header { display: flex; justify-content: space-between; align-items: start; gap: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.tool-guide-dialog .dialog-header h3 { margin: 0px; font-size: 28px; letter-spacing: -0.03em; }
.dialog-kicker { display: block; margin-bottom: 6px; color: var(--ink); font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; }
.markdown-guide { display: grid; gap: 18px; color: var(--ink); }
.markdown-guide h4 { margin: 0px 0px 8px; font-size: 18px; }
.markdown-guide p { margin: 0px; color: var(--muted); line-height: 1.75; }
.markdown-guide ul, .markdown-guide ol { margin: 0px; padding-left: 22px; color: var(--ink); line-height: 1.75; }
.markdown-guide li + li { margin-top: 4px; }
.markdown-guide code { padding: 2px 6px; border-radius: 8px; background: var(--panel-soft); color: var(--ink); font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }
.section-header { margin: 0px 0px 16px; }
.section-header h2 { margin: 0px; font-size: 26px; }
.section-header p { margin: 6px 0px 0px; color: var(--muted); }
.subnav { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.subnav-link { min-height: 36px; padding: 0px 14px; background: var(--panel-soft); color: var(--ink); border-radius: 999px; font-size: 13px; font-weight: 600; border: 1px solid var(--line); }
.subnav-link.active { background: var(--panel-soft); color: var(--ink); border-color: var(--line); box-shadow: none; }
.link-with-dot, .section-title-with-dot { display: inline-flex; align-items: center; gap: 8px; }
.badge-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--panel-soft); box-shadow: none; }
.subtab-panel { display: none; }
.subtab-panel.active { display: block; }
.dashboard-grid { grid-template-columns: 1.2fr 0.8fr; align-items: start; }
.card-title { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.card-title h2 { margin: 0px; font-size: 22px; }
.card-title h3 { margin: 0px; font-size: 20px; }
.card-title p { margin: 0px; color: var(--muted); max-width: 620px; }
.card-title p:empty, .section-header p:empty { display: none; }
.grid.two { display: grid; grid-template-columns: repeat(2, minmax(0px, 1fr)); gap: 14px; }
.stage-grid { display: grid; grid-template-columns: repeat(3, minmax(0px, 1fr)); gap: 14px; }
.compact-card { margin-bottom: 0px; }
.stage-panel { background: var(--panel-soft); border: 1px solid var(--line); border-radius: 18px; padding: 16px; display: grid; gap: 12px; }
.stage-panel h3 { margin: 0px; font-size: 17px; }
label { display: grid; gap: 7px; color: var(--muted); font-weight: 600; }
input, select { width: 100%; min-height: 42px; border: 1px solid var(--line); border-radius: 12px; padding: 9px 11px; background: var(--panel-soft); color: var(--ink); font: inherit; }
.search-inline-field { display: grid; grid-template-columns: minmax(0px, 1fr) auto; gap: 10px; align-items: center; }
.search-inline-field input { min-width: 0px; }
.secret-field { display: grid; grid-template-columns: minmax(0px, 1fr) auto; gap: 8px; align-items: center; }
.secret-field input { min-width: 0px; }
.field-label { display: block; margin-bottom: 7px; color: var(--muted); font-size: 13px; font-weight: 600; }
.file-card-row { display: grid; grid-template-columns: minmax(0px, 1fr) auto; gap: 10px; align-items: stretch; }
.file-card { min-height: 42px; display: flex; align-items: center; min-width: 0px; padding: 10px 13px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); color: var(--ink); font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.file-card.empty { color: var(--muted); font-weight: 600; }
.mini-button { min-height: 42px; padding: 0px 14px; background: var(--panel-soft); color: var(--ink); border: 1px solid var(--line); }
.check { display: flex; align-items: center; gap: 9px; color: var(--ink); }
.check input[type="checkbox"], .check-line input[type="checkbox"], .mapping-source, .directional-item input[type="checkbox"], .pattern-table input[type="checkbox"], .scope-item input[type="checkbox"], #crossExcelHeaderList input[type="checkbox"] { width: 16px; height: 16px; min-width: 16px; min-height: 16px; margin: 0px; accent-color: var(--primary); }
.check-line { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-weight: 600; }
.actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.action-row-compact { margin-top: 12px; align-items: center; }
.action-row-compact .hint { min-height: 24px; display: inline-flex; align-items: center; }
.sticky-actions { position: sticky; bottom: 18px; display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-top: 16px; padding: 14px 18px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); box-shadow: none; }
button { min-height: 40px; border: 0px; border-radius: 12px; padding: 0px 16px; font-style: inherit; font-variant: inherit; font-stretch: inherit; font-size: inherit; line-height: inherit; font-family: var(--font-ui); font-optical-sizing: inherit; font-size-adjust: inherit; font-kerning: inherit; font-feature-settings: inherit; font-variation-settings: inherit; font-language-override: inherit; font-weight: 600; cursor: pointer; transition: transform 0.18s, box-shadow 0.18s, background 0.18s, color 0.18s; }
button.primary { background: var(--panel-soft); color: var(--ink); box-shadow: none; }
button.secondary { background: var(--panel-soft); color: var(--ink); border: 1px solid var(--line); }
button.danger { background: var(--panel-soft); color: var(--ink); border: 1px solid var(--line); }
button:hover:not(:disabled) { transform: translateY(-1px); }
button.primary:hover:not(:disabled) { box-shadow: none; }
button:disabled { opacity: 0.58; cursor: not-allowed; }
.error-panel { display: grid; gap: 4px; margin: 0px 0px 14px; padding: 13px 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); color: var(--ink); }
.error-panel[hidden] { display: none; }
.pattern-table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 16px; }
.pattern-table { width: 100%; border-collapse: collapse; background: var(--panel-soft); }
.pattern-table th, .pattern-table td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
.pattern-table th { color: var(--muted); font-size: 13px; background: var(--panel-soft); }
.pattern-table tr:last-child td { border-bottom: 0px; }
.pattern-table input[type="text"] { min-height: 36px; }
.pattern-table input[type="checkbox"] { width: 18px; min-height: 18px; }
.diff-preview-table-wrap { max-width: 100%; overscroll-behavior-inline: contain; }
.diff-preview-table { width: 100%; min-width: 1240px; table-layout: fixed; }
.diff-preview-file-column { width: 150px; }
.diff-preview-sheet-column { width: 130px; }
.diff-preview-location-column { width: 230px; }
.diff-preview-comparison-column { width: 620px; }
.diff-preview-table th, .diff-preview-table td { vertical-align: top; white-space: pre-wrap; overflow-wrap: anywhere; }
.diff-preview-table td:nth-child(-n+4) { color: var(--ink); line-height: 1.55; }
.diff-preview-table td:last-child { padding: 12px; overflow: visible; }
.review-input-table-wrap, .review-result-table-wrap { max-width: 100%; overscroll-behavior-inline: contain; }
.review-input-table { width: 100%; min-width: 1260px; table-layout: fixed; }
.review-input-file-column { width: 170px; }
.review-input-location-column { width: 150px; }
.review-input-row-column { width: 78px; }
.review-input-text-column { width: 350px; }
.review-input-hint-column { width: 150px; }
.review-input-table th, .review-input-table td, .review-result-table th, .review-result-table td { vertical-align: top; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.55; }
.review-input-table td:nth-child(-n+3), .review-input-table td:last-child { color: var(--ink); }
.review-result-table { width: 100%; min-width: 0px; table-layout: fixed; }
.review-result-table-wrap { overflow-x: hidden; }
.review-result-preview-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; margin-bottom: 8px; color: var(--muted); font-size: 13px; font-weight: 600; }
.review-result-table th, .review-result-table td { min-width: 0px; overflow-wrap: anywhere; word-break: break-word; }
.review-result-table th:nth-child(3), .review-result-table td:nth-child(3) { text-align: center; }
.compact-rule-table th, .compact-rule-table td { padding: 8px; }
.compact-rule-table input[type="text"], .compact-rule-table select { min-height: 34px; padding: 6px 9px; border-radius: 10px; font-size: 14px; }
.compact-rule-table { table-layout: fixed; }
.builtin-editor-table th:nth-child(1), .builtin-editor-table td:nth-child(1), .pending-rule-table th:nth-child(1), .pending-rule-table td:nth-child(1) { width: 54px; }
.builtin-editor-table th:nth-child(2), .builtin-editor-table td:nth-child(2), .pending-rule-table th:nth-child(2), .pending-rule-table td:nth-child(2) { width: 120px; }
.builtin-editor-table th:nth-child(4), .builtin-editor-table td:nth-child(4), .pending-rule-table th:nth-child(4), .pending-rule-table td:nth-child(4) { width: 92px; }
.pending-rule-table th:nth-child(5), .pending-rule-table td:nth-child(5) { width: 360px; }
.modal-card.review-detail-modal { width: calc(-28px + 100vw); height: calc(-28px + 100vh); max-height: calc(-28px + 100vh); display: grid; grid-template-rows: auto minmax(0px, 1fr); }
.review-detail-wrap { min-height: 0px; max-height: none; overflow: auto; padding: 0px 2px 2px; }
.review-detail-table { width: 100%; min-width: 0px; table-layout: fixed; }
.review-detail-table th:nth-child(1), .review-detail-table td:nth-child(1) { width: 20%; }
.review-detail-table th:nth-child(2), .review-detail-table td:nth-child(2) { width: 20%; }
.review-detail-table th:nth-child(3), .review-detail-table td:nth-child(3) { width: 20%; }
.review-detail-table th:nth-child(4), .review-detail-table td:nth-child(4) { width: 20%; }
.review-detail-table th:nth-child(5), .review-detail-table td:nth-child(5) { width: 20%; }
.review-detail-table td { vertical-align: top; white-space: normal; overflow-wrap: anywhere; line-height: 1.6; }
.review-detail-group + .review-detail-group { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--line); }
.review-detail-group-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0px 0px 9px; }
.review-detail-group-head h4 { margin: 0px; color: var(--ink); font-size: 14px; line-height: 1.35; overflow-wrap: anywhere; }
.review-detail-group-head span { flex: 0 0 auto; color: var(--muted); font-size: 12px; }
.review-detail-group-table-wrap { overflow-x: hidden; border: 1px solid var(--line); border-radius: var(--radius-sm); }
.review-detail-issue-cell { position: relative; padding-bottom: 48px; }
.review-diff-cell .diff-inline-side { min-height: 0px; padding: 10px; border-radius: 10px; }
.review-diff-cell .diff-inline-label { margin-bottom: 6px; }
.review-followup-inline-button { position: absolute; right: 12px; bottom: 10px; min-height: 32px; padding: 0px 12px; border-radius: 999px; font-size: 13px; }
.review-feedback-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
.review-feedback-actions .review-followup-inline-button { position: static; }
.review-feedback-actions input { flex: 1 1 150px; width: 150px; min-width: 0px; }
.review-learning-panel { display: grid; gap: 8px; margin-top: 2px; }
.review-learning-summary-row { min-height: 32px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.review-learning-summary-row .hint { min-width: 0px; }
.review-memory-button { min-height: 30px; padding: 0px 11px; white-space: nowrap; }
.review-learning-progress { display: grid; gap: 6px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.review-learning-progress[hidden] { display: none; }
.review-learning-progress-head { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 12px; }
.review-learning-progress-track { height: 6px; overflow: hidden; border-radius: 999px; background: var(--panel-soft); }
.review-learning-progress-track span { display: block; width: 0px; height: 100%; border-radius: inherit; background: var(--panel-soft); transition: none; }
.review-learning-progress.running .review-learning-progress-track span { animation: 1.25s ease-in-out 0s infinite alternate none running review-learning-pulse; }
.review-learning-progress.completed .review-learning-progress-track span { background: var(--panel-soft); }
.review-learning-progress.failed .review-learning-progress-track span { background: var(--panel-soft); }
@keyframes review-learning-pulse { 
  0% { opacity: 0.58; }
  100% { opacity: 1; }
}
.review-memory-modal { width: min(920px, -32px + 100vw); display: grid; grid-template-rows: auto minmax(0px, 1fr) auto; overflow: hidden; }
.review-memory-rule-list { min-height: 180px; max-height: min(600px, -260px + 100dvh); overflow: auto; display: grid; align-content: start; gap: 12px; padding: 2px; }
.review-memory-empty { min-height: 180px; display: grid; place-items: center; color: var(--muted); text-align: center; }
.review-memory-section { display: grid; gap: 8px; }
.review-memory-section + .review-memory-section { margin-top: 6px; padding-top: 14px; border-top: 1px solid var(--line); }
.review-memory-section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.review-memory-section-head h4 { margin: 0px; color: var(--ink); font-size: 15px; }
.review-memory-section-head span { color: var(--muted); font-size: 12px; }
.review-memory-rule { display: grid; grid-template-columns: 72px 80px minmax(0px, 1fr); align-items: start; gap: 10px; padding: 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.review-memory-rule-index, .review-memory-rule-weight { padding-top: 9px; color: var(--muted); font-size: 12px; }
.review-memory-rule textarea { width: 100%; min-height: 72px; resize: vertical; line-height: 1.55; }
.review-memory-example { grid-column: 1 / -1; padding-top: 10px; border-top: 1px solid var(--line); color: var(--ink); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.review-memory-example-title { color: var(--muted); font-size: 12px; }
.review-memory-example label { display: grid; gap: 4px; margin-top: 9px; color: var(--muted); font-size: 12px; }
.review-memory-example textarea { width: 100%; min-height: 52px; resize: vertical; line-height: 1.55; }
.review-memory-footer { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line); }
.review-learning-question { flex: 0 0 auto; width: min(820px, 96%); padding: 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); color: var(--ink); overflow-wrap: anywhere; }
.review-learning-question h4 { margin: 0px 0px 8px; font-size: 15px; }
.review-learning-question p { margin: 8px 0px; white-space: pre-wrap; }
.review-learning-choices { display: grid; gap: 8px; margin: 12px 0px; }
.review-learning-choices button { min-height: 44px; width: 100%; text-align: left; white-space: normal; font-weight: 400; line-height: 1.6; background: var(--panel-soft); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.review-learning-choices button strong, .review-learning-choices button span { display: block; }
.review-learning-choices button span { margin-top: 3px; color: var(--muted); font-size: 12px; }
.review-learning-question textarea { width: 100%; min-height: 70px; resize: vertical; }
.review-learning-question button:focus-visible, .review-learning-question textarea:focus-visible { outline: 2px solid var(--focus); outline-offset: 3px; }
.review-learning-question .hint { display: block; margin-top: 8px; }
@media (max-width: 680px) {
.review-memory-rule { grid-template-columns: 1fr 1fr; }
.review-memory-rule textarea { grid-column: 1 / -1; }
}
.review-detail-table td.review-detail-issue-cell { padding-bottom: 12px; }
.review-followup-modal { width: min(1180px, -36px + 100vw); height: min(820px, -36px + 100vh); display: grid; grid-template-rows: auto minmax(0px, 1fr); }
.review-followup-layout { min-height: 0px; display: grid; grid-template-columns: minmax(260px, 360px) minmax(0px, 1fr); gap: 16px; }
.review-followup-context { min-height: 0px; overflow: auto; padding: 14px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); }
.followup-context-card { display: grid; gap: 12px; }
.followup-context-section { display: grid; gap: 5px; }
.followup-context-section span { color: var(--muted); font-size: 12px; font-weight: 600; }
.followup-context-section p { margin: 0px; max-height: 138px; overflow: auto; padding-right: 4px; color: var(--ink); line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.review-followup-chat { min-height: 0px; display: grid; grid-template-rows: minmax(0px, 1fr) auto auto; gap: 12px; }
.review-followup-messages { min-height: 0px; overflow: auto; display: grid; align-content: start; gap: 10px; padding: 14px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); }
.followup-message { width: min(78%, 720px); padding: 11px 13px; border-radius: 16px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.followup-message.user { justify-self: end; background: var(--panel-soft); color: var(--ink); }
.followup-message.assistant { justify-self: start; background: var(--panel-soft); color: var(--ink); }
.followup-message-empty { place-self: center; color: var(--muted); padding: 20px; }
.review-followup-input { display: grid; grid-template-columns: minmax(0px, 1fr) auto; gap: 10px; align-items: end; }
.review-followup-input textarea { min-height: 82px; max-height: 180px; resize: vertical; border: 1px solid var(--line); border-radius: 14px; padding: 11px 12px; font-style: inherit; font-variant: inherit; font-weight: inherit; font-stretch: inherit; font-size: inherit; font-family: var(--font-ui); font-optical-sizing: inherit; font-size-adjust: inherit; font-kerning: inherit; font-feature-settings: inherit; font-variation-settings: inherit; font-language-override: inherit; line-height: 1.55; }
@media (max-width: 860px) {
.review-followup-layout { grid-template-columns: 1fr; }
.review-followup-context { max-height: 260px; }
}
.builtin-preview-table { table-layout: fixed; }
.builtin-preview-table th:nth-child(1), .builtin-preview-table td:nth-child(1) { width: 68px; }
.builtin-preview-table th:nth-child(2), .builtin-preview-table td:nth-child(2) { width: 150px; }
.builtin-preview-table th:nth-child(3), .builtin-preview-table td:nth-child(3) { width: 120px; }
.builtin-preview-table th:nth-child(4), .builtin-preview-table td:nth-child(4) { width: 120px; }
.builtin-preview-table th:nth-child(6), .builtin-preview-table td:nth-child(6) { width: 360px; }
.compact-rule-table .pattern-actions button { min-height: 32px; padding: 0px 10px; }
.empty-cell { color: var(--muted); text-align: center; padding: 22px !important; }
.pattern-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.pattern-actions button { min-height: 34px; padding: 0px 10px; }
.color-picker-block { display: grid; gap: 10px; }
.preset-color-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.preset-color-btn { width: 22px; height: 22px; padding: 0px; border: 2px solid var(--line); border-radius: 5px; background: var(--panel-soft); box-shadow: none; cursor: pointer; position: relative; transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s; }
.preset-color-btn::after { content: ""; position: absolute; inset: 2px; border-radius: 3px; border: 1px solid var(--line); pointer-events: none; }
.preset-color-btn.active { border-color: var(--line); box-shadow: none; transform: translateY(-1px); }
.preset-color-btn:hover { transform: translateY(-1px); }
.diff-mode-actions { display: inline-flex; align-items: center; gap: 8px; }
.diff-mode-select { width: auto; min-width: 136px; min-height: 40px; padding: 0px 34px 0px 12px; font-weight: 600; }
.icon-button { width: 40px; min-width: 40px; min-height: 40px; padding: 0px; font-size: 18px; line-height: 1; }
.diff-field-settings-modal { width: min(760px, 100%); }
.diff-field-settings-grid { display: grid; gap: 12px; margin-bottom: 18px; }
.diff-header-presence { display: grid; grid-template-columns: 1fr; gap: 6px; }
.diff-header-presence span { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); color: var(--muted); font-size: 13px; }
.diff-header-presence strong { color: var(--ink); font-size: 14px; }
.diff-compare-fields-block { display: grid; gap: 8px; margin-bottom: 16px; }
.field-block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.field-block-head span { color: var(--muted); font-size: 13px; }
.diff-compare-field-list { display: grid; grid-template-columns: 1fr; gap: 0px; max-height: 320px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.diff-compare-field-item { display: flex; align-items: flex-start; gap: 10px; min-width: 0px; height: auto; min-height: 40px; padding: 10px 12px; border-width: 0px 0px 1px; border-style: none none solid; border-color: var(--line); border-image: initial; border-radius: 0px; background: var(--panel-soft); cursor: pointer; }
.diff-compare-field-item:last-child { border-bottom: 0px; }
.diff-compare-field-item:hover { background: var(--panel-soft); }
.diff-compare-field-item input[type="checkbox"] { width: 16px; height: 16px; min-width: 16px; min-height: 16px; margin: 2px 0px 0px; accent-color: var(--primary); }
.diff-compare-field-item span { flex: 1 1 0%; min-width: 0px; color: var(--ink); line-height: 1.45; white-space: normal; overflow-wrap: anywhere; word-break: break-all; }
.diff-unmatched-line { display: flex; width: fit-content; min-height: 32px; margin: 0px; padding: 4px 0px; border: 0px; border-radius: 0px; background: transparent; }
.info-tip { position: relative; display: inline-grid; place-items: center; width: 17px; height: 17px; border: 1px solid var(--line); border-radius: 50%; color: var(--ink); font-size: 12px; font-weight: 600; cursor: help; }
.info-tip-content { position: absolute; z-index: 10; left: 50%; bottom: calc(100% + 9px); width: min(330px, 70vw); padding: 10px 12px; border-radius: 10px; background: var(--panel-soft); color: var(--ink); font-size: 13px; line-height: 1.55; font-weight: 500; box-shadow: none; opacity: 0; pointer-events: none; transform: translate(-50%, 4px); transition: opacity 0.14s, transform 0.14s; }
.info-tip:hover .info-tip-content, .info-tip:focus .info-tip-content { opacity: 1; transform: translate(-50%, 0px); }
@media (max-width: 680px) {
.diff-header-presence { padding-bottom: 0px; }
.field-block-head { align-items: flex-start; flex-direction: column; gap: 3px; }
.diff-mode-actions { width: 100%; }
.diff-mode-select { flex: 1 1 0%; }
}
.diff-inline-card { display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 10px; min-width: 0px; }
.diff-inline-card.diff-inline-single { grid-template-columns: minmax(0px, 1fr); }
.diff-inline-side { min-width: 0px; border-radius: 12px; padding: 10px 12px; border: 1px solid var(--line); cursor: pointer; transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s; }
.diff-inline-side:hover { transform: translateY(-1px); box-shadow: none; }
.diff-inline-side:active { transform: translateY(0px); }
.diff-inline-delete { background: var(--panel-soft); border-color: var(--line); }
.diff-inline-add { background: var(--panel-soft); border-color: var(--line); }
.diff-inline-label { margin-bottom: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em; }
.diff-inline-delete .diff-inline-label { color: var(--ink); }
.diff-inline-add .diff-inline-label { color: var(--ink); }
.diff-inline-text { color: var(--ink); line-height: 1.7; overflow-wrap: anywhere; word-break: normal; white-space: pre-wrap; }
.diff-inline-empty { color: var(--ink); }
.diff-plain-token { color: inherit; }
.diff-token { padding: 1px 2px; border-radius: 4px; font-weight: 600; }
.diff-token-delete { background: var(--panel-soft); color: var(--ink); }
.diff-token-add { background: var(--panel-soft); color: var(--ink); }
.summary-line { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 14px; color: var(--muted); font-weight: 600; }
.summary-line span { padding: 8px 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 13px; }
.summary-line strong { color: var(--ink); }
.update-leaving-screen { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
.update-leaving-card { width: min(460px, 100%); padding: 28px; border-radius: 22px; border: 1px solid var(--line); background: var(--panel-soft); box-shadow: none; text-align: center; }
.update-leaving-card h2 { margin: 0px 0px 10px; font-size: 26px; }
.update-leaving-card p { margin: 0px; color: var(--muted); line-height: 1.7; }
.regex-cell { font: 13px / 1.45 "Cascadia Mono", Consolas, monospace; overflow-wrap: anywhere; color: var(--ink); }
.examples-cell { min-width: 0px; }
.examples-scroll { max-height: 88px; overflow-y: auto; padding-right: 4px; line-height: 1.45; white-space: normal; overflow-wrap: anywhere; }
.examples-item + .examples-item { margin-top: 6px; }
.scope-toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.scope-list { display: grid; gap: 12px; }
.scope-item { display: grid; grid-template-columns: auto minmax(0px, 1fr) auto; gap: 10px 12px; align-items: start; padding: 14px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); }
.scope-toggle { display: flex; align-items: center; justify-content: center; min-height: 42px; }
.scope-item input[type="checkbox"] { width: 18px; min-height: 18px; margin: 0px; }
.scope-fields { display: grid; gap: 8px; min-width: 0px; }
.scope-fields textarea { min-height: 46px; resize: vertical; border: 1px solid var(--line); border-radius: 12px; padding: 9px 11px; font: inherit; }
.scope-delete { min-height: 42px; padding: 0px 14px; background: var(--panel-soft); color: var(--ink); }
.scope-empty { padding: 18px; border: 1px dashed var(--line); border-radius: 16px; background: var(--panel-soft); color: var(--muted); text-align: center; }
.prompt-grid { display: grid; grid-template-columns: repeat(2, minmax(0px, 1fr)); gap: 14px; }
.prompt-card { display: grid; gap: 9px; padding: 14px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); }
.prompt-card header { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
.prompt-card strong { color: var(--ink); }
.prompt-card small { color: var(--muted); line-height: 1.45; }
.prompt-card-actions { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.prompt-reset-button { min-height: 30px; padding: 0px 10px; border-radius: 10px; }
.prompt-card textarea { min-height: 220px; resize: vertical; border: 1px solid var(--line); border-radius: 12px; padding: 11px; font: 13px / 1.55 "Cascadia Mono", Consolas, monospace; color: var(--ink); }
.prompt-badge { white-space: nowrap; border-radius: 999px; padding: 4px 9px; background: var(--panel-soft); color: var(--muted); font-size: 12px; font-weight: 600; }
.prompt-badge.modified { background: var(--panel-soft); color: var(--ink); }
.result-box, .log-box { margin: 16px 0px 0px; padding: 14px; border-radius: 14px; background: var(--panel-soft); color: var(--ink); overflow: auto; font-size: 13px; }
.cross-summary-box { display: grid; gap: 6px; align-content: center; min-height: 100%; padding: 14px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); }
.cross-summary-box span, .cross-summary-box small { color: var(--muted); }
.cross-summary-box strong { font-size: 24px; }
.cross-header-list { display: grid; gap: 10px; max-height: 320px; overflow: auto; margin-top: 14px; padding: 4px; }
.cross-header-item { display: flex; align-items: center; gap: 10px; padding: 11px 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); }
.cross-header-item input { width: 18px; min-height: 18px; margin: 0px; }
.cross-header-item span { min-width: 0px; color: var(--ink); font-weight: 600; overflow-wrap: anywhere; }
.cross-merge-actions { justify-content: space-between; gap: 16px; }
.cross-search-results { display: grid; gap: 14px; max-height: 680px; overflow: auto; padding-right: 4px; }
.cross-empty-state { padding: 18px; border: 1px dashed var(--line); border-radius: 16px; background: var(--panel-soft); color: var(--muted); text-align: center; }
.cross-result-card { border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); overflow: hidden; }
.cross-result-meta { display: flex; gap: 10px; flex-wrap: wrap; padding: 14px 16px; border-bottom: 1px solid var(--line); background: var(--panel-soft); }
.cross-result-meta span { padding: 7px 11px; border-radius: 999px; background: var(--panel-soft); border: 1px solid var(--line); color: var(--muted); font-size: 13px; font-weight: 600; }
.cross-row-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; padding: 16px; }
.cross-cell { min-height: 60px; padding: 12px 12px 10px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); text-align: left; transition: border-color 0.18s, box-shadow 0.18s, background 0.18s; }
.cross-cell:hover { border-color: var(--line); box-shadow: none; }
.cross-cell.matched { background: var(--panel-soft); border-color: var(--line); }
.cross-cell-index { display: block; margin-bottom: 7px; color: var(--muted); font-size: 12px; font-weight: 600; }
.cross-cell-text { display: block; width: 100%; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; line-height: 1.55; color: var(--ink); }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(0px, 1fr)); gap: 12px; margin-bottom: 14px; }
.metrics div { padding: 14px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: 16px; }
.metrics span { display: block; color: var(--muted); font-size: 13px; }
.metrics strong { font-size: 22px; }
.stats-panel { margin: 0px 0px 14px; padding: 14px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); }
.stats-title { margin-bottom: 10px; color: var(--muted); font-weight: 600; }
.compact-metrics { grid-template-columns: repeat(4, minmax(0px, 1fr)); margin-bottom: 0px; }
.compact-metrics div { background: var(--panel-soft); }
.compact-metrics strong { font-size: 18px; }
.result-file { display: grid; gap: 5px; padding: 14px; margin-bottom: 14px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); }
.result-file span, .result-file small { color: var(--muted); }
.result-file strong { overflow-wrap: anywhere; }
.result-metrics { grid-template-columns: repeat(4, minmax(0px, 1fr)); }
.hero-metrics { margin-bottom: 10px; }
.notice-list { display: grid; gap: 10px; color: var(--ink); }
.notice-list div { padding: 12px 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); }
.dialog { width: min(760px, -36px + 100vw); max-height: calc(-48px + 100vh); border: 0px; border-radius: 18px; padding: 0px; background: transparent; }
.dialog::backdrop { background: var(--panel-soft); }
.wide-dialog { width: min(1120px, -36px + 100vw); }
.compact-dialog { width: min(460px, -36px + 100vw); }
.dialog-body { display: grid; gap: 16px; max-height: calc(-48px + 100vh); overflow: auto; padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); box-shadow: none; }
.dialog-head { display: flex; justify-content: space-between; align-items: start; gap: 16px; }
.dialog-head h2 { margin: 0px 0px 6px; font-size: 22px; }
.dialog-head p { margin: 0px; color: var(--muted); line-height: 1.55; }
.dialog-actions { display: flex; gap: 10px; justify-content: flex-end; flex-wrap: wrap; padding-top: 4px; }
.icon-button { width: 36px; min-height: 36px; padding: 0px; border-radius: 999px; font-size: 20px; line-height: 1; }
.field { display: grid; gap: 7px; min-width: 0px; }
.field label { margin: 0px; }
.field textarea { width: 100%; min-height: 140px; resize: vertical; border: 1px solid var(--line); border-radius: 12px; padding: 11px 12px; font: inherit; }
.directional-items { display: grid; gap: 10px; max-height: 360px; overflow: auto; }
.directional-item { display: grid; grid-template-columns: auto minmax(0px, 1fr); gap: 10px; align-items: center; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); }
.directional-item input[type="checkbox"] { margin: 0px; }
.sheet-tabs { display: flex; gap: 8px; flex-wrap: wrap; max-height: 118px; overflow-y: auto; padding-bottom: 2px; }
.sheet-tab { min-height: 36px; padding: 0px 13px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--muted); white-space: nowrap; max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
.preprocess-mapping-toolbar { display: grid; grid-template-columns: auto minmax(180px, 1fr) auto minmax(180px, 1fr) auto auto; gap: 10px; align-items: center; margin-bottom: 12px; }
.preprocess-mapping-toolbar select { min-width: 0px; }
.preprocess-apply-sheet-list { display: grid; gap: 8px; max-height: 45vh; overflow: auto; margin: 12px 0px; }
@media (max-width: 760px) {
.preprocess-mapping-toolbar { grid-template-columns: 1fr; }
}
.sheet-tab.active { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.mapping-template-bar { display: grid; grid-template-columns: auto minmax(180px, 1fr) auto auto; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); }
.mapping-template-bar label { color: var(--muted); font-weight: 600; white-space: nowrap; }
.mapping-template-bar select { min-width: 0px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mapping-template-bar button { min-height: 36px; white-space: nowrap; }
.mapping-template-delete { width: 36px; border-radius: 10px; font-size: 17px; }
.mapping-template-hint { min-height: 0px; margin: -7px 0px 0px; color: var(--ink); font-size: 13px; line-height: 1.5; }
.mapping-template-hint:empty { display: none; }
.excel-mapping-columns { display: grid; gap: 10px; max-height: min(520px, 52vh); overflow: auto; padding-right: 4px; }
.mapping-row { display: grid; grid-template-columns: 58px minmax(160px, 1fr) 86px minmax(150px, 0.8fr) minmax(150px, 0.8fr) minmax(130px, 0.7fr); gap: 10px; align-items: center; padding: 10px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); }
.mapping-col-id { color: var(--ink); font-weight: 600; }
.mapping-header { min-width: 0px; overflow-wrap: anywhere; color: var(--ink); font-weight: 600; }
.mapping-row select, .mapping-row input[type="text"] { width: 100%; min-height: 36px; padding: 6px 9px; border-radius: 10px; font-size: 14px; }
.check-line.disabled-line { opacity: 0.55; }
.review-log-list { display: grid; gap: 8px; max-height: 260px; overflow: auto; margin: 0px; padding-left: 20px; }
.review-log-list li { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.5; color: var(--muted); }
.review-log-list li.error { color: var(--ink); }
.review-log-list li.debug { color: var(--ink); }
.progress { height: 12px; border-radius: 999px; background: var(--panel-soft); overflow: hidden; margin-bottom: 14px; }
.progress span { display: block; height: 100%; width: 0px; background: var(--panel-soft); transition: none; }
.hint { color: var(--ink); font-weight: 600; }
.hero-side { display: grid; gap: 12px; justify-items: end; }
.notice-button { display: inline-flex; align-items: center; gap: 10px; min-height: 42px; padding: 0px 16px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.update-notice-button { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.notice-button[hidden] { display: none !important; }
.notice-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--panel-soft); }
.modal-overlay { position: fixed; inset: 0px; display: grid; place-items: center; padding: 24px; background: var(--panel-soft); z-index: 1000; }
.modal-overlay[hidden] { display: none; }
.modal-card { width: min(1120px, 100%); max-height: calc(-48px + 100vh); overflow: auto; padding: 22px; border-radius: 22px; background: var(--panel-soft); box-shadow: none; }
.modal-header { display: flex; align-items: start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.modal-header h3 { margin: 0px; font-size: 24px; }
.modal-header p { margin: 8px 0px 0px; color: var(--muted); }
.modal-close { min-height: 38px; min-width: 38px; padding: 0px; border-radius: 999px; background: var(--panel-soft); color: var(--ink); }
.modal-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.modal-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.modal-footer-actions { display: inline-flex; align-items: center; gap: 10px; }
.update-release-notes { min-height: 180px; max-height: 360px; overflow-y: auto; padding: 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); color: var(--ink); line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.update-modal .summary-line { margin-bottom: 16px; }
.feedback-modal { width: min(680px, -36px + 100vw); }
.feedback-attachment-card, .feedback-log-card { display: grid; gap: 10px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); }
.feedback-attachment-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.feedback-dropzone { display: grid; gap: 6px; width: 100%; padding: 18px 16px; border: 1px dashed var(--line); border-radius: 14px; background: var(--panel-soft); color: var(--ink); text-align: left; cursor: pointer; transition: border-color 0.18s, background 0.18s, transform 0.18s; }
.feedback-dropzone:hover, .feedback-dropzone:focus-visible { border-color: var(--line); background: var(--panel-soft); transform: translateY(-1px); outline: none; }
.feedback-dropzone.drag-over { border-color: var(--line); background: var(--panel-soft); }
.feedback-dropzone-title { font-weight: 600; color: var(--ink); }
.feedback-dropzone-subtitle { color: var(--muted); font-size: 13px; }
.feedback-log-card code { display: block; padding: 10px 12px; border-radius: 12px; background: var(--panel-soft); color: var(--ink); font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.feedback-log-actions { justify-content: flex-start; }
.review-conversation-shell { display: grid; grid-template-columns: 236px minmax(0px, 1fr); height: clamp(620px, -190px + 100vh, 820px); min-height: 620px; border: 1px solid var(--line); border-radius: 18px; overflow: hidden; background: var(--panel-soft); }
.review-session-sidebar { min-height: 0px; padding: 14px; border-right: 1px solid var(--line); background: var(--panel-soft); overflow: hidden; }
.review-new-chat { width: 100%; }
.review-conversation-list { display: grid; gap: 7px; margin-top: 14px; max-height: calc(100% - 56px); overflow-y: auto; }
.review-session-row { display: grid; grid-template-columns: minmax(0px, 1fr) 32px; align-items: center; gap: 3px; padding: 3px; border-radius: 12px; transition: background 0.16s, box-shadow 0.16s; }
.review-session-row:hover, .review-session-row.active { background: var(--panel-soft); }
.review-session-row.active { box-shadow: none; }
.review-session-item { min-width: 0px; width: 100%; text-align: left; padding: 8px 9px; border: 0px; border-radius: 9px; background: transparent; color: var(--ink); }
.review-session-item:hover { background: transparent; }
.review-session-item strong, .review-session-item span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.review-session-item span { margin-top: 3px; color: var(--muted); font-size: 12px; }
.review-session-rename { width: 30px; height: 30px; min-height: 30px; padding: 0px; border: 0px; border-radius: 8px; background: transparent; color: var(--ink); opacity: 0.72; }
.review-session-row:hover .review-session-rename, .review-session-row.active .review-session-rename, .review-session-rename:focus-visible { opacity: 1; }
.review-session-rename:hover { color: var(--ink); background: var(--panel-soft); }
.review-session-inline-input { min-width: 0px; width: 100%; height: 34px; padding: 5px 8px; border-color: var(--line); font-weight: 600; }
.review-conversation-main { display: grid; grid-template-rows: auto minmax(0px, 1fr) auto; min-width: 0px; min-height: 0px; overflow: hidden; }
.review-conversation-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 17px 20px; border-bottom: 1px solid var(--line); }
.review-conversation-head h3, .review-conversation-head p { margin: 0px; }
.review-conversation-head p { margin-top: 4px; color: var(--muted); font-size: 13px; }
.review-conversation-title-row { display: flex; align-items: center; gap: 7px; }
.review-title-input { width: min(360px, 52vw); padding: 5px 8px; font-size: 17px; font-weight: 600; }
.review-title-edit { width: 28px; height: 28px; padding: 0px; border: 0px; border-radius: 50%; background: transparent; color: var(--muted); }
.review-title-edit:hover { color: var(--ink); background: var(--panel-soft); }
.review-conversation-messages { min-height: 0px; padding: 24px max(24px, 8%); overflow-y: auto; overscroll-behavior: contain; display: flex; flex-direction: column; gap: 18px; scrollbar-gutter: stable; }
.review-chat-message { max-width: min(820px, 88%); white-space: pre-wrap; line-height: 1.65; }
.review-chat-message.user { align-self: flex-end; padding: 11px 15px; border-radius: 16px 16px 4px; background: var(--panel-soft); }
.review-chat-message.assistant { align-self: flex-start; }
.review-chat-message.workspace-report { width: min(900px, 96%); padding: 16px 18px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel-soft); box-shadow: none; font-size: 13px; }
.review-workspace-preview { display: grid; gap: 12px; white-space: normal; }
.review-workspace-preview-head, .review-workspace-file-head, .review-workspace-mapping-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.review-workspace-preview-head > div, .review-workspace-file-head > div { min-width: 0px; }
.review-workspace-preview-head strong, .review-workspace-file-head strong { display: block; color: var(--ink); font-size: 14px; line-height: 1.35; }
.review-workspace-preview-head span, .review-workspace-file-head span, .review-workspace-mapping-head > span:last-child { color: var(--muted); font-size: 11px; }
.review-workspace-total, .review-workspace-language { flex: 0 0 auto; padding: 3px 8px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); font-weight: 600; color: var(--ink) !important; font-size: 11px !important; }
.review-workspace-file-card { display: grid; gap: 10px; padding: 13px; border: 1px solid var(--line); border-radius: 11px; background: var(--panel-soft); }
.review-workspace-file-head { justify-content: flex-start; }
.review-workspace-file-icon { display: grid; flex: 0 0 auto; place-items: center; width: 31px; height: 31px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-soft); color: var(--ink); font-size: 9px; font-weight: 600; letter-spacing: 0.25px; }
.review-workspace-mapping { display: grid; gap: 9px; padding: 11px; border-top: 1px solid var(--line); }
.review-workspace-mapping-head { min-height: 21px; }
.review-workspace-flow { display: grid; grid-template-columns: minmax(0px, 1fr) 22px minmax(0px, 1fr); align-items: stretch; gap: 7px; }
.review-workspace-endpoint { min-width: 0px; padding: 8px 9px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.review-workspace-endpoint:last-child { border-color: var(--line); background: var(--panel-soft); }
.review-workspace-endpoint.is-empty { opacity: 0.72; }
.review-workspace-endpoint span { display: block; margin-bottom: 3px; color: var(--muted); font-size: 10px; font-weight: 600; }
.review-workspace-endpoint strong { display: -webkit-box; overflow: hidden; color: var(--ink); font-size: 11px; line-height: 1.42; overflow-wrap: anywhere; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.review-workspace-arrow { display: grid; place-items: center; color: var(--ink); font-size: 16px; }
.review-workspace-reference { padding-left: 1px; color: var(--ink); font-size: 11px; }
.review-workspace-samples { display: grid; grid-template-columns: repeat(3, minmax(0px, 1fr)); gap: 7px; }
.review-workspace-sample { min-width: 0px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.review-workspace-sample > span { display: block; overflow: hidden; margin-bottom: 6px; color: var(--ink); font-size: 10px; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.review-workspace-sample-values { display: grid; gap: 6px; }
.review-workspace-sample-source, .review-workspace-sample-target { display: -webkit-box; overflow: hidden; padding-left: 7px; border-left: 2px solid var(--line); color: var(--ink); font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.review-workspace-sample-target { border-left-color: var(--line); color: var(--ink); }
.review-workspace-empty { padding: 9px; color: var(--muted); font-size: 12px; }
.review-workspace-notes { border-top: 1px solid var(--line); color: var(--muted); }
.review-workspace-notes summary { padding-top: 9px; cursor: pointer; font-size: 11px; font-weight: 600; }
.review-workspace-note-copy { display: grid; gap: 5px; padding-top: 7px; }
.review-workspace-note-copy p { margin: 0px; color: var(--muted); font-size: 11px; line-height: 1.55; }
.review-chat-message.error { color: var(--ink); }
.review-chat-message-meta { color: var(--muted); font-size: 11px; margin-top: 4px; }
.review-decision-actions { display: grid; gap: 9px; margin-top: 12px; }
.review-decision-confirm-row { display: flex; }
.review-decision-other-row { display: flex; align-items: center; gap: 8px; }
.review-decision-other-row input { width: min(420px, 100%); min-width: 220px; }
.review-decision-other-row button { flex: 0 0 auto; }
.review-composer { position: relative; margin: 0px max(24px, 8%) 22px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 18px; background: var(--panel-soft); box-shadow: none; }
.review-composer.dragging { border-color: var(--line); background: var(--panel-soft); }
.review-composer textarea { width: 100%; border: 0px; resize: vertical; min-height: 64px; box-shadow: none; background: transparent; }
.review-composer textarea:focus { outline: 0px; }
.review-composer-footer { display: flex; justify-content: space-between; gap: 12px; align-items: flex-end; }
.review-composer-tools, .review-attachment-chips, .review-target-tabs { display: flex; flex-wrap: wrap; gap: 7px; }
.composer-chip, .review-attachment-chip, .review-target-tab { padding: 7px 10px; border-radius: 999px; border: 1px solid var(--line); background: var(--panel-soft); color: var(--ink); font-size: 12px; }
.composer-chip:hover { border-color: var(--line); background: var(--panel-soft); }
.review-attachment-chip { display: inline-flex; align-items: center; gap: 6px; padding: 0px; overflow: hidden; background: var(--panel-soft); }
.review-attachment-open { padding: 7px 3px 7px 10px; border: 0px; background: transparent; color: inherit; font-size: inherit; }
.review-attachment-remove { width: 26px; height: 26px; padding: 0px; margin-right: 3px; border: 0px; border-radius: 50%; background: transparent; color: var(--muted); }
.review-attachment-remove:hover { color: var(--ink); background: var(--panel-soft); }
.review-message-files { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 9px; }
.review-message-file { display: inline-flex; align-items: center; gap: 7px; padding: 8px 11px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel-soft); color: var(--ink); cursor: default; }
.review-stream-output { max-height: 190px; margin-top: 8px; padding: 10px 12px; overflow: auto; border-radius: 10px; background: var(--panel-soft); color: var(--ink); font: 12px / 1.55 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.review-thinking-details { margin-top: 10px; border: 1px solid var(--line); border-radius: 11px; background: var(--panel-soft); overflow: hidden; }
.review-thinking-details summary { padding: 9px 11px; color: var(--ink); font-size: 12px; font-weight: 600; cursor: pointer; user-select: none; }
.review-thinking-details[open] summary { border-bottom: 1px solid var(--line); }
.review-thinking-details .review-stream-output { max-height: 260px; margin: 0px; border-radius: 0px; background: var(--panel-soft); }
dialog.modal { width: auto; max-width: none; border: 0px; padding: 0px; background: transparent; overflow: visible; }
dialog.modal::backdrop { background: var(--panel-soft); backdrop-filter: none; }
.review-attachment-mapping-card { width: min(620px, -30px + 100vw); padding: 0px; overflow: hidden; border: 1px solid var(--line); border-radius: 22px; }
.review-mapping-file-head { display: grid; grid-template-columns: 48px minmax(0px, 1fr) 36px; align-items: center; gap: 13px; padding: 22px 24px 13px; }
.review-mapping-file-icon { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 14px; background: var(--panel-soft); color: var(--ink); font-size: 10px; font-weight: 600; letter-spacing: 0.3px; box-shadow: none; }
.review-mapping-file-copy { min-width: 0px; }
.review-mapping-file-copy > span { display: block; margin-bottom: 3px; color: var(--muted); font-size: 12px; font-weight: 600; }
.review-mapping-file-copy h2 { margin: 0px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ink); font-size: 20px; line-height: 1.3; }
.review-mapping-close { width: 34px; height: 34px; min-height: 34px; padding: 0px; border: 0px; border-radius: 50%; background: var(--panel-soft); color: var(--ink); font-size: 20px; }
.review-mapping-close:hover { background: var(--panel-soft); color: var(--ink); }
.review-mapping-lead { margin: 0px; padding: 0px 24px 17px; color: var(--ink); font-size: 13px; line-height: 1.55; }
.review-import-mode-grid { display: grid; grid-template-columns: repeat(2, minmax(0px, 1fr)); gap: 10px; padding: 0px 24px; }
.review-import-mode-option { position: relative; display: grid; grid-template-columns: 38px minmax(0px, 1fr) 20px; align-items: center; gap: 10px; min-height: 92px; padding: 14px; border: 1px solid var(--line); border-radius: 15px; background: var(--panel-soft); cursor: pointer; transition: border-color 0.16s, background 0.16s, box-shadow 0.16s, transform 0.16s; }
.review-import-mode-option:hover { border-color: var(--line); background: var(--panel-soft); transform: translateY(-1px); }
.review-import-mode-option.selected { border-color: var(--line); background: var(--panel-soft); box-shadow: none; }
.review-import-mode-option.disabled { cursor: not-allowed; opacity: 0.48; transform: none; }
.review-import-mode-option input { opacity: 0; pointer-events: none; position: absolute !important; width: 1px !important; height: 1px !important; }
.review-import-mode-option > span:not(.review-import-mode-icon) { display: grid; gap: 5px; min-width: 0px; }
.review-import-mode-option strong { color: var(--ink); font-size: 14px; }
.review-import-mode-option strong em { display: inline-block; margin-left: 5px; padding: 2px 6px; border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 10px; font-style: normal; vertical-align: 1px; }
.review-import-mode-option small { color: var(--ink); font-size: 12px; line-height: 1.45; }
.review-import-mode-option > i { display: grid; place-items: center; width: 19px; height: 19px; border-radius: 50%; background: var(--panel-soft); color: var(--ink); font-size: 11px; font-style: normal; opacity: 0; transform: scale(0.78); transition: opacity 0.16s, transform 0.16s; }
.review-import-mode-option.selected > i { opacity: 1; transform: scale(1); }
.review-import-mode-icon { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; background: var(--panel-soft); color: var(--ink); font-size: 19px; }
.review-import-mode-option.selected .review-import-mode-icon { background: var(--panel-soft); color: var(--ink); }
.review-import-mode-ai { font-size: 18px; }
.review-mapping-preset-panel { display: grid; gap: 9px; margin: 14px 24px 0px; padding: 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); }
.review-mapping-field-label { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.review-mapping-field-label label { margin: 0px; color: var(--ink); font-size: 13px; font-weight: 600; }
.review-mapping-field-label span { color: var(--ink); font-size: 11px; }
.review-mapping-preset-row { display: grid; grid-template-columns: minmax(0px, 1fr) auto; gap: 9px; }
.review-mapping-preset-row select { min-width: 0px; }
.review-mapping-preset-row button { min-height: 40px; white-space: nowrap; }
.review-mapping-preset-panel > small { color: var(--ink); line-height: 1.5; }
.review-attachment-mapping-card > .hint { min-height: 0px; margin: 10px 24px 0px; color: var(--ink); font-size: 12px; }
.review-attachment-mapping-card > .hint:empty { display: none; }
.review-attachment-mapping-card > .modal-footer { margin-top: 18px; padding: 15px 24px 20px; border-top: 1px solid var(--line); background: var(--panel-soft); }
.review-target-tab.active { color: var(--ink); background: var(--panel-soft); border-color: var(--line); }
.review-send-button { min-width: 68px; border-radius: 999px; }
.review-conversation-results { margin-top: 18px; }
.review-inline-progress { display: grid; grid-template-columns: auto auto minmax(120px, 1fr); align-items: center; gap: 12px; margin-bottom: 14px; }
.review-language-popover { position: absolute; z-index: 30; bottom: 56px; left: 14px; width: min(650px, 100% - 28px); overflow: hidden; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); box-shadow: none; }
.review-language-popover-head { display: grid; grid-template-columns: 32px 1fr auto; align-items: center; gap: 8px; padding: 11px 14px 8px; }
.review-language-popover-head strong { font-size: 14px; }
.review-language-popover-head span { color: var(--muted); font-size: 12px; }
.review-language-back { width: 30px; height: 30px; padding: 0px; border: 0px; border-radius: 50%; background: transparent; color: var(--ink); font-size: 25px; line-height: 1; }
.review-language-back:hover { background: var(--panel-soft); }
.review-language-search-wrap { display: flex; align-items: center; gap: 8px; padding: 0px 15px 10px; border-bottom: 1px solid var(--line); color: var(--ink); }
.review-language-search-wrap input { width: 100%; padding: 7px 0px; border: 0px; border-radius: 0px; box-shadow: none; background: transparent; }
.review-language-search-wrap input:focus { outline: 0px; }
.review-language-options { display: grid; grid-template-columns: repeat(3, minmax(0px, 1fr)); gap: 2px 14px; max-height: 330px; overflow: auto; padding: 9px; }
.review-language-option { position: relative; display: flex; align-items: center; gap: 8px; min-height: 36px; padding: 7px 10px; border: 0px; border-radius: 4px; color: var(--ink); cursor: pointer; user-select: none; }
.review-language-option:hover { background: var(--panel-soft); }
.review-language-option.selected { color: var(--ink); background: var(--panel-soft); }
.review-language-option input { position: absolute; opacity: 0; pointer-events: none; }
.review-language-check { width: 14px; color: var(--ink); font-weight: 600; visibility: hidden; }
.visually-hidden { width: 1px; height: 1px; padding: 0px; margin: -1px; overflow: hidden; clip: rect(0px, 0px, 0px, 0px); white-space: nowrap; border: 0px; position: absolute !important; }
.preprocess-task-grid { display: grid; grid-template-columns: minmax(0px, 1.05fr) minmax(360px, 0.95fr); gap: 28px; align-items: start; }
.preprocess-file-pane, .preprocess-settings-pane { display: grid; gap: 14px; min-width: 0px; }
.preprocess-file-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }
.preprocess-file-summary { color: var(--muted); font-size: 13px; min-height: 20px; }
.preprocess-settings-pane .actions { margin-top: 2px; }
.preprocess-file-item { display: grid; gap: 4px; min-width: 0px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel-soft); color: var(--ink); text-align: left; cursor: pointer; }
.preprocess-file-item:hover, .preprocess-file-item.active { border-color: var(--line); background: var(--panel-soft); }
.preprocess-file-item strong, .preprocess-file-item small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preprocess-file-item small { color: var(--muted); }
.inline-task-hint { min-height: 22px; margin-top: 14px; color: var(--muted); font-size: 13px; line-height: 1.6; }
.inline-task-hint.is-error { color: var(--ink); }
.review-language-option.selected .review-language-check { visibility: visible; }
.review-term-base-chip { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.review-term-base-popover { position: absolute; z-index: 62; bottom: 56px; left: 14px; width: min(410px, 100% - 28px); max-height: 390px; overflow: hidden auto; padding: 7px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); box-shadow: none; }
.review-term-base-action, .review-term-base-option { display: grid; grid-template-columns: 30px minmax(0px, 1fr) auto; align-items: center; gap: 9px; width: 100%; min-height: 48px; padding: 8px 10px; border: 0px; border-radius: 8px; background: transparent; color: var(--ink); text-align: left; }
.review-term-base-action:hover, .review-term-base-option:hover { background: var(--panel-soft); }
.review-term-base-action-icon { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 7px; background: var(--panel-soft); color: var(--ink); font-weight: 600; }
.review-term-base-action > span:nth-child(2), .review-term-base-option-copy { display: grid; min-width: 0px; gap: 2px; }
.review-term-base-action strong, .review-term-base-option strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.review-term-base-action small, .review-term-base-option small { overflow: hidden; color: var(--ink); text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
.review-term-base-options { margin-top: 5px; padding-top: 5px; border-top: 1px solid var(--line); }
.review-term-base-option.selected { background: var(--panel-soft); color: var(--ink); }
.review-term-base-option-check { color: var(--ink); font-weight: 600; }
.review-term-base-delete { width: 28px; height: 28px; min-height: 28px; padding: 0px; border: 0px; border-radius: 6px; background: transparent; color: var(--ink); }
.review-term-base-delete:hover { background: var(--panel-soft); color: var(--ink); }
.danger-text { color: var(--ink); }
.compact-actions { align-items: center; }
@media (max-width: 980px) {
.preprocess-folder-field, .preprocess-file-list, .preprocess-mapping-field, .preprocess-language-field { grid-column: auto; }
.shell { grid-template-columns: 1fr; }
.sidebar { position: static; }
.hero, .grid.two, .stage-grid, .metrics, .prompt-grid, .dashboard-grid, .scope-list, .compact-metrics, .result-metrics, .cross-row-grid { grid-template-columns: 1fr; }
.sticky-actions { position: static; }
.content { padding: 18px; }
.hero-side { justify-items: stretch; }
.modal-card { padding: 18px; }
.modal-footer { align-items: stretch; }
.mapping-template-bar { grid-template-columns: 1fr auto; }
.mapping-template-bar label { grid-column: 1 / -1; }
.mapping-template-bar .secondary { grid-column: 1 / 2; }
.review-conversation-shell { grid-template-columns: 1fr; }
.review-conversation-shell { height: 760px; min-height: 0px; grid-template-rows: auto minmax(0px, 1fr); }
.review-session-sidebar { border-right: 0px; border-bottom: 1px solid var(--line); }
.review-import-mode-grid { grid-template-columns: 1fr; }
.review-mapping-preset-row { grid-template-columns: 1fr; }
.review-conversation-list { display: flex; overflow-x: auto; }
.review-session-item { min-width: 180px; }
.review-language-popover { width: calc(100% - 20px); left: 10px !important; }
.review-language-options { grid-template-columns: 1fr 1fr; }
.review-decision-other-row { align-items: stretch; flex-direction: column; }
.review-decision-other-row input { min-width: 0px; width: 100%; }
}
html { background: var(--panel-soft); }
body { min-width: 320px; background: var(--panel-soft); color: var(--ink); font-family: var(--font-ui); font-size: 14px; line-height: 1.5; }
button, summary, [role="button"] { cursor: pointer; }
button:hover:not(:disabled), .nav-link:hover, .tool-guide-card:hover { transform: none; }
:where(button, input, select, textarea, summary, a):focus-visible { outline: var(--focus) solid 2px; outline-offset: 2px; box-shadow: none; }
.skip-link { position: fixed; z-index: 100; top: 12px; left: 12px; padding: 8px 12px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); font-weight: 600; transform: translateY(-160%); transition: transform 0.16s ease-out; }
.skip-link:focus { transform: translateY(0px); }
.shell { grid-template-columns: 236px minmax(0px, 1fr); min-height: 100vh; }
.sidebar { position: sticky; top: 0px; display: flex; min-height: 100vh; max-height: 100vh; flex-direction: column; padding: 20px 14px 16px; overflow-y: auto; background: var(--panel-soft); border-right: 1px solid var(--line); backdrop-filter: none; }
.brand { gap: 10px; margin: 0px 6px 24px; }
.brand-mark { width: 34px; height: 34px; border: 1px solid var(--line); border-radius: 8px; box-shadow: none; }
.brand-copy { gap: 1px; }
.brand-version { order: 3; padding: 0px; background: transparent; color: var(--ink); font-size: 10px; font-weight: 600; letter-spacing: 0.04em; }
.brand strong { font-size: 15px; letter-spacing: -0.02em; }
.brand small { font-size: 11px; color: var(--ink); }
.sidebar-nav { gap: 4px; margin: 0px; }
.nav-link, .nav-link-top, .nav-link-sub { min-height: 34px; padding: 0px 10px; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; box-shadow: none; color: var(--ink); font-size: 13px; font-weight: 600; transition: background 0.16s, border-color 0.16s, color 0.16s; }
.nav-link-top { min-height: 38px; color: var(--ink); font-weight: 600; }
.nav-link-sub { min-height: 32px; padding-left: 28px; font-size: 12px; }
.nav-link.active, .nav-link:hover, .nav-link-top:hover { background: var(--panel-soft); border-color: var(--line); color: var(--ink); }
.nav-accordion { border: 0px; border-radius: 0px; background: transparent; box-shadow: none; overflow: visible; }
.nav-accordion[open] { background: transparent; box-shadow: none; }
.nav-accordion-summary { min-height: 38px; padding: 0px 10px; border: 1px solid transparent; border-radius: var(--radius-sm); }
.nav-accordion-summary:hover { background: var(--panel-soft); border-color: var(--line); }
.nav-accordion-summary::after { width: 18px; height: 18px; border-radius: 4px; background: transparent; color: var(--ink); font-size: 16px; font-weight: 500; }
.nav-group-title { color: var(--ink); font-size: 13px; font-weight: 600; letter-spacing: 0px; }
.nav-submenu { gap: 2px; padding: 2px 0px 4px; }
.sidebar-status { gap: 10px; margin: auto 0px 0px; padding: 12px; background: var(--panel-soft); border: 1px solid var(--line); border-radius: var(--radius-md); }
.sidebar-status-heading { display: flex; align-items: center; justify-content: space-between; color: var(--ink); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.sidebar-local-badge { padding: 2px 5px; border: 1px solid var(--line); border-radius: 4px; background: var(--panel-soft); color: var(--ink); font-size: 10px; letter-spacing: 0px; }
.status-block { gap: 4px; padding-bottom: 9px; border-bottom-color: var(--line); }
.status-caption { color: var(--ink); font-size: 10px; font-weight: 600; letter-spacing: 0.06em; }
.status-block strong { color: var(--ink); font-size: 12px; }
.status-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.status-line strong { font-size: 12px; }
.pill { padding: 2px 7px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 11px; font-weight: 600; }
.pill.running { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.pill.failed { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.service-tip { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--ink); font-size: 11px; }
.service-tip code { padding: 2px 4px; border: 1px solid var(--line); border-radius: 4px; background: var(--panel-soft); color: var(--ink); font-size: 10px; }
.sidebar-actions-panel { margin-top: 8px; }
.feedback-entry-button { min-height: 34px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); font-size: 12px; font-weight: 600; box-shadow: none; }
.feedback-entry-button:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.content { max-width: 1480px; padding: 32px 40px 56px; }
.hero { display: block; margin: 0px 0px 24px; padding: 0px 0px 20px; border-bottom: 1px solid var(--line); }
.hero-context { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; color: var(--ink); font-size: 11px; font-weight: 600; letter-spacing: 0.025em; }
.eyebrow { margin: 0px; color: var(--ink); font-size: 11px; font-weight: 600; letter-spacing: 0.08em; }
.hero-context-divider { width: 3px; height: 3px; border-radius: 50%; background: var(--panel-soft); }
.hero h1 { max-width: none; font-size: clamp(26px, 2.4vw, 34px); letter-spacing: -0.035em; }
.lede { margin: 7px 0px 0px; max-width: 760px; color: var(--muted); font-size: 14px; line-height: 1.65; }
.inline-notice { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); font-size: 12px; line-height: 1.55; }
.inline-notice strong { color: var(--ink); font-weight: 600; }
.inline-notice-icon { display: grid; flex: 0 0 auto; width: 18px; height: 18px; place-items: center; color: var(--ink); }
.inline-notice-icon svg { width: 16px; height: 16px; }
.tool-guide-grid { grid-template-columns: repeat(6, minmax(0px, 1fr)); gap: 12px; margin-bottom: 24px; }
.tool-guide-card { display: grid; min-height: 198px; align-content: space-between; gap: 18px; padding: 16px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; color: var(--ink); text-align: left; transition: border-color 0.16s, background 0.16s; }
.tool-guide-card:nth-child(1), .tool-guide-card:nth-child(2) { grid-column: span 3; }
.tool-guide-card:nth-child(3) { grid-column: span 4; }
.tool-guide-card:nth-child(4) { grid-column: span 2; }
.tool-guide-card:hover, .tool-guide-card:focus-visible { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.tool-guide-card-top, .tool-guide-card-footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tool-guide-icon { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); }
.tool-guide-icon svg { width: 19px; height: 19px; }
.tool-guide-badge { padding: 3px 6px; border: 1px solid var(--line); border-radius: 4px; color: var(--ink); font-size: 10px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
.tool-guide-badge-ai { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.tool-guide-card-copy { display: grid; gap: 5px; }
.tool-guide-card-copy strong { color: var(--ink); font-size: 17px; font-weight: 600; letter-spacing: -0.02em; }
.tool-guide-card-copy small { max-width: 420px; color: var(--ink); font-size: 12px; font-weight: 500; line-height: 1.55; }
.tool-guide-card-footer { padding-top: 10px; border-top: 1px solid var(--line); color: var(--ink); font-size: 11px; font-weight: 600; }
.tool-guide-arrow { color: var(--ink); font-size: 16px; line-height: 1; }
.tool-guide-card-review { border-color: var(--line); background: var(--panel-soft); }
.tool-guide-card-review .tool-guide-icon { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.card, .advanced-card, .hero-card { border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; }
.card { padding: 20px; margin-bottom: 16px; }
.advanced-card { margin-bottom: 16px; }
.advanced-card summary { padding: 16px 20px; }
.advanced-card summary::after { min-height: 28px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); font-size: 11px; }
.stage-panel, .review-followup-context, .review-followup-messages { border-radius: var(--radius-md); background: var(--panel-soft); }
.section-header { margin-bottom: 14px; }
.section-header h2 { font-size: 22px; letter-spacing: -0.025em; }
.card-title { margin-bottom: 16px; }
.card-title h2 { font-size: 20px; }
.card-title h3 { font-size: 17px; }
.card-title p, .section-header p { font-size: 13px; line-height: 1.55; }
.grid.two, .stage-grid { gap: 12px; }
label { gap: 6px; color: var(--ink); font-size: 12px; font-weight: 600; }
input, select, textarea { border-color: var(--line); border-radius: var(--radius-sm); box-shadow: none; }
input, select { min-height: 38px; padding: 8px 10px; }
textarea { padding: 9px 10px; }
input:hover, select:hover, textarea:hover { border-color: var(--line); }
.actions { gap: 8px; margin-top: 14px; }
button { min-height: 36px; border-radius: var(--radius-sm); padding: 0px 12px; font-size: 13px; font-weight: 600; box-shadow: none; transition: border-color 0.16s, background 0.16s, color 0.16s; }
button.primary { border: 1px solid var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
button.primary:hover:not(:disabled) { border-color: var(--line); background: var(--panel-soft); box-shadow: none; }
button.secondary, .mini-button { border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); }
button.secondary:hover:not(:disabled), .mini-button:hover:not(:disabled) { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
button.danger { border-color: var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); }
.check-line { min-height: 32px; padding: 6px 9px; border-radius: var(--radius-sm); background: var(--panel-soft); }
.subnav { gap: 6px; margin-bottom: 14px; }
.subnav-link { min-height: 32px; border-radius: var(--radius-sm); background: var(--panel-soft); font-size: 12px; }
.subnav-link.active { border-color: var(--line); background: var(--panel-soft); box-shadow: none; }
.sticky-actions { padding: 10px 12px; border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; }
.pattern-table-wrap, .result-box, .review-result-table-wrap, .review-input-table-wrap { border-radius: var(--radius-md); }
.pattern-table th, .pattern-table td { padding: 9px 10px; }
.pattern-table th { background: var(--panel-soft); color: var(--ink); font-size: 11px; }
dialog.modal::backdrop { background: var(--panel-soft); backdrop-filter: none; }
.modal-card, .tool-guide-dialog .dialog-card { border-radius: var(--radius-lg); box-shadow: none; }
.tool-guide-dialog .dialog-card { padding: 20px; }
.tool-guide-dialog .dialog-header h3 { font-size: 24px; }
.review-language-popover { border-radius: var(--radius-md); box-shadow: none; }
@media (max-width: 980px) {
.shell { grid-template-columns: 1fr; }
.sidebar { position: static; max-height: none; min-height: 0px; padding: 14px; }
.brand { margin-bottom: 14px; }
.sidebar-nav { grid-template-columns: repeat(2, minmax(0px, 1fr)); gap: 4px; }
.nav-accordion { grid-column: span 2; }
.sidebar-status { margin-top: 14px; }
.content { padding: 24px 20px 40px; }
.tool-guide-grid { grid-template-columns: repeat(2, minmax(0px, 1fr)); }
.tool-guide-card:nth-child(n) { grid-column: span 1; min-height: 176px; }
}
@media (max-width: 560px) {
.content { padding: 20px 14px 32px; }
.hero { margin-bottom: 18px; padding-bottom: 16px; }
.hero h1 { font-size: 25px; }
.sidebar-nav { grid-template-columns: 1fr; }
.nav-accordion { grid-column: span 1; }
.tool-guide-grid { grid-template-columns: 1fr; }
.tool-guide-card:nth-child(n) { min-height: 152px; }
.inline-notice { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) {
*, ::before, ::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
}
html { min-width: 320px; overflow-x: hidden; background: var(--panel-soft); color-scheme: dark; }
body { min-width: 320px; overflow-x: hidden; background-image: none; background-color: var(--panel-soft); background-size: auto, auto, 32px 32px, 32px 32px, auto; color: var(--ink); font-family: var(--font-ui); font-size: 14px; line-height: 1.5; }
::selection { background: var(--panel-soft); color: var(--ink); }
* { min-width: 0px; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { border: 3px solid transparent; border-radius: 999px; background: var(--panel-soft); }
::-webkit-scrollbar-thumb:hover { background: var(--panel-soft); }
:where(button, input, select, textarea, summary, a):focus-visible { outline: var(--focus) solid 2px; outline-offset: 2px; box-shadow: none; }
.shell { grid-template-columns: 244px minmax(0px, 1fr); min-height: 100dvh; }
.sidebar { position: sticky; top: 0px; min-height: 100dvh; max-height: 100dvh; padding: 22px 14px 16px; overflow-y: auto; background: var(--panel-soft); border-right: 1px solid var(--line); box-shadow: none; backdrop-filter: none; }
.brand { gap: 10px; margin: 0px 8px 28px; }
.brand-mark { width: 34px; height: 34px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-soft); box-shadow: none; }
.brand-copy { gap: 1px; }
.brand-version { order: 3; padding: 0px; color: var(--ink); background: transparent; font-size: 10px; font-weight: 600; letter-spacing: 0.08em; }
.brand strong { color: var(--ink); font-size: 15px; letter-spacing: -0.02em; }
.brand small { color: var(--ink); font-size: 11px; }
.sidebar-nav { gap: 5px; margin: 0px; }
.nav-link, .nav-link-top, .nav-link-sub { min-height: 38px; padding: 0px 10px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--ink); font-size: 13px; font-weight: 600; transition: color 0.18s, background 0.18s, border-color 0.18s, box-shadow 0.18s; }
.nav-link-top { min-height: 40px; color: var(--ink); font-weight: 600; }
.nav-link-sub { min-height: 34px; padding-left: 28px; color: var(--ink); font-size: 12px; }
.nav-link:hover, .nav-link-top:hover, .nav-accordion-summary:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.nav-link.active { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.nav-accordion, .nav-accordion[open] { overflow: visible; border: 0px; border-radius: 0px; background: transparent; box-shadow: none; }
.nav-accordion-summary { min-height: 40px; padding: 0px 10px; border: 1px solid transparent; border-radius: 5px; color: var(--ink); transition: color 0.18s, background 0.18s, border-color 0.18s; }
.nav-accordion-summary::after { width: 18px; height: 18px; border: 0px; border-radius: 4px; background: transparent; color: var(--ink); font-size: 17px; font-weight: 500; }
.nav-group-title { color: inherit; font-size: 13px; font-weight: 600; }
.nav-submenu { gap: 2px; padding: 3px 0px 5px; }
.sidebar-status { gap: 10px; margin: auto 0px 0px; padding: 12px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; backdrop-filter: none; }
.sidebar-status-heading { color: var(--ink); font-size: 10px; font-weight: 600; letter-spacing: 0.09em; }
.sidebar-local-badge { border-color: var(--line); border-radius: 3px; background: var(--panel-soft); color: var(--ink); }
.status-block { gap: 4px; border-bottom-color: var(--line); }
.status-caption { color: var(--ink); }
.status-block strong { color: var(--ink); }
.service-tip { color: var(--ink); }
.service-tip code { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.pill { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.pill.running { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.pill.failed { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.feedback-entry-button { min-height: 38px; border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.feedback-entry-button:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.content { width: min(1480px, 100%); max-width: none; padding: 36px 44px 56px; }
.hero { margin: 0px 0px 24px; padding: 0px 0px 22px; border-bottom: 1px solid var(--line); }
.hero-context { color: var(--ink); font-size: 11px; letter-spacing: 0.08em; }
.eyebrow { color: var(--ink); font-size: 11px; font-weight: 600; }
.hero-context-divider { background: var(--panel-soft); }
.hero h1 { color: var(--ink); font-size: clamp(27px, 2.4vw, 35px); letter-spacing: -0.045em; }
.lede { color: var(--ink); font-size: 14px; }
.inline-notice { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.inline-notice strong { color: var(--ink); }
.inline-notice-icon { color: var(--ink); }
.tool-guide-grid { grid-template-columns: repeat(6, minmax(0px, 1fr)); gap: 12px; }
.tool-guide-card { min-height: 196px; border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; color: var(--ink); backdrop-filter: none; transition: border-color 0.18s, background 0.18s, box-shadow 0.18s; }
.tool-guide-card:hover, .tool-guide-card:focus-visible { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.tool-guide-icon { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.tool-guide-badge { border-color: var(--line); border-radius: 3px; color: var(--ink); }
.tool-guide-badge-ai { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.tool-guide-card-copy strong { color: var(--ink); }
.tool-guide-card-copy small { color: var(--ink); }
.tool-guide-card-footer { border-top-color: var(--line); color: var(--ink); }
.tool-guide-arrow { color: var(--ink); }
.tool-guide-card-review { border-color: var(--line); background: var(--panel-soft); }
.tool-guide-card-review .tool-guide-icon { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.card, .advanced-card, .hero-card { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; backdrop-filter: none; }
.card { padding: 20px; margin-bottom: 16px; }
.advanced-card summary { padding: 16px 20px; }
.advanced-card summary::after { border-color: var(--line); border-radius: 4px; background: var(--panel-soft); color: var(--ink); }
.advanced-card summary strong, .section-header h2, .card-title h2, .card-title h3 { color: var(--ink); }
.advanced-card summary small, .card-title p, .section-header p { color: var(--ink); }
.stage-panel, .review-followup-context, .review-followup-messages { border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--panel-soft); }
label, .field-label { color: var(--ink); }
input, select, textarea { border-color: var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
input::placeholder, textarea::placeholder { color: var(--ink); }
input:hover, select:hover, textarea:hover { border-color: var(--line); }
input:focus, select:focus, textarea:focus { border-color: var(--line); }
select option { background: var(--panel-soft); color: var(--ink); }
.file-card, .check-line { border-color: var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); color: var(--ink); }
.file-card.empty { color: var(--ink); }
.check-line { min-height: 36px; }
.actions, .modal-actions, .modal-footer, .modal-footer-actions, .sticky-actions, .review-composer-footer { row-gap: 8px; }
button { min-height: 38px; border-radius: 5px; padding: 0px 13px; color: var(--ink); transition: transform 0.18s, border-color 0.18s, color 0.18s, background 0.18s, box-shadow 0.18s; }
button.primary { position: relative; isolation: isolate; overflow: hidden; min-height: 42px; border: 1px solid var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
button.primary::before { content: ""; position: absolute; z-index: -1; inset: 1px 48% 1px 1px; background: var(--panel-soft); }
button.primary:hover:not(:disabled) { transform: translateY(-1px); border-color: var(--line); background: var(--panel-soft); box-shadow: none; }
button.primary:active:not(:disabled) { transform: translateY(0px); box-shadow: none; }
button.secondary, .mini-button { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
button.secondary:hover:not(:disabled), .mini-button:hover:not(:disabled) { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
button.danger { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
button:disabled { opacity: 0.48; }
.subnav-link { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.subnav-link.active { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.sticky-actions { bottom: 14px; border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; backdrop-filter: none; }
.pattern-table-wrap, .result-box, .review-result-table-wrap, .review-input-table-wrap { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); }
.pattern-table, .result-box { background: transparent; color: var(--ink); }
.pattern-table th { background: var(--panel-soft); color: var(--ink); }
.pattern-table th, .pattern-table td { border-bottom-color: var(--line); }
.pattern-table tbody tr:hover { background: var(--panel-soft); }
.error-panel { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); }
.notice-button { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.update-notice-button { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.modal-overlay { z-index: 1200; padding: max(16px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) max(16px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); background: var(--panel-soft); backdrop-filter: none; }
.modal-card, .tool-guide-dialog .dialog-card { width: min(1120px, -32px + 100vw); max-height: min(820px, -32px + 100dvh); border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.modal-header { border-bottom: 1px solid var(--line); padding-bottom: 14px; }
.modal-header h3, .dialog-head h2, .tool-guide-dialog .dialog-header h3 { color: var(--ink); }
.modal-header p, .dialog-head p { color: var(--ink); }
.modal-close, .review-mapping-close { border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.modal-close:hover, .review-mapping-close:hover { background: var(--panel-soft); color: var(--ink); }
.skip-link { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.skip-link:focus { box-shadow: none; }
.dialog-body { border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.dialog-body .dialog-head { padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.dialog-body .dialog-actions { margin-top: 2px; padding-top: 14px; border-top: 1px solid var(--line); }
.dialog-body .icon-button { border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.dialog-body .icon-button:hover { background: var(--panel-soft); color: var(--ink); }
.dialog-body .field label, .dialog-body .mapping-template-hint { color: var(--ink); }
.dialog-body .hint { color: var(--ink); }
dialog.modal, .dialog { z-index: 1300; }
dialog.modal::backdrop, .dialog::backdrop { background: var(--panel-soft); backdrop-filter: none; }
.update-release-notes, .feedback-attachment-card, .feedback-log-card { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); }
.feedback-dropzone { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); }
.feedback-dropzone:hover, .feedback-dropzone:focus-visible { border-color: var(--line); background: var(--panel-soft); }
.feedback-dropzone-title { color: var(--ink); }
.feedback-log-card code { background: var(--panel-soft); color: var(--ink); }
.review-conversation-shell { height: clamp(580px, -188px + 100dvh, 820px); min-height: 580px; border-color: var(--line); border-radius: var(--radius-lg); background: var(--panel-soft); box-shadow: none; }
.review-session-sidebar { border-right-color: var(--line); background: var(--panel-soft); }
.review-session-row { border-radius: 5px; }
.review-session-row:hover, .review-session-row.active { background: var(--panel-soft); }
.review-session-row.active { box-shadow: none; }
.review-session-item { color: var(--ink); }
.review-session-item span { color: var(--ink); }
.review-session-rename { color: var(--ink); }
.review-session-rename:hover { background: var(--panel-soft); color: var(--ink); }
.review-conversation-head { border-bottom-color: var(--line); background: var(--panel-soft); }
.review-conversation-head h3 { color: var(--ink); }
.review-conversation-head p { color: var(--ink); }
.review-conversation-messages { padding: 24px clamp(18px, 7%, 84px); gap: 16px; }
.review-chat-message.user { border: 1px solid var(--line); border-radius: 12px 12px 3px; background: var(--panel-soft); color: var(--ink); }
.review-chat-message.workspace-report { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.review-workspace-preview-head strong, .review-workspace-file-head strong { color: var(--ink); }
.review-workspace-preview-head span, .review-workspace-file-head span, .review-workspace-mapping-head > span:last-child { color: var(--ink); }
.review-workspace-total, .review-workspace-language { border-color: var(--line); background: var(--panel-soft); color: var(--ink) !important; }
.review-workspace-file-card { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); }
.review-workspace-file-icon { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.review-workspace-mapping { border-top-color: var(--line); }
.review-workspace-endpoint { border-color: var(--line); border-radius: 6px; background: var(--panel-soft); }
.review-workspace-endpoint:last-child { border-color: var(--line); background: var(--panel-soft); }
.review-workspace-endpoint span, .review-workspace-reference { color: var(--ink); }
.review-workspace-endpoint strong { color: var(--ink); }
.review-workspace-arrow { color: var(--ink); }
.review-workspace-sample { border-color: var(--line); border-radius: 6px; background: var(--panel-soft); }
.review-workspace-sample > span { color: var(--ink); }
.review-workspace-sample-source { border-left-color: var(--line); color: var(--ink); }
.review-workspace-sample-target { border-left-color: var(--line); color: var(--ink); }
.review-workspace-empty { color: var(--ink); }
.review-workspace-notes { border-top-color: var(--line); color: var(--ink); }
.review-workspace-note-copy p { color: var(--ink); }
.review-chat-message-meta { color: var(--ink); }
.review-composer { margin: 0px clamp(18px, 7%, 84px) 20px; border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); box-shadow: none; backdrop-filter: none; }
.review-composer.dragging { border-color: var(--line); background: var(--panel-soft); }
.review-composer textarea { color: var(--ink); }
.composer-chip, .review-attachment-chip, .review-target-tab { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.composer-chip:hover, .review-target-tab:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.review-attachment-chip { background: var(--panel-soft); color: var(--ink); }
.review-message-file { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.review-stream-output, .review-thinking-details { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.review-thinking-details summary { color: var(--ink); }
.review-thinking-details[open] summary { border-bottom-color: var(--line); }
.review-thinking-details .review-stream-output { background: var(--panel-soft); }
.review-attachment-mapping-card { width: min(680px, -30px + 100vw); border-color: var(--line); border-radius: var(--radius-lg); }
.review-mapping-file-head { border-bottom: 1px solid var(--line); }
.review-mapping-file-icon { border-radius: 7px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.review-mapping-file-copy > span, .review-mapping-lead, .review-mapping-field-label span, .review-mapping-preset-panel > small { color: var(--ink); }
.review-mapping-file-copy h2, .review-mapping-field-label label, .review-import-mode-option strong { color: var(--ink); }
.review-import-mode-option { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); }
.review-import-mode-option:hover { border-color: var(--line); background: var(--panel-soft); }
.review-import-mode-option.selected { border-color: var(--line); background: var(--panel-soft); box-shadow: none; }
.review-import-mode-option small { color: var(--ink); }
.review-import-mode-option strong em { background: var(--panel-soft); color: var(--ink); }
.review-import-mode-option > i { background: var(--panel-soft); color: var(--ink); }
.review-import-mode-icon { border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.review-import-mode-option.selected .review-import-mode-icon { background: var(--panel-soft); color: var(--ink); }
.review-mapping-preset-panel { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); }
.sheet-tab { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.sheet-tab:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.sheet-tab.active { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.mapping-template-bar { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); }
.mapping-row { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); }
.mapping-col-id { color: var(--ink); }
.mapping-header { color: var(--ink); }
.mapping-row select, .mapping-row input[type="text"] { border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.mapping-row select:disabled, .mapping-row input[type="text"]:disabled { border-color: var(--line); background: var(--panel-soft); color: var(--ink); opacity: 1; }
.review-attachment-mapping-card > .modal-footer { border-top-color: var(--line); background: var(--panel-soft); }
.review-target-tab.active { border-color: var(--line); background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.review-send-button { min-width: 76px; border-radius: 5px; }
.review-language-popover { z-index: 60; border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.review-language-popover-head span, .review-language-search-wrap { color: var(--ink); border-bottom-color: var(--line); }
.review-language-option { color: var(--ink); border-radius: 4px; }
.review-language-option:hover { background: var(--panel-soft); }
.review-language-option.selected { background: var(--panel-soft); color: var(--ink); }
.review-language-check { color: var(--ink); }
.review-term-base-popover { border-color: var(--line); border-radius: var(--radius-md); background: var(--panel-soft); color: var(--ink); box-shadow: none; backdrop-filter: none; }
.review-term-base-action, .review-term-base-option { color: var(--ink); }
.review-term-base-action:hover, .review-term-base-option:hover { background: var(--panel-soft); }
.review-term-base-action-icon { background: var(--panel-soft); color: var(--ink); }
.review-term-base-action small, .review-term-base-option small { color: var(--ink); }
.review-term-base-options { border-top-color: var(--line); }
.review-term-base-option.selected { background: var(--panel-soft); color: var(--ink); }
.review-term-base-option-check { color: var(--ink); }
.review-term-base-delete { color: var(--ink); }
@media (max-width: 1120px) {
.content { padding: 30px 28px 46px; }
.tool-guide-grid { grid-template-columns: repeat(2, minmax(0px, 1fr)); }
.tool-guide-card:nth-child(n) { grid-column: span 1; min-height: 178px; }
}
@media (max-width: 980px) {
.shell { grid-template-columns: 1fr; }
.sidebar { position: static; min-height: 0px; max-height: none; padding: 14px; }
.brand { margin-bottom: 14px; }
.sidebar-nav { grid-template-columns: repeat(2, minmax(0px, 1fr)); gap: 5px; }
.nav-accordion { grid-column: span 2; }
.sidebar-status { margin-top: 14px; }
.content { padding: 24px 20px 40px; }
.review-conversation-shell { height: min(760px, -120px + 100dvh); min-height: 560px; }
}
@media (max-width: 700px) {
.content { padding: 20px 14px 34px; }
.hero { margin-bottom: 18px; padding-bottom: 17px; }
.hero h1 { font-size: 26px; }
.card { padding: 16px; }
.modal-card, .tool-guide-dialog .dialog-card { width: calc(-24px + 100vw); max-height: calc(-24px + 100dvh); padding: 16px; }
.modal-header { align-items: flex-start; }
.review-conversation-shell { height: min(720px, -96px + 100dvh); min-height: 520px; border-radius: 8px; }
.review-conversation-head { align-items: flex-start; padding: 14px; }
.review-conversation-head > :last-child { flex-wrap: wrap; justify-content: flex-end; }
.review-conversation-messages { padding: 16px; }
.review-composer { margin: 0px 12px 12px; padding: 10px; }
.review-composer-footer { align-items: stretch; flex-direction: column; }
.review-composer-tools { width: 100%; }
.review-send-button { align-self: flex-end; }
.review-workspace-samples { grid-template-columns: 1fr; }
.review-inline-progress { grid-template-columns: auto 1fr; }
.review-inline-progress > :last-child { grid-column: 1 / -1; }
.review-language-popover { bottom: 48px; width: calc(100% - 16px); left: 8px !important; }
.review-language-options { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 520px) {
.sidebar-nav { grid-template-columns: 1fr; }
.nav-accordion { grid-column: span 1; }
.tool-guide-grid { grid-template-columns: 1fr; }
.tool-guide-card:nth-child(n) { min-height: 152px; }
.grid.two, .stage-grid, .dashboard-grid { grid-template-columns: 1fr; }
.card-title { align-items: flex-start; flex-direction: column; gap: 6px; }
.actions > button, .modal-footer-actions > button { flex: 1 1 auto; }
.review-conversation-shell { min-height: 500px; }
.review-session-sidebar { padding: 10px; }
.review-conversation-list { gap: 4px; }
.review-session-item { padding: 7px; }
.review-decision-other-row { align-items: stretch; flex-direction: column; }
.review-decision-other-row input { width: 100%; min-width: 0px; }
.review-decision-other-row button { align-self: flex-end; }
.review-workspace-flow { grid-template-columns: 1fr; gap: 5px; }
.review-workspace-arrow { height: 16px; transform: rotate(90deg); }
.review-language-options { grid-template-columns: 1fr; max-height: 280px; }
}
body { background-image: none; background-color: var(--panel-soft); background-size: auto, auto, 32px 32px, 32px 32px, auto; }
.card, .advanced-card, .hero-card { background: var(--panel-soft); border-color: var(--line); box-shadow: none; }
.metrics { gap: 10px; }
.metrics div { min-height: 82px; padding: 13px 14px; border-color: var(--line); border-radius: 8px; background: var(--panel-soft); box-shadow: none; }
.metrics span { color: var(--ink); font-size: 12px; }
.metrics strong { color: var(--ink); font-size: 21px; letter-spacing: -0.025em; }
.compact-metrics div { background: var(--panel-soft); }
.compact-metrics strong { color: var(--ink); }
.stats-panel { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); box-shadow: none; }
.stats-title { color: var(--ink); }
.result-file, .notice-list div { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); box-shadow: none; }
.result-file strong { color: var(--ink); }
.result-file span, .result-file small { color: var(--ink); }
.cross-result-meta { border-bottom-color: var(--line); background: var(--panel-soft); }
.cross-result-meta span, .cross-cell { border-color: var(--line); border-radius: 7px; background: var(--panel-soft); color: var(--ink); }
.cross-cell:hover { border-color: var(--line); box-shadow: none; background: var(--panel-soft); }
.cross-cell.matched { border-color: var(--line); background: var(--panel-soft); }
.cross-cell-index { color: var(--ink); }
.cross-cell-text { color: var(--ink); }
.result-box, .log-box, pre { color: var(--ink); }
.progress-track, .progress-bar-wrap { background: var(--panel-soft); }
.progress-fill, .progress-bar { background: var(--panel-soft); }
button.primary { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
button.primary:hover:not(:disabled) { border-color: var(--line); background: var(--panel-soft); }
.tool-guide-card, .review-conversation-shell { background: var(--panel-soft); border-color: var(--line); }
.scope-item, .prompt-card, .cross-summary-box, .cross-empty-state, .cross-result-card, .cross-header-item, .diff-header-presence span, .diff-compare-field-list, .diff-compare-field-item, .review-followup-context, .review-followup-messages, .update-leaving-card { border-color: var(--line); border-radius: 8px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.scope-empty, .cross-empty-state { min-height: 58px; display: grid; place-items: center; border-style: dashed; color: var(--ink); background: var(--panel-soft); }
.prompt-card { gap: 10px; padding: 15px; }
.prompt-card strong { color: var(--ink); }
.prompt-card small { color: var(--ink); }
.prompt-card textarea, .scope-fields textarea, .review-followup-input textarea { border-color: var(--line); border-radius: 6px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.prompt-card textarea:disabled, .scope-fields textarea:disabled, textarea:disabled, input:disabled, select:disabled { border-color: var(--line); background: var(--panel-soft); color: var(--ink); opacity: 1; }
.prompt-badge { border: 1px solid var(--line); border-radius: 4px; background: var(--panel-soft); color: var(--ink); }
.prompt-badge.modified { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.scope-delete { border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.cross-summary-box { min-height: 112px; }
.cross-summary-box span, .cross-summary-box small, .cross-header-item span { color: var(--ink); }
.cross-summary-box strong { color: var(--ink); }
.cross-header-item { transition: border-color 0.18s, background 0.18s; }
.cross-header-item:hover { border-color: var(--line); background: var(--panel-soft); }
.cross-result-card { overflow: hidden; }
.cross-result-meta { border-bottom-color: var(--line); background: var(--panel-soft); }
.cross-result-meta span { border-color: var(--line); border-radius: 4px; background: var(--panel-soft); color: var(--ink); }
.cross-merge-actions .check { color: var(--ink); }
.diff-header-presence strong, .diff-compare-field-item span { color: var(--ink); }
.diff-compare-field-item { border-radius: 0px; border-width: 0px 0px 1px; border-bottom-color: var(--line); box-shadow: none; }
.diff-compare-field-item:last-child { border-bottom: 0px; }
.diff-compare-field-item:hover { background: var(--panel-soft); }
.diff-inline-side { border-color: var(--line); box-shadow: none; }
.diff-inline-side:hover { border-color: var(--line); box-shadow: none; }
.diff-inline-delete { background: var(--panel-soft); border-color: var(--line); }
.diff-inline-add { background: var(--panel-soft); border-color: var(--line); }
.diff-inline-delete .diff-inline-label { color: var(--ink); }
.diff-inline-add .diff-inline-label { color: var(--ink); }
.diff-inline-text, .followup-context-section p { color: var(--ink); }
.diff-token-delete { color: var(--ink); }
.diff-token-add { color: var(--ink); }
.summary-line span { border-color: var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); }
.followup-message.user { background: var(--panel-soft); color: var(--ink); }
.followup-message.assistant { background: var(--panel-soft); color: var(--ink); }
.review-followup-context, .review-followup-messages { overflow: auto; }
.review-detail-table td:nth-child(-n+5), .review-input-table td:nth-child(-n+3), .review-input-table td:last-child, .diff-preview-table td:nth-child(-n+4) { color: var(--ink); }
.pattern-table, .review-input-table, .review-result-table, .review-detail-table, .diff-preview-table { background: transparent; color: var(--ink); }
.pattern-table td, .review-input-table td, .review-result-table td, .review-detail-table td, .diff-preview-table td { border-bottom-color: var(--line); }
.pattern-table th, .review-input-table th, .review-result-table th, .review-detail-table th, .diff-preview-table th { background: var(--panel-soft); color: var(--ink); }
.update-leaving-card h2 { color: var(--ink); }
.update-leaving-card p { color: var(--ink); }
.tool-guide-dialog { width: min(860px, -32px + 100vw); max-height: calc(-32px + 100dvh); padding: 0px; overflow: hidden; }
.tool-guide-dialog .dialog-card { width: 100%; max-height: calc(-32px + 100dvh); display: grid; grid-template-rows: auto minmax(0px, 1fr); gap: 0px; padding: 0px; overflow: hidden; }
.tool-guide-dialog .dialog-header { min-width: 0px; padding: 20px 22px 16px; border-bottom: 1px solid var(--line); }
.tool-guide-dialog .dialog-header h3 { color: var(--ink); }
.tool-guide-dialog .dialog-kicker { color: var(--ink); }
.tool-guide-dialog .markdown-guide { min-height: 0px; overflow: auto; padding: 20px 22px 24px; color: var(--ink); }
.tool-guide-dialog .markdown-guide section { padding: 0px 0px 18px; border-bottom: 1px solid var(--line); }
.tool-guide-dialog .markdown-guide section + section { padding-top: 18px; }
.tool-guide-dialog .markdown-guide section:last-child { padding-bottom: 0px; border-bottom: 0px; }
.tool-guide-dialog .markdown-guide h4 { color: var(--ink); }
.tool-guide-dialog .markdown-guide p, .tool-guide-dialog .markdown-guide ul, .tool-guide-dialog .markdown-guide ol { color: var(--ink); }
.tool-guide-dialog .markdown-guide code { border-radius: 4px; background: var(--panel-soft); color: var(--ink); }
.compact-rule-table .pattern-actions button, .pattern-actions button { border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); box-shadow: none; }
.compact-rule-table .pattern-actions button:hover, .pattern-actions button:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.preprocess-progress-card { display: grid; gap: 14px; }
.preprocess-progress-card .card-title { margin-bottom: 0px; align-items: flex-start; }
.preprocess-progress-card .card-title > div { display: grid; gap: 4px; }
.preprocess-status-pill { flex: 0 0 auto; min-width: 54px; padding: 5px 9px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel-soft); color: var(--ink); font-size: 12px; font-weight: 600; text-align: center; }
.preprocess-status-pill.is-running { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.preprocess-status-pill.is-completed { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.preprocess-status-pill.is-failed { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.preprocess-status-pill.is-paused { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
.preprocess-progress-overview { display: grid; grid-template-columns: minmax(132px, 0.72fr) minmax(0px, 1.8fr) auto; align-items: stretch; gap: 1px; overflow: hidden; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }
.preprocess-progress-overview > div, .preprocess-progress-percent { display: grid; align-content: center; gap: 4px; min-height: 68px; padding: 12px 14px; background: var(--panel-soft); }
.preprocess-progress-overview span { color: var(--ink); font-size: 12px; }
.preprocess-progress-overview strong { color: var(--ink); font-size: 19px; letter-spacing: -0.02em; }
.preprocess-progress-percent { min-width: 74px; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink) !important; }
.preprocess-progress-card .progress { height: 7px; margin: -3px 0px 0px; border: 0px; border-radius: 999px; background: var(--panel-soft); }
.preprocess-progress-card .progress > span { display: block; height: 100%; border-radius: inherit; background: var(--panel-soft); box-shadow: none; transition: none; }
.preprocess-progress-metrics { display: grid; grid-template-columns: repeat(6, minmax(0px, 1fr)); gap: 8px; }
.preprocess-progress-metrics > div { display: grid; gap: 5px; min-width: 0px; padding: 10px 11px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel-soft); }
.preprocess-progress-metrics span { color: var(--ink); font-size: 11px; }
.preprocess-progress-metrics strong { overflow: hidden; color: var(--ink); font-size: 16px; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.preprocess-events { overflow: hidden; border: 1px solid var(--line); border-radius: 7px; background: var(--panel-soft); }
.preprocess-events-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 11px; border-bottom: 1px solid var(--line); background: var(--panel-soft); }
.preprocess-events-head strong { color: var(--ink); font-size: 12px; }
.preprocess-events-head span { color: var(--ink); font-size: 11px; }
.preprocess-events-list { display: grid; gap: 0px; }
.preprocess-event { display: grid; grid-template-columns: 8px minmax(0px, 1fr); align-items: center; gap: 8px; min-height: 30px; padding: 7px 11px; border-top: 1px solid var(--line); color: var(--ink); font-size: 12px; line-height: 1.4; }
.preprocess-event:first-child { border-top: 0px; }
.preprocess-event.is-latest { color: var(--ink); background: var(--panel-soft); }
.preprocess-event-marker { width: 5px; height: 5px; border-radius: 50%; background: var(--panel-soft); }
.preprocess-event.is-latest .preprocess-event-marker { background: var(--panel-soft); box-shadow: none; }
.preprocess-event span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preprocess-events-empty { padding: 11px; color: var(--ink); font-size: 12px; }
.review-request-queue { margin: 0px 0px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); overflow: hidden; }
.review-request-queue-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--line); background: var(--panel-soft); }
.review-request-queue-head strong { color: var(--ink); font-size: 13px; }
.review-request-queue-head span { color: var(--ink); font-size: 12px; white-space: nowrap; }
.review-request-columns { display: grid; grid-template-columns: repeat(3, minmax(0px, 1fr)); gap: 8px; max-height: 280px; overflow: auto; padding: 10px; }
.review-request-lane { min-width: 0px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel-soft); overflow: hidden; }
.review-request-lane-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 9px; border-bottom: 1px solid var(--line); font-size: 12px; }
.review-request-lane-head strong { color: var(--ink); font-weight: 600; }
.review-request-lane-head span { min-width: 20px; padding: 1px 6px; border: 1px solid var(--line); border-radius: 999px; color: var(--ink); font-variant-numeric: tabular-nums; text-align: center; }
.review-request-lane.status-queued .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-submitted .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-thinking .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-output .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-retrying .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-completed .review-request-lane-head { box-shadow: none; }
.review-request-lane.status-failed .review-request-lane-head { box-shadow: none; }
.review-request-items { display: grid; gap: 6px; padding: 8px; }
.review-request-item { display: grid; gap: 3px; padding: 7px 8px; border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); }
.review-request-item strong { color: var(--ink); font-size: 12px; font-weight: 600; }
.review-request-item span { overflow: hidden; color: var(--ink); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.review-request-item em { color: var(--ink); font-size: 11px; font-style: normal; }
.review-request-more { padding: 3px 2px 0px; color: var(--ink); font-size: 11px; }
.review-request-empty { padding: 10px; color: var(--ink); font-size: 12px; }
.sidebar-actions-panel { display: grid; gap: 8px; }
.theme-toggle-button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; width: 100%; min-height: 34px; border: 1px solid var(--line); border-radius: 5px; background: var(--panel-soft); color: var(--ink); font-size: 12px; font-weight: 600; box-shadow: none; }
.theme-toggle-icon { width: 14px; font-size: 15px; line-height: 1; }
.theme-toggle-button:hover { border-color: var(--line); background: var(--panel-soft); color: var(--ink); }
@media (max-width: 700px) {
.preprocess-progress-overview { grid-template-columns: 1fr auto; }
.preprocess-progress-stage { grid-column: 1 / -1; border-top: 1px solid var(--line); }
.preprocess-progress-metrics { grid-template-columns: repeat(3, minmax(0px, 1fr)); }
.review-request-columns { grid-template-columns: repeat(2, minmax(0px, 1fr)); }
.review-request-queue-head { align-items: flex-start; flex-direction: column; gap: 3px; }
.tool-guide-dialog { width: calc(-20px + 100vw); max-height: calc(-20px + 100dvh); }
.tool-guide-dialog .dialog-card { max-height: calc(-20px + 100dvh); }
.tool-guide-dialog .dialog-header { padding: 16px; }
.tool-guide-dialog .markdown-guide { padding: 16px; }
}
'''
