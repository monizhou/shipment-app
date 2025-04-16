# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 数据兼容性优化版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st


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


# ==================== 辅助函数 ====================
def find_data_file():
    """查找数据文件（优化查找效率）"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None


def apply_card_styles():
    """应用卡片样式（保持不变）"""
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


# ==================== 数据加载 ====================
@st.cache_data(ttl=10)
def load_data():
    """加载并处理数据（增强数据兼容性处理）"""

    def safe_convert_to_numeric(series, default=0):
        """
        安全转换为数值类型
        处理以下特殊情况：
        - 空值/缺失值
        - 文本中包含数字（如"约10吨"）
        - 特殊符号（如"10+"、"5-10"）
        - 千分位分隔符（如"1,000"）
        """
        # 统一转为字符串处理
        str_series = series.astype(str)

        # 清洗数据：移除非数字字符（保留小数点和负号）
        cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)

        # 处理空字符串
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})

        # 转换为数值
        return pd.to_numeric(cleaned, errors='coerce').fillna(default)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        st.markdown(f"**尝试查找的路径：**")
        for path in AppConfig.DATA_PATHS:
            st.markdown(f"- `{path}`")
        return pd.DataFrame()

    try:
        # 先读取原始数据，不指定dtype以避免转换错误
        df = pd.read_excel(data_path, engine='openpyxl')

        # 验证必要列是否存在
        if len(df.columns) > 17:
            df = df.rename(columns={df.columns[17]: "项目部名称"})
        else:
            st.error("Excel文件缺少第18列（R列），请检查文件格式")
            return pd.DataFrame()

        # 标准化处理
        df["项目部名称"] = df["项目部名称"].astype(str).str.strip()
        df["项目部名称"] = df["项目部名称"].replace({
            "": "未指定项目部",
            "nan": "未指定项目部",
            "None": "未指定项目部",
            None: "未指定项目部"
        })

        # 列名标准化
        for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
            for alt_col in alt_cols:
                if alt_col in df.columns:
                    df.rename(columns={alt_col: std_col}, inplace=True)
                    break

        # 必要列验证
        missing_cols = [col for col in AppConfig.REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            st.error(f"缺少必要列: {missing_cols}")
            return pd.DataFrame()

        # 数据处理（使用增强的转换函数）
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        df = df[~df["下单时间"].isna()]  # 过滤无效日期记录

        # 数值转换（处理各种异常情况）
        df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
        df["已发量"] = safe_convert_to_numeric(df.get("已发量", 0)).astype(int)
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
        return pd.DataFrame()


def check_data_quality(df):
    """检查数据质量问题并提示用户"""
    if df.empty:
        return

    # 检查"已发量"异常值
    invalid_shipped = df[df["已发量"].astype(str).str.contains('[^0-9.-]')]
    if not invalid_shipped.empty:
        st.warning(f"发现 {len(invalid_shipped)} 条'已发量'包含非数字字符（已自动处理）")
        with st.expander("查看详情"):
            st.dataframe(invalid_shipped[["标段名称", "下单时间", "已发量"]].head(10))

    # 检查负值
    negative_values = df[(df["需求量"] < 0) | (df["已发量"] < 0)]
    if not negative_values.empty:
        st.warning(f"发现 {len(negative_values)} 条负值记录（已自动处理为0）")
        with st.expander("查看详情"):
            st.dataframe(negative_values[["标段名称", "下单时间", "需求量", "已发量"]].head(10))


# ==================== 页面组件 ====================
def show_project_selection(df):
    """显示项目部选择界面（保持不变）"""
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司**")
    st.write("请先选择您所属的项目部")

    # 获取有效项目部列表
    valid_projects = [p for p in df["项目部名称"].unique() if p != "未指定项目部"]
    valid_projects = sorted(valid_projects)
    options = ["中铁物贸成都分公司"] + valid_projects

    selected = st.selectbox("选择项目部", options)
    if st.button("确认进入", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.rerun()


def display_metrics_cards(filtered_df):
    """显示指标卡片（优化计算性能）"""
    if filtered_df.empty:
        return

    # 批量计算指标
    total_demand = int(filtered_df["需求量"].sum())
    shipped_quantity = int(filtered_df["已发量"].sum())
    remaining_quantity = int(filtered_df["剩余量"].sum())

    overdue_orders = filtered_df[filtered_df["超期天数"] > 0]
    overdue_count = len(overdue_orders)
    max_overdue = int(overdue_orders["超期天数"].max()) if not overdue_orders.empty else 0

    # 卡片数据
    cards_data = [
        {"type": "total", "icon": "📦", "title": "总需求量", "value": f"{total_demand:,}", "unit": "吨"},
        {"type": "shipped", "icon": "🚚", "title": "已发货量", "value": f"{shipped_quantity:,}", "unit": "吨"},
        {"type": "pending", "icon": "⏳", "title": "待发货量", "value": f"{remaining_quantity:,}", "unit": "吨"},
        {"type": "overdue", "icon": "⚠️", "title": "超期订单", "value": f"{overdue_count}", "unit": "单",
         "extra": f"最大超期: {max_overdue}天" if overdue_count > 0 else ""}
    ]

    # 渲染卡片
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


def show_data_panel(df, project):
    """显示数据面板（优化交互体验）"""
    st.title(f"{project} - 发货数据")

    # 操作按钮
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新数据", help="点击重新加载最新数据"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("← 返回项目部选择"):
            st.session_state.project_selected = False
            st.rerun()

    # 日期范围选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=1),
            format="YYYY/MM/DD"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            format="YYYY/MM/DD"
        )

    if start_date > end_date:
        st.error("结束日期不能早于开始日期")
        return

    # 数据筛选
    filtered_df = df if project == "中铁物贸成都分公司" else df[df["项目部名称"] == project]
    date_range_df = filtered_df[
        (filtered_df["下单时间"].dt.date >= start_date) &
        (filtered_df["下单时间"].dt.date <= end_date)
        ]

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

        # 数据导出
        st.download_button(
            label="⬇️ 导出当前数据",
            data=display_df.to_csv(index=False).encode('utf-8-sig'),
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
