# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 修复版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import hashlib

# ==================== 系统配置 ====================
class AppConfig:
    # 只保留本地绝对路径
    DATA_PATHS = [
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx"
    ]
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }
    # 密码配置（使用SHA256加密存储）
    ADMIN_PASSWORD_HASH = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"  # 默认密码123456

# ==================== 辅助函数 ====================
def find_data_file():
    """查找数据文件（增强错误处理）"""
    for path in AppConfig.DATA_PATHS:
        try:
            if os.path.exists(path):
                return path
        except Exception as e:
            st.error(f"路径检查错误: {str(e)}")
    return None

def apply_card_styles():
    """应用卡片样式"""
    st.markdown("""
    <style>
        .metric-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }
        .metric-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid;
        }
        .metric-card.total { border-color: #3498db; }
        .metric-card.shipped { border-color: #2ecc71; }
        .metric-card.pending { border-color: #f39c12; }
        .metric-card.overdue { border-color: #e74c3c; }
        .card-value {
            font-size: 1.5rem;
            font-weight: bold;
            margin: 0.5rem 0;
            color: #333;
        }
        .card-unit {
            font-size: 0.9rem;
            color: #666;
        }
        .overdue-row {
            background-color: #ffdddd !important;
        }
        .password-container {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
            border-left: 4px solid #3498db;
        }
        .file-input-container {
            background: #f0f2f6;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        @media screen and (max-width: 768px) {
            .dataframe {
                font-size: 12px;
            }
            .dataframe th, .dataframe td {
                padding: 4px 8px;
                white-space: nowrap;
            }
        }
    </style>
    """, unsafe_allow_html=True)

