# -*- coding: utf-8 -*-
"""钢筋发货监控系统（保留汇总统计版）"""
import os
import io
import hashlib
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


# ==================== 自动更新逻辑 ====================
def get_file_hash(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def check_file_update():
    data_path = find_data_file()
    if not data_path:
        return False

    current_hash = get_file_hash(data_path)
    if 'file_hash' not in st.session_state:
        st.session_state.file_hash = current_hash

    if current_hash != st.session_state.file_hash:
        st.session_state.file_hash = current_hash
        st.cache_data.clear()
        return True
    return False


# ==================== 样式设置 ====================
def apply_card_styles():
    st.markdown("""
    <style>
        .metric-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid;
            text-decoration: none; /* 防止链接下划线 */
            color: inherit;
        }
        .metric-card.total { border-color: #3498db; }
        .metric-card.shipped { border-color: #2ecc71; }
        .metric-card.pending { border-color: #f39c12; }
        .metric-card.overdue { border-color: #e74c3c; }
        .card-value {
            font-size: 1.8rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }
        .card-unit {
            font-size: 1rem;
            opacity: 0.8;
        }
    </style>
    """, unsafe_allow_html=True)


# ==================== 数据加载 ====================
def find_data_file():
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None


@st.cache_data(ttl=10)
def load_data():
    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件")
        return pd.DataFrame()

    try:
        df = pd.read_excel(data_path, engine='openpyxl')
        st.session_state['data_path'] = data_path

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
        df["需求量"] = pd.to_numeric(df["需求量"], errors="coerce").fillna(0)
        df["已发量"] = pd.to_numeric(df.get("已发量", 0), errors="coerce").fillna(0)
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0)

        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)
            df["超期天数"] = (pd.Timestamp.now().normalize() - df["计划进场时间"]).dt.days.clip(lower=0)
        else:
            df["超期天数"] = 0

        return df
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()


