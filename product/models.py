# 保持原样，仅把 import 改成相对
from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, DateTime, func, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from database_setup import Base

class ProductStatus:
    DRAFT = 0
    ON_SALE = 1
    OFF_SALE = 2
    OUT_OF_STOCK = 3

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_status_category", "status", "category"),
        Index("ix_products_pinyin", "pinyin", mysql_prefix="FULLTEXT"),
        Index("ix_products_user_id", "user_id"),
    )

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    pinyin = Column(Text)
    description = Column(Text)
    category = Column(String(100), nullable=False)
    main_image = Column(String(500))
    detail_images = Column(Text)
    status = Column(Integer, default=ProductStatus.DRAFT)
    user_id = Column(BIGINT(unsigned=True), ForeignKey("users.id"), nullable=True)
    is_member_product = Column(Boolean, default=False, nullable=False)
    buy_rule = Column(Text, nullable=True)
    freight = Column(Numeric(precision=12, scale=2), default=0.00, nullable=False, comment="运费，默认0包邮")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    skus = relationship("ProductSku", back_populates="product", cascade="all, delete-orphan")
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")
    banners = relationship("Banner", back_populates="product", cascade="all, delete-orphan")

class ProductSku(Base):
    __tablename__ = "product_skus"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = Column(BIGINT(unsigned=True), ForeignKey("products.id"), nullable=False)
    sku_code = Column(String(64), unique=True, nullable=False)
    price = Column(Numeric(precision=12, scale=2), default=0.00)
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    product = relationship("Product", back_populates="skus")

class ProductAttribute(Base):
    __tablename__ = "product_attributes"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = Column(BIGINT(unsigned=True), ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(String(255), nullable=False)
    product = relationship("Product", back_populates="attributes")

class Banner(Base):
    __tablename__ = "banners"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = Column(BIGINT(unsigned=True), ForeignKey("products.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    link_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    status = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    product = relationship("Product", back_populates="banners")

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)