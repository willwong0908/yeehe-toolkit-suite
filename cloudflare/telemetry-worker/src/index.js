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
const STATE_APP_UPDATE_INFO = "app_update_info_v1";

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
  const todayRow = await env.DB.prepare(
    `SELECT COALESCE(SUM(count), 0) AS total_count
     FROM event_counts
     WHERE event_date = ?`
  ).bind(todayDate).first();
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
        return jsonResponse(await syncTelemetryStats(env));
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
      if (!rows.length) {
        return jsonResponse({ ok: true, accepted: 0 });
      }
      const written = await writeBatch(env, rows);
      return jsonResponse({ ok: true, accepted: rows.length, written });
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
    ctx.waitUntil(syncTelemetryStats(env));
  },
};
