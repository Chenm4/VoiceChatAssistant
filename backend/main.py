"""
FastAPI 主应用
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from backend.api.routes import router
from backend.utils.logger import get_app_logger

# 初始化日志
logger = get_app_logger()
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "5188")
FRONTEND_ORIGINS = [
    f"http://localhost:{FRONTEND_PORT}",
    f"http://127.0.0.1:{FRONTEND_PORT}",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# 创建 FastAPI 应用
app = FastAPI(
    title="ChatGPT Web API",
    description="语音识别 + AI 对话的 Web 应用",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router, prefix="/api")

# 挂载前端静态文件（生产环境）
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    logger.info(f"挂载前端静态文件: {frontend_dist}")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("="*60)
    logger.info("🚀 ChatGPT Web 应用启动")
    logger.info("="*60)
    logger.info("📡 API 端点: http://localhost:8888/api")
    logger.info(f"📱 前端开发地址: http://localhost:{FRONTEND_PORT}")
    logger.info("📚 API 文档: http://localhost:8888/docs")
    logger.info("📖 ReDoc: http://localhost:8888/redoc")
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用正在关闭...")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "服务运行正常"}


if __name__ == "__main__":
    import uvicorn

    logger.info("启动 Uvicorn 服务器...")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,  # 开发模式下自动重载
        log_level="info"
    )
