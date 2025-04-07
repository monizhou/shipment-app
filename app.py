# -*- coding: utf-8 -*-
"""钢筋发货监控系统（移动端优化版）"""
import os
import io
from datetime import datetime
import pandas as pd
import streamlit as st

# ==================== 系统配置 ====================
class AppConfig:
    # 多路径配置（自动选择可用路径）
    DATA_PATHS = [
        os.path.join(os.path.dirname(__file__), "发货计划.xlsx"),  # 优先使用相对路径
        r"F:\1.中铁物贸成都分公司-四川物供中心\钢材-结算\钢筋发货计划-发丁小刚\发货计划（宜宾项目）汇总.xlsx",
        r"D:\PyCharm\PycharmProjects\project\发货计划.xlsx"
    ]
    DATE_FORMAT = "%Y-%m-%d"
    REQUIRED_COLS = ['标段名称', '下单时间', '需求量']
    BACKUP_COL_MAPPING = {
        '标段名称': ['项目标段', '工程名称', '标段'],
        '需求量': ['需求吨位', '计划量', '数量'],
        '下单时间': ['创建时间', '日期', '录入时间']
    }

# ==================== 样式设置 ====================
def apply_card_styles():
    """应用现代化卡片样式（已优化移动端）"""
    st.markdown("""
    <style>
        /* 基础重置 */
        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        
        /* 主容器设置 */
        .main .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.2rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        
        /* 标题优化 */
        h1 {
            font-size: 1.6rem !important;
            margin-bottom: 0.8rem !important;
        }
        h2 {
            font-size: 1.4rem !important;
            margin-top: 1.2rem !important;
        }
        h3 {
            font-size: 1.2rem !important;
        }

        /* 卡片样式优化 */
        .metric-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.8rem;
            margin: 0.5rem 0 1.2rem 0;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            transition: all 0.2s ease;
            border-left: 4px solid;
            position: relative;
            overflow: hidden;
            height: 100%;
        }
        .metric-card:active {
            transform: scale(0.98);
        }
        .metric-card.total {
            border-color: #3498db;
        }
        .metric-card.shipped {
            border-color: #2ecc71;
        }
        .metric-card.pending {
            border-color: #f39c12;
        }
        .metric-card.overdue {
            border-color: #e74c3c;
        }
        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 0.6rem;
        }
        .card-icon {
            font-size: 1.4rem;
            margin-right: 0.5rem;
        }
        .card-value {
            font-size: 1.6rem;
            font-weight: 700;
            margin: 0.3rem 0;
            line-height: 1.2;
        }
        .card-unit {
            font-size: 0.85rem;
            font-weight: 400;
            margin-left: 0.2rem;
            opacity: 0.8;
        }
        .progress-container {
            margin: 0.6rem 0;
        }
        .progress-bar {
            height: 4px;
            background: #f0f0f0;
            border-radius: 2px;
            margin-top: 0.3rem;
        }
        .progress-fill {
            height: 100%;
            border-radius: 2px;
        }
        .card-footer {
            font-size: 0.75rem;
            color: #7f8c8d;
            margin-top: 0.3rem;
        }

        /* 表格优化 */
        .stDataFrame {
            border-radius: 6px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.05);
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .stDataFrame table {
            font-size: 14px;
            width: 100%;
        }
        .stDataFrame th, .stDataFrame td {
            padding: 0.5rem 0.8rem !important;
        }
        
        /* 预警样式 */
        .warning-board {
            background: #fff8e1;
            border-left: 4px solid #ffc107;
            padding: 0.8rem;
            margin: 1rem 0;
            border-radius: 0 6px 6px 0;
        }
        .warning-board h3 {
            margin: 0 0 0.5rem 0 !important;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* 按钮优化 */
        .stButton>button {
            min-width: 120px;
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
            border-radius: 6px;
        }
        .stDownloadButton>button {
            width: 100%;
        }

        /* 分割线优化 */
        hr {
            margin: 1.2rem 0 !important;
        }

        /* 移动端适配 */
        @media screen and (max-width: 768px) {
            .main .block-container {
                padding: 0.8rem;
            }
            .metric-container {
                grid-template-columns: 1fr;
                gap: 0.6rem;
            }
            .metric-card {
                padding: 0.9rem;
            }
            .card-value {
                font-size: 1.5rem;
            }
            .card-icon {
                font-size: 1.2rem;
            }
            .warning-board {
                padding: 0.7rem;
            }
            .stDataFrame table {
                font-size: 13px;
            }
            h1 {
                font-size: 1.4rem !important;
            }
            h2 {
                font-size: 1.2rem !important;
            }
            h3 {
                font-size: 1.1rem !important;
            }
        }
        
        /* 超小屏幕优化 */
        @media screen and (max-width: 480px) {
            .main .block-container {
                padding: 0.6rem;
            }
            .metric-card {
                padding: 0.8rem;
            }
            .card-value {
                font-size: 1.3rem;
            }
            .card-header {
                margin-bottom: 0.4rem;
            }
            .stDataFrame table {
                font-size: 12px;
            }
        }
    </style>
    """, unsafe_allow_html=True)

