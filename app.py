# -*- coding: utf-8 -*-
"""钢筋发货监控系统（中铁总部视图版）- 物流明细优化版"""
import os
import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import requests  # 用于飞书Webhook通知


# ==================== 系统配置 ====================
class AppConfig:
    # 原有发货计划数据路径
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划（宜宾项目）汇总.xlsx"),
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划（宜宾项目）汇总.xlsx"
    ]

    # 物流明细配置
    LOGISTICS_SHEET_NAME = "物流明细"  # 物流明细所在的工作表名称
    LOGISTICS_COLUMNS = [
        "钢厂", "物资名称", "规格型号", "单位", "数量",
        "交货时间", "交货地点", "联系人", "联系方式", "项目部",
        "到货状态", "发货状态", "备注"
    ]

    # 原有配置
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }

    # 飞书Webhook配置
    WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/dcf16af3-78d2-433f-9c3d-b4cd108c7b60"


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
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 16px;
            border-radius: 4px 4px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #f0f2f6;
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
    """加载并处理发货计划数据（增强数据兼容性处理）"""

    def safe_convert_to_numeric(series, default=0):
        """安全转换为数值类型"""
        str_series = series.astype(str)
        cleaned = str_series.str.replace(r'[^\d.-]', '', regex=True)
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'None': '0'})
        return pd.to_numeric(cleaned, errors='coerce').fillna(default)

    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到发货计划数据文件")
        st.markdown(f"**尝试查找的路径：**")
        for path in AppConfig.DATA_PATHS:
            st.markdown(f"- `{path}`")
        return pd.DataFrame()

    try:
        # 读取原始数据
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

        # 数据处理
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        df = df[~df["下单时间"].isna()]  # 过滤无效日期记录

        # 数值转换
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

        return df
    except Exception as e:
        st.error(f"发货计划数据加载失败: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=10)
def load_logistics_data():
    """从同一Excel文件的'物流明细'工作表加载数据"""
    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)

    try:
        # 读取物流明细工作表
        df = pd.read_excel(
            data_path,
            sheet_name=AppConfig.LOGISTICS_SHEET_NAME,
            engine='openpyxl'
        )

        # 标准化列名
        if not df.empty:
            # 确保所有必要列都存在
            for col in AppConfig.LOGISTICS_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col != "数量" else 0

            # 数据清洗
            df["数量"] = pd.to_numeric(df["数量"], errors="coerce").fillna(0)
            df["交货时间"] = pd.to_datetime(df["交货时间"], errors="coerce")

            # 如果项目部列不存在，设置为空
            if "项目部" not in df.columns:
                df["项目部"] = ""

            return df
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)
    except Exception as e:
        st.error(f"物流明细数据加载失败: {str(e)}")
        return pd.DataFrame(columns=AppConfig.LOGISTICS_COLUMNS)


