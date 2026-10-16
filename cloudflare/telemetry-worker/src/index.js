const EVENT_NAME_RE = /^[a-z0-9_.-]{3,80}$/;

const FEEDBACK_FIELD_TEXT = "\u53cd\u9988";
const FEEDBACK_FIELD_DATE = "\u65e5\u671f";
const FEEDBACK_FIELD_SCREENSHOT = "\u622a\u56fe";
const FEEDBACK_FIELD_LOG = "\u65e5\u5fd7";

const STATS_TABLE_NAME = "\u4f7f\u7528\u6b21\u6570\u7edf\u8ba1";
const STATS_FIELD_KEY = "\u952e";
const STATS_FIELD_DATE = "\u65e5\u671f";
const STATS_FIELD_EVENT = "\u7edf\u8ba1\u9879";
const STATS_FIELD_VERSION = "\u7248\u672c";
const STATS_FIELD_COUNT = "\u6b21\u6570";
const DEFAULT_FEISHU_APP_TOKEN = "IQzWbHaNSa0YS4s8TQ0cNwcjnig";
const DEFAULT_FEEDBACK_TABLE_ID = "tbllz4fLlof3RPsf";
const DEFAULT_STATS_TABLE_ID = "tblktD7KDOt1scMp";
const REVIEW_MONITOR_TABLE_NAME = "AI 审校记录";
const DEFAULT_PM_MAPPING_TABLE_ID = "tblRn2AV5qiHkEwS";
const REVIEW_FIELD_RECORD_ID = "记录ID";
const REVIEW_FIELD_TASK_ID = "任务关联ID";
const REVIEW_FIELD_FILENAME = "文件名";
const REVIEW_FIELD_PM = "PM";
const REVIEW_FIELD_STARTED = "执行时间";
const REVIEW_FIELD_FINISHED = "完成时间";
const REVIEW_FIELD_DURATION = "耗时";
const REVIEW_FIELD_STATUS = "状态";
const REVIEW_FIELD_LANGUAGE = "目标语言";
const REVIEW_FIELD_TOTAL = "条目数";
const REVIEW_FIELD_REQUESTED = "AI请求条数";
const REVIEW_FIELD_CACHED = "缓存命中数";
const REVIEW_FIELD_FAILED = "失败条目数";
const REVIEW_FIELD_MODEL = "模型";
const REVIEW_FIELD_VERSION = "应用版本";
const REVIEW_FIELD_ERROR = "错误类别";
const REVIEW_FIELD_ACTIVITY = "最后活动时间";
const REVIEW_MONITOR_FIELDS = [
  [REVIEW_FIELD_TASK_ID, 1], [REVIEW_FIELD_FILENAME, 1], [REVIEW_FIELD_PM, 1],
  [REVIEW_FIELD_STARTED, 5], [REVIEW_FIELD_FINISHED, 5], [REVIEW_FIELD_DURATION, 2],
  [REVIEW_FIELD_STATUS, 1], [REVIEW_FIELD_LANGUAGE, 1], [REVIEW_FIELD_TOTAL, 2],
  [REVIEW_FIELD_REQUESTED, 2], [REVIEW_FIELD_CACHED, 2], [REVIEW_FIELD_FAILED, 2],
  [REVIEW_FIELD_MODEL, 1], [REVIEW_FIELD_VERSION, 1], [REVIEW_FIELD_ERROR, 1],
  [REVIEW_FIELD_ACTIVITY, 5],
];
const PM_FIELD_ALIASES = ["PM", "pm", "PM姓名", "负责人", "负责人姓名", "姓名", "人员"];
const KEY_FIELD_ALIASES = ["API Key", "API key", "api key", "api_key", "Key", "key", "密钥", "DeepSeek API Key"];
let pmMappingCache = {
  loadedAt: 0,
  map: new Map(),
  conflicts: new Set(),
  error: "",
  recordCount: 0,
  mappedCount: 0,
  skippedCount: 0,
  fieldNames: [],
};
let pmMappingRefreshAt = 0;
const PM_MAPPING_CACHE_MS = 5 * 60 * 1000;
const PM_MAPPING_REFRESH_COOLDOWN_MS = 60 * 1000;
const STATE_APP_UPDATE_INFO = "app_update_info_v1";
const DAILY_USAGE_TOTAL_EVENTS = new Set([
  "task_start.text_preprocess",
  "task_start.ai_review",
  "task_action.cross_excel_search",
  "task_action.cross_excel_merge",
  "diff.compare.start",
]);

const CHUNK_CREATE_LIMIT = 1000;
const CHUNK_DELETE_LIMIT = 500;

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function utcDate(tsSeconds) {
  const date = new Date(Number(tsSeconds || Date.now() / 1000) * 1000);
  return date.toISOString().slice(0, 10);
}

function utcNow() {
  return new Date().toISOString();
}

function startOfUtcDay(dateText) {
  return Date.parse(`${String(dateText || "").trim()}T00:00:00.000Z`);
}

