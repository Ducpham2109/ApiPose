import os
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from requests import RequestException

from label_odom2world_pose import manipulate_pose

load_dotenv()


class AdjustPoseRequest(BaseModel):
    input_rel_path: str = Field(..., description="Relative URL path (appended to NGINX_INPUT_BASE_URL) to *_PRIOR.rrd")
    xyz: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rpy: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])

    @validator("xyz")
    def _validate_xyz(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("xyz must have exactly 3 numbers")
        return [float(x) for x in v]

    @validator("rpy")
    def _validate_rpy(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("rpy must have exactly 3 numbers")
        return [float(x) for x in v]


class AdjustPoseResponse(BaseModel):
    output_rel_path: str = Field(
        ...,
        description="Relative URL path (appended to NGINX_INPUT_BASE_URL) to the processed RRD file",
    )
    output_url: str = Field(
        ...,
        description="Absolute URL (served by nginx) to the processed RRD file",
    )


app = FastAPI(title="RRD Pose Adjust API")

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

def _resolve_storage_root() -> Path:
    root = os.getenv("STORAGE_ROOT", "")
    if not root:
        raise RuntimeError("Missing STORAGE_ROOT in environment")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _nginx_input_base_url() -> str:
    url = os.getenv("NGINX_INPUT_BASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("Missing NGINX_INPUT_BASE_URL in environment")
    return url


def _input_prefix_parts() -> list[str]:
    prefix = os.getenv("INPUT_PATH_PREFIX", "uploads").strip()
    if not prefix:
        return []
    return [
        segment
        for segment in Path(prefix.lstrip("/\\")).parts
        if segment not in {"", "."}
    ]


def _normalize_rel_path(rel_path: str) -> Path:
    cleaned = rel_path.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="input_rel_path cannot be empty")

    rel = Path(cleaned.lstrip("/\\"))
    if not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
        raise HTTPException(status_code=400, detail="Invalid input_rel_path")
    return rel


def _download_input_rrd(storage_root: Path, rel_path: str) -> tuple[Path, Path, list[str]]:
    rel = _normalize_rel_path(rel_path)
    prefix_parts = _input_prefix_parts()
    rel_parts = list(rel.parts)
    prefix_consumed = False
    if prefix_parts and rel_parts[: len(prefix_parts)] == prefix_parts:
        rel_parts = rel_parts[len(prefix_parts) :]
        prefix_consumed = True

    stripped_rel = Path(*rel_parts)
    if not stripped_rel.parts:
        raise HTTPException(status_code=400, detail="input_rel_path cannot point to a directory")

    target_path = storage_root.joinpath(*stripped_rel.parts)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_url = urljoin(f"{_nginx_input_base_url()}/", rel.as_posix())
    try:
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
    except RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Failed to download input RRD: {exc}") from exc

    with target_path.open("wb") as file_handle:
        file_handle.write(response.content)

    return target_path, stripped_rel, prefix_parts if prefix_consumed else []


def _build_output_relative_path(input_rel: Path) -> Path:
    if not input_rel.parts:
        raise HTTPException(status_code=400, detail="Invalid input_rel_path")

    file_name = input_rel.name
    if "_PRIOR.rrd" not in file_name:
        raise HTTPException(status_code=400, detail="input_rel_path must point to *_PRIOR.rrd")
    file_name = file_name.replace("_PRIOR.rrd", ".rrd")

    base_dir_parts = list(input_rel.parent.parts)
    override_dir = os.getenv("OUTPUT_BASE_REL_PATH", "").strip()
    if override_dir:
        base_dir_parts = [
            segment for segment in Path(override_dir.lstrip("/\\")).parts if segment not in {"", "."}
        ]
    else:
        target_segment = os.getenv("OUTPUT_TARGET_SEGMENT", "process")
        if "origin" in base_dir_parts:
            idx = base_dir_parts.index("origin")
            base_dir_parts[idx] = target_segment
        else:
            base_dir_parts.append(target_segment)

    relative = Path(*base_dir_parts, file_name) if base_dir_parts else Path(file_name)

    prefix = os.getenv("OUTPUT_PATH_PREFIX", "").strip()
    if prefix:
        prefix_parts = [segment for segment in Path(prefix.lstrip("/\\")).parts if segment not in {"", "."}]
        relative = Path(*prefix_parts, *relative.parts)

    return relative


@app.post("/api/adjust-pose", response_model=AdjustPoseResponse)
def adjust_pose(payload: AdjustPoseRequest = Body(...)) -> AdjustPoseResponse:
    storage_root = _resolve_storage_root()

    # download input RRD via nginx into storage_root
    base_rrd_path, input_rel, input_prefix = _download_input_rrd(storage_root, payload.input_rel_path)

    # gọi hàm xử lý
    try:
        class _Args:
            def __init__(self, base_rrd: str, xyz: list[float], rpy: list[float]) -> None:
                self.base_rrd = base_rrd
                self.xyz = xyz
                self.rpy = rpy

        manipulate_pose(_Args(str(base_rrd_path), payload.xyz, payload.rpy))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    # output file: đổi _PRIOR.rrd → .rrd
    output_rel = _build_output_relative_path(input_rel)
    output_rrd = storage_root.joinpath(*output_rel.parts)
    output_rrd.parent.mkdir(parents=True, exist_ok=True)

    processed_source = Path(str(base_rrd_path).replace("_PRIOR.rrd", ".rrd"))
    if output_rrd.exists():
        output_rrd.unlink()
    processed_source.replace(output_rrd)

    response_rel = Path(*input_prefix, *output_rel.parts) if input_prefix else output_rel
    relative_path = response_rel.as_posix()
    absolute_url = urljoin(f"{_nginx_input_base_url().rstrip('/')}/", relative_path)

    return AdjustPoseResponse(output_rel_path=relative_path, output_url=absolute_url)


def create_app() -> FastAPI:
    return app
