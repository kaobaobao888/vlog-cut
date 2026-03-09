"""
Vlog 自动剪辑工具 - 后端主程序

根据用户上传的视频素材和文案，自动将视频切割成与文案段落对应的片段并拼接成完整 vlog。
使用 FFmpeg 进行视频处理，支持多视频上传和智能分段。
"""

import os
import re
import uuid
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 创建应用
app = FastAPI(
    title="Vlog 自动剪辑工具",
    description="根据视频素材和文案自动剪辑 vlog 视频",
    version="1.0.0"
)

# 跨域配置，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 工作目录配置
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_script_into_segments(script: str) -> List[str]:
    """
    将文案解析为段落列表。
    
    按空行、换行符分割，过滤空段落，保留有内容的文本块。
    每个段落对应视频中的一个剪辑片段。
    
    Args:
        script: 用户输入的完整文案
        
    Returns:
        段落列表，每个元素为一个文案段落
    """
    if not script or not script.strip():
        return []
    
    # 按双换行或单换行分割，同时处理不同换行符
    raw_segments = re.split(r'\n\s*\n|\r\n\s*\r\n', script.strip())
    
    # 过滤空段落，去除首尾空白
    segments = [s.strip() for s in raw_segments if s.strip()]
    
    return segments


def get_video_duration(video_path: str) -> float:
    """
    使用 FFprobe 获取视频时长（秒）。
    
    Args:
        video_path: 视频文件路径
        
    Returns:
        视频时长（秒），失败时返回 0
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return 0.0


def cut_video_segment(
    input_path: str,
    output_path: str,
    start_time: float,
    duration: float
) -> bool:
    """
    切割视频片段。
    
    使用 FFmpeg 的 -ss -t 参数进行精确切割，-c copy 避免重新编码以加快速度。
    
    Args:
        input_path: 输入视频路径
        output_path: 输出片段路径
        start_time: 开始时间（秒）
        duration: 片段时长（秒）
        
    Returns:
        是否成功
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss", str(start_time),
                "-i", input_path,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "1",
                output_path
            ],
            capture_output=True,
            timeout=120,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def concatenate_videos(input_paths: List[str], output_path: str) -> bool:
    """
    将多个视频片段拼接成一个文件。
    
    使用 FFmpeg concat demuxer，需要先创建 concat 列表文件。
    
    Args:
        input_paths: 输入视频路径列表（按顺序）
        output_path: 输出视频路径
        
    Returns:
        是否成功
    """
    if not input_paths:
        return False
    
    # 创建 concat 列表文件
    list_path = Path(output_path).parent / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in input_paths:
            # FFmpeg concat 需要 file 'path' 格式，路径中的单引号需转义
            escaped = str(Path(p).absolute()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c", "copy",
                output_path
            ],
            capture_output=True,
            timeout=300,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    finally:
        if list_path.exists():
            list_path.unlink()


def process_vlog(
    video_paths: List[str],
    script: str,
    output_path: str
) -> tuple[bool, str]:
    """
    核心处理逻辑：根据文案段落将视频切割并拼接。
    
    策略：
    1. 将文案按段落分割
    2. 计算所有视频总时长
    3. 按段落数量均分总时长，得到每个片段的目标时长
    4. 按顺序从视频列表中取片段（支持多视频循环使用）
    5. 拼接所有片段
    
    Args:
        video_paths: 上传的视频文件路径列表
        script: 用户文案
        output_path: 最终输出视频路径
        
    Returns:
        (是否成功, 错误信息)
    """
    segments = parse_script_into_segments(script)
    if not segments:
        return False, "文案为空或无法解析出有效段落"
    
    if not video_paths:
        return False, "未上传任何视频"
    
    # 获取每个视频的时长
    durations = []
    for vp in video_paths:
        d = get_video_duration(vp)
        if d <= 0:
            return False, f"无法读取视频时长: {Path(vp).name}"
        durations.append(d)
    
    total_duration = sum(durations)
    segment_count = len(segments)
    segment_duration = total_duration / segment_count
    
    work_dir = Path(output_path).parent
    chunk_paths = []
    current_video_idx = 0
    current_offset = 0.0
    
    for i in range(segment_count):
        # 循环使用多个视频
        while current_video_idx < len(video_paths):
            vp = video_paths[current_video_idx]
            dur = durations[current_video_idx]
            remaining = dur - current_offset
            take = min(segment_duration, remaining)
            if take > 0.1:  # 至少 0.1 秒
                break
            current_video_idx += 1
            current_offset = 0
        
        if current_video_idx >= len(video_paths):
            return False, "视频总时长不足，无法生成与文案段落数量匹配的片段"
        
        vp = video_paths[current_video_idx]
        chunk_path = work_dir / f"chunk_{i}.mp4"
        if not cut_video_segment(vp, str(chunk_path), current_offset, take):
            for c in chunk_paths:
                if Path(c).exists():
                    Path(c).unlink()
            return False, f"切割视频片段失败: 片段 {i+1}"
        
        chunk_paths.append(str(chunk_path))
        current_offset += take
        if current_offset >= dur - 0.01:
            current_video_idx += 1
            current_offset = 0
    
    if not concatenate_videos(chunk_paths, output_path):
        for c in chunk_paths:
            if Path(c).exists():
                Path(c).unlink()
        return False, "拼接视频失败"
    
    for c in chunk_paths:
        if Path(c).exists():
            Path(c).unlink()
    
    return True, ""


def cleanup_old_files():
    """清理过期的上传和输出文件（超过 1 小时）"""
    import time
    now = time.time()
    for d in [UPLOAD_DIR, OUTPUT_DIR]:
        for f in d.iterdir():
            if f.is_file():
                if now - f.stat().st_mtime > 3600:
                    try:
                        f.unlink()
                    except OSError:
                        pass


@app.post("/api/process")
async def process_vlog_api(
    background_tasks: BackgroundTasks,
    script: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    处理 vlog 剪辑请求。
    
    接收文案和多个视频文件，返回任务 ID，后续通过 /api/status/{task_id} 和 /api/download/{task_id} 获取结果。
    """
    if not script.strip():
        raise HTTPException(status_code=400, detail="文案不能为空")
    
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个视频文件")
    
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    video_paths = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
            continue
        path = task_dir / f.filename
        with open(path, "wb") as out:
            content = await f.read()
            out.write(content)
        video_paths.append(str(path))
    
    if not video_paths:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="未上传有效的视频文件（支持 mp4/mov/avi/mkv/webm）")
    
    output_path = str(OUTPUT_DIR / f"{task_id}.mp4")
    
    success, err = process_vlog(video_paths, script, output_path)
    
    # 清理上传的原始文件
    shutil.rmtree(task_dir, ignore_errors=True)
    
    if not success:
        raise HTTPException(status_code=500, detail=err)
    
    background_tasks.add_task(cleanup_old_files)
    
    return {"task_id": task_id, "status": "completed", "download_url": f"/api/download/{task_id}"}


@app.get("/api/download/{task_id}")
async def download_video(task_id: str):
    """下载处理完成的视频"""
    path = OUTPUT_DIR / f"{task_id}.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="视频不存在或已过期")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"vlog_{task_id[:8]}.mp4"
    )


# 静态文件（生产环境前端构建产物）
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        @app.get("/")
        async def serve_index():
            return FileResponse(index_html)


@app.get("/api/health")
async def health():
    """健康检查，用于检测 FFmpeg 是否可用"""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None
    return {
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
