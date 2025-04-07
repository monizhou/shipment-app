# -*- coding: utf-8 -*-
"""钢筋发货监控系统（支持自动更新数据）"""
import os
import io
import time
import hashlib
from datetime import datetime
import pandas as pd
import streamlit as st

# ==================== 系统配置 ====================
class AppConfig:
    # 多路径配置（自动选择可用路径）
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),  # 优先使用相对路径
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }

# ==================== 自动更新逻辑 ====================
def get_file_hash(filename):
    """计算文件哈希值用于检测变更"""
    if not os.path.exists(filename):
        return None
    with open(filename, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def check_file_update():
    """检查文件是否更新"""
    data_path = find_data_file()
    if not data_path:
        return False
    
    current_hash = get_file_hash(data_path)
    if 'file_hash' not in st.session_state:
        st.session_state.file_hash = current_hash
    
    if current_hash != st.session_state.file_hash:
        st.session_state.file_hash = current_hash
        return True
    return False

# ==================== 样式设置 ====================
def apply_card_styles():
    """应用现代化卡片样式（已优化移动端）"""
    st.markdown("""
    <style>
        /* [原有样式代码保持不变，与您提供的完全一致] */
    </style>
    """, unsafe_allow_html=True)

# ==================== 数据加载 ====================
def find_data_file():
    """查找可用的数据文件"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None

@st.cache_data(ttl=10)  # 10秒缓存（兼顾性能与实时性）
def load_data():
    """加载并验证Excel数据"""
    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件，请检查路径配置")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')
        st.session_state['data_path'] = data_path

        # [原有数据处理逻辑保持不变，与您提供的完全一致]
        
        return df
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()

# ==================== 主页面 ====================
def main():
    # 页面配置
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="collapsed"
    )

    # 应用样式
    apply_card_styles()
    st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1.0">', unsafe_allow_html=True)

    # 标题栏
    st.markdown(f"""
    <div style="color:#2c3e50; padding-bottom:0.3rem; margin-bottom:1rem">
        <h1 style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.3rem;">
            <span>🏗️</span>
            <span>钢筋发货监控系统</span>
        </h1>
        <div style="color:#7f8c8d; font-size:0.85rem">
            更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
            {": 检测到新数据 🔄" if check_file_update() else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 强制刷新按钮
    if st.button("🔄 手动刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # 加载数据
    df = load_data()
    if df.empty:
        st.error("❌ 数据加载失败，请检查文件格式和路径")
        return

    # [原有数据显示逻辑保持不变，与您提供的完全一致]

# ==================== 程序入口 ====================
if __name__ == "__main__":
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    main()
