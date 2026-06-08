const EVENT_NAME_RE = /^[a-z0-9_.-]{3,80}$/;
const FEEDBACK_TABLE_NAME = "反馈";
const FIELD_FEEDBACK = "反馈";
const FIELD_DATE = "日期";
const FIELD_SCREENSHOT = "截图";
const FIELD_LOG = "日志";

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

async function feishuJson(env, path, options = {}) {
  const token = await getTenantAccessToken(env);
  const response = await fetch(`https://open.feishu.cn${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
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

async function getTenantAccessToken(env) {
  const appId = String(env.FEISHU_APP_ID || "").trim();
  const appSecret = String(env.FEISHU_APP_SECRET || "").trim();
  if (!appId || !appSecret) {
    throw new Error("Feedback service is not configured.");
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

async function listFields(env, appToken, tableId) {
  const data = await feishuJson(
    env,
    `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields?page_size=100`,
    { method: "GET" }
  );
  return Array.isArray(data.items) ? data.items : [];
}

async function updateField(env, appToken, tableId, fieldId, fieldName, type) {
  await feishuJson(env, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields/${fieldId}`, {
    method: "PUT",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      field_name: fieldName,
      type,
    }),
  });
}

async function createField(env, appToken, tableId, fieldName, type) {
  await feishuJson(env, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields`, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      field_name: fieldName,
      type,
    }),
  });
}

async function deleteField(env, appToken, tableId, fieldId) {
  await feishuJson(env, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields/${fieldId}`, {
    method: "DELETE",
  });
}

async function createBitable(env) {
  const appData = await feishuJson(env, "/open-apis/bitable/v1/apps", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({ name: "译禾工具合集反馈" }),
  });
  const appToken = String(appData?.app?.app_token || "").trim();
  const tableId = String(appData?.app?.default_table_id || "").trim();
  if (!appToken || !tableId) {
    throw new Error("Failed to create feedback bitable.");
  }
  await writeState(env, "feedback_bitable_app_token", appToken);
  await writeState(env, "feedback_bitable_table_id", tableId);
  return { appToken, tableId };
}

async function ensureFeedbackTable(env) {
  let appToken = await readState(env, "feedback_bitable_app_token");
  let tableId = await readState(env, "feedback_bitable_table_id");
  if (!appToken || !tableId) {
    const created = await createBitable(env);
    appToken = created.appToken;
    tableId = created.tableId;
  }

  let fields = await listFields(env, appToken, tableId);
  const byName = new Map(fields.map((field) => [String(field.field_name || ""), field]));

  let feedbackField = byName.get(FIELD_FEEDBACK);
  if (!feedbackField) {
    const primaryText = fields.find((field) => Boolean(field.is_primary) && Number(field.type) === 1);
    if (primaryText) {
      await updateField(env, appToken, tableId, String(primaryText.field_id), FIELD_FEEDBACK, 1);
    } else {
      const textField = fields.find((field) => Number(field.type) === 1);
      if (textField) {
        await updateField(env, appToken, tableId, String(textField.field_id), FIELD_FEEDBACK, 1);
      } else {
        await createField(env, appToken, tableId, FIELD_FEEDBACK, 1);
      }
    }
    fields = await listFields(env, appToken, tableId);
  }

  if (!fields.find((field) => String(field.field_name || "") === FIELD_DATE)) {
    const dateField = fields.find((field) => Number(field.type) === 5);
    if (dateField) {
      await updateField(env, appToken, tableId, String(dateField.field_id), FIELD_DATE, 5);
    } else {
      await createField(env, appToken, tableId, FIELD_DATE, 5);
    }
    fields = await listFields(env, appToken, tableId);
  }

  if (!fields.find((field) => String(field.field_name || "") === FIELD_SCREENSHOT)) {
    const attachmentField = fields.find((field) => Number(field.type) === 17);
    if (attachmentField) {
      await updateField(env, appToken, tableId, String(attachmentField.field_id), FIELD_SCREENSHOT, 17);
    } else {
      await createField(env, appToken, tableId, FIELD_SCREENSHOT, 17);
    }
    fields = await listFields(env, appToken, tableId);
  }

  if (!fields.find((field) => String(field.field_name || "") === FIELD_LOG)) {
    const remainingAttachment = fields.find(
      (field) => Number(field.type) === 17 && String(field.field_name || "") !== FIELD_SCREENSHOT
    );
    if (remainingAttachment) {
      await updateField(env, appToken, tableId, String(remainingAttachment.field_id), FIELD_LOG, 17);
    } else {
      await createField(env, appToken, tableId, FIELD_LOG, 17);
    }
    fields = await listFields(env, appToken, tableId);
  }

  const singleSelectField = fields.find((field) => String(field.field_name || "") === "单选" && Number(field.type) === 3);
  if (singleSelectField) {
    try {
      await deleteField(env, appToken, tableId, String(singleSelectField.field_id));
    } catch {
    }
  }

  return { appToken, tableId };
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

async function uploadAttachment(env, appToken, attachment) {
  if (!attachment?.content_base64) {
    return "";
  }
  const bytes = decodeBase64Content(attachment.content_base64);
  if (!bytes) {
    return "";
  }
  const token = await getTenantAccessToken(env);
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
      Authorization: `Bearer ${token}`,
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
  const normalized = normalizeFeedbackBody(body);
  if (!normalized.feedback) {
    throw new Error("Feedback text is required.");
  }
  const { appToken, tableId } = await ensureFeedbackTable(env);
  const screenshotToken = normalized.screenshotAttachment
    ? await uploadAttachment(env, appToken, normalized.screenshotAttachment)
    : "";
  const logToken = normalized.logAttachment
    ? await uploadAttachment(env, appToken, normalized.logAttachment)
    : "";

  const fields = {
    [FIELD_FEEDBACK]: `版本：${normalized.appVersion}\n\n${normalized.feedback}`,
    [FIELD_DATE]: Date.now(),
  };
  if (screenshotToken) {
    fields[FIELD_SCREENSHOT] = [{ file_token: screenshotToken }];
  }
  if (logToken) {
    fields[FIELD_LOG] = [{ file_token: logToken }];
  }

  await feishuJson(env, `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records`, {
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({ ok: true, service: "yeehe-telemetry" });
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
};