# ==================== 数据加载 ====================
def find_data_file():
    """查找可用的数据文件"""
    for path in AppConfig.DATA_PATHS:
        if os.path.exists(path):
            return path
    return None

@st.cache_data
def load_data():
    """加载并验证Excel数据"""
    data_path = find_data_file()
    if not data_path:
        st.error("❌ 未找到数据文件，请检查路径配置")
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
            st.error(f"缺少必要列: {missing_cols}\n现有列: {df.columns.tolist()}")
            return pd.DataFrame()

        # 数据类型转换
        df["下单时间"] = pd.to_datetime(df["下单时间"], errors='coerce').dt.tz_localize(None)
        if "计划进场时间" in df.columns:
            df["计划进场时间"] = pd.to_datetime(df["计划进场时间"], errors='coerce').dt.tz_localize(None)

        # 数值处理
        df["需求量"] = pd.to_numeric(df["需求量"], errors="coerce").fillna(0)
        df["已发量"] = pd.to_numeric(df.get("已发量", 0), errors="coerce").fillna(0)

        # 计算字段
        df["剩余量"] = (df["需求量"] - df["已发量"]).clip(lower=0)
        if "计划进场时间" in df.columns:
            df["超期天数"] = (pd.Timestamp.now().normalize() - df["计划进场时间"]).dt.days.clip(lower=0)
            df["剩余天数"] = (df["计划进场时间"] - pd.Timestamp.now().normalize()).dt.days.clip(lower=0)
        else:
            df["超期天数"] = 0
            df["剩余天数"] = 0

        return df

    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return pd.DataFrame()

