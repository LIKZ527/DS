# database_setup.py - 表结构与项目2完全一致
# 注意：此文件主要用于数据库表结构定义和初始化
# 日常数据库操作请使用 config.get_conn() 或 core.database.get_conn()
import logging
from sqlalchemy import create_engine
from sqlalchemy.sql import text  # 仅用于表结构初始化
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from config import get_db_config, PLATFORM_MERCHANT_ID, MEMBER_PRODUCT_PRICE, LOG_FILE

# 配置日志：统一输出到 logs/api.log
# 注意：如果 finance_logic.py 已经配置了 basicConfig，这里不会重复配置
# 使用 getLogger 获取 logger 实例，共享全局日志配置
logger = logging.getLogger(__name__)

_engine = None

# SQLAlchemy Base 类（用于 ORM 模型定义，product 模块仍在使用）
Base = declarative_base()

def get_engine():
    global _engine
    if _engine is None:
        try:
            cfg = get_db_config()
            connection_url = (
                f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
                f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
                f"?charset={cfg['charset']}"
            )
            _engine = create_engine(
                connection_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_pre_ping=True,
                echo=False
            )
            logger.info("✅ SQLAlchemy 引擎已创建 (pool_size=20)")
        except Exception as e:
            logger.error(f"❌ SQLAlchemy 引擎创建失败: {e}")
            raise
    return _engine

# engine - 用于兼容 product 模块（延迟初始化）
# 注意：这是一个属性访问，每次访问都会调用 get_engine()
# 为了兼容 product 模块，我们提供一个属性访问方式
class _EngineProxy:
    """Engine 代理类，用于兼容 product 模块"""
    def __getattr__(self, name):
        return getattr(get_engine(), name)
    
    def __call__(self, *args, **kwargs):
        return get_engine()(*args, **kwargs)
    
    def connect(self, *args, **kwargs):
        return get_engine().connect(*args, **kwargs)
    
    def execute(self, *args, **kwargs):
        return get_engine().execute(*args, **kwargs)

# 创建 engine 实例（兼容 product 模块）
engine = _EngineProxy()

# 注意：以下 Session 相关代码已废弃，统一使用 config.get_conn() 或 core.database.get_conn()
# 保留 engine 用于表结构定义和初始化
# 
# 如需使用数据库连接，请使用：
#   from config import get_conn
#   with get_conn() as conn:
#       with conn.cursor() as cur:
#           cur.execute("SELECT ...")