function chunkArray(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function normalizeEvents(body) {
  const version = String(body?.app_version || "").trim() || "unknown";
  const events = Array.isArray(body?.events) ? body.events : [];
  const normalized = [];
  for (const item of events) {
    const name = String(item?.name || "").trim();
    if (name === "review_monitor") continue;
    const count = Math.max(1, Math.min(100, Number(item?.count || 1) || 1));
    const ts = Number(item?.ts || Math.floor(Date.now() / 1000));
    if (!EVENT_NAME_RE.test(name)) {
      continue;
    }
    normalized.push({
      event_date: utcDate(ts),
      event_name: name,
      app_version: version,
      count,
    });
  }
  return normalized;
}

async function writeBatch(env, rows) {
  if (!rows.length) {
    return 0;
  }
  const merged = new Map();
  for (const row of rows) {
    const key = `${row.event_date}::${row.event_name}::${row.app_version}`;
    const existing = merged.get(key);
    if (existing) {
      existing.count += row.count;
      continue;
    }
    merged.set(key, { ...row });
  }
  const now = utcNow();
  const statements = [];
  for (const row of merged.values()) {
    statements.push(
      env.DB.prepare(
        `INSERT INTO event_counts (event_date, event_name, app_version, count, updated_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(event_date, event_name, app_version)
         DO UPDATE SET count = event_counts.count + excluded.count, updated_at = excluded.updated_at`
      ).bind(row.event_date, row.event_name, row.app_version, row.count, now)
    );
  }
  await env.DB.batch(statements);
  return merged.size;
}

async function readState(env, key) {
  const row = await env.DB.prepare("SELECT value FROM worker_state WHERE key = ?").bind(key).first();
  return row?.value ? String(row.value) : "";
}

async function writeState(env, key, value) {
  await env.DB.prepare(
    `INSERT INTO worker_state (key, value, updated_at)
     VALUES (?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`
  ).bind(key, String(value), utcNow()).run();
}

async function getTenantAccessToken(env) {
  const appId = String(env.FEISHU_APP_ID || "").trim();
  const appSecret = String(env.FEISHU_APP_SECRET || "").trim();
  if (!appId || !appSecret) {
    throw new Error("Feishu service is not configured.");
  }
  const response = await fetch("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      app_id: appId,
      app_secret: appSecret,
    }),
  });
  const data = await response.json();
  if (!response.ok || Number(data?.code || 0) !== 0 || !data?.tenant_access_token) {
    throw new Error(String(data?.msg || "Failed to get Feishu access token."));
  }
  return String(data.tenant_access_token);
}

async function createFeishuSession(env) {
  return {
    env,
    token: await getTenantAccessToken(env),
  };
}

function getConfiguredAppToken(env) {
  return String(env.FEISHU_BASE_APP_TOKEN || DEFAULT_FEISHU_APP_TOKEN).trim();
}

function getConfiguredFeedbackTableId(env) {
  return String(env.FEISHU_FEEDBACK_TABLE_ID || DEFAULT_FEEDBACK_TABLE_ID).trim();
}

function getConfiguredStatsTableId(env) {
  return String(env.FEISHU_STATS_TABLE_ID || DEFAULT_STATS_TABLE_ID).trim();
}

function getConfiguredPmMappingTableId(env) {
  return String(env.FEISHU_PM_MAPPING_TABLE_ID || DEFAULT_PM_MAPPING_TABLE_ID).trim();
}

function getConfiguredReviewMonitorTableId(env) {
  return String(env.FEISHU_REVIEW_MONITOR_TABLE_ID || "").trim();
}

function normalizeReviewRecords(body) {
  const records = Array.isArray(body?.review_records)
    ? body.review_records
    : (Array.isArray(body?.events) ? body.events.filter((item) => String(item?.name || "") === "review_monitor").map((item) => item.payload) : []);
  const version = String(body?.app_version || "").trim().slice(0, 80) || "unknown";
  const normalized = [];
  for (const item of records) {
    if (!item || typeof item !== "object") continue;
    const recordId = String(item.record_id || "").trim().slice(0, 128);
    if (!recordId) continue;
    normalized.push({
      record_id: recordId,
      task_id: String(item.task_id || recordId).trim().slice(0, 128),
      group_id: String(item.group_id || recordId).trim().slice(0, 160),
      revision: Math.max(1, Math.min(1000000000, Number(item.revision || 1) || 1)),
      expected_languages: Array.isArray(item.expected_languages)
        ? item.expected_languages.map((value) => String(value || "").trim().slice(0, 80)).filter(Boolean).slice(0, 20)
        : [],
      filename: String(item.filename || "未命名文件").trim().slice(0, 500),
      pm_fingerprint: String(item.pm_fingerprint || "").trim().toLowerCase().slice(0, 128),
      status: String(item.status || "运行中").trim().slice(0, 40),
      started_at: String(item.started_at || "").trim().slice(0, 40),
      finished_at: item.finished_at ? String(item.finished_at).trim().slice(0, 40) : null,
      last_activity_at: String(item.last_activity_at || item.started_at || utcNow()).trim().slice(0, 40),
      target_language: String(item.target_language || "").trim().slice(0, 80),
      total_count: Math.max(0, Math.min(100000000, Number(item.total_count || 0) || 0)),
      requested_count: Math.max(0, Math.min(100000000, Number(item.requested_count || 0) || 0)),
      cached_count: Math.max(0, Math.min(100000000, Number(item.cached_count || 0) || 0)),
      failed_count: Math.max(0, Math.min(100000000, Number(item.failed_count || 0) || 0)),
      model: String(item.model || "").trim().slice(0, 120),
      app_version: String(item.app_version || version).trim().slice(0, 80) || "unknown",
      error_category: String(item.error_category || "").trim().slice(0, 200),
      updated_at: utcNow(),
    });
  }
  return normalized;
}

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((item) => item.toString(16).padStart(2, "0")).join("");
}

function fieldValue(fields, aliases) {
  for (const alias of aliases) {
    const value = fields?.[alias];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (Array.isArray(value) && value.length) {
      const text = value.map((item) => typeof item === "string" ? item : item?.text || item?.name || "").join("").trim();
      if (text) return text;
    }
    if (value && typeof value === "object") {
      const text = String(value.text || value.name || value.value || "").trim();
      if (text) return text;
    }
  }
  return "";
}

