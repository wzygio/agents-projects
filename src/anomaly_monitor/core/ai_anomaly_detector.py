import os
import pandas as pd
import logging
from pydantic import BaseModel, Field
from typing import List

# CrewAI 核心组件
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

# 引入之前的集中性分析器
from .concentration_analyzer import ConcentrationAnalyzer

logger = logging.getLogger(__name__)

# --- 定义最终输出结构 ---
class AnomalyVerdict(BaseModel):
    is_real: bool = Field(description="最终判定结果：是否为需要关注的异常")
    anomaly_type: str = Field(description="异常分类：'真实异常'(CT站点)、'当站超规'(非CT站点) 或 ''(空字符串)")
    reasons: List[str] = Field(description="最终判定的关键理由列表")
    analysis_summary: str = Field(description="委员会的综合分析摘要")

class AIAnomalyDetector:
    """
    【AI 评审委员会】基于 CrewAI 多智能体协同的判定系统
    """

    def __init__(self, df_yield_detail: pd.DataFrame):
        self.concentrator = ConcentrationAnalyzer(df_yield_detail)
        
        # 配置 LLM (阿里 Qwen)
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        self.llm = ChatOpenAI(
            model="qwen-plus", # 建议用 qwen-max 以获得更好的逻辑推理能力
            openai_api_key=api_key, # type: ignore
            openai_api_base=base_url, # type: ignore
            temperature=0.1
        )

    def _prepare_data_brief(self, row: pd.Series, df_history: pd.DataFrame) -> str:
        """准备数据简报 (Context)"""
        # ... (此处代码与之前相同，计算 batch_ratio, hist_max, conc_text 等) ...
        # 为了节省篇幅，沿用上一版的 _prepare_context 逻辑，计算出 context 字符串
        # [这里请直接复制上一版 _prepare_context 的代码内容]
        
        # --- 简略版实现 (请替换为您之前的完整逻辑) ---
        prod = str(row.get('prod_code'))
        defect = str(row.get('defect_desc'))
        station = str(row.get('oper_group')).upper()
        batch_ratio = float(row.get('batch_ratio', 0))
        lot_input_ratio = float(row.get('lot_input_ratio', 0))
        multiplier = float(row.get('multiplier', 0))
        ng_qty = int(float(row.get('ng_qty', 0)))
        
        hist_max_ct = 0.0
        if not df_history.empty:
            # 简化逻辑：获取 CT 历史 max
            pass # (实际代码请保留之前的计算逻辑)

        # 调用集中性分析
        batch = str(row.get('batch', ''))
        conc_text = self.concentrator.analyze(prod, defect, batch)

        context = f"""
        【基本信息】产品:{prod}, 不良:{defect}, 站点:{station}
        【当前指标】良损:{batch_ratio:.2%}, 产出率:{lot_input_ratio:.1%}, 倍数:{multiplier:.2%}, 数量:{ng_qty}
        【判定门槛】良损>0.1%, 产出率>20%, 倍数>30%, 数量>20
        【历史水位】CT历史最高良损: {hist_max_ct:.2%} (当前是否超过: {'是' if batch_ratio > hist_max_ct else '否'})
        【集中性】分析结果: "{conc_text}" (是否存在集中性: {'否' if '无明显集中性' in conc_text else '是'})
        """
        return context

    def check_is_real_anomaly(self, row: pd.Series, df_history: pd.DataFrame) -> dict:
        """
        启动 CrewAI 多智能体工作流
        """
        data_context = self._prepare_data_brief(row, df_history)

        # =================================================================
        # 1. 定义 Agents (角色)
        # =================================================================
        
        # 角色A: 门槛审核员 (Executor - 严格执行规则)
        screener_agent = Agent(
            role='数据门槛审核员',
            goal='检查数据是否满足基础的报警门槛',
            backstory='你是一名一丝不苟的数据质检员。你只关心数字是否达标，绝不通融。如果基础指标太低，你会建议直接忽略。',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

        # 角色B: 异常侦探 (Analyzer - 寻找定性证据)
        detective_agent = Agent(
            role='异常分析侦探',
            goal='判断是否发生了实质性的恶化',
            backstory='你是一名经验丰富的侦探。你负责寻找两个证据：1.是否突破了历史最高水位？2.是否有明显的集中性爆发？只要满足其中任何一条，你就认为事态严重。',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

        # 角色C: 首席工程师 (Judge - 最终拍板)
        chief_agent = Agent(
            role='首席工艺工程师',
            goal='综合下属报告，给出最终定性和分类',
            backstory='你是部门的技术权威。你汇总审核员和侦探的结论。如果审核员说不达标，直接否决。如果审核员通过且侦探发现了问题，判定为真。你会根据站点(CT/非CT)给异常打上准确的标签。',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

        # =================================================================
        # 2. 定义 Tasks (任务链)
        # =================================================================

        # 任务1: 门槛初筛
        task_screen = Task(
            description=f"""
            分析以下数据概览：
            {data_context}
            
            检查【判定门槛】：
            1. 本批次良损 > 0.1% ?
            2. 批次产出率 > 20% ?
            3. 倍数 > 30% ?
            4. 不良数量 > 20 ?
            
            所有4个条件必须同时满足。告诉下一个Agent你的检查结果（通过/不通过）。
            """,
            agent=screener_agent,
            expected_output="一份简短的检查报告，说明基础门槛是否全部通过。"
        )

        # 任务2: 深度研判
        task_analyze = Task(
            description="""
            阅读“数据门槛审核员”的报告。如果门槛没过，直接停止分析。
            如果门槛通过，请检查【定性条件】：
            A. 是否超过了 CT历史最高良损？
            B. 集中性分析结果是否显示有集中性（即不是“无明显集中性”）？
            
            逻辑：条件A 和 条件B 只要满足任意一个，就视为有异常风险。
            """,
            agent=detective_agent,
            expected_output="一份分析报告，明确指出是否满足恶化条件（历史超标或集中性），并列出证据。"
        )

        # 任务3: 最终裁决
        task_verdict = Task(
            description=f"""
            作为首席工程师，根据前两位的报告做最终决定。
            
            判定逻辑：
            1. 如果【门槛审核】未通过 -> 判定为假 (is_real=False).
            2. 如果【门槛审核】通过，但【深度研判】未发现任何风险 -> 判定为假.
            3. 只有【门槛通过】且【深度研判发现风险】 -> 判定为真 (is_real=True).
            
            如果判定为真，请根据【站点】打标签：
            - 如果站点是 'CT' -> anomaly_type = '真实异常'
            - 如果站点不是 'CT' -> anomaly_type = '当站超规'
            
            请严格按照 JSON 格式输出。
            """,
            agent=chief_agent,
            expected_output="JSON格式的最终判定结果",
            output_pydantic=AnomalyVerdict # 强制结构化输出
        )

        # =================================================================
        # 3. 组建 Crew 并执行
        # =================================================================
        crew = Crew(
            agents=[screener_agent, detective_agent, chief_agent],
            tasks=[task_screen, task_analyze, task_verdict],
            process=Process.sequential, # 顺序执行：Screener -> Detective -> Chief
            verbose=True
        )

        try:
            # 执行
            result = crew.kickoff()
            
            # 解析结果
            verdict = result.pydantic if hasattr(result, 'pydantic') else result # type: ignore
            
            # 容错处理
            if not hasattr(verdict, 'is_real'):
                 logger.error(f"AI Output Error: {result}")
                 return {"is_real": False, "anomaly_type": "", "reasons": ["AI解析错误"]}

            # 提取简报
            conc_text = data_context.split("分析结果: ")[1].split("\n")[0] if "分析结果: " in data_context else ""

            return {
                "is_real": verdict.is_real, # type: ignore
                "anomaly_type": verdict.anomaly_type if verdict.is_real else "", # type: ignore
                "reasons": verdict.reasons, # type: ignore
                "conc_text": conc_text,
                "ai_summary": verdict.analysis_summary # type: ignore
            }

        except Exception as e:
            logger.error(f"CrewAI Execution Failed: {e}")
            return {"is_real": False, "anomaly_type": "", "reasons": ["AI服务不可用"]}