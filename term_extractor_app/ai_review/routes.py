from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.cache_service import (
    clear_read_cache,
    create_batch,
    get_batch,
    get_batch_items,
    get_latest_ready_batch,
    open_directory,
    replace_batch_items,
    save_upload_file,
)
from app.config import OUTPUTS_DIR, STATIC_DIR, ensure_directories
from app.database import init_db
from app.deepseek_client import DeepSeekError, list_models, test_chat
from app.directional_service import (
    delete_directional_template,
    get_directional_template,
    list_directional_templates,
    save_directional_template,
)
from app.forbidden_service import (
    delete_forbidden_template,
    get_forbidden_template,
    list_forbidden_templates,
    save_forbidden_template,
)
from app.file_reader import (
    detect_file_type,
    read_excel_headers,
    read_excel_items,
    read_excel_items_by_mapping,
    read_xliff_items,
    read_xliff_language_metadata,
)
from app.excel_mapping_service import (
    delete_excel_mapping_preset,
    get_excel_mapping_preset,
    list_excel_mapping_presets,
    save_excel_mapping_preset,
)
from app.prompt_service import (
    delete_prompt_template,
    get_prompt_template,
    list_prompt_templates,
    reset_default_prompt_template,
    save_prompt_template,
)
from app.review_service import (
    ReviewTaskError,
    create_review_task,
    get_review_logs,
    get_review_results,
    get_review_task,
)
from app.settings_service import get_ai_settings, public_ai_settings, save_ai_settings


class SelectColumnsRequest(BaseModel):
    batch_id: str
    source_column: str
    target_column: str


class ExcelMappingRequest(BaseModel):
    batch_id: str
    mapping: dict


class ExcelMappingPresetSaveRequest(BaseModel):
    id: str | None = None
    name: str
    mapping: dict


class DeepSeekLoadRequest(BaseModel):
    api_key: str
    max_concurrency: int = 8
    max_chars_per_request: int = 3000
    enable_thinking: bool = False


class DeepSeekSaveRequest(BaseModel):
    selected_model: str
    max_concurrency: int = 8
    max_chars_per_request: int = 3000
    enable_thinking: bool = False


class PromptTemplateSaveRequest(BaseModel):
    id: str | None = None
    name: str
    system_prompt: str
    user_prompt: str


class StartReviewRequest(BaseModel):
    batch_id: str
    prompt_template_id: str | None = None
    source_language: str = ""
    target_language: str = ""
    mode: str = "normal"
    directional_template_id: str | None = None
    enable_ai_review: bool = True
    enable_forbidden_check: bool = False
    forbidden_template_id: str | None = None


class DirectionalTemplateSaveRequest(BaseModel):
    id: str | None = None
    name: str
    items: list[dict]


class ForbiddenTemplateSaveRequest(BaseModel):
    id: str | None = None
    name: str
    words_text: str


app = FastAPI(title="AI 定向审校工具")


@app.on_event("startup")
def on_startup() -> None:
    ensure_directories()
    init_db()


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "unknown"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")

    stored_path = save_upload_file(filename, data)
    try:
        file_type = detect_file_type(stored_path)
        if file_type == "excel":
            metadata = read_excel_headers(stored_path)
            batch_id = create_batch(
                original_filename=filename,
                stored_path=stored_path,
                file_type=file_type,
                status="uploaded",
                metadata=metadata,
            )
            return {
                "file_type": file_type,
                "batch_id": batch_id,
                "filename": filename,
                "headers": metadata["headers"],
                "headers_by_sheet": metadata["headers_by_sheet"],
                "columns_by_sheet": metadata["columns_by_sheet"],
                "sheet_names": metadata["sheet_names"],
                "needs_column_selection": True,
            }

        items = read_xliff_items(stored_path, filename)
        language_metadata = read_xliff_language_metadata(stored_path)
        batch_id = create_batch(
            original_filename=filename,
            stored_path=stored_path,
            file_type=file_type,
            status="uploaded",
            metadata=language_metadata,
        )
        replace_batch_items(
            batch_id=batch_id,
            items=items,
            metadata_update={"preview_ready": True, **language_metadata},
        )
        return _batch_response(batch_id, "XLIFF 读取完成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取失败：{exc}") from exc


@app.post("/api/select-columns")
def select_columns(payload: SelectColumnsRequest) -> dict:
    batch = get_batch(payload.batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="读取批次不存在")
    if batch["file_type"] != "excel":
        raise HTTPException(status_code=400, detail="只有 Excel 文件需要选择列")

    stored_path = Path(batch["stored_path"])
    try:
        items = read_excel_items(
            stored_path,
            payload.source_column,
            payload.target_column,
            batch["original_filename"],
        )
        replace_batch_items(
            batch_id=payload.batch_id,
            items=items,
            source_column=payload.source_column,
            target_column=payload.target_column,
            metadata_update={"preview_ready": True},
        )
        return _batch_response(payload.batch_id, "Excel 读取完成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取失败：{exc}") from exc