# ==================== 卡片显示 ====================
def display_metrics_cards(filtered_df):
    """显示现代化统计卡片（移动端优化）"""
    if not filtered_df.empty:
        try:
            # 计算核心指标
            total_demand = filtered_df["需求量"].sum()
            shipped_quantity = filtered_df["已发量"].sum()
            remaining_quantity = filtered_df["剩余量"].sum()

            # 计算百分比
            shipped_pct = round((shipped_quantity / total_demand * 100), 1) if total_demand > 0 else 0.0
            remaining_pct = min(100 - shipped_pct, 100)

            # 超期订单
            overdue_orders = filtered_df[filtered_df["超期天数"] > 0]
            overdue_count = len(overdue_orders)
            max_overdue = overdue_orders["超期天数"].max() if not overdue_orders.empty else 0
            project_count = overdue_orders["标段名称"].nunique() if not overdue_orders.empty else 0

            # 构建卡片数据
            cards_data = [
                {
                    "type": "total",
                    "icon": "📦",
                    "title": "总需求量",
                    "value": f"{total_demand:,.0f}",
                    "unit": "吨",
                    "progress": 100,
                    "footer": "所有标段总需求",
                    "color": "#3498db"
                },
                {
                    "type": "shipped",
                    "icon": "🚚",
                    "title": "已发货量",
                    "value": f"{shipped_quantity:,.0f}",
                    "unit": "吨",
                    "progress": shipped_pct,
                    "label": f"完成进度 {shipped_pct}%",
                    "color": "#2ecc71"
                },
                {
                    "type": "pending",
                    "icon": "⏳",
                    "title": "待发货量",
                    "value": f"{remaining_quantity:,.0f}",
                    "unit": "吨",
                    "progress": remaining_pct,
                    "label": f"剩余比例 {remaining_pct}%",
                    "color": "#f39c12"
                },
                {
                    "type": "overdue",
                    "icon": "⚠️",
                    "title": "超期订单",
                    "value": overdue_count,
                    "unit": "单",
                    "progress": 100,
                    "label": f"涉及 {project_count} 个标段",
                    "footer": f"最大超期 {max_overdue} 天",
                    "color": "#e74c3c"
                }
            ]

            # 动态生成卡片
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)

            cols = st.columns(4)
            for idx, card in enumerate(cards_data):
                with cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card card-{card['type']}">
                        <div class="card-content">
                            <div class="card-header">
                                <div class="card-icon">{card['icon']}</div>
                                <div style="flex-grow:1">
                                    <div style="font-size:0.95rem;font-weight:600">{card['title']}</div>
                                </div>
                            </div>
                            <div class="card-value">
                                {card['value']}<span class="card-unit">{card['unit']}</span>
                            </div>
                            <div class="progress-container">
                                <div style="font-size:0.8rem;color:#666;">{card.get('label', '')}</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width:{card['progress']}%; background-color:{card['color']}"></div>
                                </div>
                            </div>
                            <div class="card-footer">{card.get('footer', '')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        except Exception as e:
            st.error(f"指标卡片生成错误: {str(e)}")

# ==================== 超期预警 ====================
def show_overdue_warning(df):
    """显示超期订单预警（移动端优化）"""
    overdue_df = df[df["超期天数"] > 0]
    if not overdue_df.empty:
        overdue_count = len(overdue_df)
        max_overdue = overdue_df["超期天数"].max()
        project_count = overdue_df["标段名称"].nunique()

        st.markdown(f"""
        <div class="warning-board">
            <h3>🚨 超期预警 ({overdue_count}单)</h3>
            <div style="display: flex; gap: 1.5rem; margin-top: 0.5rem; flex-wrap: wrap;">
                <div>
                    <div style="font-size: 0.85rem; color: #666;">涉及标段</div>
                    <div style="font-size: 1.1rem; font-weight: bold;">{project_count}个</div>
                </div>
                <div>
                    <div style="font-size: 0.85rem; color: #666;">最大超期</div>
                    <div style="font-size: 1.1rem; font-weight: bold; color: #e74c3c;">{max_overdue}天</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==================== 主页面 ====================
def main():
    # 页面配置 - 添加移动端优化参数
    st.set_page_config(
        layout="wide",
        page_title="钢筋发货监控系统",
        page_icon="🏗️",
        initial_sidebar_state="collapsed",  # 移动端默认收起侧边栏
        menu_items={
            'Get Help': 'https://example.com',
            'About': "# 中铁物贸成都分公司\n钢筋发货监控系统 v3.4"
        }
    )

    # 应用优化后的样式
    apply_card_styles()

    # 添加视口元标签
    st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """, unsafe_allow_html=True)

    # 页面标题 - 优化移动端显示
    st.markdown(f"""
    <div style="color:#2c3e50; padding-bottom:0.3rem; margin-bottom:1rem">
        <h1 style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.3rem;">
            <span>🏗️</span>
            <span>钢筋发货监控系统</span>
        </h1>
        <div style="color:#7f8c8d; font-size:0.85rem">
            更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 加载数据
    df = load_data()
    if df.empty:
        st.error("""
        ❌ 数据加载失败，可能原因：
        1. 文件路径不正确
        2. Excel文件格式不正确
        3. 缺少必要列（标段名称、下单时间、需求量）
        """)
        return

    # 只筛选今日数据
    today = datetime.now().date()
    filtered_df = df[df["下单时间"].dt.date == today]

    # 显示统计卡片
    display_metrics_cards(filtered_df)

    # 显示超期预警
    show_overdue_warning(filtered_df)

    # 数据表格展示
    if not filtered_df.empty:
        st.subheader("📋 发货明细", divider="gray")

        # 定义显示列及格式
        display_cols = {
            "标段名称": "工程标段",
            "物资名称": "材料名称",
            "规格型号": "规格型号",
            "需求量": "需求(吨)",
            "已发量": "已发(吨)",
            "剩余量": "待发(吨)",
            "计划进场时间": "计划进场",
            "超期天数": "超期天数",
            "剩余天数": "剩余天数",
            "收货人": "收货人",
            "收货人电话": "联系电话",
            "收货地址": "收货地址"
        }

        # 只保留存在的列
        available_cols = {k: v for k, v in display_cols.items() if k in filtered_df.columns}
        display_df = filtered_df[available_cols.keys()].rename(columns=available_cols)

        # 格式化显示
        if "计划进场" in display_df.columns:
            display_df["计划进场"] = pd.to_datetime(display_df["计划进场"]).dt.strftime(AppConfig.DATE_FORMAT)
        if "联系电话" in display_df.columns:
            display_df["联系电话"] = display_df["联系电话"].astype(str).str.replace(r'\.0$', '', regex=True)

        # 配置自动列
        column_config = {
            "需求(吨)": st.column_config.NumberColumn(format="%.1f 吨"),
            "已发(吨)": st.column_config.NumberColumn(format="%.1f 吨"),
            "待发(吨)": st.column_config.NumberColumn(format="%.1f 吨"),
            "超期天数": st.column_config.NumberColumn(
                format="%d 天",
                help="计划进场时间已过期的天数"
            ),
            "剩余天数": st.column_config.NumberColumn(
                format="%d 天",
                help="距离计划进场时间剩余天数"
            )
        }

        # 高亮超期行
        def highlight_overdue(row):
            if "超期天数" in row.index and row["超期天数"] > 0:
                return ['background-color: #fff3e0'] * len(row)
            return [''] * len(row)

        # 使用容器包装表格确保移动端可滚动
        with st.container():
            st.dataframe(
                display_df.style.apply(highlight_overdue, axis=1),
                use_container_width=True,
                height=500,
                column_config=column_config,
                hide_index=True
            )

        # 添加导出按钮
        st.divider()
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("📥 导出当前数据", use_container_width=True):
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    filtered_df.to_excel(writer, index=False)
                st.download_button(
                    label="⬇️ 下载Excel文件",
                    data=buffer.getvalue(),
                    file_name=f"今日发货数据_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    else:
        st.info("今日没有发货记录")

# ==================== 程序入口 ====================
if __name__ == "__main__":
    # Windows系统中文路径兼容处理
    if os.name == 'nt':
        os.system('chcp 65001 > nul')

    main()
