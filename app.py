# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 物流状态独立存储版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests
import hashlib
import json


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
        "交货时间", "收货地址", "联系人", "联系方式", "项目部",
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
    LOGISTICS_DATE_RANGE_DAYS = 5

    LOGISTICS_STATUS_FILE = "logistics_status.csv"
    STATUS_OPTIONS = ["已到货", "未到货"]
    PROJECT_COLUMN = "项目部名称"

    CARD_STYLES = {
        "hover_shadow": "0 8px 16px rgba(0,0,0,0.2)",
        "glass_effect": """
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        """,
        "number_animation": """
            @keyframes countup {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        """,
        "floating_animation": """
            @keyframes floating {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-8px); }
                100% { transform: translateY(0px); }
            }
        """,
        "pulse_animation": """
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.03); }
                100% { transform: scale(1); }
            }
        """
    }


# ==================== 辅助函数 ====================
def find_data_file():
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None


def apply_card_styles():
    st.markdown(f"""
    <style>
        {AppConfig.CARD_STYLES['number_animation']}
        {AppConfig.CARD_STYLES['floating_animation']}
        {AppConfig.CARD_STYLES['pulse_animation']}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .metric-container {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 1rem; 
            margin: 1rem 0; 
            animation: fadeIn 0.6s ease-out;
        }}
        .metric-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            transition: all 0.3s ease;
            padding: 1.5rem;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: {AppConfig.CARD_STYLES['hover_shadow']};
        }}
        .card-value {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            color: transparent;
            animation: countup 0.8s ease-out;
            margin: 0.5rem 0;
        }}
        .card-unit {{
            font-size: 0.9rem;
            color: #666;
        }}
        .overdue-row {{ background-color: #ffdddd !important; }}
        .status-arrived {{ background-color: #ddffdd !important; }}
        .status-not-arrived {{ background-color: #ffdddd !important; }}
        .status-empty {{ background-color: transparent !important; }}

        .home-card {{
            {AppConfig.CARD_STYLES['glass_effect']}
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: all 0.3s ease;
            animation: floating 4s ease-in-out infinite;
        }}
        .home-card:hover {{
            animation: pulse 1.5s infinite;
            box-shadow: {AppConfig.CARD_STYLES['hover_shadow']};
        }}
        .home-card-title {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #2c3e50;
            border-bottom: 2px solid rgba(44, 62, 80, 0.1);
            padding-bottom: 0.5rem;
        }}
        .home-card-content {{
            font-size: 1rem;
            line-height: 1.6;
            color: #555;
        }}
        .home-card-icon {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: #3498db;
        }}
        .project-selector {{
            margin-top: 2rem;
            margin-bottom: 2rem;
        }}
        .welcome-header {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            color: transparent;
            text-align: center;
        }}
        .welcome-subheader {{
            font-size: 1.2rem;
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }}
        .dataframe {{
            animation: fadeIn 0.6s ease-out;
        }}
    </style>
    """, unsafe_allow_html=True)


def generate_record_id(row):
    key_fields = [
        str(row["钢厂"]),
        str(row["物资名称"]),
        str(row["规格型号"]),
        str(row["交货时间"]),
        str(row["项目部"])
    ]
    return hashlib.md5("|".join(key_fields).encode('utf-8')).hexdigest()