async function loadPmMapping(env, session, force = false) {
  const now = Date.now();
  if (!force && pmMappingCache.loadedAt && now - pmMappingCache.loadedAt < PM_MAPPING_CACHE_MS) return pmMappingCache;
  if (now - pmMappingRefreshAt < PM_MAPPING_REFRESH_COOLDOWN_MS && pmMappingCache.loadedAt) return pmMappingCache;
  pmMappingRefreshAt = now;
  try {
    const records = await listRecords(session, getConfiguredAppToken(env), getConfiguredPmMappingTableId(env));
    const map = new Map();
    const conflicts = new Set();
    const fieldNames = new Set();
    let skippedCount = 0;
    for (const record of records) {
      const fields = record?.fields || {};
      for (const fieldName of Object.keys(fields)) fieldNames.add(fieldName);
      const key = fieldValue(fields, KEY_FIELD_ALIASES);
      const pm = fieldValue(fields, PM_FIELD_ALIASES);
      if (!key || !pm) {
        skippedCount += 1;
        continue;
      }
      const fingerprint = await sha256Hex(key);
      const existing = map.get(fingerprint);
      if (existing && existing !== pm) {
        conflicts.add(fingerprint);
      } else if (!conflicts.has(fingerprint)) {
        map.set(fingerprint, pm);
      }
    }
    pmMappingCache = {
      loadedAt: now,
      map,
      conflicts,
      error: "",
      recordCount: records.length,
      mappedCount: map.size,
      skippedCount,
      fieldNames: Array.from(fieldNames).sort(),
    };
  } catch {
    pmMappingCache = { ...pmMappingCache, error: "mapping_unavailable" };
  }
  return pmMappingCache;
}

function pmMappingSummary() {
  return {
    record_count: Number(pmMappingCache.recordCount || 0),
    mapped_count: Number(pmMappingCache.mappedCount || pmMappingCache.map.size || 0),
    skipped_count: Number(pmMappingCache.skippedCount || 0),
    conflict_count: pmMappingCache.conflicts.size,
    field_names: Array.isArray(pmMappingCache.fieldNames) ? pmMappingCache.fieldNames : [],
    error: String(pmMappingCache.error || ""),
  };
}

async function resolvePm(env, session, fingerprint) {
  const normalized = String(fingerprint || "").trim().toLowerCase();
  if (!normalized) return "未识别";
  let cache = await loadPmMapping(env, session, false);
  if (!cache.map.has(normalized) && !cache.conflicts.has(normalized)) {
    cache = await loadPmMapping(env, session, true);
  }
  if (cache.conflicts.has(normalized)) return "映射冲突";
  return cache.map.get(normalized) || "未识别";
}

async function upsertReviewMonitorRecords(env, records) {
  if (!records.length) return 0;
  let session = null;
  try {
    session = await createFeishuSession(env);
  } catch {
    session = null;
  }
  const resolved = [];
  for (const record of records) {
    let pm = "未识别";
    if (session) {
      try {
        pm = await resolvePm(env, session, record.pm_fingerprint);
      } catch {
        pm = pmMappingCache.map.get(record.pm_fingerprint) || "未识别";
      }
    }
    resolved.push({ ...record, pm });
  }
  const statements = resolved.map((record) => env.DB.prepare(
    `INSERT INTO review_monitor_records
      (record_id, task_id, group_id, revision, filename, pm_fingerprint, pm, status, started_at, finished_at,
       last_activity_at, target_language, total_count, requested_count, cached_count, failed_count,
       model, app_version, error_category, expected_languages_json, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(record_id) DO UPDATE SET
       task_id=excluded.task_id, group_id=excluded.group_id, revision=excluded.revision, filename=excluded.filename,
       pm_fingerprint=excluded.pm_fingerprint, pm=excluded.pm, status=excluded.status,
       started_at=excluded.started_at, finished_at=excluded.finished_at,
       last_activity_at=excluded.last_activity_at, target_language=excluded.target_language,
       total_count=excluded.total_count, requested_count=excluded.requested_count,
       cached_count=excluded.cached_count, failed_count=excluded.failed_count,
       model=excluded.model, app_version=excluded.app_version,
       error_category=excluded.error_category, expected_languages_json=excluded.expected_languages_json,
       updated_at=excluded.updated_at
       WHERE excluded.revision >= review_monitor_records.revision`
  ).bind(record.record_id, record.task_id, record.group_id, record.revision, record.filename, record.pm_fingerprint, record.pm,
    record.status, record.started_at, record.finished_at, record.last_activity_at, record.target_language,
    record.total_count, record.requested_count, record.cached_count, record.failed_count, record.model,
    record.app_version, record.error_category, JSON.stringify(record.expected_languages || []), record.updated_at));
  await env.DB.batch(statements);
  return resolved;
}

async function feishuJson(session, path, options = {}) {
  const response = await fetch(`https://open.feishu.cn${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${session.token}`,
      ...(options.headers || {}),
    },
  });
  const data = await response.json();
  if (!response.ok || Number(data?.code || 0) !== 0) {
    const message = String(data?.msg || data?.message || `Feishu request failed: ${response.status}`);
    throw new Error(message);
  }
  return data.data || {};
}

async function listFields(session, appToken, tableId) {
  const data = await feishuJson(
    session,
    `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields?page_size=100`,
    { method: "GET" }
  );
  return Array.isArray(data.items) ? data.items : [];
}

async function createField(session, appToken, tableId, fieldName, type) {
  await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      field_name: fieldName,
      type,
    }),
  });
}

async function updateField(session, appToken, tableId, fieldId, fieldName, type) {
  await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields/${fieldId}`, {
    method: "PUT",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      field_name: fieldName,
      type,
    }),
  });
}

async function deleteField(session, appToken, tableId, fieldId) {
  await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields/${fieldId}`, {
    method: "DELETE",
  });
}

