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
    output_url: str = Field(..., description="URL path to the processed RRD file")


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


def _normalize_rel_path(rel_path: str) -> Path:
    cleaned = rel_path.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="input_rel_path cannot be empty")

    rel = Path(cleaned.lstrip("/\\"))
    if not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
        raise HTTPException(status_code=400, detail="Invalid input_rel_path")
    return rel


def _download_input_rrd(storage_root: Path, rel_path: str) -> Path:
    rel = _normalize_rel_path(rel_path)
    target_path = storage_root.joinpath(*rel.parts)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_url = urljoin(f"{_nginx_input_base_url()}/", rel.as_posix())
    try:
        response = requests.get(source_url, timeout=30)
        response.raise_for_status()
    except RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Failed to download input RRD: {exc}") from exc

    with target_path.open("wb") as file_handle:
        file_handle.write(response.content)

    return target_path


@app.post("/api/adjust-pose", response_model=AdjustPoseResponse)
def adjust_pose(payload: AdjustPoseRequest = Body(...)) -> AdjustPoseResponse:
    storage_root = _resolve_storage_root()

    # download input RRD via nginx into storage_root
    base_rrd_path = _download_input_rrd(storage_root, payload.input_rel_path)

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
    output_rrd = Path(str(base_rrd_path).replace("_PRIOR.rrd", ".rrd"))

    try:
        # Move the generated file so that upload paths swap "origin" for "process"
        rel_to_root = output_rrd.relative_to(storage_root)
        rel_path = Path(rel_to_root)
        rel_parts = list(rel_path.parts)
        file_name = rel_parts[-1]
        dir_parts = rel_parts[:-1]

        target_dir_parts = dir_parts.copy()
        if "origin" in target_dir_parts:
            idx = target_dir_parts.index("origin")
            target_dir_parts[idx] = "process"
        else:
            target_dir_parts.append("process")

        target_dir = storage_root.joinpath(*target_dir_parts) if target_dir_parts else storage_root / "process"
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / file_name
        if target.exists():
            target.unlink()
        output_rrd.replace(target)
        output_rrd = target
    except Exception:
        pass

    # build lại relative path cho response
    rel_posix = (
        output_rrd.relative_to(storage_root).as_posix()
        if storage_root in output_rrd.parents
        else output_rrd.name
    )
    rel_url_path = f"/{rel_posix}"

    return AdjustPoseResponse(
        output_url=rel_url_path
    )


def create_app() -> FastAPI:
    return app
