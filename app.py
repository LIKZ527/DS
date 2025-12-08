"""
统一的应用入口 - 集中创建 FastAPI 实例和配置
"""
import sys
import pathlib
import pymysql
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到路径
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# 导入配置和数据库初始化
from config import CFG
from database_setup import initialize_database

# 导入路由注册函数
from finance.api_interface import register_finance_routes
from user.app.routes import register_routes as register_user_routes
from order import register_routes as register_order_routes
from product.api_interface import register_routes as register_product_routes


def ensure_database():
    """确保数据库存在"""
    try:
        pymysql.connect(**CFG, cursorclass=pymysql.cursors.DictCursor).close()
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1049:
            print("📦 数据库不存在，正在自动创建并初始化 …")
            initialize_database()
            print("✅ 自动初始化完成！")
        else:
            raise


# 创建统一的 FastAPI 应用实例
app = FastAPI(
    title="综合管理系统API",
    description="财务管理系统 + 用户中心 + 订单系统 + 商品管理",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI 文档地址
    redoc_url="/redoc",  # ReDoc 文档地址
    openapi_url="/openapi.json"  # OpenAPI Schema 地址
)

# 定义 OpenAPI Tags 元数据，用于在 Swagger UI 中更好地组织接口
tags_metadata = [
    {
        "name": "财务系统",
        "description": "财务管理系统相关接口，包括用户管理、订单结算、退款、补贴、提现、奖励、报表等功能。",
    },
    {
        "name": "用户中心",
        "description": "用户中心相关接口，包括用户认证、资料管理、地址管理、积分管理、团队奖励、董事功能等。",
    },
    {
        "name": "订单系统",
        "description": "订单系统相关接口，包括购物车、订单管理、退款、地址管理、商家后台等功能。",
    },
    {
        "name": "商品管理",
        "description": "商品管理系统相关接口，包括商品搜索、商品列表、商品详情、商品创建、商品更新、图片上传、轮播图、销售数据等功能。",
    },
]

# 更新 OpenAPI Schema 的 tags 元数据
app.openapi_tags = tags_metadata

# 自定义 OpenAPI Schema 生成函数，确保只显示定义的3个标签
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=tags_metadata,  # 只使用定义的3个标签
    )
    # 过滤掉未定义的标签，只保留 tags_metadata 中定义的标签
    defined_tag_names = {tag["name"] for tag in tags_metadata}
    if "tags" in openapi_schema:
        openapi_schema["tags"] = [tag for tag in openapi_schema["tags"] if tag["name"] in defined_tag_names]
    # 确保所有路径的 tags 都在定义的标签列表中
    if "paths" in openapi_schema:
        for path_item in openapi_schema["paths"].values():
            for operation in path_item.values():
                if "tags" in operation and operation["tags"]:
                    # 如果路由使用了未定义的标签，根据内容替换为合适的标签
                    filtered_tags = []
                    for tag in operation["tags"]:
                        if tag in defined_tag_names:
                            filtered_tags.append(tag)
                        elif "订单系统" in tag:
                            filtered_tags.append("订单系统")
                        elif "商品" in tag or "商品管理" in tag or "商品扩展" in tag:
                            filtered_tags.append("商品管理")
                    operation["tags"] = filtered_tags if filtered_tags else ["商品管理"]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# 添加 CORS 中间件（统一配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件（订单系统）
# 注意：需要确保 static 目录存在
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"⚠️ 静态文件目录挂载失败（可忽略）: {e}")

# 注册所有模块的路由
register_finance_routes(app)
register_user_routes(app)
register_order_routes(app)
register_product_routes(app)