class DatabaseManager:
    def __init__(self):
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        try:
            temp_config = get_db_config().copy()
            database = temp_config.pop('database')
            import pymysql
            conn = pymysql.connect(**temp_config)
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                f"DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            conn.close()
            logger.info(f"✅ 数据库 `{database}` 已就绪")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise

    def init_all_tables(self, conn):
        logger.info("\n=== 初始化数据库表结构 ===")

        tables = {
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    mobile VARCHAR(30) UNIQUE,
                    password_hash CHAR(60),
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    phone VARCHAR(20),
                    member_level TINYINT NOT NULL DEFAULT 0,
                    points BIGINT NOT NULL DEFAULT 0,
                    promotion_balance DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    merchant_points BIGINT NOT NULL DEFAULT 0,
                    merchant_balance DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    status TINYINT NOT NULL DEFAULT 1,
                    level_changed_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_mobile (mobile),
                    INDEX idx_email (email),
                    INDEX idx_member_level (member_level)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'products': """
                CREATE TABLE IF NOT EXISTS products (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    sku VARCHAR(64) UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    pinyin TEXT,
                    description TEXT,
                    category VARCHAR(100),
                    price DECIMAL(12,2) DEFAULT 0.00,
                    stock INT NOT NULL DEFAULT 0,
                    main_image VARCHAR(500),
                    detail_images TEXT,
                    image_url VARCHAR(500),
                    is_member_product TINYINT(1) NOT NULL DEFAULT 0,
                    is_vip TINYINT(1) DEFAULT 0 COMMENT '1=会员商品（兼容订单系统）',
                    status TINYINT NOT NULL DEFAULT 0,
                    user_id BIGINT UNSIGNED,
                    merchant_id BIGINT UNSIGNED,
                    buy_rule TEXT,
                    freight DECIMAL(12,2) DEFAULT 0.00,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_is_member_product (is_member_product),
                    INDEX idx_is_vip (is_vip),
                    INDEX idx_merchant (merchant_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_status (status),
                    INDEX idx_category (category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'orders': """
                CREATE TABLE IF NOT EXISTS orders (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(64) UNIQUE,
                    order_number VARCHAR(50) UNIQUE COMMENT '订单号（兼容订单系统）',
                    user_id BIGINT UNSIGNED NOT NULL,
                    merchant_id BIGINT UNSIGNED,
                    total_amount DECIMAL(12,2) NOT NULL,
                    original_amount DECIMAL(12,2) DEFAULT 0.00,
                    points_discount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                    is_member_order TINYINT(1) NOT NULL DEFAULT 0,
                    is_vip_item TINYINT(1) DEFAULT 0 COMMENT '1=含会员商品（兼容订单系统）',
                    status VARCHAR(30) NOT NULL DEFAULT 'pending_pay',
                    refund_status VARCHAR(30) DEFAULT NULL,
                    consignee_name VARCHAR(100),
                    consignee_phone VARCHAR(20),
                    province VARCHAR(20) DEFAULT '',
                    city VARCHAR(20) DEFAULT '',
                    district VARCHAR(20) DEFAULT '',
                    shipping_address TEXT,
                    pay_way ENUM('alipay','wechat','card','wx_pub','wx_app') DEFAULT 'alipay',
                    refund_reason TEXT,
                    auto_recv_time DATETIME NULL COMMENT '7 天后自动收货',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_order_no (order_no),
                    INDEX idx_order_number (order_number),
                    INDEX idx_created_at (created_at),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'order_items': """
                CREATE TABLE IF NOT EXISTS order_items (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    order_id BIGINT UNSIGNED NOT NULL,
                    product_id BIGINT UNSIGNED NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    unit_price DECIMAL(12,2) NOT NULL,
                    total_price DECIMAL(12,2) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_order (order_id),
                    INDEX idx_product (product_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'finance_accounts': """
                CREATE TABLE IF NOT EXISTS finance_accounts (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    account_name VARCHAR(100) NOT NULL,
                    account_type VARCHAR(50) UNIQUE NOT NULL,
                    balance DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_account_type (account_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'account_flow': """
                CREATE TABLE IF NOT EXISTS account_flow (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    account_id BIGINT UNSIGNED,
                    related_user BIGINT UNSIGNED,
                    account_type VARCHAR(50),
                    change_amount DECIMAL(14,2) NOT NULL,
                    balance_after DECIMAL(14,2),
                    flow_type VARCHAR(50),
                    remark VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_account (account_id),
                    INDEX idx_related_user (related_user),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'points_log': """
                CREATE TABLE IF NOT EXISTS points_log (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    change_amount BIGINT NOT NULL,
                    balance_after BIGINT NOT NULL,
                    type ENUM('member','merchant') NOT NULL,
                    reason VARCHAR(255),
                    related_order BIGINT UNSIGNED,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_order (related_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'user_referrals': """
                CREATE TABLE IF NOT EXISTS user_referrals (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED UNIQUE NOT NULL,
                    referrer_id BIGINT UNSIGNED,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_referrer (referrer_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'pending_rewards': """
                CREATE TABLE IF NOT EXISTS pending_rewards (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    reward_type ENUM('referral','team') NOT NULL,
                    amount DECIMAL(12,2) NOT NULL,
                    order_id BIGINT UNSIGNED NOT NULL,
                    layer TINYINT DEFAULT NULL,
                    status ENUM('pending','approved','rejected') DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_status (user_id, status),
                    INDEX idx_order_id (order_id),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'coupons': """
                CREATE TABLE IF NOT EXISTS coupons (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    coupon_type ENUM('user','merchant') NOT NULL,
                    amount DECIMAL(14,2) NOT NULL,
                    status ENUM('unused','used','expired') NOT NULL DEFAULT 'unused',
                    valid_from DATE NOT NULL,
                    valid_to DATE NOT NULL,
                    used_at DATETIME DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_status (user_id, status),
                    INDEX idx_valid_to (valid_to)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'withdrawals': """
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    amount DECIMAL(14,2) NOT NULL,
                    tax_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    actual_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    status VARCHAR(30) NOT NULL DEFAULT 'pending_auto',
                    audit_remark VARCHAR(255) DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed_at DATETIME DEFAULT NULL,
                    INDEX idx_user_status (user_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'team_rewards': """
                CREATE TABLE IF NOT EXISTS team_rewards (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    from_user_id BIGINT UNSIGNED NOT NULL,
                    order_id BIGINT UNSIGNED,
                    layer TINYINT NOT NULL,
                    reward_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_from_user_id (from_user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'weekly_subsidy_records': """
                CREATE TABLE IF NOT EXISTS weekly_subsidy_records (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    week_start DATE NOT NULL,
                    subsidy_amount DECIMAL(14,2) NOT NULL,
                    points_before BIGINT NOT NULL,
                    points_deducted BIGINT NOT NULL,
                    coupon_id BIGINT UNSIGNED,
                    INDEX idx_user_week (user_id, week_start)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'director_dividends': """
                CREATE TABLE IF NOT EXISTS director_dividends (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    period_date DATE NOT NULL,
                    dividend_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
                    status VARCHAR(30) NOT NULL DEFAULT 'pending',
                    paid_at DATETIME DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # ========== 订单系统相关表（来自 order/database_setup1.py） ==========
            'merchants': """
                CREATE TABLE IF NOT EXISTS merchants (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    login_user VARCHAR(50) UNIQUE NOT NULL,
                    login_pwd VARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'merchant_balance': """
                CREATE TABLE IF NOT EXISTS merchant_balance (
                    merchant_id BIGINT UNSIGNED PRIMARY KEY,
                    balance DECIMAL(10,2) NOT NULL DEFAULT 0,
                    bank_name VARCHAR(100) DEFAULT '',
                    bank_account VARCHAR(50) DEFAULT '',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # 注意：Merchant_Balance 表的外键约束在表创建后单独添加
            # 注意：Users 和 Products 表已整合到统一的 users 和 products 表中
            'cart': """
                CREATE TABLE IF NOT EXISTS cart (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    product_id BIGINT UNSIGNED NOT NULL,
                    quantity INT DEFAULT 1,
                    selected TINYINT DEFAULT 1,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_user_product (user_id, product_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_product_id (product_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # 注意：Cart 表的外键约束在表创建后单独添加，避免类型不匹配问题
            # 注意：Orders 和 Order_Items 表已整合到统一的 orders 和 order_items 表中
            'refunds': """
                CREATE TABLE IF NOT EXISTS refunds (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    order_number VARCHAR(50) NOT NULL,
                    refund_type ENUM('return','refund_only') NOT NULL COMMENT 'return=退货退款，refund_only=仅退款',
                    reason TEXT NOT NULL,
                    status ENUM('applied','seller_ok','success','rejected') DEFAULT 'applied',
                    reject_reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_order_number (order_number)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # 注意：Refunds 表的外键约束在表创建后单独添加，避免类型不匹配问题
            'user_addresses': """
                CREATE TABLE IF NOT EXISTS user_addresses (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT UNSIGNED NOT NULL,
                    label VARCHAR(20) NOT NULL COMMENT '家/公司/朋友',
                    consignee_name VARCHAR(100) NOT NULL,
                    consignee_phone VARCHAR(20) NOT NULL,
                    province VARCHAR(20) NOT NULL DEFAULT '',
                    city VARCHAR(20) NOT NULL DEFAULT '',
                    district VARCHAR(20) NOT NULL DEFAULT '',
                    detail TEXT NOT NULL,
                    lng DECIMAL(10,6) NULL,
                    lat DECIMAL(10,6) NULL,
                    is_default TINYINT(1) DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # 注意：User_Addresses 表的外键约束在表创建后单独添加
            'order_split': """
                CREATE TABLE IF NOT EXISTS order_split (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    order_number VARCHAR(50) NOT NULL,
                    item_type ENUM('merchant','pool') NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    pool_type VARCHAR(20) NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'merchant_statement': """
                CREATE TABLE IF NOT EXISTS merchant_statement (
                    merchant_id BIGINT UNSIGNED NOT NULL,
                    date DATE NOT NULL,
                    opening_balance DECIMAL(10,2) NOT NULL,
                    income DECIMAL(10,2) NOT NULL,
                    withdraw DECIMAL(10,2) NOT NULL,
                    closing_balance DECIMAL(10,2) NOT NULL,
                    PRIMARY KEY (merchant_id, date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'alert_order': """
                CREATE TABLE IF NOT EXISTS alert_order (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    order_number VARCHAR(50) NOT NULL,
                    alert_type VARCHAR(50) NOT NULL,
                    detail TEXT NOT NULL,
                    is_handled TINYINT(1) DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        for table_name, sql in tables.items():
            conn.execute(text(sql))
            logger.info(f"✅ 表 `{table_name}` 已创建/确认")

        # 在表创建后添加外键约束（避免类型不匹配问题）
        self._add_cart_foreign_keys(conn)
        self._add_refunds_foreign_keys(conn)
        self._add_orders_foreign_keys(conn)
        self._add_order_items_foreign_keys(conn)
        self._add_user_addresses_foreign_keys(conn)
        self._add_merchant_balance_foreign_keys(conn)

        self._init_finance_accounts(conn)
        logger.info("✅ 所有表结构初始化完成")

    def _add_cart_foreign_keys(self, conn):
        """为 cart 表添加外键约束（如果不存在）"""
        try:
            # 检查 cart 表和被引用表是否存在
            result = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME IN ('cart', 'users', 'products')
            """))
            existing_tables = {row[0] for row in result.fetchall()}
            
            if 'cart' not in existing_tables or 'users' not in existing_tables or 'products' not in existing_tables:
                logger.debug("⚠️ cart 表或引用表不存在，跳过外键添加")
                return
            
            # 检查外键是否已存在
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'cart' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'cart_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE cart 
                    ADD CONSTRAINT cart_ibfk_1 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                logger.info("✅ cart 表外键约束 cart_ibfk_1 已添加")
            
            if 'cart_ibfk_2' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE cart 
                    ADD CONSTRAINT cart_ibfk_2 
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                """))
                logger.info("✅ cart 表外键约束 cart_ibfk_2 已添加")
        except Exception as e:
            # 如果添加外键失败（可能是类型不匹配或表不存在），静默忽略
            logger.debug(f"⚠️ cart 表外键约束添加失败（已忽略）: {e}")

    def _add_refunds_foreign_keys(self, conn):
        """为 refunds 表添加外键约束（如果不存在）"""
        try:
            # 检查 refunds 表和 orders 表是否存在，以及 orders 表是否有 order_number 列
            result = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME IN ('refunds', 'orders')
            """))
            existing_tables = {row[0] for row in result.fetchall()}
            
            if 'refunds' not in existing_tables or 'orders' not in existing_tables:
                logger.debug("⚠️ refunds 表或 orders 表不存在，跳过外键添加")
                return
            
            # 检查 orders 表是否有 order_number 列
            result = conn.execute(text("""
                SELECT COLUMN_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'order_number'
            """))
            if result.fetchone() is None:
                logger.debug("⚠️ orders 表缺少 order_number 列，跳过外键添加")
                return
            
            # 检查外键是否已存在
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'refunds' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'refunds_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE refunds 
                    ADD CONSTRAINT refunds_ibfk_1 
                    FOREIGN KEY (order_number) REFERENCES orders(order_number) ON DELETE CASCADE
                """))
                logger.info("✅ refunds 表外键约束 refunds_ibfk_1 已添加")
        except Exception as e:
            # 如果添加外键失败（可能是类型不匹配或表不存在），静默忽略
            logger.debug(f"⚠️ refunds 表外键约束添加失败（已忽略）: {e}")

    def _add_orders_foreign_keys(self, conn):
        """为 orders 表添加外键约束（如果不存在）"""
        try:
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'orders_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE orders 
                    ADD CONSTRAINT orders_ibfk_1 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                logger.info("✅ orders 表外键约束 orders_ibfk_1 已添加")
        except Exception as e:
            logger.warning(f"⚠️ orders 表外键约束添加失败（可忽略）: {e}")

    def _add_order_items_foreign_keys(self, conn):
        """为 order_items 表添加外键约束（如果不存在）"""
        try:
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'order_items' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'order_items_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE order_items 
                    ADD CONSTRAINT order_items_ibfk_1 
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
                """))
                logger.info("✅ order_items 表外键约束 order_items_ibfk_1 已添加")
            
            if 'order_items_ibfk_2' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE order_items 
                    ADD CONSTRAINT order_items_ibfk_2 
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                """))
                logger.info("✅ order_items 表外键约束 order_items_ibfk_2 已添加")
        except Exception as e:
            logger.warning(f"⚠️ order_items 表外键约束添加失败（可忽略）: {e}")

    def _add_user_addresses_foreign_keys(self, conn):
        """为 user_addresses 表添加外键约束（如果不存在）"""
        try:
            # 检查 user_addresses 表和 users 表是否存在
            result = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME IN ('user_addresses', 'users')
            """))
            existing_tables = {row[0] for row in result.fetchall()}
            
            if 'user_addresses' not in existing_tables or 'users' not in existing_tables:
                logger.debug("⚠️ user_addresses 表或 users 表不存在，跳过外键添加")
                return
            
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'user_addresses' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'user_addresses_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE user_addresses 
                    ADD CONSTRAINT user_addresses_ibfk_1 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                logger.info("✅ user_addresses 表外键约束 user_addresses_ibfk_1 已添加")
        except Exception as e:
            # 如果添加外键失败（可能是类型不匹配或表不存在），静默忽略
            logger.debug(f"⚠️ user_addresses 表外键约束添加失败（已忽略）: {e}")

    def _add_merchant_balance_foreign_keys(self, conn):
        """为 merchant_balance 表添加外键约束（如果不存在）"""
        try:
            result = conn.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'merchant_balance' 
                AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """))
            existing_fks = [row[0] for row in result.fetchall()]
            
            if 'merchant_balance_ibfk_1' not in existing_fks:
                conn.execute(text("""
                    ALTER TABLE merchant_balance 
                    ADD CONSTRAINT merchant_balance_ibfk_1 
                    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
                """))
                logger.info("✅ merchant_balance 表外键约束 merchant_balance_ibfk_1 已添加")
        except Exception as e:
            logger.warning(f"⚠️ merchant_balance 表外键约束添加失败（可忽略）: {e}")

    def _init_finance_accounts(self, conn):
        accounts = [
            ('周补贴池', 'subsidy_pool'),
            ('公益基金', 'public_welfare'),
            ('平台维护', 'platform'),
            ('荣誉董事分红', 'honor_director'),
            ('社区店', 'community'),
            ('城市运营中心', 'city_center'),
            ('大区分公司', 'region_company'),
            ('事业发展基金', 'development'),
            ('公司积分账户', 'company_points'),
            ('公司余额账户', 'company_balance'),
            ('平台收入池（会员商品）', 'platform_revenue_pool'),
        ]

        conn.execute(text("DELETE FROM finance_accounts"))
        for name, acc_type in accounts:
            conn.execute(
                text("INSERT INTO finance_accounts (account_name, account_type, balance) VALUES (:name, :type, 0)"),
                {"name": name, "type": acc_type}
            )
        logger.info(f"✅ 初始化 {len(accounts)} 个资金池账户")

    def create_test_data(self, conn) -> int:
        logger.info("\n--- 创建测试数据 ---")

        pwd_hash = '$2b$12$9LjsHS5r4u1M9K4nG5KZ7e6zZxZn7qZ'

        mobile = '13800138004'
        # 幂等处理：如果手机号已存在则复用该用户，否则插入新用户
        existing = conn.execute(
            text("SELECT id FROM users WHERE mobile = :mobile"),
            {"mobile": mobile}
        ).fetchone()
        if existing and getattr(existing, 'id', None):
            merchant_id = existing.id
            logger.info(f"ℹ️ 测试商家手机号已存在，复用商家ID: {merchant_id}")
        else:
            result = conn.execute(
                text("INSERT INTO users (mobile, password_hash, name, status) VALUES (:mobile, :pwd, :name, 1)"),
                {"mobile": mobile, "pwd": pwd_hash, "name": '优质商家'}
            )
            merchant_id = result.lastrowid

        # 创建会员商品（若 SKU 已存在则跳过）
        sku_member = 'SKU-MEMBER-001'
        existing_prod = conn.execute(
            text("SELECT id FROM products WHERE sku = :sku"),
            {"sku": sku_member}
        ).fetchone()
        if existing_prod and getattr(existing_prod, 'id', None):
            logger.info(f"ℹ️ 会员商品 SKU 已存在，跳过插入，product_id={existing_prod.id}")
        else:
            conn.execute(
                text("""INSERT INTO products (sku, name, price, stock, is_member_product, merchant_id, status)
                        VALUES (:sku, :name, :price, 100, 1, :merchant_id, 1)"""),
                {"sku": sku_member, "name": '会员星卡', "price": float(MEMBER_PRODUCT_PRICE), "merchant_id": PLATFORM_MERCHANT_ID}
            )

        # 创建普通商品（若 SKU 已存在则跳过）
        sku_normal = 'SKU-NORMAL-001'
        existing_normal = conn.execute(
            text("SELECT id FROM products WHERE sku = :sku"),
            {"sku": sku_normal}
        ).fetchone()
        if existing_normal and getattr(existing_normal, 'id', None):
            logger.info(f"ℹ️ 普通商品 SKU 已存在，跳过插入，product_id={existing_normal.id}")
        else:
            conn.execute(
                text("""INSERT INTO products (sku, name, price, stock, is_member_product, merchant_id, status)
                        VALUES (:sku, :name, 500.00, 200, 0, :merchant_id, 1)"""),
                {"sku": sku_normal, "name": '普通商品', "merchant_id": merchant_id}
            )

        conn.commit()
        logger.info(f"✅ 测试数据创建完成 | 商家ID: {merchant_id}")
        return merchant_id


# ==================== 数据库初始化函数 ====================

def create_database():
    """根据 `.env` 中的配置，创建 MySQL 数据库（如果不存在）。

    该函数会加载环境变量，然后以不指定数据库的方式连接 MySQL，执行
    `CREATE DATABASE IF NOT EXISTS ...`。调用者可在程序启动时先调用此函数。
    """
    import pymysql
    cfg = get_db_config()
    host = cfg['host']
    port = cfg['port']
    user = cfg['user']
    password = cfg['password']
    dbname = cfg['database']

    conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
    finally:
        conn.close()

    print("数据库创建完成（若不存在）。")


def initialize_database():
    """初始化数据库表结构（如果尚未创建）。

    先确保数据库存在（调用 `create_database()`），再通过 SQLAlchemy 创建表结构。
    """
    print("正在检查数据库表结构...")
    # 确保数据库已创建
    create_database()

    engine = get_engine()
    with engine.connect() as conn:
        with conn.begin():
            db_manager = DatabaseManager()
            db_manager.init_all_tables(conn)

    print("数据库表结构初始化完成。")


def create_test_data():
    """创建测试数据（可选）"""
    print("正在创建测试数据...")
    engine = get_engine()
    with engine.connect() as conn:
        with conn.begin():
            db_manager = DatabaseManager()
            db_manager.create_test_data(conn)
    print("测试数据创建完成。")


# ==================== 订单系统相关函数（来自 order/database_setup1.py） ====================

def init_db():
    """一键初始化数据库（兼容 order 模块的接口）
    
    这是 initialize_database() 的别名，用于保持与 order 模块的兼容性。
    """
    initialize_database()
    print("[database_setup] 初始化完成！")


def auto_receive_task(db_cfg: dict = None):
    """自动收货和结算守护进程
    
    该函数会启动一个后台线程，每小时检查一次待收货订单，
    如果订单超过自动收货时间，则自动完成订单并结算给商家。
    
    参数:
        db_cfg: 数据库配置字典（可选，默认使用 get_db_config()）
    
    注意:
        这是一个守护进程，会在后台持续运行。
        需要在应用启动时调用此函数。
    """
    import threading
    import time
    from datetime import datetime
    
    def run():
        while True:
            try:
                from config import get_conn
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        now = datetime.now()
                        cur.execute(
                            "SELECT id, order_number, total_amount FROM orders "
                            "WHERE status='pending_recv' AND auto_recv_time<=%s",
                            (now,)
                        )
                        for row in cur.fetchall():
                            cur.execute(
                                "UPDATE orders SET status='completed' WHERE id=%s",
                                (row["id"],)
                            )
                            # 注意：settle_to_merchant 函数需要从 order 模块导入
                            # 这里只做订单状态更新，结算逻辑需要单独处理
                            conn.commit()
                            logger.info(f"[auto_receive] 订单 {row['order_number']} 已自动完成。")
            except Exception as e:
                logger.error(f"[auto_receive] 异常: {e}")
            time.sleep(3600)  # 每小时检查一次
    
    t = threading.Thread(target=run, daemon=True)
    t.start()
    logger.info("✅ 自动收货守护进程已启动")


# ==================== Product 模块相关功能（来自 product/database_setup.py） ====================

def _fix_pinyin():
    """补全商品拼音（来自 product/init_db.py 的 fix_pinyin_once 函数）
    
    该函数会检查所有商品，如果 pinyin 字段为空，则自动生成拼音。
    可重复执行，幂等操作。
    等价于 product/init_db.py 中的 fix_pinyin_once() 函数。
    """
    try:
        from pypinyin import lazy_pinyin, Style
        from config import get_conn
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 查询所有商品
                cur.execute("SELECT id, name, pinyin FROM products")
                products = cur.fetchall()
                
                updated_count = 0
                for product in products:
                    if not product.get('pinyin'):
                        pinyin = ' '.join(lazy_pinyin(product['name'], style=Style.NORMAL)).upper()
                        cur.execute("UPDATE products SET pinyin = %s WHERE id = %s", (pinyin, product['id']))
                        updated_count += 1
                
                conn.commit()
                logger.info(f"✅ 商品拼音补全完成，更新了 {updated_count} 条记录")
    except ImportError:
        logger.warning("⚠️ pypinyin 未安装，跳过拼音补全功能")
    except Exception as e:
        logger.error(f"❌ 拼音补全失败: {e}")


def create_tables_with_orm():
    """根据 ORM 模型建表（来自 product/init_db.py）
    
    该函数会创建所有 ORM 模型定义的表。
    等价于 product/init_db.py 中的 create_tables() 函数。
    """
    try:
        # 导入 product 模块的模型，确保所有模型都被注册到 Base.metadata
        from product.models import Product, ProductSku, ProductAttribute, Banner
        engine = get_engine()
        Base.metadata.create_all(engine)
        logger.info("✅ ORM 模型表创建完成")
    except Exception as e:
        logger.warning(f"⚠️ ORM 表创建失败（可忽略）: {e}")


def initialize_database_with_orm():
    """初始化数据库（包含 ORM 表创建和拼音补全，兼容 product 模块）
    
    该函数会：
    1. 确保数据库存在
    2. 创建所有表（包括 ORM 模型定义的表）
    3. 补全商品拼音
    
    等价于 product/init_db.py 中的 main() 函数（已注释掉的功能）。
    """
    # 先执行标准的数据库初始化
    initialize_database()
    
    # 创建 ORM 模型定义的表
    create_tables_with_orm()
    
    # 补全拼音
    _fix_pinyin()