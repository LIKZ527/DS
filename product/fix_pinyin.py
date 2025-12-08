#!/usr/bin/env python3
"""补全商品拼音（可重复执行，幂等）"""

from config import get_conn
from pypinyin import lazy_pinyin, Style

def fix_all():
    """使用 pymysql 更新商品拼音"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 查询所有商品
            cur.execute("SELECT id, name, pinyin FROM products")
            products = cur.fetchall()
            
            updated_count = 0
            for product in products:
                if not product.get('pinyin'):
                    pinyin = ' '.join(lazy_pinyin(product['name'], style=Style.NORMAL)).upper()
                    cur.execute(
                        "UPDATE products SET pinyin = %s WHERE id = %s",
                        (pinyin, product['id'])
                    )
                    updated_count += 1
            
            conn.commit()
            print(f"✅ 现有商品拼音已补全，更新了 {updated_count} 条记录")

if __name__ == "__main__":
    fix_all()