# ==================== 显示组件 ====================
def display_metrics_cards(filtered_df):
    if filtered_df.empty:
        return

    try:
        total_demand = filtered_df["需求量"].sum()
        shipped_quantity = filtered_df["已发量"].sum()
        remaining_quantity = filtered_df["剩余量"].sum()

        overdue_orders = filtered_df[filtered_df["超期天数"] > 0]
        overdue_count = len(overdue_orders)
        max_overdue = overdue_orders["超期天数"].max() if not overdue_orders.empty else 0

        # 四张卡片：总需求量、已发货量、待发货量、超期订单
        cards_data = [
            {"type": "total", "icon": "📦", "title": "总需求量", "value": f"{total_demand:,.0f}", "unit": "吨",
             "color": "#3498db"},
            {"type": "shipped", "icon": "🚚", "title": "已发货量", "value": f"{shipped_quantity:,.0f}", "unit": "吨",
             "color": "#2ecc71"},
            {"type": "pending", "icon": "⏳", "title": "待发货量", "value": f"{remaining_quantity:,.0f}", "unit": "吨",
             "color": "#f39c12"},
            {"type": "overdue", "icon": "⚠️", "title": "超期订单", "value": overdue_count, "unit": "单",
             "color": "#ff0000"}  # 改为红色
        ]

        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        cols = st.columns(4)
        for idx, card in enumerate(cards_data):
            with cols[idx]:
                # 添加超期订单跳转链接
                if card['type'] == 'overdue':
                    st.markdown(
                        f'<a href="?show_overdue=true" style="text-decoration: none; display: block; color: inherit;">',
                        unsafe_allow_html=True
                    )

                st.markdown(f"""
                <div class="metric-card {card['type']}">
                    <div class="card-header">
                        <span style="font-size:1.5rem">{card['icon']}</span>
                        <span style="font-weight:600">{card['title']}</span>
                    </div>
                    <div class="card-value">
                        {card['value']}<span class="card-unit">{card['unit']}</span>
                    </div>
                    {f'<div style="font-size:0.8rem">最大超期: {max_overdue}天</div>' if card['type'] == 'overdue' else ''}
                </div>
                """, unsafe_allow_html=True)

                if card['type'] == 'overdue':
                    st.markdown('</a>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"指标卡片生成错误: {str(e)}")


# ==================== 主页面 ====================
def main():
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="collapsed"
    )

    apply_card_styles()
    st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1.0">', unsafe_allow_html=True)

    # 直接使用 st.query_params（关键修复点）
    params = st.query_params
    show_overdue = params.get('show_overdue', ['false'])[0].lower() == 'true'

    # 标题栏
    update_status = "🔄 检测到新数据" if check_file_update() else ""
    st.markdown(f"""
    <div style="margin-bottom:1.5rem">
        <h1 style="display:flex; align-items:center; gap:0.5rem;">
            <span>🏗️</span>
            <span>钢筋发货监控系统</span>
        </h1>
        <div style="color:#666; font-size:0.9rem">
            {datetime.now().strftime('%Y-%m-%d %H:%M')} {update_status}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 手动刷新按钮
    if st.button("🔄 手动刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.experimental_rerun()

    # 数据加载
    df = load_data()
    if df.empty:
        return

    # 根据参数选择显示数据
    if show_overdue:
        # 显示超期订单详细数据
        overdue_df = df[df["超期天数"] > 0]
        if not overdue_df.empty:
            st.subheader("超期订单详细信息", divider="gray")
            display_cols = {
                "标段名称": "工程标段",
                "物资名称": "材料名称",
                "需求量": "需求(吨)",
                "已发量": "已发(吨)",
                "剩余量": "待发(吨)",
                "超期天数": "超期天数",
                "计划进场时间": "计划进场",
                "收货人": "收货人",
                "收货人电话": "电话",
                "收货地址": "收货地址"
            }
            available_cols = {k: v for k, v in display_cols.items() if k in overdue_df.columns}
            display_df = overdue_df[available_cols.keys()].rename(columns=available_cols)

            if "计划进场" in display_df.columns:
                display_df["计划进场"] = pd.to_datetime(display_df["计划进场"]).dt.strftime(AppConfig.DATE_FORMAT)

            # 高亮超期行
            def highlight_overdue(row):
                return ['background-color: #fff3e0'] * len(row) if row["超期天数"] > 0 else [''] * len(row)

            st.dataframe(
                display_df.style.apply(highlight_overdue, axis=1),
                use_container_width=True,
                height=500,
                hide_index=True
            )
        else:
            st.write("暂无超期订单")

        # 返回按钮（关键修复点：直接设置参数并强制刷新）
        if st.button("返回"):
            st.query_params = {}  # 清除参数
            st.experimental_rerun()  # 强制刷新

    else:
        # 原始逻辑：显示今日数据
        today = datetime.now().date()
        filtered_df = df[df["下单时间"].dt.date == today]

        # 显示统计卡片
        display_metrics_cards(filtered_df)

        # 数据表格
        if not filtered_df.empty:
            st.subheader("📋 发货明细", divider="gray")

            display_cols = {
                "标段名称": "工程标段",
                "物资名称": "材料名称",
                "规格型号": "规格型号",
                "需求量": "需求(吨)",
                "已发量": "已发(吨)",
                "剩余量": "待发(吨)",
                "计划进场时间": "计划进场",
                "超期天数": "超期天数",
                "收货人": "收货人",
                "收货人电话": "电话",
                "收货地址": "收货地址"
            }

            available_cols = {k: v for k, v in display_cols.items() if k in filtered_df.columns}
            display_df = filtered_df[available_cols.keys()].rename(columns=available_cols)

            if "计划进场" in display_df.columns:
                display_df["计划进场"] = pd.to_datetime(display_df["计划进场"]).dt.strftime(AppConfig.DATE_FORMAT)

            # 高亮超期行
            def highlight_overdue(row):
                if "超期天数" in row.index and row["超期天数"] > 0:
                    return ['background-color: #fff3e0'] * len(row)
                return [''] * len(row)

            st.dataframe(
                display_df.style.apply(highlight_overdue, axis=1),
                use_container_width=True,
                height=500,
                hide_index=True
            )

            # 数据导出
            st.divider()
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False)
            st.download_button(
                label="⬇️ 导出Excel数据",
                data=buffer.getvalue(),
                file_name=f"发货数据_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("今日没有发货记录")


if __name__ == "__main__":
    if os.name == 'nt':
        os.system('chcp 65001 > nul')
    main()