async function listTables(session, appToken) {
  const data = await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables?page_size=100`, {
    method: "GET",
  });
  return Array.isArray(data.items) ? data.items : [];
}

async function createBitableTable(session, appToken, name) {
  const data = await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    // Feishu requires an initial field when default_view_name is supplied.
    // The first field becomes the table's primary text field.
    body: JSON.stringify({
      table: {
        name,
        default_view_name: "表格视图",
        fields: [{ field_name: REVIEW_FIELD_RECORD_ID, type: 1 }],
      },
    }),
  });
  return String(data.table_id || data.table?.table_id || "");
}

async function listRecords(session, appToken, tableId) {
  const records = [];
  let pageToken = "";
  while (true) {
    const params = new URLSearchParams({ page_size: "500" });
    if (pageToken) {
      params.set("page_token", pageToken);
    }
    const data = await feishuJson(
      session,
      `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records?${params.toString()}`,
      { method: "GET" }
    );
    records.push(...(Array.isArray(data.items) ? data.items : []));
    if (!data.has_more || !data.page_token) {
      break;
    }
    pageToken = String(data.page_token || "");
  }
  return records;
}

async function deleteAllRecords(session, appToken, tableId) {
  const records = await listRecords(session, appToken, tableId);
  if (!records.length) {
    return 0;
  }
  let deleted = 0;
  for (const batch of chunkArray(records, CHUNK_DELETE_LIMIT)) {
    await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records/batch_delete`, {
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        records: batch.map((item) => String(item.record_id || item.id || "")),
      }),
    });
    deleted += batch.length;
  }
  return deleted;
}

async function batchCreateRecords(session, appToken, tableId, records) {
  if (!records.length) {
    return 0;
  }
  let created = 0;
  for (const batch of chunkArray(records, CHUNK_CREATE_LIMIT)) {
    await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records/batch_create`, {
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        records: batch.map((fields) => ({ fields })),
      }),
    });
    created += batch.length;
  }
  return created;
}

async function batchUpdateRecords(session, appToken, tableId, records) {
  if (!records.length) return 0;
  let updated = 0;
  for (const batch of chunkArray(records, CHUNK_CREATE_LIMIT)) {
    await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records/batch_update`, {
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: JSON.stringify({ records: batch.map((item) => ({ record_id: item.record_id, fields: item.fields })) }),
    });
    updated += batch.length;
  }
  return updated;
}

async function ensurePrimaryTextField(session, appToken, tableId, targetName) {
  const fields = await listFields(session, appToken, tableId);
  const existing = fields.find((field) => String(field.field_name || "") === targetName);
  if (existing) {
    return;
  }
  const primaryText = fields.find((field) => Boolean(field.is_primary) && Number(field.type) === 1);
  if (primaryText) {
    await updateField(session, appToken, tableId, String(primaryText.field_id), targetName, 1);
    return;
  }
  const textField = fields.find((field) => Number(field.type) === 1);
  if (textField) {
    await updateField(session, appToken, tableId, String(textField.field_id), targetName, 1);
    return;
  }
  await createField(session, appToken, tableId, targetName, 1);
}

async function ensureNamedField(session, appToken, tableId, fieldName, type) {
  const fields = await listFields(session, appToken, tableId);
  if (fields.find((field) => String(field.field_name || "") === fieldName)) {
    return;
  }
  await createField(session, appToken, tableId, fieldName, type);
}

async function cleanupLegacySelectField(session, appToken, tableId) {
  const fields = await listFields(session, appToken, tableId);
  const selectField = fields.find(
    (field) => String(field.field_name || "") === "\u5355\u9009" && Number(field.type) === 3
  );
  if (selectField) {
    try {
      await deleteField(session, appToken, tableId, String(selectField.field_id));
    } catch {
    }
  }
}

async function cleanupUnexpectedFields(session, appToken, tableId, allowedNames) {
  const allowed = new Set(allowedNames.map((item) => String(item || "")));
  const fields = await listFields(session, appToken, tableId);
  for (const field of fields) {
    const fieldName = String(field.field_name || "");
    if (Boolean(field.is_primary)) {
      continue;
    }
    if (allowed.has(fieldName)) {
      continue;
    }
    try {
      await deleteField(session, appToken, tableId, String(field.field_id || ""));
    } catch {
    }
  }
}

async function ensureFeedbackTable(session) {
  const env = session.env;
  const appToken = getConfiguredAppToken(env);
  const tableId = getConfiguredFeedbackTableId(env);

  await ensurePrimaryTextField(session, appToken, tableId, FEEDBACK_FIELD_TEXT);
  await ensureNamedField(session, appToken, tableId, FEEDBACK_FIELD_DATE, 5);
  await ensureNamedField(session, appToken, tableId, FEEDBACK_FIELD_SCREENSHOT, 17);
  await ensureNamedField(session, appToken, tableId, FEEDBACK_FIELD_LOG, 17);
  await cleanupLegacySelectField(session, appToken, tableId);
  return { appToken, tableId };
}