@app.post("/api/select-excel-mapping")
def select_excel_mapping(payload: ExcelMappingRequest) -> dict:
    batch = get_batch(payload.batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="读取批次不存在")
    if batch["file_type"] != "excel":
        raise HTTPException(status_code=400, detail="只有 Excel 文件需要配置列映射")

    stored_path = Path(batch["stored_path"])
    try:
        items = read_excel_items_by_mapping(stored_path, payload.mapping, batch["original_filename"])
        replace_batch_items(
            batch_id=payload.batch_id,
            items=items,
            source_column=None,
            target_column=None,
            metadata_update={
                "preview_ready": True,
                "excel_mapping": payload.mapping,
                "source_language": str(payload.mapping.get("source_language") or ""),
                "target_language": str(payload.mapping.get("target_language") or ""),
            },
        )
        return _batch_response(payload.batch_id, "Excel 列映射读取完成")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取失败：{exc}") from exc


@app.get("/api/excel-mapping-presets")
def excel_mapping_presets() -> dict:
    return {"presets": list_excel_mapping_presets()}


@app.get("/api/excel-mapping-presets/{preset_id}")
def excel_mapping_preset(preset_id: str) -> dict:
    try:
        return {"preset": get_excel_mapping_preset(preset_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/excel-mapping-presets")
def save_excel_mapping(payload: ExcelMappingPresetSaveRequest) -> dict:
    preset = save_excel_mapping_preset(payload.name, payload.mapping, payload.id)
    return {"ok": True, "message": "Excel 列映射预设已保存", "preset": preset}


@app.delete("/api/excel-mapping-presets/{preset_id}")
def delete_excel_mapping(preset_id: str) -> dict:
    try:
        delete_excel_mapping_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": "Excel 列映射预设已删除"}


@app.get("/api/cache/latest")
def latest_cache() -> dict:
    batch = get_latest_ready_batch()
    if not batch:
        return {"has_cache": False}
    return {"has_cache": True, **_batch_response(batch["id"], "发现上一批读取缓存")}


@app.post("/api/cache/use")
def use_cache() -> dict:
    batch = get_latest_ready_batch()
    if not batch:
        raise HTTPException(status_code=404, detail="没有可用读取缓存")
    return _batch_response(batch["id"], "已使用上一批读取缓存")


@app.post("/api/cache/clear")
def clear_cache() -> dict:
    clear_read_cache()
    return {"ok": True, "message": "读取缓存已清空"}


@app.get("/api/ai/settings")
def ai_settings() -> dict:
    return public_ai_settings()


@app.post("/api/ai/deepseek/load")
def load_deepseek(payload: DeepSeekLoadRequest) -> dict:
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="请填写 DeepSeek API Key")
    try:
        models = list_models(api_key)
    except DeepSeekError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not models:
        raise HTTPException(status_code=400, detail="没有读取到可用模型")

    selected_model = models[0]
    current = get_ai_settings()
    if current.get("selected_model") in models:
        selected_model = current["selected_model"]
    elif "deepseek-chat" in models:
        selected_model = "deepseek-chat"

    save_ai_settings(
        {
            "api_key": api_key,
            "models": models,
            "selected_model": selected_model,
            "max_concurrency": max(1, payload.max_concurrency),
            "max_chars_per_request": max(1, payload.max_chars_per_request),
            "enable_thinking": bool(payload.enable_thinking),
        }
    )
    return {"ok": True, "message": "DeepSeek 模型加载完成", **public_ai_settings()}


@app.post("/api/ai/deepseek/save")
def save_deepseek(payload: DeepSeekSaveRequest) -> dict:
    settings = get_ai_settings()
    models = settings.get("models", [])
    if payload.selected_model and models and payload.selected_model not in models:
        raise HTTPException(status_code=400, detail="所选模型不在当前可用模型列表中")
    save_ai_settings(
        {
            "selected_model": payload.selected_model,
            "max_concurrency": max(1, payload.max_concurrency),
            "max_chars_per_request": max(1, payload.max_chars_per_request),
            "enable_thinking": bool(payload.enable_thinking),
        }
    )
    return {"ok": True, "message": "AI 设置已保存", **public_ai_settings()}


@app.post("/api/ai/deepseek/test")
def test_deepseek() -> dict:
    settings = get_ai_settings()
    api_key = settings.get("api_key", "")
    model = settings.get("selected_model", "")
    enable_thinking = bool(settings.get("enable_thinking", False))
    if not api_key:
        raise HTTPException(status_code=400, detail="请先加载 DeepSeek API Key")
    if not model:
        raise HTTPException(status_code=400, detail="请先选择模型")
    try:
        content = test_chat(api_key, model, enable_thinking=enable_thinking)
    except DeepSeekError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "测试 OK", "model": model, "response": content}


