# -*- coding: utf-8 -*-
"""钢筋发货监控系统（完整修复版）"""
import io
import pandas as pd
import streamlit as st
from datetime import datetime
import hashlib

# ==================== 系统配置 ====================
class AppConfig:
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    ADMIN_PASSWORD_HASH = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"  # 123456

# ==================== 数据加载 ====================
def load_data(uploaded_file):
    """处理上传的Excel文件（增强版）"""
    if uploaded_file is None:
        return None  # 返回None而不是空DataFrame以区分未上传和空数据
    
    try:
        # 读取时显示加载状态
        with st.spinner('正在解析Excel文件...'):
            df = pd.read_excel(
                io.BytesIO(uploaded_file.getvalue()),
                engine='openpyxl',
                dtype=str,
                keep_default_na=False
            )
        
        # 列名标准化（不区分大小写和空格）
        df.columns = df.columns.str.strip().str.replace(' ', '')
        
        # 自动列名映射（支持更多变体）
        col_mapping = {
            '项目部名称': ['项目部名称', '项目部', '项目名称', '部门', 'department'],
            '标段名称': ['标段名称', '项目标段', '工程名称', '标段', 'project'],
            '下单时间': ['下单时间', '创建时间', '日期', '时间', 'orderdate'],
            '需求量': ['需求量', '需求吨位', '计划量', '数量', 'weight'],
            '已发量': ['已发量', '已发吨位', '已发数量', 'shipped'],
            '计划进场时间': ['计划进场时间', '进场时间', '计划日期', 'plandate']
        }
        
        # 执行列名重命名
        for standard_col, possible_cols in col_mapping.items():
            for col in possible_cols:
                if col in df.columns and standard_col not in df.columns:
                    df = df.rename(columns={col: standard_col})
                    break
        
        # 验证必要列
        missing_cols = [col for col in AppConfig.REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            st.error(f"❌ 缺少必要列: {missing_cols}")
            st.write("📋 当前文件列名:", df.columns.tolist())
            return None
        
        # 数据类型转换（增强容错）
        try:
            df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce')
            df["需求量"] = pd.to_numeric(df["需求量"], errors='coerce').fillna(0).astype(int)
            df["已发量"] = pd.to_numeric(df.get("已发量", 0), errors='coerce').fillna(0).astype(int)
            df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)
            
            if "计划进场时间" in df.columns:
                df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce')
                df["超期天数"] = ((pd.Timestamp.now() - df["计划进场时间"]).dt.days.clip(lower=0))
            else:
                df["超期天数"] = 0
                
            # 过滤无效数据
            df = df[df["下单时间"].notna()]
            return df
            
        except Exception as e:
            st.error(f"🔧 数据处理错误: {str(e)}")
            st.write("💡 请检查数据格式是否正确")
            return None
            
    except Exception as e:
        st.error(f"❌ 文件读取失败: {str(e)}")
        st.write("⚠️ 请确认上传的是有效的Excel文件")
        return None

# ==================== 页面组件 ====================
def show_file_uploader():
    """文件上传组件（带样式和说明）"""
    st.markdown("""
    <style>
        .upload-box {
            border: 2px dashed #4CAF50;
            border-radius: 10px;
            padding: 25px;
            text-align: center;
            margin: 20px 0;
            background-color: #f8f9fa;
        }
        .upload-title {
            color: #4CAF50;
            font-size: 1.2rem;
            margin-bottom: 15px;
        }
    </style>
    <div class="upload-box">
        <div class="upload-title">📤 上传钢筋发货数据表</div>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "选择Excel文件（支持.xlsx或.xls格式）",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="data_uploader",
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        st.success(f"已上传文件: {uploaded_file.name}")
    else:
        st.info("请上传Excel格式的发货数据表")
    
    return uploaded_file

def show_data_preview(df):
    """数据预览（增强交互）"""
    if df is None or df.empty:
        st.warning("没有可显示的数据")
        return
    
    st.subheader("🔍 数据预览")
    
    # 显示数据统计信息
    with st.expander("📊 数据概览", expanded=True):
        cols = st.columns(3)
        cols[0].metric("总记录数", len(df))
        cols[1].metric("项目部数量", df["项目部名称"].nunique())
        cols[2].metric("时间范围", 
                      f"{df['下单时间'].min().date()} 至 {df['下单时间'].max().date()}")
    
    # 显示前5条数据
    with st.expander("📋 前5条数据", expanded=False):
        st.dataframe(df.head().style.format({
            '需求量': '{:,}',
            '已发量': '{:,}',
            '剩余量': '{:,}'
        }))

def show_project_selection(df):
    """项目部选择界面（增强）"""
    if df is None:
        st.warning("请先上传有效数据文件")
        return
    
    st.title("🏗️ 选择项目部")
    
    # 项目部选择器
    valid_projects = [p for p in df["项目部名称"].unique() 
                    if p and str(p).strip() not in ["", "未指定项目部", "nan"]]
    valid_projects = sorted(list(set(valid_projects)))
    
    if not valid_projects:
        st.error("未识别到有效的项目部数据")
        st.write("请检查'项目部名称'列是否包含有效数据")
        return
    
    selected = st.selectbox(
        "选择您所属的项目部",
        ["中铁物贸成都分公司"] + valid_projects,
        key="project_select"
    )
    
    # 总部密码验证
    if selected == "中铁物贸成都分公司":
        if st.session_state.get("password_verified", False):
            st.success("✅ 已通过总部权限验证")
        else:
            st.markdown("---")
            st.subheader("🔒 总部权限验证")
            password = st.text_input("请输入总部访问密码", type="password")
            if st.button("验证"):
                if hashlib.sha256(password.encode()).hexdigest() == AppConfig.ADMIN_PASSWORD_HASH:
                    st.session_state.password_verified = True
                    st.rerun()
                else:
                    st.error("密码错误，请重试")
            return
    
    # 确认按钮
    if st.button("进入数据面板", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.session_state.current_df = df  # 缓存数据
        st.rerun()

# ==================== 主程序 ====================
def main():
    # 页面配置
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    
    # 初始化session状态
    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = None
    
    # 页面标题
    st.title("钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司 - 云端版**")
    
    # 主流程
    uploaded_file = show_file_uploader()
    df = load_data(uploaded_file)
    
    if df is not None:
        show_data_preview(df)
    
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        # 数据展示面板（原有实现）
        st.success(f"已选择: {st.session_state.selected_project}")

if __name__ == "__main__":
    main()
