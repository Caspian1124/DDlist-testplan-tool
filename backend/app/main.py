from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title='DDlist Testplan Backend',
    version='0.2.0',
    description='DDlist 测试编排工具后端服务（FastAPI）',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router, prefix='/api')


@app.get('/')
def root():
    return {'service': 'DDlist Testplan Backend', 'status': 'running', 'docs': '/docs'}
