# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 完整修正版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests


# ==================== 系统配置 ====================
class AppConfig:
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    LOGISTICS_SHEET_NAME = "物流明细"
    LOGISTICS_COLUMNS = [
        "钢厂", "物资名称", "规格型号", "单位", "数量",
        "交货时间", "交货地点", "联系人", "联系方式", "项目部",
        "到货状态"
    ]

    DATE_FORMAT = "%Y-%m-%d"
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '物资名称': ['材料名称', '品名', '名称'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }
    WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dcf16af3-78d2-433f-9c3d-b4cd108c7b60"


# ==================== 辅助函数 ====================
def find_data_file():
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None


def apply_card_styles():
    st.markdown("""
    <style>
        .metric-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0; }
        .metric-card { background: #f8f9fa; border-radius: 8px; padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid; }
        .metric-card.total { border-color: #3498db; }
        .metric-card.shipped { border-color: #2ecc71; }
        .metric-card.pending { border-color: #f39c12; }
        .metric-card.overdue { border-color: #e74c3c; }
        .card-value { font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0; color: #333; }
        .card-unit { font-size: 0.9rem; color: #666; }
        .overdue-row { background-color: #ffdddd !important; }
    </style>
    """, unsafe_allow_html=True)


# ==================== 数据加载 ====================
@st.cache_data(ttl=10)
def load_data():
    def safe_convert_to_numeric(series, default=0):
        str_series = series.astype(str)
        cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
        return pd.to_numeric(cleaned, errors='coerce').fillna(default)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到发货计划数据文件")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')

        # 列名标准化 - 确保物资名称列存在
        for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
            for alt_col in alt_cols:
                if alt_col in df.columns and std_col not in df.columns:
                    df.rename(columns={alt_col: std_col}, inplace=True)
                    break

        # 验证必要列 - 确保包含物资名称
        REQUIRED_COLS = ['标段名称', '物资名称', '下单时间', '需求量']
        missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            st.error(f"缺少必要列: {missing_cols}")
            return pd.DataFrame()

        # 数据处理 - 确保物资名称不为空
        df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
            "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})

        df["项目部名称"] = df.iloc[:, 17].astype(str).str.strip().replace({
            "": "未指定项目部", "nan": "未指定项目部", "None": "未指定项目部", None: "未指定项目部"})

        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        df = df[~df["下单时间"].isna()]

        df["需求量"] = safe_convert_to_numeric(df["需求量"]).astype(int)
        df["已发量"] = safe_convert_to_numeric(df.get("已发量", 0)).astype(int)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0).astype(int)

        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
            df["超期天数"] = ((pd.Timestamp.now() - df["计划进场时间"]).dt.days.clip(lower=0).fillna(0).astype(int))
        else:
            df["超期天数"] = 0

        return df
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=10)
def load_logistics_data():
    data_path = find_data_file()
    if not data_path:
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)

    try:
        df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')

        # 标准化列 - 确保物资名称列存在
        for col in AppConfig.LOGISTICS_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col != "数量" else 0

        # 确保物资名称不为空
        df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
            "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})

        df["数量"] = pd.to_numeric(df["数量"], errors="coerce").fillna(0)
        df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")
        df["联系方式"] = df["联系方式"].astype(str)

        return df[AppConfig.LOGISTICS_COLUMNS]
    except Exception as e:
        st.error(f"物流数据加载失败: {str(e)}")
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)


def save_logistics_data(df):
    data_path = find_data_file()
    if not data_path:
        return False

    try:
        # 备份原始数据
        original = pd.read_excel(data_path, sheet_name=None, engine='openpyxl')

        with pd.ExcelWriter(data_path, engine='openpyxl') as writer:
            # 保存其他工作表
            for sheet_name, sheet_data in original.items():
                if sheet_name != AppConfig.LOGISTICS_SHEET_NAME:
                    sheet_data.to_excel(writer, sheet_name=sheet_name, index=False)

            # 保存物流明细
            df.to_excel(writer, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, index=False)

        return True
    except PermissionError:
        st.error("无法保存文件，请关闭Excel文件后重试")
    except Exception as e:
        st.error(f"保存失败: {str(e)}")
    return False


def send_feishu_notification(message):
    try:
        requests.post(AppConfig.WEBHOOK_URL, json={
            "msg_type": "text",
            "content": {"text": message}
        })
    except Exception as e:
        st.error(f"通知发送失败: {str(e)}")


# ==================== 页面组件 ====================
def show_project_selection(df):
    st.title("🏗️ 钢筋发货监控系统")
    st.markdown("**中铁物贸成都分公司**")

    valid_projects = sorted([p for p in df["项目部名称"].unique() if p != "未指定项目部"])
    selected = st.selectbox("选择项目部", ["中铁物贸成都分公司"] + valid_projects)

    if st.button("确认进入", type="primary"):
        st.session_state.project_selected = True
        st.session_state.selected_project = selected
        st.rerun()