async function ensureTelemetryStatsTable(session) {
  const env = session.env;
  const appToken = getConfiguredAppToken(env);
  const appUrl = `https://oy98p636wy.feishu.cn/base/${appToken}`;
  let tableId = getConfiguredStatsTableId(env);

  const tables = await listTables(session, appToken);
  const matchedTable = tables.find((item) => String(item.table_id || "") === tableId);
  if (!matchedTable) {
    const namedTable = tables.find((item) => String(item.name || "") === STATS_TABLE_NAME);
    if (!namedTable) {
      throw new Error(`Stats table is missing: ${tableId}`);
    }
    tableId = String(namedTable.table_id || "");
  }

  await cleanupUnexpectedFields(session, appToken, tableId, [
    STATS_FIELD_DATE,
    STATS_FIELD_EVENT,
    STATS_FIELD_VERSION,
    STATS_FIELD_COUNT,
  ]);
  await ensurePrimaryTextField(session, appToken, tableId, STATS_FIELD_KEY);
  await ensureNamedField(session, appToken, tableId, STATS_FIELD_DATE, 5);
  await ensureNamedField(session, appToken, tableId, STATS_FIELD_EVENT, 1);
  await ensureNamedField(session, appToken, tableId, STATS_FIELD_VERSION, 1);
  await ensureNamedField(session, appToken, tableId, STATS_FIELD_COUNT, 2);
  await cleanupLegacySelectField(session, appToken, tableId);

  return { appToken, appUrl, tableId };
}

async function ensureReviewMonitorTable(session) {
  const env = session.env;
  const appToken = getConfiguredAppToken(env);
  const appUrl = `https://oy98p636wy.feishu.cn/base/${appToken}`;
  let tableId = getConfiguredReviewMonitorTableId(env);
  const tables = await listTables(session, appToken);
  let matched = tableId ? tables.find((item) => String(item.table_id || "") === tableId) : null;
  if (!matched) {
    matched = tables.find((item) => String(item.name || "") === REVIEW_MONITOR_TABLE_NAME);
    tableId = matched ? String(matched.table_id || "") : "";
  }
  if (!tableId) {
    tableId = await createBitableTable(session, appToken, REVIEW_MONITOR_TABLE_NAME);
    if (!tableId) throw new Error("Failed to create review monitor table.");
  }
  await ensurePrimaryTextField(session, appToken, tableId, REVIEW_FIELD_RECORD_ID);
  for (const [fieldName, type] of REVIEW_MONITOR_FIELDS) {
    await ensureNamedField(session, appToken, tableId, fieldName, type);
  }
  return { appToken, appUrl, tableId };
}

function isoToMillis(value) {
  const timestamp = Date.parse(String(value || ""));
  return Number.isFinite(timestamp) ? timestamp : null;
}

function monitorDurationSeconds(row) {
  if (!row?.started_at || !row?.finished_at) return null;
  const start = Date.parse(String(row.started_at));
  const finish = Date.parse(String(row.finished_at));
  return Number.isFinite(start) && Number.isFinite(finish) ? Math.max(0, Math.round((finish - start) / 1000)) : null;
}

function buildReviewMonitorFields(row) {
  const fields = {
    [REVIEW_FIELD_TASK_ID]: String(row.task_id || ""),
    [REVIEW_FIELD_FILENAME]: String(row.filename || "未命名文件"),
    [REVIEW_FIELD_PM]: String(row.pm || "未识别"),
    [REVIEW_FIELD_STARTED]: isoToMillis(row.started_at),
    [REVIEW_FIELD_FINISHED]: isoToMillis(row.finished_at),
    [REVIEW_FIELD_DURATION]: monitorDurationSeconds(row),
    [REVIEW_FIELD_STATUS]: String(row.status || "运行中"),
    [REVIEW_FIELD_LANGUAGE]: String(row.target_language || ""),
    [REVIEW_FIELD_TOTAL]: Number(row.total_count || 0),
    [REVIEW_FIELD_REQUESTED]: Number(row.requested_count || 0),
    [REVIEW_FIELD_CACHED]: Number(row.cached_count || 0),
    [REVIEW_FIELD_FAILED]: Number(row.failed_count || 0),
    [REVIEW_FIELD_MODEL]: String(row.model || ""),
    [REVIEW_FIELD_VERSION]: String(row.app_version || ""),
    [REVIEW_FIELD_ERROR]: String(row.error_category || ""),
    [REVIEW_FIELD_ACTIVITY]: isoToMillis(row.last_activity_at),
  };
  for (const key of Object.keys(fields)) {
    if (fields[key] === null || fields[key] === undefined) delete fields[key];
  }
  fields[REVIEW_FIELD_RECORD_ID] = String(row.record_id || "");
  return fields;
}

async function loadReviewMonitorRows(env) {
  const result = await env.DB.prepare(
    `SELECT record_id, task_id, group_id, revision, filename, pm, pm_fingerprint, status, started_at, finished_at,
            last_activity_at, target_language, total_count, requested_count, cached_count,
            failed_count, model, app_version, error_category, expected_languages_json
     FROM review_monitor_records ORDER BY updated_at ASC`
  ).all();
  return Array.isArray(result.results) ? result.results : [];
}

