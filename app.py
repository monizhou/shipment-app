# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 数据兼容性优化版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from hashlib import sha256  # 导入哈希模块

# ==================== 系统配置 ====================
class AppConfig:
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
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
    # 新增密码配置（使用SHA256加密存储，此处权限密码为 "admin123" 的哈希值）
    ADMIN_PASSWORD_HASH = "202cb962ac59075b964b07152d234b70"  # 示例: "admin123" 的MD5哈希（此处用SHA256替换）

# ==================== 辅助函数 ====================
def find_data_file():
    """查找数据文件"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None

def apply_card_styles():
    """样式设置"""
    st.markdown("""
    <style>
    ...
    </style>
    """, unsafe_allow_html=True)

def hash_password(password):
    """密码加密"""
    return sha256(password.encode('utf-8')).hexdigest()

def check_admin_password(password):
    """权限验证函数"""
    hashed_input = hash_password(password)
    return hashed_input == AppConfig.ADMIN_PASSWORD_HASH

# ============== 数据加载模块（关键修正） ===============
@st.cache_data(ttl=10)
def load_data():
    def safe_convert_to_numeric(series, default=0):
        str_series = series.astype(str)
        cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
        return pd.to_numeric(cleaned, errors='coerce').fillna(default)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')

        if len(df.columns) > 17:
            df = df.rename(columns={df.columns[17]: "项目部名称"})
        else:
            st.error("文件格式错误: 缺少第18列（项目部名称）")
            return pd.DataFrame()

        df["项目部名称"] = df["项目部名称"].astype(str).str.strip()
        df["项目部名称"] = df["项目部名称"].replace({"": "未指定项目部", None: "未指定项目部", float("nan"): "未指定项目部"})

        # 列名映射处理
        for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
            for alt_col in alt_cols:
                if alt_col in df.columns:
                    df.rename(columns={alt_col: std_col}, inplace=True)
                    break

        missing_cols = [col for col in AppConfig.REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            st.error(f"缺少必要列: {missing_cols}")
            return pd.DataFrame()

        df["下单时间"] = pd.to_datetime(df["下单时间"]).dt.tz_localize(None)
        df = df[~df["下单时间"].isna()]

        # 数值转换
        df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
        df["已发量"] = safe_convert_to_numeric(df.get("已发量",0)).astype(int)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)

        # 超期计算
        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"]).dt.tz_localize(None)
            df["超期天数"] = (pd.Timestamp.now().normalize() - df["计划进场时间"]).dt.days.clip(lower=0)
        else:
            df["超期天数"] = 0

        check_data_quality(df)

        return df
    except Exception as e:
        st.error(f"加载失败: {str(e)}")
        return pd.DataFrame()

def check_data_quality(df):
    """数据验证"""
    invalid_shipped = df[pd.to_numeric(df["已发量"].astype(str), errors='coerce') < 0]
    if not invalid_shipped.empty:
        st.warning("检测到已发量为负值，请核对数据\n受影响记录：" + str(len(invalid_shipped)), icon='⚠️')

    invalid_demand = df[df["需求量"] < 0]
    if not invalid_demand.empty:
        st.warning("检测到需求量为负值，请核对数据", icon='⚠️')

# ============== 页面组件 ===============
def show_project_selection(df):
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown('<span style="color: #003366;">中铁物贸成都分公司</span>', 
            unsafe_allow_html=True)
    
    valid_projects = sorted([p for p in df["项目部名称"].unique() if p != "未指定项目部"])
    options = ["中铁物贸成都分公司"] + valid_projects

    select_container = st.empty()
    selected = select_container.selectbox("请选择项目部", options)
    
    # 处理总部选择的特殊逻辑
    if selected == "中铁物贸成都分公司":
        with st.form("password_form", clear_on_submit=True):
            st.write("🔒 需要管理员权限访问总部数据")
            password = st.text_input("请输入密码：", type="password", key="admin_password")
            submitted = st.form_submit_button("验证权限")
            
            if submitted:
                if check_admin_password(password.strip()):
                    st.session_state["password_verified"] = True  # 更新状态
                    st.session_state["project_selected"] = True
                    st.session_state["selected_project"] = selected
                    st.experimental_rerun()
                else:
                    st.error("❌ 密码错误，请重输！") 
    else:
        if st.button("确认进入", key="confirm_button", type="primary"):
            st.session_state["project_selected"] = True
            st.session_state["selected_project"] = selected
            st.experimental_rerun()

def show_data_panel(df, project):
    st.title(f"{project} - 发货数据监控")
    
    # 返回按钮设计
    col_left, col_right = st.columns([0.3, 0.7])
    with col_left:
        if st.button("⇦ 返回选择", use_container_width=True):
            st.session_state.project_selected = False
            st.experimental_rerun()
    
    # 日期筛选组件
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("起始时间", 
            datetime.now() - timedelta(days=7), 
            label_visibility="collapsed",
            format="YYYY-MM-DD")
    with col_end:
        end_date = st.date_input("截止时间", 
            datetime.now(), 
            label_visibility="collapsed",
            format="YYYY-MM-DD")
    
    if start_date > end_date:
        st.error("日期区间错误，请重新选择")
        return
    
    # 数据过滤
    if project == "中铁物贸成都分公司":
        filtered = df.copy()
    else:
        filtered = df[df["项目部名称"] == project]
    
    date_mask = (filtered["下单时间"].dt.date >= pd.to_datetime(start_date).date()) & \
                (filtered["下单时间"].dt.date <= pd.to_datetime(end_date).date())
    
    display_df = filtered[date_mask].copy()
    
    # 展示核心指标
    display_metrics_cards(display_df)
    
    # 展示明细数据
    if not display_df.empty:
        styled_df = display_df.style.format({
            '需求量': '{:,.0f}吨',
            '已发量': '{:,.0f}吨',
            '剩余量': '{:,.0f}吨',
            "下单时间": lambda x: x.strftime("%Y-%m-%d") if not pd.isnull(x) else "",
            "计划进场时间": lambda x: x.strftime("%Y-%m-%d") if not pd.isnull(x) else ""
        })
        
        styled_df.apply(lambda r: ['background: #FFD700' if r['超期天数'] > 0 else '' for _ in r], subset=['超期天数'], axis=1,)
        
        st.dataframe(styled_df, hide_index=True, use_container_width=True)
        
        # 数据导出按钮
        csv = display_df.to_csv(index=False, encoding='utf_8_sig')
        st.download_button(
            label="导出当前数据",
            data=csv,
            file_name=f"{project}_{start_date}_{end_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info(f"无{start_date}至{end_date}间的记录")
    
# ============== 核心组件 ===============
def display_metrics_cards(filtered):
    if len(filtered) == 0:
        return
    
    total_demand = filtered["需求量"].sum()
    shipped = filtered["已发量"].sum()
    remaining = filtered["剩余量"].sum()
    
    overdue = filtered["超期天数"] > 0
    overdue_count = overdue.sum()
    max_delay = filtered.loc[overdue, "超期天数"].max() if overdue.any() else 0
        
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总需求量", f"{total_demand:,.0f}", help="单位：吨", delta=None, label_visibility="visible")
    
    with col2:
        st.metric("已发总量", f"{shipped:,.0f}", delta=f"{(shipped/total_demand*100):.0f}%", delta_color="off")
    
    with col3:
        st.metric("待发总量", f"{remaining:,.0f}", delta=f"{(remaining/total_demand*100):.0f}%", delta_color="inverse")
    
    with col4:
        st.metric("超期订单", f"{overdue_count}", delta=f"最严重：{max_delay}天", 
                  delta_color="inverse" if max_delay >0 else "normal")
        
# ============== 主程序 ===============
def main():
    st.set_page_config(
        page_title="钢筋监控系统",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={
            'Report a bug': "mailto:admin@zhongtie.com",
            'Get help': None
        }
    )
    
    # 初始化状态变量
    if "project_selected" not in st.session_state:
        st.session_state["project_selected"] = False
    
    if "password_verified" not in st.session_state:
        st.session_state["password_verified"] = False
    
    if "selected_project" not in st.session_state:
        st.session_state["selected_project"] = ""
    
    df = load_data()
    apply_card_styles()
    
    # 权限路由控制
    if st.session_state["project_selected"]:
        current_project = st.session_state["selected_project"]
        
        # 特殊权限检查
        if current_project == "中铁物贸成都分公司" and not st.session_state["password_verified"]:
            st.error("权限不足！请从初始页面重新选择并验证权限")
            st.session_state["project_selected"] = False
            st.experimental_rerun()
            
        show_data_panel(df, current_project)
    else:
        show_project_selection(df)

if __name__ == "__main__":
    # Windows terminal字符编码设置（国内用户建议保留）
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    
    main()
