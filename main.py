import sys
import pathlib
import uvicorn
import pymysql

# 添加项目根目录到路径
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# 导入数据库初始化
from database_setup import initialize_database
from config import CFG

# 从 app.py 导入统一的 FastAPI 实例
from app import app, ensure_database


if __name__ == "__main__":
    # 初始化数据库表结构
    print("正在初始化数据库...")
    initialize_database()
    
    # 确保数据库存在
    ensure_database()
    
    print("启动综合管理系统 API...")
    print("财务管理系统 API 文档: http://127.0.0.1:8000/docs")
    print("用户中心 API 文档: http://127.0.0.1:8000/docs")
    print("订单系统 API 文档: http://127.0.0.1:8000/docs")
    print("商品管理系统 API 文档: http://127.0.0.1:8000/docs")
    
    # 使用导入字符串以支持热重载
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 热重载已启用
        log_level="info",
        access_log=True
    )