@app.get("/api/prompt-templates")
def prompt_templates() -> dict:
    return {"templates": list_prompt_templates()}


@app.get("/api/prompt-templates/{template_id}")
def prompt_template(template_id: str) -> dict:
    try:
        return {"template": get_prompt_template(template_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/prompt-templates")
def save_template(payload: PromptTemplateSaveRequest) -> dict:
    try:
        template = save_prompt_template(
            template_id=payload.id,
            name=payload.name.strip() or "未命名模板",
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "提示词模板已保存", "template": template}


@app.post("/api/prompt-templates/reset-default")
def reset_prompt_default() -> dict:
    template = reset_default_prompt_template()
    return {"ok": True, "message": "默认提示词已恢复", "template": template}


@app.delete("/api/prompt-templates/{template_id}")
def delete_template(template_id: str) -> dict:
    try:
        delete_prompt_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "提示词模板已删除"}


@app.get("/api/directional-templates")
def directional_templates() -> dict:
    return {"templates": list_directional_templates()}


@app.get("/api/directional-templates/{template_id}")
def directional_template(template_id: str) -> dict:
    try:
        return {"template": get_directional_template(template_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/directional-templates")
def save_directional(payload: DirectionalTemplateSaveRequest) -> dict:
    try:
        template = save_directional_template(
            payload.id,
            payload.name.strip() or "未命名定向模板",
            payload.items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "定向审校模板已保存", "template": template}


@app.delete("/api/directional-templates/{template_id}")
def delete_directional(template_id: str) -> dict:
    try:
        delete_directional_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "定向审校模板已删除"}


@app.get("/api/forbidden-templates")
def forbidden_templates() -> dict:
    return {"templates": list_forbidden_templates()}


@app.get("/api/forbidden-templates/{template_id}")
def forbidden_template(template_id: str) -> dict:
    try:
        return {"template": get_forbidden_template(template_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/forbidden-templates")
def save_forbidden(payload: ForbiddenTemplateSaveRequest) -> dict:
    try:
        template = save_forbidden_template(
            payload.id,
            payload.name.strip() or "未命名禁用词模板",
            payload.words_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "禁用词模板已保存", "template": template}


@app.delete("/api/forbidden-templates/{template_id}")
def delete_forbidden(template_id: str) -> dict:
    try:
        delete_forbidden_template(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "禁用词模板已删除"}


@app.post("/api/review/start")
def start_review(payload: StartReviewRequest) -> dict:
    try:
        task_id = create_review_task(
            payload.batch_id,
            payload.prompt_template_id,
            payload.source_language.strip(),
            payload.target_language.strip(),
            payload.mode,
            payload.directional_template_id,
            payload.enable_ai_review,
            payload.enable_forbidden_check,
            payload.forbidden_template_id,
        )
    except (ReviewTaskError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    task = get_review_task(task_id)
    return {"ok": True, "message": "审校任务已启动", "task": task}


@app.post("/api/outputs/open")
def open_outputs() -> dict:
    try:
        open_directory(OUTPUTS_DIR)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"打开目录失败：{exc}") from exc
    return {"ok": True, "message": "已打开结果目录", "path": str(OUTPUTS_DIR)}


@app.get("/api/review/tasks/{task_id}")
def review_task(task_id: str) -> dict:
    task = get_review_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="审校任务不存在")
    return {
        "task": task,
        "results": get_review_results(task_id, limit=10),
    }


@app.get("/api/review/tasks/{task_id}/logs")
def review_logs(task_id: str, after_id: int = 0) -> dict:
    if not get_review_task(task_id):
        raise HTTPException(status_code=404, detail="审校任务不存在")
    return {"logs": get_review_logs(task_id, after_id)}


def _batch_response(batch_id: str, message: str) -> dict:
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="读取批次不存在")
    preview = get_batch_items(batch_id, limit=5)
    return {
        "ok": True,
        "message": message,
        "batch": {
            "id": batch["id"],
            "filename": batch["original_filename"],
            "file_type": batch["file_type"],
            "source_column": batch["source_column"],
            "target_column": batch["target_column"],
            "item_count": batch["item_count"],
            "source_language": batch["metadata"].get("source_language", ""),
            "target_language": batch["metadata"].get("target_language", ""),
            "updated_at": batch["updated_at"],
        },
        "preview": preview,
    }