def display_metrics_cards(filtered_df):
    if filtered_df.empty:
        return

    total = int(filtered_df["需求量"].sum())
    shipped = int(filtered_df["已发量"].sum())
    pending = int(filtered_df["剩余量"].sum())
    overdue = len(filtered_df[filtered_df["超期天数"] > 0])
    max_overdue = filtered_df["超期天数"].max() if overdue > 0 else 0

    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    metrics = [
        ("📦", "总需求量", f"{total:,}", "吨", "total"),
        ("🚚", "已发货量", f"{shipped:,}", "吨", "shipped"),
        ("⏳", "待发货量", f"{pending:,}", "吨", "pending"),
        ("⚠️", "超期订单", f"{overdue}", "单", "overdue", f"最大超期: {max_overdue}天" if overdue > 0 else "")
    ]

    for idx, metric in enumerate(metrics):
        with cols[idx]:
            st.markdown(f"""
            <div class="metric-card {metric[4]}">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <span style="font-size:1.2rem">{metric[0]}</span>
                    <span style="font-weight:600">{metric[1]}</span>
                </div>
                <div class="card-value">{metric[2]}</div>
                <div class="card-unit">{metric[3]}</div>
                {f'<div style="font-size:0.8rem; color:#666;">{metric[5]}</div>' if len(metric) > 5 else ''}
            </div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def show_logistics_tab(project):
    st.subheader("🚛 钢材物流明细管理")
    df = load_logistics_data()

    if project != "中铁物贸成都分公司":
        df = df[df["项目部"] == project]

    if not df.empty:
        # 确保物资名称列显示
        if "物资名称" not in df.columns:
            st.error("物流数据中缺少'物资名称'列")
            return

        # 配置可编辑列
        column_config = {
            col: st.column_config.Column(disabled=True)
            for col in df.columns
            if col != "到货状态"
        }
        column_config["到货状态"] = st.column_config.SelectboxColumn(
            options=["已到货", "未到货"],
            width="medium"
        )

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            column_config=column_config,
            key="logistics_editor"
        )

        if st.button("💾 保存修改", type="primary"):
            try:
                # 检查未到货记录
                new_not_arrived = edited_df[
                    (edited_df["到货状态"] == "未到货") &
                    ((df["到货状态"] != "未到货") | (df["到货状态"].isna()))
                    ]

                if not new_not_arrived.empty:
                    message = "⚠️ 以下物资被标记为未到货:\n\n" + "\n".join(
                        f"{row['物资名称']}({row['规格型号']}) {row['数量']}吨 @{row['钢厂']}"
                        for _, row in new_not_arrived.iterrows()
                    )
                    send_feishu_notification(message)

                if save_logistics_data(edited_df):
                    st.success("数据已保存!")
                    st.rerun()
            except Exception as e:
                st.error(f"保存失败: {str(e)}")
    else:
        st.info("暂无物流数据")


def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("← 返回"):
            st.session_state.project_selected = False
            st.rerun()

    tab1, tab2 = st.tabs(["📋 发货计划", "🚛 物流明细"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("结束日期", datetime.now())

        if start_date > end_date:
            st.error("日期范围无效")
        else:
            filtered_df = df if project == "中铁物贸成都分公司" else df[df["项目部名称"] == project]
            date_range_df = filtered_df[
                (filtered_df["下单时间"].dt.date >= start_date) &
                (filtered_df["下单时间"].dt.date <= end_date)
                ]

            if not date_range_df.empty:
                display_metrics_cards(date_range_df)

                # 确保物资名称列在显示列中
                display_cols = {
                    "标段名称": "工程标段",
                    "物资名称": "材料名称",  # 确保物资名称显示
                    "规格型号": "规格型号",
                    "需求量": "需求(吨)",
                    "已发量": "已发(吨)",
                    "剩余量": "待发(吨)",
                    "超期天数": "超期天数",
                    "下单时间": "下单时间",
                    "计划进场时间": "计划进场时间"
                }

                # 只保留数据中实际存在的列
                available_cols = {k: v for k, v in display_cols.items() if k in date_range_df.columns}
                display_df = date_range_df[available_cols.keys()].rename(columns=available_cols)

                # 确保物资名称显示不为空
                if "材料名称" in display_df.columns:
                    display_df["材料名称"] = display_df["材料名称"].fillna("未指定物资")

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

                st.download_button(
                    "⬇️ 导出数据",
                    display_df.to_csv(index=False).encode('utf-8-sig'),
                    f"{project}_发货数据_{start_date}_{end_date}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("该时间段无数据")

    with tab2:
        show_logistics_tab(project)


# ==================== 主程序 ====================
def main():
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    apply_card_styles()

    if 'project_selected' not in st.session_state:
        st.session_state.project_selected = False
    if 'selected_project' not in st.session_state:
        st.session_state.selected_project = "中铁物贸成都分公司"

    with st.spinner('加载数据中...'):
        df = load_data()

    if not st.session_state.project_selected:
        show_project_selection(df)
    else:
        show_data_panel(df, st.session_state.selected_project)


if __name__ == "__main__":
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    main()