def send_feishu_notification(material_info):
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "elements": [{
                "tag": "div",
                "text": {
                    "content": f"**物资名称**: {material_info['物资名称']}\n"
                               f"**规格型号**: {material_info['规格型号']}\n"
                               f"**数量**: {material_info['数量']}\n"
                               f"**交货时间**: {material_info['交货时间']}\n"
                               f"**项目部**: {material_info['项目部']}",
                    "tag": "lark_md"
                }
            }, {
                "tag": "hr"
            }, {
                "tag": "note",
                "elements": [{
                    "content": "⚠️ 该物资状态已更新为【未到货】，请及时跟进",
                    "tag": "plain_text"
                }]
            }],
            "header": {
                "template": "red",
                "title": {
                    "content": "【物流状态更新通知】",
                    "tag": "plain_text"
                }
            }
        }
    }
    try:
        response = requests.post(
            AppConfig.WEBHOOK_URL,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception as e:
        st.error(f"飞书通知发送失败: {str(e)}")
        return False


# ==================== 数据加载 ====================
@st.cache_data(ttl=3600)
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
        with st.spinner("正在加载基础数据..."):
            df = pd.read_excel(data_path, engine='openpyxl')

            for std_col, alt_cols in AppConfig.BACKUP_COL_MAPPING.items():
                for alt_col in alt_cols:
                    if alt_col in df.columns and std_col not in df.columns:
                        df.rename(columns={alt_col: std_col}, inplace=True)
                        break

            REQUIRED_COLS = ['标段名称', '物资名称', '下单时间', '需求量']
            missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
            if missing_cols:
                st.error(f"缺少必要列: {missing_cols}")
                return pd.DataFrame()

            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
                "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})

            df[AppConfig.PROJECT_COLUMN] = df.iloc[:, 17].astype(str).str.strip().replace({
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


@st.cache_data(ttl=3600)
def load_logistics_data():
    data_path = find_data_file()
    if not data_path:
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)

    try:
        with st.spinner("正在加载物流数据..."):
            df = pd.read_excel(data_path, sheet_name=AppConfig.LOGISTICS_SHEET_NAME, engine='openpyxl')

            for col in AppConfig.LOGISTICS_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col != "数量" else 0

            df["物资名称"] = df["物资名称"].astype(str).str.strip().replace({
                "": "未指定物资", "nan": "未指定物资", "None": "未指定物资", None: "未指定物资"})
            df["钢厂"] = df["钢厂"].astype(str).str.strip().replace({
                "": "未指定钢厂", "nan": "未指定钢厂", "None": "未指定钢厂", None: "未指定钢厂"})
            df["项目部"] = df["项目部"].astype(str).str.strip().replace({
                "未指定项目部": "", "nan": "", "None": "", None: ""})

            df["数量"] = pd.to_numeric(df["数量"], errors="coerce").fillna(0)
            df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")
            df["联系方式"] = df["联系方式"].astype(str)

            df["record_id"] = df.apply(generate_record_id, axis=1)
            return df[AppConfig.LOGISTICS_COLUMNS + ["record_id"]]
    except Exception as e:
        st.error(f"物流数据加载失败: {str(e)}")
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS + ["record_id"])


# ==================== 物流状态管理 ====================
def load_logistics_status():
    if os.path.exists(AppConfig.LOGISTICS_STATUS_FILE):
        with st.spinner("加载物流状态..."):
            status_df = pd.read_csv(AppConfig.LOGISTICS_STATUS_FILE)
            if "record_id" not in status_df.columns:
                status_df["record_id"] = ""
            if "update_time" not in status_df.columns:
                status_df["update_time"] = datetime.now().strftime(AppConfig.DATE_FORMAT)
            return status_df
    return pd.DataFrame(columns=["record_id", "到货状态", "update_time"])


def save_logistics_status(status_df):
    try:
        with st.spinner("保存状态..."):
            status_df.to_csv(AppConfig.LOGISTICS_STATUS_FILE, index=False, encoding='utf-8-sig')
            return True
    except Exception as e:
        st.error(f"状态保存失败: {str(e)}")
        return False


def merge_logistics_with_status(logistics_df):
    if logistics_df.empty:
        return logistics_df

    status_df = load_logistics_status()
    if status_df.empty:
        logistics_df["到货状态"] = " "
        return logistics_df

    merged = pd.merge(
        logistics_df,
        status_df[["record_id", "到货状态"]],
        on="record_id",
        how="left",
        suffixes=("", "_status")
    )
    merged["到货状态"] = merged["到货状态_status"].fillna("")
    return merged.drop(columns=["到货状态_status"])


def update_logistics_status(record_id, new_status, original_row=None):
    status_df = load_logistics_status()

    if new_status is None:
        new_status = ""
    new_status = str(new_status).strip()

    send_notification = False
    if new_status == "未到货":
        existing_status = status_df.loc[status_df["record_id"] == record_id, "到货状态"]
        if len(existing_status) == 0 or existing_status.iloc[0] != "未到货":
            send_notification = True

    if record_id in status_df["record_id"].values:
        if new_status == " ":
            status_df = status_df[status_df["record_id"] != record_id]
        else:
            status_df.loc[status_df["record_id"] == record_id, "到货状态"] = new_status
            status_df.loc[status_df["record_id"] == record_id, "update_time"] = datetime.now().strftime(
                AppConfig.DATE_FORMAT)
    elif new_status != " ":
        new_record = pd.DataFrame([{
            "record_id": record_id,
            "到货状态": new_status,
            "update_time": datetime.now().strftime(AppConfig.DATE_FORMAT)
        }])
        status_df = pd.concat([status_df, new_record], ignore_index=True)

    if save_logistics_status(status_df):
        if send_notification and original_row is not None:
            material_info = {
                "物资名称": original_row["物资名称"],
                "规格型号": original_row["规格型号"],
                "数量": original_row["数量"],
                "交货时间": original_row["交货时间"].strftime("%Y-%m-%d %H:%M"),
                "项目部": original_row["项目部"]
            }
            if send_feishu_notification(material_info):
                st.toast("已发送物流异常通知到相关负责人", icon="📨")
        return True
    return False


# ==================== 页面组件 ====================
def show_logistics_tab(project):
    st.subheader("🚛 钢材物流明细管理")

    col1, col2 = st.columns(2)
    with col1:
        logistics_start_date = st.date_input(
            "开始日期",
            datetime.now().date() - timedelta(days=AppConfig.LOGISTICS_DATE_RANGE_DAYS),
            key="logistics_start"
        )
    with col2:
        logistics_end_date = st.date_input(
            "结束日期",
            datetime.now().date(),
            key="logistics_end"
        )

    if logistics_start_date > logistics_end_date:
        st.error("结束日期不能早于开始日期")
        return

    with st.spinner("加载物流信息..."):
        logistics_df = load_logistics_data()
        if project != "中铁物贸成都分公司":
            logistics_df = logistics_df[logistics_df["项目部"] == project]

        if not logistics_df.empty:
            logistics_df = merge_logistics_with_status(logistics_df)
            mask = (
                    (logistics_df["交货时间"].dt.date >= logistics_start_date) &
                    (logistics_df["交货时间"].dt.date <= logistics_end_date)
            )
            filtered_df = logistics_df[mask].copy()

            st.caption(f"显示 {logistics_start_date} 至 {logistics_end_date} 的数据（共 {len(filtered_df)} 条记录）")

            edited_df = st.data_editor(
                filtered_df.drop(columns=["record_id"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "到货状态": st.column_config.SelectboxColumn(
                        "到货状态",
                        options=AppConfig.STATUS_OPTIONS,
                        default="",
                        required=False,
                        width="small"
                    ),
                    **{col: {"width": "auto"} for col in filtered_df.columns if col != "到货状态"}
                },
                key=f"logistics_editor_{project}"
            )

            if 'logistics_editor_' + project in st.session_state:
                changed_rows = st.session_state['logistics_editor_' + project]['edited_rows']
                rows_to_process = []
                for row_index, changes in changed_rows.items():
                    if "到货状态" in changes:
                        rows_to_process.append(row_index)

                for row_index in rows_to_process:
                    changes = changed_rows[row_index]
                    record_id = filtered_df.iloc[row_index]["record_id"]
                    new_status = changes["到货状态"]
                    original_row = filtered_df.iloc[row_index]

                    if update_logistics_status(record_id, new_status, original_row):
                        st.toast(f"已自动保存状态更新：{original_row['物资名称']}", icon="✅")

                    del st.session_state['logistics_editor_' + project]['edited_rows'][row_index]

            status_df = load_logistics_status()
            if not status_df.empty:
                last_update = pd.to_datetime(status_df["update_time"]).max()
                st.caption(f"状态最后更新时间: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("指定日期范围内无物流数据")


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


def show_project_selection(df):
    st.markdown("""
    <div class="welcome-header">
        欢迎使用钢筋发货监控系统
    </div>
    <div class="welcome-subheader">
        中铁物贸成都分公司 - 四川物供中心
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="home-card">
            <div class="home-card-icon">🏗️</div>
            <div class="home-card-title">项目监控</div>
            <div class="home-card-content">
                实时监控各项目钢筋发货情况，确保工程进度顺利推进。
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="home-card">
            <div class="home-card-icon">🚚</div>
            <div class="home-card-title">物流跟踪</div>
            <div class="home-card-content">
                跟踪钢材物流状态，及时掌握物资到货情况。
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="project-selector">', unsafe_allow_html=True)

    with st.spinner("加载项目部信息..."):
        logistics_df = load_logistics_data()
        valid_projects = sorted([p for p in logistics_df["项目部"].unique() if p != ""])

    selected = st.selectbox(
        "选择项目部",
        ["中铁物贸成都分公司"] + valid_projects,
        key="project_selector"
    )

    if st.button("确认进入", type="primary"):
        if selected == "中铁物贸成都分公司":
            st.session_state.temp_selected_project = selected
            st.session_state.need_password = True
        else:
            st.session_state.project_selected = True
            st.session_state.selected_project = selected
        st.rerun()

    if st.session_state.get('need_password', False):
        password = st.text_input("请输入密码",
                                 type="password",
                                 key="password_input")
        if st.button("验证密码"):
            if password == "123456":
                st.session_state.project_selected = True
                st.session_state.selected_project = st.session_state.temp_selected_project
                keys_to_remove = ['need_password', 'temp_selected_project']
                for key in keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            else:
                st.error("密码错误，请重新输入")

    st.markdown('</div>', unsafe_allow_html=True)


def show_data_panel(df, project):
    st.title(f"{project} - 发货数据")

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新数据"):
            with st.spinner("刷新数据中..."):
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
            start_date = st.date_input("开始日期", datetime.now() - timedelta(days=0))
        with col2:
            end_date = st.date_input("结束日期", datetime.now())

        if start_date > end_date:
            st.error("日期范围无效")
        else:
            with st.spinner("筛选数据..."):
                filtered_df = df if project == "中铁物贸成都分公司" else df[df[AppConfig.PROJECT_COLUMN] == project]
                date_range_df = filtered_df[
                    (filtered_df["下单时间"].dt.date >= start_date) &
                    (filtered_df["下单时间"].dt.date <= end_date)
                    ]

                if not date_range_df.empty:
                    display_metrics_cards(date_range_df)

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
