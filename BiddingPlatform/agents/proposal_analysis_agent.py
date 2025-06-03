# agents/proposal_analysis_agent.py
from typing import Dict, Any, List
import re
import json
import asyncio
from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from langchain_google_genai import ChatGoogleGenerativeAI

class ProposalAnalysisAgent(BaseAgent):
    """Agent specialized in analyzing individual proposals against evaluation criteria"""
    
    def __init__(self, agent_id: str = None, config: Dict[str, Any] = None):
        super().__init__(agent_id, config)
        self.llm = config.get('llm') if config else None
        if not self.llm:
            raise ValueError("LLM instance required for ProposalAnalysisAgent")
        
        self.max_concurrent_analysis = config.get('max_concurrent_analysis', 2) if config else 2
    
    def get_capabilities(self) -> List[str]:
        return [
            "proposal_content_analysis",
            "criteria_matching",
            "strength_identification",
            "weakness_detection",
            "evidence_extraction"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process proposal analysis tasks"""
        task_type = task.input_data.get('task_type')
        
        if task_type == 'analyze_single_proposal':
            return await self._analyze_single_proposal(task)
        elif task_type == 'analyze_batch_proposals':
            return await self._analyze_batch_proposals(task)
        elif task_type == 'extract_strengths':
            return await self._extract_proposal_strengths(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _analyze_single_proposal(self, task: AgentTask) -> AgentResult:
        """Analyze a single proposal against criteria"""
        proposal = task.input_data.get('proposal')
        criteria = task.input_data.get('criteria', [])
        
        if not proposal or not criteria:
            raise ValueError("Proposal and criteria required for analysis")
        
        company_name = proposal.get('company_name')
        proposal_text = proposal.get('pdf_text', '')
        
        # Analyze each criterion
        criterion_analyses = []
        for criterion in criteria:
            analysis = await self._analyze_criterion_match(
                proposal_text, criterion, company_name
            )
            criterion_analyses.append(analysis)
        
        # Extract overall strengths and weaknesses
        overall_analysis = await self._extract_overall_analysis(
            proposal_text, criteria, company_name
        )
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'company_name': company_name,
                'criterion_analyses': criterion_analyses,
                'overall_analysis': overall_analysis,
                'proposal_quality': self._assess_proposal_quality(criterion_analyses)
            }
        )
    
    async def _analyze_batch_proposals(self, task: AgentTask) -> AgentResult:
        """Analyze multiple proposals concurrently"""
        proposals = task.input_data.get('proposals', [])
        criteria = task.input_data.get('criteria', [])
        
        if not proposals or not criteria:
            raise ValueError("Proposals and criteria required for batch analysis")
        
        # Process proposals concurrently with semaphore
        semaphore = asyncio.Semaphore(self.max_concurrent_analysis)
        analysis_tasks = []
        
        for proposal in proposals:
            task_coro = self._analyze_single_proposal_with_semaphore(
                semaphore, proposal, criteria
            )
            analysis_tasks.append(task_coro)
        
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # Process results
        successful_analyses = []
        failed_analyses = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_analyses.append({
                    'company_name': proposals[i].get('company_name', f'Company_{i}'),
                    'error': str(result)
                })
            else:
                successful_analyses.append(result)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'successful_analyses': successful_analyses,
                'failed_analyses': failed_analyses,
                'success_count': len(successful_analyses),
                'failure_count': len(failed_analyses)
            }
        )
    
    async def _analyze_single_proposal_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                                     proposal: Dict, criteria: List[Dict]):
        """Analyze single proposal with concurrency control"""
        async with semaphore:
            return await self._analyze_single_proposal_internal(proposal, criteria)
    
    async def _analyze_single_proposal_internal(self, proposal: Dict, criteria: List[Dict]):
        """Internal method for analyzing a single proposal"""
        company_name = proposal.get('company_name')
        proposal_text = proposal.get('pdf_text', '')
        
        # Analyze each criterion
        criterion_analyses = []
        for criterion in criteria:
            analysis = await self._analyze_criterion_match(
                proposal_text, criterion, company_name
            )
            criterion_analyses.append(analysis)
        
        # Extract overall analysis
        overall_analysis = await self._extract_overall_analysis(
            proposal_text, criteria, company_name
        )
        
        return {
            'company_name': company_name,
            'criterion_analyses': criterion_analyses,
            'overall_analysis': overall_analysis,
            'proposal_quality': self._assess_proposal_quality(criterion_analyses)
        }
    
# ------------------------------------------------------------------ #
#  ⬇︎ استبدل الدالة _analyze_criterion_match كاملة بهذا الإصدار
# ------------------------------------------------------------------ #
    async def _analyze_criterion_match(self, proposal_text: str, criterion: Dict,
                                       company_name: str) -> Dict[str, Any]:
        """Analyze how well a proposal matches a specific criterion via LLM (with fallback)."""
        criterion_name = criterion.get('name', '')
        criterion_desc = criterion.get('description', '')

        # Limit text length for LLM processing
        text_sample = proposal_text[:4000]  # سمحنا بمقتطف أكبر قليلاً

        prompt = f"""
نظام الدور: أنت خبير تقييم عروض (Technical & Financial Proposal Evaluator) لدى جهة حكومية سعودية.

🧮 **الهدف**: قياس مدى استيفاء عرض شركة «{company_name}» لمعيار التقييم الموضَّح أدناه، مع تبرير الدرجة بالأدلة.

📋 **المعيار المستهدف**
• الاسم   : {criterion_name}
• الوصف   : {criterion_desc}

📑 **مقتطف من العرض** (قد يكون مقتطعاً):
\"\"\" 
{text_sample}
\"\"\" 

🛠️ **المطلوب – أعده بصيغة JSON فقط ودون أي تعليق آخر**:
{{
  "score": <عدد صحيح 0-100؛ 90+ = ممتاز، 75-89 = جيد، 60-74 = متوسط، أقل من 60 = ضعيف>,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "evidence": ["اقتباس قصير ≤ 200 حرف يدعم التقييم"],
  "justification": "جملة مختصرة تلخّص سبب الدرجة"
}}

⚠️ **تعليمات إلزامية**
• التزم تماماً بالبناء JSON أعلاه؛ لا تضف أو تحذف حقولاً.  
• إذا لم تجد أي ذكر واضح للمطلوب، اجعل الدرجة 0 وسجّل ضعفاً مناسباً.  
• الأدلة يجب أن تكون اقتباسات حقيقية من النص (يمكن تقصيرها بعلامة “…”) ولا تتجاوز 200 حرف.
"""

        try:
            response = self.llm.invoke(prompt)
            result_text = response.content if hasattr(response, "content") else str(response)

            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", result_text)
            if json_match:
                analysis = json.loads(json_match.group(0))

                # Sanity-check score
                score_val = analysis.get("score", 0)
                if not isinstance(score_val, (int, float)) or not (0 <= score_val <= 100):
                    score_val = 50

                return {
                    "criterion_name": criterion_name,
                    "score": score_val,
                    "strengths": analysis.get("strengths", []),
                    "weaknesses": analysis.get("weaknesses", []),
                    "evidence": analysis.get("evidence", []),
                    "justification": analysis.get("justification", ""),
                }

        except Exception as e:
            self.logger.warning(f"LLM analysis failed for criterion {criterion_name}: {e}")

        # --- Fallback: keyword-based quick estimate ---
        return self._fallback_criterion_analysis(proposal_text, criterion)
    
    def _fallback_criterion_analysis(self, proposal_text: str, criterion: Dict) -> Dict[str, Any]:
        """Fallback analysis when LLM fails"""
        criterion_name = criterion.get('name', '')
        
        # Simple keyword-based scoring
        keywords = self._get_criterion_keywords(criterion_name)
        score = self._calculate_keyword_score(proposal_text, keywords)
        
        return {
            'criterion_name': criterion_name,
            'score': score,
            'strengths': ["تم العثور على محتوى متعلق بالمعيار"],
            'weaknesses': ["يحتاج تحليل أكثر تفصيلاً"],
            'evidence': [],
            'justification': f"تقييم أولي بناء على الكلمات المفتاحية - {score}/100"
        }
    
# ------------------------------------------------------------------ #
#  ⬇︎ استبدل الدالة _get_criterion_keywords كاملة بهذا الإصدار
# ------------------------------------------------------------------ #
    def _get_criterion_keywords(self, criterion_name: str) -> List[str]:
        """Return a richer Arabic/English keyword list relevant to the criterion name."""
        keyword_map = {
            # الكفاءة الفنية / Technical Competence
            "الكفاءة الفنية": [
                "تقني", "تكنولوج", "خبرة", "مهارة", "ابتكار", "معمارية", "تكامل",
                "صيانة", "دعم", "SLA", "أمن", "سيبرانية", "جودة", "اعتمادية",
                "performance", "security", "integration", "maintenance"
            ],
            # الخبرة السابقة / Past Experience
            "الخبرة السابقة": [
                "خبرة", "مشروع", "تنفيذ", "إنجاز", "مرجع", "عميل", "نجاح",
                "حالة", "case study", "شهادة", "reference", "tor", "تحالف", "توريد"
            ],
            # خطة التنفيذ والجدول الزمني / Implementation Plan
            "خطة التنفيذ": [
                "خطة", "جدول", "زمني", "مرحلة", "مسار", "نشاط", "موعد", "توريد",
                "موارد", "مخاطر", "تحكم", "منهجية", "agile", "waterfall", "sprint",
                "Gantt", "timeline"
            ],
            # فريق العمل / Project Team
            "فريق العمل": [
                "فريق", "هيكل", "سيرة", "CV", "مهندس", "محلل", "مدير مشروع",
                "متخصص", "خبير", "شهادة", "PMP", "خبرات", "الموارد البشرية",
                "team structure", "staff", "consultant"
            ],
            # القيمة المالية / Financial Offer
            "القيمة المالية": [
                "سعر", "تكلفة", "عرض مالي", "مالي", "ميزانية", "دفع", "خصم",
                "قيمة", "وفر", "فعالية", "ROI", "جدوى", "cost", "price", "economy"
            ],
            # مدى المطابقة للمواصفات / Compliance
            "مدى المطابقة": [
                "مطابقة", "مواصفة", "متطلبات", "توافق", "compliance", "iso",
                "سياسة", "معيار", "لائحة", "ضمان", "معتمد", "متوافق"
            ],
            # خطة التسليم / Delivery
            "التسليم": [
                "تسليم", "مدة", "مهلة", "جدول", "خدمة", "تشغيل", "commissioning",
                "handover", "CPM", "milestone", "موعد نهائي", "deadline"
            ],
            # الأداء السابق / Past Performance
            "الأداء السابق": [
                "أداء", "مؤشر", "kpi", "kpi", "رضا", "satisfaction", "تقييم",
                "مرجعية", "موثوقية", "reliability", "uptime", "SLR", "slo"
            ],
        }

        # Pick the first key whose words appear in the criterion_name
        for key, words in keyword_map.items():
            if any(part in criterion_name for part in key.split()):
                return words

        # Generic fallback keywords
        return ["جودة", "تميز", "كفاءة", "احتراف", "value", "best practice"]
    
    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> int:
        """Calculate a simple score based on keyword presence"""
        text_lower = text.lower()
        found_keywords = sum(1 for keyword in keywords if keyword in text_lower)
        
        # Base score of 40, plus 10 points per found keyword (max 100)
        score = min(40 + (found_keywords * 10), 100)
        return score
    
    async def _extract_overall_analysis(self, proposal_text: str, criteria: List[Dict], 
                                      company_name: str) -> Dict[str, Any]:
        """Extract overall strengths and weaknesses of the proposal"""
        # Limit text for processing
        text_sample = proposal_text[:1500] if len(proposal_text) > 1500 else proposal_text
        criteria_names = [c.get('name', '') for c in criteria]
        
        prompt = f"""
        أنت خبير في تقييم العطاءات. يرجى تحليل العرض التقني بشكل شامل.
        
        معايير التقييم: {', '.join(criteria_names)}
        
        نص العرض:
        {text_sample}
        
        المطلوب:
        1. حدد أبرز 3 نقاط قوة في العرض
        2. حدد أبرز 3 نقاط ضعف أو مجالات تحسين
        3. قيّم جودة العرض عموماً (ممتاز/جيد/متوسط/ضعيف)
        
        أرجع في تنسيق JSON:
        {{
            "overall_strengths": ["نقطة قوة 1", "نقطة قوة 2", "نقطة قوة 3"],
            "overall_weaknesses": ["نقطة ضعف 1", "نقطة ضعف 2"],
            "overall_quality": "جيد",
            "summary": "ملخص قصير عن العرض"
        }}
        """
        
        try:
            response = self.llm.invoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                return json.loads(json_text)
            
        except Exception as e:
            self.logger.warning(f"Overall analysis failed: {e}")
        
        # Fallback
        return {
            'overall_strengths': ["عرض فني متكامل"],
            'overall_weaknesses': ["يحتاج مراجعة تفصيلية"],
            'overall_quality': "متوسط",
            'summary': f"عرض تقني من {company_name}"
        }
    
    def _assess_proposal_quality(self, criterion_analyses: List[Dict]) -> Dict[str, Any]:
        """Assess overall proposal quality based on criterion analyses"""
        if not criterion_analyses:
            return {'quality_score': 0, 'quality_level': 'ضعيف'}
        
        # Calculate average score
        scores = [analysis.get('score', 0) for analysis in criterion_analyses]
        avg_score = sum(scores) / len(scores)
        
        # Determine quality level
        if avg_score >= 85:
            quality_level = 'ممتاز'
        elif avg_score >= 70:
            quality_level = 'جيد'
        elif avg_score >= 50:
            quality_level = 'متوسط'
        else:
            quality_level = 'ضعيف'
        
        return {
            'quality_score': round(avg_score, 1),
            'quality_level': quality_level,
            'score_distribution': scores,
            'min_score': min(scores),
            'max_score': max(scores)
        }
    
    async def _extract_proposal_strengths(self, task: AgentTask) -> AgentResult:
        """Extract key strengths from a proposal for justification"""
        proposal = task.input_data.get('proposal')
        criteria = task.input_data.get('criteria', [])
        
        if not proposal:
            raise ValueError("Proposal required for strength extraction")
        
        analysis = await self._analyze_single_proposal_internal(proposal, criteria)
        
        # Compile top strengths with evidence
        strengths_with_evidence = []
        for criterion_analysis in analysis['criterion_analyses']:
            if criterion_analysis.get('score', 0) >= 70:  # Good scores
                for strength in criterion_analysis.get('strengths', []):
                    strengths_with_evidence.append({
                        'strength': strength,
                        'criterion': criterion_analysis['criterion_name'],
                        'score': criterion_analysis['score'],
                        'evidence': criterion_analysis.get('evidence', [])
                    })
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'company_name': proposal.get('company_name'),
                'strengths_with_evidence': strengths_with_evidence,
                'overall_analysis': analysis.get('overall_analysis', {}),
                'top_criteria_scores': sorted(
                    [(ca['criterion_name'], ca['score']) for ca in analysis['criterion_analyses']],
                    key=lambda x: x[1], reverse=True
                )[:3]
            }
        )
