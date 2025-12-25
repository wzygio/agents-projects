# 文件路径：packages/anomaly_monitor/src/interface/hl_app.py
import streamlit as st
import pandas as pd
import logging
import sys
from pathlib import Path

# --- 1. 初始化系统环境 ---
from application.hl_report_service import HLReportService
from packages.common_utils.src.infrastructure.app_setup import AppSetup
from packages.anomaly_monitor.src.interface.view_models.hl_dashboard_vm import MWDL_COLUMN_MAPPING, COLUMN_CONFIG, prepare_display_data

# 使用 cache_resource 避免重复初始化
@st.cache_resource
def init_system():
    AppSetup.initialize_app("hl_dashboard.log")
init_system()

logger = logging.getLogger(__name__)

# --- 3. 主程序 ---
def render_dashboard(service: HLReportService):
    # ====================================================
    #                   1. 初始化
    # ====================================================
    """
    渲染异常监控仪表盘的主入口函数。
    :param service: 可选，依赖注入 Service。如果为 None，则尝试内部初始化。
    """
    st.markdown("## 🛡️ OLED 良率异常监控台")
    # 获取服务对象
    if service is None:
        service = _init_service_internal()
    
    if not service or service.df_hl is None:
        st.warning("数据未加载")
        return

    # st.write("🔍 当前可用字段:", service.df_hl.columns.tolist())

    # [新增] 自动执行判定 (如果还没判定过)
    if 'is_real_anomaly' not in service.df_hl.columns:
        with st.spinner("🤖 AI 正在逐行分析异常真实性..."):
            service.run_batch_anomaly_detection()

    # ====================================================
    #                   2. 数据过滤
    # ====================================================
    # 2.1 侧边栏过滤器
    st.sidebar.title("📊 过滤器")

    # [修改] 拆分为两个独立的筛选器，控制粒度更细
    filter_mode = st.sidebar.radio(
        "🤖 异常筛选模式",
        options=["全部显示", "仅看真实异常 (CT)", "仅看当站超规"],
        index=0 # 默认为全部显示，或者您可以改为 1
    )
    
    # 1. 基础过滤
    show_worsening = st.sidebar.checkbox("只看恶化 (Gap > 0)", value=True)
    
    # 2. 产品筛选
    # 获取所有唯一产品并排序
    all_prods = ["全部"] + sorted(service.df_hl['prod_code'].astype(str).unique().tolist())
    sel_prod = st.sidebar.selectbox("产品型号", all_prods)

    # 3. 🔍 新增：站点筛选
    # 获取所有唯一站点并排序
    all_stations = ["全部"] + sorted(service.df_hl['oper_group'].astype(str).unique().tolist())
    sel_station = st.sidebar.selectbox("发生站点", all_stations)
    
    # 2.2 应用数据过滤与排序
    df_view = service.df_hl.copy()
    
    # A. 应用过滤
    if show_worsening and 'batch_gap' in df_view.columns:
        df_view = df_view[df_view['batch_gap'] > 0]
        
    if sel_prod != "全部":
        df_view = df_view[df_view['prod_code'] == sel_prod]
        
    if sel_station != "全部":
        df_view = df_view[df_view['oper_group'] == sel_station]
    
    # 应用真实性过滤
    if filter_mode == "仅看真实异常 (CT)":
        if 'anomaly_type' in df_view.columns:
            df_view = df_view[df_view['anomaly_type'] == '真实异常']
            
    elif filter_mode == "仅看当站超规":
        if 'anomaly_type' in df_view.columns:
            df_view = df_view[df_view['anomaly_type'] == '当站超规']

    # B. 🔍 核心逻辑：自定义层级排序
    # 需求：产品(升序) -> 不良(升序) -> 站点(CT置顶)
    if not df_view.empty:
        # 1. 创建辅助列：如果是 CT 赋值 0，其他赋值 1；使用 upper() 确保大小写不敏感
        df_view['_station_rank'] = df_view['oper_group'].astype(str).apply(
            lambda x: 0 if x.upper().strip() == 'CT' else 1
        )
        
        # 2. 执行排序：优先级: 产品 -> 不良 -> 站点权重 -> 恶化程度(作为最后的Tie-breaker，可选)
        sort_cols = ['prod_code', 'defect_desc', '_station_rank', 'batch_gap']
        ascending_order = [True, True, True, False] # 产品升, 不良升, 权重升(0在1前), Gap降
        
        # 容错: 确保列存在
        valid_sort_cols = []
        valid_asc = []
        for col, asc in zip(sort_cols, ascending_order):
            if col in df_view.columns:
                valid_sort_cols.append(col)
                valid_asc.append(asc)
        
        df_view = df_view.sort_values(by=valid_sort_cols, ascending=valid_asc)
        
        # 3. 删除辅助列 (不展示给用户)
        df_view = df_view.drop(columns=['_station_rank'])

    # ====================================================
    #                   3. 数据展示
    # ====================================================
    # 准备展示数据
    df_display = prepare_display_data(df_view)

    # [核心修改 1] 从表格配置中移除 "generated_report"，保持表格清爽
    current_col_config = COLUMN_CONFIG.copy()
    
    if "✅" in df_display.columns and "异常类型" in df_display.columns:
        # 使用 Pandas 的布尔索引进行批量赋值
        # 将 '异常类型' 为 '真实异常' 的行，其 '✅' 列设为 True
        mask_real = df_display["异常类型"] == "真实异常"
        df_display.loc[mask_real, "✅"] = True
        
        # 调试日志
        auto_checked_count = mask_real.sum()
        if auto_checked_count > 0:
            logger.info(f"⚡ 已自动勾选 {auto_checked_count} 条真实异常")

    # [可选优化] 如果表格数据太多，自动勾选后可能想把它们排到最前面？
    df_display = df_display.sort_values(by=["✅"], ascending=False)

    st.subheader("🛡️ 异常监控列表 (Spotfire 视图)")
    
    # 渲染表格 (主表只负责勾选)
    edited_df = st.data_editor(
        df_display,
        column_config=current_col_config,
        hide_index=True,
        use_container_width=True,
        height=600,
        # 禁用除勾选框以外的所有列编辑
        disabled=df_display.columns.drop("✅") 
    )

    # 获取勾选行
    selected_rows = edited_df[edited_df["✅"] == True]
    
    if len(selected_rows) == 1:
        st.divider()
        st.subheader("📈 批次月周天数据 (历史趋势)")
        
        # 获取选中行的 key info
        idx = selected_rows.index[0]
        row_data = service.df_hl.loc[idx]
        prod = row_data['prod_code']
        defect = row_data['defect_desc']
        
        st.caption(f"当前分析对象: {prod} - {defect}")
        
        # 调用 Service 查询历史
        df_history = service.get_history_by_prod_defect(prod, defect)
        
        if not df_history.empty:
            # 适配器：重命名和筛选列
            cols_show = [c for c in MWDL_COLUMN_MAPPING.keys() if c in df_history.columns]
            df_hist_display = df_history[cols_show].rename(columns=MWDL_COLUMN_MAPPING)
            
            # === 🔍 新增：MWDL 百分比修正 ===
            mwdl_pct_cols = ["ratio_fanel", "lot_input_ratio"]
            for col in mwdl_pct_cols:
                if col in df_hist_display.columns:
                     # 确保是数字
                     df_hist_display[col] = pd.to_numeric(df_hist_display[col], errors='coerce').fillna(0)
                     # 乘以 100
                     df_hist_display[col] = df_hist_display[col] * 100

            # 配置显示的列格式
            hist_config = {
                "ratio_fanel": st.column_config.NumberColumn("ratio_fanel", format="%.2f%%"),
                "lot_input_ratio": st.column_config.NumberColumn("lot_input_ratio", format="%.1f%%"),
                "ng_qty": st.column_config.NumberColumn("ng_qty", format="%d"),
                "input_qty": st.column_config.NumberColumn("input_qty", format="%d"),
            }
            
            st.dataframe(
                df_hist_display, 
                column_config=hist_config, 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("暂无该不良的历史批次数据。")
            
    elif len(selected_rows) > 1:
        st.info("💡 请仅勾选 1 行以查看其详细历史趋势。")
    
    # ====================================================
    #             4. 报告生成与写入区域 (核心重构)
    # ====================================================
    
    if not selected_rows.empty:
        st.divider()
        st.subheader("📝 异常通报与台账录入")
        
        # 使用 Session State 管理编辑后的文本，防止重绘丢失
        if "report_drafts" not in st.session_state:
            st.session_state["report_drafts"] = {}

        # 布局：左边是操作按钮，右边或者是下方是编辑器
        # 这里我们采用“逐个展示编辑器”的模式
        
        # 收集待提交的数据
        data_to_commit = [] 
        
        # 遍历选中的每一行
        for idx in selected_rows.index:
            try:
                # 1. 回溯到原始 df_hl 获取完整信息
                # 注意：这里务必使用 .loc[idx]，因为 idx 是原始索引
                raw_row = service.df_hl.loc[idx]
                
                prod = raw_row.get('prod_code')
                defect = raw_row.get('defect_desc')
                station = raw_row.get('oper_group')
                
                # 2. 获取 AI 预生成的草稿
                # get() 方法第二个参数是默认值，如果字段不存在则返回 ''
                ai_draft = raw_row.get('generated_report', '')
                
                # 3. [核心修复] 兜底生成逻辑 (含孪生站点查找)
                if not ai_draft or pd.isna(ai_draft) or str(ai_draft).strip() == "":
                    ai_draft = service.generator.generate_text( # type: ignore
                        raw_row, 
                        full_df=service.df_hl # 👈 关键：复用 Service 中的全量数据
                    )
                    
                # 4. 标题展示
                header_text = f"📄 {prod} - {defect} ({station})"
                
                with st.expander(header_text, expanded=True):
                    # 5. 文本编辑器
                    text_key = f"rpt_edit_{idx}"
                    
                    # 优先使用用户刚才编辑过的缓存，没有则使用 ai_draft (无论是预生成的还是现生成的)
                    default_text = st.session_state["report_drafts"].get(text_key, ai_draft)
                    
                    user_text = st.text_area(
                        "通报内容 (可编辑)", 
                        value=default_text, 
                        height=250, 
                        key=text_key
                    )
                    
                    # 更新缓存
                    st.session_state["report_drafts"][text_key] = user_text
                    
                    # 准备提交数据
                    record = raw_row.to_dict()
                    record['generated_report'] = user_text 
                    data_to_commit.append(record)

            except Exception as e:
                st.error(f"处理行 {idx} 时发生错误: {e}")
                logger.error(f"UI Error processing row {idx}: {e}", exc_info=True)

        # --- 提交按钮区域 ---
        st.write("") # Spacer
        col_submit, col_info = st.columns([1, 4])
        
        with col_submit:
            if st.button("💾 确认并写入台账", type="primary", use_container_width=True):
                if not data_to_commit:
                    st.warning("没有数据可写入")
                else:
                    with st.spinner(f"正在写入 {len(data_to_commit)} 条数据到 Excel..."):
                        # 将 list[dict] 转回 DataFrame 传给 Service
                        df_commit = pd.DataFrame(data_to_commit)
                        
                        # 调用 Service
                        success, msg = service.commit_reports_to_ledger(df_commit)
                        
                        if success:
                            st.balloons()
                            st.success(msg)
                            # 可选：写入成功后清空勾选？这需要重置 key，比较复杂，暂不处理
                        else:
                            st.error(msg)
                            
        with col_info:
            st.caption(f"共选中 {len(data_to_commit)} 条。点击按钮后，上述文本将写入 HL 台账 Excel。")

@st.cache_resource
def _init_service_internal():
    service = HLReportService()
    try:
        service.load_resources()
        return service
    except Exception as e:
        st.error(f"Service Init Failed: {e}")
        return None