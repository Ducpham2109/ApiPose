import os
from pathlib import Path

from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

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


@app.post("/api/adjust-pose", response_model=AdjustPoseResponse)
def adjust_pose(payload: AdjustPoseRequest = Body(...)) -> AdjustPoseResponse:
    storage_root = _resolve_storage_root()

    # lấy file input từ storage_root + input_rel_path
    base_rrd_path = storage_root / payload.input_rel_path.lstrip("/")
    if not base_rrd_path.is_file():
        raise HTTPException(status_code=400, detail="Input RRD not found")

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
        rel_to_root = output_rrd.relative_to(storage_root)

        parts = list(Path(rel_to_root).parts)
        if "origin" in parts:
            idx = parts.index("origin")
            pre = parts[:idx]
            target_dir = storage_root.joinpath(*pre, "process")
        else:
            parent_rel = Path(rel_to_root).parent
            target_dir = storage_root / parent_rel / "process"

        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / output_rrd.name
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