def hash_password(password):
    """密码哈希处理"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password():
    """检查密码是否正确"""
    if 'password_verified' not in st.session_state:
        st.session_state.password_verified = False
    return st.session_state.password_verified

# ==================== 数据加载 ====================
@st.cache_data(ttl=10)
def load_data():
    """加载并处理数据（全面增强错误处理）"""
    def safe_convert_to_numeric(series, default=0):
        try:
            str_series = series.astype(str)
            cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
            cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
            return pd.to_numeric(cleaned, errors='coerce').fillna(default)
        except Exception as e:
            st.error(f"数值转换错误: {str(e)}")
            return pd.Series([default] * len(series))

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        st.markdown("**尝试查找的路径：**")
        for path in AppConfig.DATA_PATHS:
            st.markdown(f"- `{path}`")
        
        # 添加手动上传功能
        with st.expander("或手动上传Excel文件"):
            uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
            if uploaded_file:
                try:
                    temp_path = os.path.join(os.getcwd(), uploaded_file.name)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    AppConfig.DATA_PATHS.insert(0, temp_path)
                    st.success(f"已临时使用上传文件: {uploaded_file.name}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"文件上传失败: {str(e)}")
        return pd.DataFrame()

    try:
        st.toast(f"正在读取文件: {os.path.basename(data_path)}", icon="📂")
        
        # 读取时指定列名，避免依赖列位置
        df = pd.read_excel(
            data_path,
            engine='openpyxl',
            dtype=str,
            keep_default_na=False
        )
        
        # 列名标准化处理
        df.columns = df.columns.str.strip()
        
        # 自动检测项目部名称列
        dept_col = None
        possible_names = ["项目部名称", "项目部", "项目名称", "department"]
        for col in df.columns:
            if any(name in col for name in possible_names):
                dept_col = col
                break
        
        if dept_col:
            df = df.rename(columns={dept_col: "项目部名称"})
        else:
            st.error("未检测到项目部名称列，请检查文件格式")
            st.write("现有列名:", df.columns.tolist())
            return pd.DataFrame()
        
        # 检查必要列
        missing_cols = []
        for req_col in AppConfig.REQUIRED_COLS:
            if req_col not in df.columns:
                # 尝试从备用名称查找
                for alt_col in AppConfig.BACKUP_COL_MAPPING.get(req_col, []):
                    if alt_col in df.columns:
                        df = df.rename(columns={alt_col: req_col})
                        break
                else:
                    missing_cols.append(req_col)
        
        if missing_cols:
            st.error(f"缺少必要列: {missing_cols}")
            st.write("当前文件列名:", df.columns.tolist())
            return pd.DataFrame()
        
        # 数据处理
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        df = df[~df["下单时间"].isna()]
        
        df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
        df["已发量"] = safe_convert_to_numeric(df.get("已发量", pd.Series(0))).astype(int)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)
        
        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
            df["超期天数"] = ((pd.Timestamp.now().normalize() - df["计划进场时间"]).dt.days
                              .clip(lower=0)
                              .fillna(0)
                              .astype(int))
        else:
            df["超期天数"] = 0
        
        # 数据质量检查
        check_data_quality(df)
        
        return df
    
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        st.write("调试信息：")
        st.write(f"文件路径: {data_path}")
        st.write(f"文件存在: {os.path.exists(data_path)}")
        if os.path.exists(data_path):
            st.write(f"文件大小: {os.path.getsize(data_path)/1024:.2f} KB")
            st.write(f"修改时间: {datetime.fromtimestamp(os.path.getmtime(data_path))}")
        return pd.DataFrame()

def check_data_quality(df):
    """检查数据质量问题"""
    if df.empty:
        return

    # 检查数值列
    numeric_cols = ["需求量", "已发量", "剩余量"]
    for col in numeric_cols:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            st.warning(f"列 '{col}' 包含非数值数据，已自动转换")
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 检查负值
    negative_values = df[(df["需求量"] < 0) | (df["已发量"] < 0)]
    if not negative_values.empty:
        st.warning(f"发现 {len(negative_values)} 条负值记录（已自动处理为0）")
        with st.expander("查看详情"):
            st.dataframe(negative_values[["标段名称", "下单时间", "需求量", "已发量"]].head(10))

# ==================== 页面组件 ====================
def show_password_input():
    """显示密码输入框"""
    st.markdown('<div class="password-container">', unsafe_allow_html=True)
    st.write("### 总部数据访问授权")
    password = st.text_input("请输入访问密码", type="password", key="admin_password")
    
    if st.button("验证密码", key="verify_password"):
        if hash_password(password) == AppConfig.ADMIN_PASSWORD_HASH:
            st.session_state.password_verified = True
            st.success("密码验证成功！")
            st.rerun()
        else:
            st.error("密码错误，请重新输入")
    st.markdown('</div>', unsafe_allow_html=True)

def show_project_selection(df):
    """显示项目部选择界面（增强空数据处理）"""
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司**")
    
    # 显示文件状态
    data_path = find_data_file()
    if data_path:
        st.success(f"已加载数据文件: {os.path.basename(data_path)}")
        st.caption(f"路径: {data_path}")
        st.caption(f"最后修改: {datetime.fromtimestamp(os.path.getmtime(data_path)) if os.path.exists(data_path) else '未知'}")
    else:
        st.error("未找到有效数据文件")
    
    # 文件路径管理
    with st.expander("文件设置", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_path = st.text_input(
                "修改数据文件路径",
                value=AppConfig.DATA_PATHS[0] if AppConfig.DATA_PATHS else ""
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("确认更新路径"):
                if os.path.exists(new_path):
                    AppConfig.DATA_PATHS[0] = new_path
                    st.success("路径已更新！")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("路径不存在")
        
        # 文件上传作为备用方案
        uploaded_file = st.file_uploader("或上传Excel文件", type=["xlsx", "xls"])
        if uploaded_file:
            try:
                temp_path = os.path.join(os.getcwd(), uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                AppConfig.DATA_PATHS.insert(0, temp_path)
                st.success(f"已使用上传文件: {uploaded_file.name}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"文件上传失败: {str(e)}")
    
    # 空数据情况处理
    if df.empty:
        st.warning("当前没有可用的数据，请检查文件设置")
        if st.button("🔄 重新加载数据"):
            st.cache_data.clear()
            st.rerun()
        return
    
    # 项目部选择
    try:
        if "项目部名称" not in df.columns:
            st.error("数据中缺少'项目部名称'列")
            st.write("当前数据列:", df.columns.tolist())
            return
        
        # 获取有效项目部列表
        valid_projects = [p for p in df["项目部名称"].unique() if p and str(p).strip() != "未指定项目部"]
        valid_projects = sorted([p for p in valid_projects if pd.notna(p)])
        
        if not valid_projects:
            st.error("未找到有效的项目部数据")
            st.write("项目部名称样例:", df["项目部名称"].unique()[:5])
            return
        
        options = ["中铁物贸成都分公司"] + valid_projects
        
        selected = st.selectbox("选择项目部", options, key="project_select")
        
        # 密码验证
        if selected == "中铁物贸成都分公司" and not check_password():
            show_password_input()
            return
        
        if st.button("确认进入", type="primary", key="confirm_enter"):
            st.session_state.project_selected = True
            st.session_state.selected_project = selected
            st.rerun()
    
    except Exception as e:
        st.error(f"项目部选择界面错误: {str(e)}")
        st.write("调试信息：")
        if not df.empty:
            st.write("数据前两行:", df.head(2))
        st.write("项目部名称列内容:", df.get("项目部名称", pd.Series(["无"])).unique())

def display_metrics_cards(filtered_df):
    """显示指标卡片"""
    if filtered_df.empty:
        st.warning("没有可显示的数据")
        return

    try:
        total_demand = int(filtered_df["需求量"].sum())
        shipped_quantity = int(filtered_df["已发量"].sum())
        remaining_quantity = int(filtered_df["剩余量"].sum())

        overdue_orders = filtered_df[filtered_df["超期天数"] > 0]
        overdue_count = len(overdue_orders)
        max_overdue = int(overdue_orders["超期天数"].max()) if not overdue_orders.empty else 0

        cards_data = [
            {"type": "total", "icon": "📦", "title": "总需求量", "value": f"{total_demand:,}", "unit": "吨"},
            {"type": "shipped", "icon": "🚚", "title": "已发货量", "value": f"{shipped_quantity:,}", "unit": "吨"},
            {"type": "pending", "icon": "⏳", "title": "待发货量", "value": f"{remaining_quantity:,}", "unit": "吨"},
            {"type": "overdue", "icon": "⚠️", "title": "超期订单", "value": f"{overdue_count}", "unit": "单",
             "extra": f"最大超期: {max_overdue}天" if overdue_count > 0 else ""}
        ]

        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        cols = st.columns(4)
        for idx, card in enumerate(cards_data):
            with cols[idx]:
                content = f"""
                <div class="metric-card {card['type']}">
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span style="font-size:1.2rem">{card['icon']}</span>
                        <span style="font-weight:600">{card['title']}</span>
                    </div>
                    <div class="card-value">{card['value']}</div>
                    <div class="card-unit">{card['unit']}</div>
                    {f'<div style="font-size:0.8rem; color:#666;">{card.get("extra", "")}</div>' if card.get("extra") else ''}
                </div>
                """
                st.markdown(content, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"指标计算错误: {str(e)}")
        st.write("数据列:", filtered_df.columns.tolist())

def show_data_panel(df, project):
    """显示数据面板"""
    st.title(f"{project} - 发货数据")
    
    # 显示当前数据文件信息
    data_path = find_data_file()
    if data_path:
        st.caption(f"数据源: {os.path.basename(data_path)} (最后更新: {datetime.fromtimestamp(os.path.getmtime(data_path))})")
    else:
        st.warning("数据文件未找到")
    
    # 操作按钮
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 刷新数据", help="重新加载最新数据"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("📁 更改文件", help="选择其他数据文件"):
            st.session_state.project_selected = False
            st.rerun()
    with col3:
        if st.button("← 返回项目部选择"):
            st.session_state.project_selected = False
            st.rerun()

    # 日期范围选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=7),
            format="YYYY/MM/DD",
            key="start_date"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            format="YYYY/MM/DD",
            key="end_date"
        )

    if start_date > end_date:
        st.error("结束日期不能早于开始日期")
        return

    # 数据筛选
    try:
        filtered_df = df if project == "中铁物贸成都分公司" else df[df["项目部名称"] == project]
        date_range_df = filtered_df[
            (filtered_df["下单时间"].dt.date >= start_date) &
            (filtered_df["下单时间"].dt.date <= end_date)
        ]
    except Exception as e:
        st.error(f"数据筛选错误: {str(e)}")
        st.write("调试信息：")
        st.write(f"项目部名称列内容:", df["项目部名称"].unique())
        st.write(f"下单时间列类型:", type(df["下单时间"].iloc[0]) if len(df) > 0 else "空数据")
        return

    if not date_range_df.empty:
        display_metrics_cards(date_range_df)
        st.subheader("📋 发货明细")

        # 准备显示列
        display_cols = {
            "标段名称": "工程标段",
            "物资名称": "材料名称",
            "规格型号": "规格型号",
            "需求量": "需求(吨)",
            "已发量": "已发(吨)",
            "剩余量": "待发(吨)",
            "超期天数": "超期天数",
            "下单时间": "下单时间",
            "计划进场时间": "计划进场时间"
        }
        available_cols = {k: v for k, v in display_cols.items() if k in date_range_df.columns}
        display_df = date_range_df[available_cols.keys()].rename(columns=available_cols)

        # 渲染表格
        try:
            st.dataframe(
                display_df.style.format({
                    '需求(吨)': '{:,}',
                    '已发(吨)': '{:,}',
                    '待发(吨)': '{:,}',
                    '超期天数': '{:,}',
                    '下单时间': lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else '',
                    '计划进场时间': lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else ''
                }).apply(
                    lambda row: ['background-color: #ffdddd' if row.get('超期天数', 0) > 0 else ''
                                 for _ in row],
                    axis=1
                ),
                use_container_width=True,
                height=min(600, 35 * len(display_df) + 40),
                hide_index=True
            )
        except Exception as e:
            st.error(f"表格渲染错误: {str(e)}")
            st.write("尝试显示原始数据:")
            st.write(display_df)

        # 数据导出
        st.download_button(
            label="⬇️ 导出当前数据",
            data=display_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
            file_name=f"{project}_发货数据_{start_date}_{end_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info(
            f"{'所有项目部' if project == '中铁物贸成都分公司' else project}在{start_date}至{end_date}期间没有发货记录")

# ==================== 主程序 ====================
def main():
    # 初始化配置
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    apply_card_styles()

    # 初始化session状态
    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = None

    # 加载数据
    with st.spinner('正在加载数据...'):
        df = load_data()

    # 页面路由
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)

if __name__ == "__main__":
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    main()
