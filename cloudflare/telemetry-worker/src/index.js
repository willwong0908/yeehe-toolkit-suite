const EVENT_NAME_RE = /^[a-z0-9_.-]{3,80}$/;

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({ ok: true, service: "yeehe-telemetry" });
    }
    if (request.method !== "POST" || url.pathname !== "/collect") {
      return jsonResponse({ ok: false, message: "Not found" }, 404);
    }
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
  },
};