function mergeReviewMonitorRows(rows) {
  const groups = new Map();
  for (const row of rows) {
    const groupId = String(row.group_id || row.record_id || "");
    if (!groups.has(groupId)) {
      groups.set(groupId, { ...row, record_id: groupId, task_id: groupId, _statuses: [String(row.status || "")],
        _languages: new Set([String(row.target_language || ""), ...JSON.parse(row.expected_languages_json || "[]")].filter(Boolean)),
        _task_ids: new Set([String(row.task_id || "")].filter(Boolean)) });
      continue;
    }
    const current = groups.get(groupId);
    current.total_count += Number(row.total_count || 0);
    current.requested_count += Number(row.requested_count || 0);
    current.cached_count += Number(row.cached_count || 0);
    current.failed_count += Number(row.failed_count || 0);
    current.target_language = Array.from(new Set(`${current.target_language || ""},${row.target_language || ""}`.split(",").map((item) => item.trim()).filter(Boolean))).join(", ");
    for (const language of [row.target_language, ...JSON.parse(row.expected_languages_json || "[]")]) {
      if (language) current._languages.add(language);
    }
    current.target_language = Array.from(current._languages).join(", ");
    if (row.task_id) current._task_ids.add(String(row.task_id));
    current.task_id = Array.from(current._task_ids).join(", ");
    current.started_at = [current.started_at, row.started_at].filter(Boolean).sort()[0] || current.started_at;
    current.finished_at = [current.finished_at, row.finished_at].filter(Boolean).sort().slice(-1)[0] || current.finished_at;
    current.last_activity_at = [current.last_activity_at, row.last_activity_at].filter(Boolean).sort().slice(-1)[0] || current.last_activity_at;
    current._statuses.push(String(row.status || ""));
    if (current.pm !== row.pm && row.pm) {
      if (current.pm === "未识别") current.pm = row.pm;
      else if (row.pm !== "未识别") current.pm = "映射冲突";
    }
  }
  for (const row of groups.values()) {
    const statuses = row._statuses;
    if (statuses.includes("运行中")) row.status = "运行中";
    else if (statuses.includes("联系中断")) row.status = "联系中断";
    else if (statuses.includes("失败") && statuses.some((item) => item === "完成" || item === "部分失败")) row.status = "部分失败";
    else if (statuses.includes("部分失败")) row.status = "部分失败";
    else if (statuses.every((item) => item === "完成")) row.status = "完成";
    else if (statuses.every((item) => item === "失败")) row.status = "失败";
    else row.status = statuses[0] || "运行中";
    const terminal = statuses.length > 0 && statuses.every((item) => ["完成", "部分失败", "失败"].includes(item));
    row.finished_at = terminal ? row.finished_at : null;
    delete row._statuses;
    delete row._languages;
    delete row._task_ids;
    delete row.expected_languages_json;
  }
  return Array.from(groups.values());
}

async function markStaleReviewRecords(env) {
  const cutoff = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  await env.DB.prepare(
    `UPDATE review_monitor_records SET status = '联系中断', updated_at = ?
     WHERE status = '运行中' AND last_activity_at < ?`
  ).bind(utcNow(), cutoff).run();
}

async function syncReviewMonitor(env) {
  await markStaleReviewRecords(env);
  // Ensure the monitoring table is visible even before the first release-client
  // task is reported. Previously the empty D1 state returned early and skipped
  // table creation entirely.
  const session = await createFeishuSession(env);
  const monitor = await ensureReviewMonitorTable(session);
  const rows = mergeReviewMonitorRows(await loadReviewMonitorRows(env));
  if (!rows.length) {
    return {
      ok: true,
      app_token: monitor.appToken,
      app_url: monitor.appUrl,
      monitor_table_id: monitor.tableId,
      monitor_row_count: 0,
      created_rows: 0,
      updated_rows: 0,
      pm_mapping: pmMappingSummary(),
    };
  }
  for (const row of rows) {
    try {
      const mappedPm = await resolvePm(env, session, row.pm_fingerprint);
      if (mappedPm !== "未识别" && mappedPm !== row.pm) {
        row.pm = mappedPm;
        await env.DB.prepare("UPDATE review_monitor_records SET pm = ?, updated_at = ? WHERE record_id = ?")
          .bind(mappedPm, utcNow(), row.record_id).run();
      }
    } catch {
    }
  }
  const existing = await listRecords(session, monitor.appToken, monitor.tableId);
  const byRecordId = new Map();
  for (const item of existing) {
    const id = fieldValue(item.fields || {}, [REVIEW_FIELD_RECORD_ID]);
    if (id) byRecordId.set(id, String(item.record_id || item.id || ""));
  }
  const creates = [];
  const updates = [];
  for (const row of rows) {
    const fields = buildReviewMonitorFields(row);
    const existingId = byRecordId.get(String(row.record_id || ""));
    if (existingId) updates.push({ record_id: existingId, fields });
    else creates.push(fields);
  }
  const updated = await batchUpdateRecords(session, monitor.appToken, monitor.tableId, updates);
  const created = await batchCreateRecords(session, monitor.appToken, monitor.tableId, creates);
  return {
    ok: true,
    app_token: monitor.appToken,
    app_url: monitor.appUrl,
    monitor_table_id: monitor.tableId,
    monitor_row_count: rows.length,
    created_rows: created,
    updated_rows: updated,
    pm_mapping: pmMappingSummary(),
  };
}

