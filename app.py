# -*- coding: utf-8 -*-
"""钢筋发货监控系统（云端部署版）"""
import os
import io
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import hashlib

# ==================== 系统配置 ====================
class AppConfig:
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    ADMIN_PASSWORD_HASH = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"  # 123456

# ==================== 数据加载 ====================
def load_data(uploaded_file=None):
    """处理上传的Excel文件"""
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        df = pd.read_excel(
            io.BytesIO(uploaded_file.getvalue()),
            engine='openpyxl',
            dtype=str,
            keep_default_na=False
        )
        
        # 自动检测关键列
        col_mapping = {
            '项目部名称': ['项目部名称', '项目部', '项目名称'],
            '标段名称': ['标段名称', '项目标段', '工程名称'],
            '下单时间': ['下单时间', '创建时间', '日期'],
            '需求量': ['需求量', '需求吨位', '计划量']
        }
        
        for target_col, possible_names in col_mapping.items():
            if target_col not in df.columns:
                for name in possible_names:
                    if name in df.columns:
                        df = df.rename(columns={name: target_col})
                        break
        
        # 验证必要列
        missing_cols = [col for col in AppConfig.REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            st.error(f"缺少必要列: {missing_cols}")
            st.write("现有列名:", df.columns.tolist())
            return pd.DataFrame()
        
        # 数据处理
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
        df["需求量"] = pd.to_numeric(df["需求量"], errors='coerce').fillna(0).astype(int)
        df["已发量"] = pd.to_numeric(df.get("已发量", 0), errors='coerce').fillna(0).astype(int)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)
        
        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce')
            df["超期天数"] = ((pd.Timestamp.now() - df["计划进场时间"]).dt.days.clip(lower=0))
        else:
            df["超期天数"] = 0
            
        return df
        
    except Exception as e:
        st.error(f"文件处理失败: {str(e)}")
        return pd.DataFrame()

# ==================== 页面组件 ====================
def show_file_uploader():
    """文件上传组件"""
    st.markdown("""
    <style>
        .upload-box {
            border: 2px dashed #ccc;
            border-radius: 5px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
        .st-eb {
            width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="upload-box">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "请上传Excel文件", 
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="data_uploader"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return uploaded_file

def show_project_selection(df):
    """项目部选择界面"""
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司**")
    
    if df.empty:
        st.warning("请先上传数据文件")
        return
    
    # 获取有效项目部列表
    valid_projects = [p for p in df["项目部名称"].unique() 
                     if p and str(p).strip() not in ["", "未指定项目部", "nan"]]
    valid_projects = sorted(list(set(valid_projects)))
    
    options = ["中铁物贸成都分公司"] + valid_projects
    selected = st.selectbox("选择项目部", options)
    
    # 密码验证
    if selected == "中铁物贸成都分公司":
        if 'password_verified' not in st.session_state or not st.session_state.password_verified:
            st.markdown('<div class="password-box">', unsafe_allow_html=True)
            password = st.text_input("请输入管理密码", type="password")
            if st.button("验证"):
                if hashlib.sha256(password.encode()).hexdigest() == AppConfig.ADMIN_PASSWORD_HASH:
                    st.session_state.password_verified = True
                    st.rerun()
                else:
                    st.error("密码错误")
            st.markdown('</div>', unsafe_allow_html=True)
            return
    
    if st.button("进入系统", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.rerun()

# ==================== 主程序 ====================
def main():
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    
    # 初始化session状态
    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    
    # 文件上传和数据处理
    uploaded_file = show_file_uploader()
    df = load_data(uploaded_file)
    
    # 页面路由
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        # 数据展示面板（原有实现）
        pass

if __name__ == "__main__":
    main()
