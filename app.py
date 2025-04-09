# -*- coding: utf-8 -*-
"""钢筋发货监控系统（移动端优化版）"""
import os
import io
import hashlib
import numpy as np
from datetime import datetime
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
    """查找数据文件"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None


def apply_card_styles():
    """应用响应式卡片样式"""
    st.markdown("""
    <style>
        /* 响应式卡片布局 */
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

        /* 响应式表格 */
        @media screen and (max-width: 768px) {
            .dataframe {
                font-size: 12px;
            }
            .dataframe th, .dataframe td {
                padding: 4px 8px;
            }
        }
    </style>
    """, unsafe_allow_html=True)


# ==================== 数据加载 ====================
@st.cache_data(ttl=10)
def load_data():
    """加载并处理数据"""

    def safe_convert_to_int(series, default=0):
        """安全转换为整数"""
        series = pd.to_numeric(series, errors='coerce')
        series = series.replace([np.inf, -np.inf], np.nan).fillna(default)
        return series.astype(int)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')

        # 将第18列（R列）命名为"项目部名称"
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

        # 数据处理
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        df["需求量"] = safe_convert_to_int(df["需求量"])
        df["已发量"] = safe_convert_to_int(df.get("已发量", 0))
        df["剩余量"] = safe_convert_to_int(df["需求量"] - df["已发量"]).clip(lower=0)

        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
            df["超期天数"] = safe_convert_to_int(
                (pd.Timestamp.now().normalize() - df["计划进场时间"]).dt.days
            ).clip(lower=0)
        else:
            df["超期天数"] = 0

        return df
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()


# ==================== 页面组件 ====================
def show_project_selection(df):
    """显示项目部选择界面"""
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司**")
    st.write("请先选择您所属的项目部")

    # 获取有效项目部列表（确保"中铁物贸成都分公司"在最前面）
    valid_projects = [p for p in df["项目部名称"].unique() if p != "未指定项目部"]
    valid_projects = sorted(valid_projects)
    if "中铁物贸成都分公司" in valid_projects:
        valid_projects.remove("中铁物贸成都分公司")
        valid_projects.insert(0, "中铁物贸成都分公司")

    options = ["所有项目部"] + valid_projects

    selected = st.selectbox("选择项目部", options)

    if st.button("确认进入", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.rerun()


def display_metrics_cards(filtered_df):
    """显示指标卡片（优化显示效果）"""
    if filtered_df.empty:
        return

    try:
        total_demand = int(filtered_df["需求量"].sum())
        shipped_quantity = int(filtered_df["已发量"].sum())
        remaining_quantity = int(filtered_df["剩余量"].sum())

        overdue_orders = filtered_df[filtered_df["超期天数"] > 0]
        overdue_count = len(overdue_orders)
        max_overdue = int(overdue_orders["超期天数"].max()) if not overdue_orders.empty else 0

        # 四张卡片：总需求量、已发货量、待发货量、超期订单
        cards_data = [
            {"type": "total", "icon": "📦", "title": "总需求量", "value": f"{total_demand:,}", "unit": "吨"},
            {"type": "shipped", "icon": "🚚", "title": "已发货量", "value": f"{shipped_quantity:,}", "unit": "吨"},
            {"type": "pending", "icon": "⏳", "title": "待发货量", "value": f"{remaining_quantity:,}", "unit": "吨"},
            {"type": "overdue", "icon": "⚠️", "title": "超期订单", "value": f"{overdue_count}", "unit": "单"}
        ]

        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        cols = st.columns(4)
        for idx, card in enumerate(cards_data):
            with cols[idx]:
                st.markdown(f"""
                <div class="metric-card {card['type']}">
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span style="font-size:1.2rem">{card['icon']}</span>
                        <span style="font-weight:600">{card['title']}</span>
                    </div>
                    <div class="card-value">{card['value']}</div>
                    <div class="card-unit">{card['unit']}</div>
                    {f'<div style="font-size:0.8rem; color:#666;">最大超期: {max_overdue}天</div>' if card['type'] == 'overdue' else ''}
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"指标卡片生成错误: {str(e)}")


def show_data_panel(df, project):
    """显示数据面板"""
    st.title(f"{project} - 发货数据")

    if st.button("← 返回项目部选择"):
        st.session_state.project_selected = False
        st.rerun()

    # 筛选数据
    filtered_df = df if project == "所有项目部" else df[df["项目部名称"] == project]
    today_df = filtered_df[filtered_df["下单时间"].dt.date == datetime.now().date()]

    if not today_df.empty:
        # 显示统计卡片
        display_metrics_cards(today_df)

        # 显示数据表格（优化移动端显示）
        st.subheader("📋 发货明细")

        # 准备显示列
        display_cols = {
            "标段名称": "工程标段",
            "物资名称": "材料名称",
            "规格型号": "规格型号",
            "需求量": "需求(吨)",
            "已发量": "已发(吨)",
            "剩余量": "待发(吨)",
            "超期天数": "超期天数"
        }

        # 过滤有效列
        available_cols = {k: v for k, v in display_cols.items() if k in today_df.columns}
        display_df = today_df[available_cols.keys()].rename(columns=available_cols)

        # 设置表格样式
        st.markdown("""
        <style>
            .stDataFrame {
                width: 100%;
                overflow-x: auto;
            }
            .stDataFrame table {
                min-width: 100%;
            }
        </style>
        """, unsafe_allow_html=True)

        # 显示表格（带缩放功能）
        st.dataframe(
            display_df.style.format({
                '需求(吨)': '{:,}',
                '已发(吨)': '{:,}',
                '待发(吨)': '{:,}'
            }),
            use_container_width=True,
            height=min(400, 35 * len(display_df) + 35),  # 动态调整高度
            hide_index=True
        )

        # 数据导出
        st.download_button(
            label="⬇️ 导出当前数据",
            data=display_df.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"{project}_发货数据_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info(f"{project}今日没有发货记录")


# ==================== 主程序 ====================
def main():
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

    if df.empty:
        st.error("无法加载数据，请检查Excel文件")
        return

    # 页面路由
    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)


if __name__ == "__main__":
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    main()