function decodeBase64Content(encoded) {
  const text = String(encoded || "").trim();
  if (!text) {
    return null;
  }
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function uploadAttachment(session, appToken, attachment) {
  if (!attachment?.content_base64) {
    return "";
  }
  const bytes = decodeBase64Content(attachment.content_base64);
  if (!bytes) {
    return "";
  }
  const form = new FormData();
  form.append("file_name", String(attachment.filename || "attachment.bin"));
  form.append("parent_type", "bitable_file");
  form.append("parent_node", appToken);
  form.append("size", String(bytes.byteLength));
  form.append(
    "file",
    new Blob([bytes], { type: String(attachment.mime_type || "application/octet-stream") }),
    String(attachment.filename || "attachment.bin")
  );
  const response = await fetch("https://open.feishu.cn/open-apis/drive/v1/medias/upload_all", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.token}`,
    },
    body: form,
  });
  const data = await response.json();
  if (!response.ok || Number(data?.code || 0) !== 0 || !data?.data?.file_token) {
    throw new Error(String(data?.msg || "Failed to upload attachment."));
  }
  return String(data.data.file_token);
}

function normalizeFeedbackBody(body) {
  return {
    appVersion: String(body?.app_version || "").trim() || "unknown",
    feedback: String(body?.feedback || "").trim(),
    screenshotAttachment: body?.screenshot_attachment || null,
    logAttachment: body?.log_attachment || null,
  };
}

async function createFeedbackRecord(env, body) {
  const session = await createFeishuSession(env);
  const normalized = normalizeFeedbackBody(body);
  if (!normalized.feedback) {
    throw new Error("Feedback text is required.");
  }
  const { appToken, tableId } = await ensureFeedbackTable(session);
  const screenshotToken = normalized.screenshotAttachment
    ? await uploadAttachment(session, appToken, normalized.screenshotAttachment)
    : "";
  const logToken = normalized.logAttachment
    ? await uploadAttachment(session, appToken, normalized.logAttachment)
    : "";

  const fields = {
    [FEEDBACK_FIELD_TEXT]: `Version: ${normalized.appVersion}\n\n${normalized.feedback}`,
    [FEEDBACK_FIELD_DATE]: Date.now(),
  };
  if (screenshotToken) {
    fields[FEEDBACK_FIELD_SCREENSHOT] = [{ file_token: screenshotToken }];
  }
  if (logToken) {
    fields[FEEDBACK_FIELD_LOG] = [{ file_token: logToken }];
  }

  await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({ fields }),
  });

  return {
    ok: true,
    app_token: appToken,
    table_id: tableId,
  };
}

async function loadEventRows(env) {
  const result = await env.DB.prepare(
    `SELECT event_date, event_name, app_version, count
     FROM event_counts
     ORDER BY event_date DESC, event_name ASC, app_version ASC`
  ).all();
  return Array.isArray(result.results) ? result.results : [];
}

function buildDailyTotals(rows) {
  const merged = new Map();
  for (const row of rows) {
    if (!DAILY_USAGE_TOTAL_EVENTS.has(String(row.event_name || "").trim())) {
      continue;
    }
    const date = String(row.event_date || "");
    const count = Number(row.count || 0);
    merged.set(date, (merged.get(date) || 0) + count);
  }
  return Array.from(merged.entries())
    .map(([eventDate, totalCount]) => ({ event_date: eventDate, total_count: totalCount }))
    .sort((left, right) => String(right.event_date).localeCompare(String(left.event_date)));
}

function buildEventTableRecords(rows) {
  return rows.map((row) => ({
    [STATS_FIELD_KEY]: `${row.event_date}::${row.event_name}::${row.app_version}`,
    [STATS_FIELD_DATE]: startOfUtcDay(row.event_date),
    [STATS_FIELD_EVENT]: String(row.event_name || ""),
    [STATS_FIELD_VERSION]: String(row.app_version || ""),
    [STATS_FIELD_COUNT]: Number(row.count || 0),
  }));
}

function buildStatsTableRecords(eventRows, dailyRows) {
  const records = [];
  for (const row of dailyRows) {
    records.push({
      [STATS_FIELD_KEY]: `daily::${row.event_date}`,
      [STATS_FIELD_DATE]: startOfUtcDay(row.event_date),
      [STATS_FIELD_EVENT]: "\u5f53\u65e5\u4f7f\u7528\u603b\u91cf",
      [STATS_FIELD_VERSION]: "",
      [STATS_FIELD_COUNT]: Number(row.total_count || 0),
    });
  }
  for (const row of eventRows) {
    records.push({
      [STATS_FIELD_KEY]: `${row.event_date}::${row.event_name}::${row.app_version}`,
      [STATS_FIELD_DATE]: startOfUtcDay(row.event_date),
      [STATS_FIELD_EVENT]: String(row.event_name || ""),
      [STATS_FIELD_VERSION]: String(row.app_version || ""),
      [STATS_FIELD_COUNT]: Number(row.count || 0),
    });
  }
  return records;
}

async function listDashboards(session, appToken) {
  const data = await feishuJson(session, `/open-apis/bitable/v1/apps/${appToken}/dashboards?page_size=100`, {
    method: "GET",
  }).catch(() => ({ items: [] }));
  return Array.isArray(data.items) ? data.items : [];
}

async function syncTelemetryStats(env) {
  const session = await createFeishuSession(env);
  const rows = await loadEventRows(env);
  const dailyRows = buildDailyTotals(rows);
  const stats = await ensureTelemetryStatsTable(session);

  const deleted = await deleteAllRecords(session, stats.appToken, stats.tableId);
  const created = await batchCreateRecords(session, stats.appToken, stats.tableId, buildStatsTableRecords(rows, dailyRows));
  const dashboards = await listDashboards(session, stats.appToken);

  return {
    ok: true,
    app_token: stats.appToken,
    app_url: stats.appUrl,
    stats_table_id: stats.tableId,
    event_row_count: rows.length,
    daily_row_count: dailyRows.length,
    deleted_rows: deleted,
    created_rows: created,
    dashboard_count: dashboards.length,
    dashboards,
  };
}

async function getStatsInfo(env) {
  const appToken = getConfiguredAppToken(env);
  let statsTableId = getConfiguredStatsTableId(env);
  const appUrl = appToken ? `https://oy98p636wy.feishu.cn/base/${appToken}` : "";
  const todayDate = utcDate();
  const placeholders = Array.from(DAILY_USAGE_TOTAL_EVENTS).map(() => "?").join(", ");
  const todayRow = await env.DB.prepare(
    `SELECT COALESCE(SUM(count), 0) AS total_count
     FROM event_counts
     WHERE event_date = ?
       AND event_name IN (${placeholders})`
  ).bind(todayDate, ...Array.from(DAILY_USAGE_TOTAL_EVENTS)).first();
  let dashboards = [];
  if (appToken) {
    const session = await createFeishuSession(env);
    dashboards = await listDashboards(session, appToken);
    const tables = await listTables(session, appToken);
    const matchedTable = tables.find(
      (item) => String(item.table_id || "") === statsTableId || String(item.name || "") === STATS_TABLE_NAME
    );
    if (matchedTable) {
      statsTableId = String(matchedTable.table_id || "");
    }
  }
  return {
    ok: true,
    has_stats_app: Boolean(appToken),
    app_token: appToken,
    app_url: appUrl,
    stats_table_id: statsTableId,
    dashboard_count: dashboards.length,
    dashboards,
    today_date: todayDate,
    today_total: Number(todayRow?.total_count || 0),
  };
}

function normalizeAppUpdateBody(body) {
  const latestVersion = String(body?.latest_version || body?.version || "").trim();
  const downloadUrl = String(body?.download_url || "").trim();
  if (!latestVersion) {
    throw new Error("latest_version is required.");
  }
  if (!downloadUrl) {
    throw new Error("download_url is required.");
  }
  return {
    latest_version: latestVersion,
    release_notes: String(body?.release_notes || "").trim(),
    published_at: String(body?.published_at || new Date().toISOString()).trim(),
    download_url: downloadUrl,
    asset_name: String(body?.asset_name || "").trim(),
    message: String(body?.message || "").trim(),
    updated_at: utcNow(),
  };
}

async function getAppUpdateInfo(env) {
  const raw = await readState(env, STATE_APP_UPDATE_INFO);
  if (!raw) {
    return {
      latest_version: "",
      release_notes: "",
      published_at: "",
      download_url: "",
      asset_name: "",
      message: "暂时没有可用的更新信息。",
    };
  }
  try {
    return JSON.parse(raw);
  } catch {
    return {
      latest_version: "",
      release_notes: "",
      published_at: "",
      download_url: "",
      asset_name: "",
      message: "更新信息读取失败。",
    };
  }
}

async function saveAppUpdateInfo(env, body) {
  const info = normalizeAppUpdateBody(body);
  await writeState(env, STATE_APP_UPDATE_INFO, JSON.stringify(info));
  return { ok: true, update: info };
}

function isAuthorizedAdminRequest(request, env) {
  const expectedToken = String(env.ADMIN_SYNC_TOKEN || "").trim();
  if (!expectedToken) {
    return false;
  }
  const authorization = String(request.headers.get("authorization") || "");
  return authorization === `Bearer ${expectedToken}`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({ ok: true, service: "yeehe-telemetry" });
    }

    if (request.method === "GET" && url.pathname === "/app-update") {
      try {
        return jsonResponse(await getAppUpdateInfo(env));
      } catch (error) {
        return jsonResponse({ ok: false, message: String(error?.message || "Failed to load update info.") }, 500);
      }
    }

    if (request.method === "POST" && url.pathname === "/admin/app-update") {
      if (!isAuthorizedAdminRequest(request, env)) {
        return jsonResponse({ ok: false, message: "Unauthorized" }, 401);
      }
      let body = {};
      try {
        body = await request.json();
      } catch {
        return jsonResponse({ ok: false, message: "Invalid JSON" }, 400);
      }
      try {
        return jsonResponse(await saveAppUpdateInfo(env, body));
      } catch (error) {
        return jsonResponse({ ok: false, message: String(error?.message || "Failed to save update info.") }, 400);
      }
    }

    if (request.method === "GET" && url.pathname === "/stats-info") {
      try {
        return jsonResponse(await getStatsInfo(env));
      } catch (error) {
        return jsonResponse({ ok: false, message: String(error?.message || "Failed to load stats info.") }, 500);
      }
    }

    if (request.method === "POST" && url.pathname === "/admin/sync-telemetry") {
      if (!isAuthorizedAdminRequest(request, env)) {
        return jsonResponse({ ok: false, message: "Unauthorized" }, 401);
      }
      try {
        const [stats, review] = await Promise.all([syncTelemetryStats(env), syncReviewMonitor(env)]);
        return jsonResponse({ ok: true, stats, review });
      } catch (error) {
        return jsonResponse({ ok: false, message: String(error?.message || "Sync failed.") }, 500);
      }
    }

    if (request.method === "POST" && url.pathname === "/collect") {
      let body = {};
      try {
        body = await request.json();
      } catch {
        return jsonResponse({ ok: false, message: "Invalid JSON" }, 400);
      }
      const rows = normalizeEvents(body);
      const written = rows.length ? await writeBatch(env, rows) : 0;
      return jsonResponse({ ok: true, accepted: rows.length, written });
    }

    if (request.method === "POST" && url.pathname === "/review-monitor") {
      let body = {};
      try {
        body = await request.json();
      } catch {
        return jsonResponse({ ok: false, message: "Invalid JSON" }, 400);
      }
      const records = normalizeReviewRecords(body);
      if (!records.length) {
        return jsonResponse({ ok: true, acknowledged: [] });
      }
      try {
        const resolved = await upsertReviewMonitorRecords(env, records);
        return jsonResponse({
          ok: true,
          acknowledged: resolved.map((record) => ({ record_id: record.record_id, revision: record.revision })),
        });
      } catch (error) {
        return jsonResponse({ ok: false, message: "Review monitor persistence failed." }, 503);
      }
    }

    if (request.method === "POST" && url.pathname === "/feedback") {
      let body = {};
      try {
        body = await request.json();
      } catch {
        return jsonResponse({ ok: false, message: "Invalid JSON" }, 400);
      }
      try {
        const result = await createFeedbackRecord(env, body);
        return jsonResponse(result);
      } catch (error) {
        return jsonResponse(
          {
            ok: false,
            message: String(error?.message || "Feedback submission failed."),
          },
          500
        );
      }
    }

    return jsonResponse({ ok: false, message: "Not found" }, 404);
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(Promise.allSettled([syncTelemetryStats(env), syncReviewMonitor(env)]));
  },
};