def save_logistics_data(df):
    """保存物流明细数据到原Excel文件"""
    data_path = find_data_file()
    if not data_path:
        st.error("无法保存，未找到数据文件")
        return False

    try:
        # 读取整个Excel文件
        with pd.ExcelWriter(data_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            # 保存物流明细数据
            df.to_excel(
                writer,
                sheet_name=AppConfig.LOGISTICS_SHEET_NAME,
                index=False
            )

        # 检查未到货记录并发送通知
        overdue_records = df[(df["到货状态"] == "未到货") & (df["发货状态"] == "已发货")]
        if not overdue_records.empty:
            message = "⚠️ 有以下未到货的发货记录:\n"
            for _, row in overdue_records.iterrows():
                message += (
                    f"物资: {row['物资名称']} ({row['规格型号']}), "
                    f"数量: {row['数量']}吨, "
                    f"交货时间: {row['交货时间'].strftime('%Y-%m-%d') if pd.notna(row['交货时间']) else '未指定'}, "
                    f"项目部: {row['项目部']}\n"
                )
            send_feishu_notification(message)

        return True
    except Exception as e:
        st.error(f"物流明细数据保存失败: {str(e)}")
        return False


def send_feishu_notification(message):
    """发送飞书通知"""
    try:
        payload = {
            "msg_type": "text",
            "content": {"text": message}
        }
        requests.post(AppConfig.WEBHOOK_URL, json=payload)
    except Exception as e:
        st.error(f"飞书通知发送失败: {str(e)}")


# ==================== 页面组件 ====================
def show_project_selection(df):
    """显示项目部选择界面"""
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


def show_logistics_tab(project):
    """显示物流明细功能"""
    st.subheader("🚛 钢材物流明细管理")

    # 加载现有数据
    logistics_df = load_logistics_data()

    # 确保联系方式列是字符串类型
    if "联系方式" in logistics_df.columns:
        logistics_df["联系方式"] = logistics_df["联系方式"].astype(str)

    # 如果是项目部视图，只显示该部门数据
    if project != "中铁物贸成都分公司":
        logistics_df = logistics_df[logistics_df["项目部"] == project]

    # 创建显示用的DataFrame（不包含发货状态和备注）
    display_columns = [col for col in logistics_df.columns if col not in ["发货状态", "备注"]]
    display_df = logistics_df[display_columns].copy()

    # 显示现有数据
    if not display_df.empty:
        # 创建列配置
        column_config = {
            col: st.column_config.Column(disabled=True)
            for col in display_df.columns
            if col != "到货状态"
        }

        # 到货状态列配置
        column_config["到货状态"] = st.column_config.SelectboxColumn(
            options=["已到货", "未到货"],
            width="medium"
        )

        # 显示数据编辑器（仅到货状态可编辑）
        edited_display_df = st.data_editor(
            display_df,
            use_container_width=True,
            column_config=column_config,
            key="logistics_editor"
        )

        # 保存修改
        if st.button("💾 保存修改", type="primary"):
            try:
                # 创建完整的数据副本用于保存
                saved_df = logistics_df.copy()

                # 更新到货状态
                if "到货状态" in edited_display_df.columns:
                    saved_df["到货状态"] = edited_display_df["到货状态"]

                    # 检查是否有到货状态被改为"未到货"的记录
                    new_not_arrived = edited_display_df[
                        (edited_display_df["到货状态"] == "未到货") &
                        ((display_df["到货状态"] != "未到货") | (display_df["到货状态"].isna()))
                        ]

                    # 发送飞书通知
                    if not new_not_arrived.empty:
                        message = "⚠️ 有以下物资被标记为未到货:\n\n"
                        for idx, row in new_not_arrived.iterrows():
                            message += (
                                f"**物资名称**: {row['物资名称']} ({row.get('规格型号', '')})\n"
                                f"**数量**: {row.get('数量', 0)}吨\n"
                                f"**钢厂**: {row.get('钢厂', '')}\n"
                                f"**交货时间**: {row['交货时间'].strftime('%Y-%m-%d') if pd.notna(row.get('交货时间')) else '未指定'}\n"
                                f"**项目部**: {row.get('项目部', '')}\n\n"
                            )
                        send_feishu_notification(message)

                # 尝试以只读模式打开文件检查权限
                with open(find_data_file(), 'rb'):
                    pass

                # 确保联系方式列是字符串类型
                saved_df["联系方式"] = saved_df["联系方式"].astype(str)

                if save_logistics_data(saved_df):
                    st.success("物流明细数据已保存！")
                    st.rerun()

            except PermissionError:
                st.error("无法保存文件，请关闭Excel文件后重试")
            except Exception as e:
                st.error(f"物流明细数据保存失败: {str(e)}")
    else:
        st.info("暂无物流明细数据")


def show_data_panel(df, project):
    """显示数据面板（新增物流明细标签页）"""
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

    # 使用标签页组织功能
    tab1, tab2 = st.tabs(["📋 发货计划", "🚛 物流明细"])

    with tab1:
        # 原有发货计划功能
        # 日期范围选择
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "开始日期",
                value=datetime.now() - timedelta(days=0),
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
        else:
            # 数据筛选
            filtered_df = df if project == "中铁物贸成都分公司" else df[df["项目部名称"] == project]
            date_range_df = filtered_df[
                (filtered_df["下单时间"].dt.date >= start_date) &
                (filtered_df["下单时间"].dt.date <= end_date)
                ]

            if not date_range_df.empty:
                display_metrics_cards(date_range_df)

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

    with tab2:
        # 新增物流明细功能
        show_logistics_tab(project)


# ==================== 主程序 ====================
def main():
    # 初始化页面配置
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
        st.session_state.selected_project = "中铁物贸成都分公司"

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
