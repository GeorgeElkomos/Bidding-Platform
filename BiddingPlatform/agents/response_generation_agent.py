# agents/response_generation_agent.py
from typing import Dict, Any, List
import json
from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from langchain_google_genai import ChatGoogleGenerativeAI

class ResponseGenerationAgent(BaseAgent):
    """Agent specialized in generating final formatted responses and justifications"""
    
    def __init__(self, agent_id: str = None, config: Dict[str, Any] = None):
        super().__init__(agent_id, config)
        self.llm = config.get('llm') if config else None
        self.language = config.get('language', 'arabic') if config else 'arabic'
    
    def get_capabilities(self) -> List[str]:
        return [
            "response_formatting",
            "justification_generation",
            "arabic_text_generation",
            "json_output_formatting",
            "quality_assurance"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentResult:
      """Process response generation tasks"""
      task_type = task.input_data.get('task_type')
      
      if task_type == 'generate_final_response':
          return await self._generate_final_response(task)
      elif task_type == 'generate_justifications':
          return await self._generate_justifications(task)
      elif task_type == 'format_output':
          return await self._format_output(task)
      else:
          raise ValueError(f"Unknown task type: {task_type}")
    
    async def _generate_final_response(self, task: AgentTask) -> AgentResult:
        """Generate the complete final response"""
        chosen_companies = task.input_data.get('chosen', [])
        not_chosen_companies = task.input_data.get('not_chosen', [])
        analysis_data = task.input_data.get('analysis_data', {})
        criteria = task.input_data.get('criteria', [])
        
        # Generate detailed justifications for chosen companies
        enhanced_chosen = []
        for company in chosen_companies:
            enhanced_company = await self._enhance_company_with_justification(
                company, analysis_data
            )
            enhanced_chosen.append(enhanced_company)
        
        # Format the final response
        final_response = {
            "chosen": enhanced_chosen,
            "not_chosen": not_chosen_companies,
            "evaluation_criteria": criteria,
            "evaluation_summary": self._generate_evaluation_summary(
                enhanced_chosen, not_chosen_companies, analysis_data
            )
        }
        
        # Validate the response format
        validation_result = self._validate_response_format(final_response)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'final_response': final_response,
                'validation_result': validation_result,
                'total_chosen': len(enhanced_chosen),
                'total_not_chosen': len(not_chosen_companies)
            }
        )
    
    async def _enhance_company_with_justification(self, company: Dict, analysis_data: Dict) -> Dict[str, Any]:
        """Enhance a company entry with detailed Arabic justifications"""
        company_name = company.get('company', '')
        total_score = company.get('total_score', 0)
        rank = company.get('rank', 0)
        
        # Find the analysis data for this company
        company_analysis = None
        for analysis in analysis_data.get('successful_analyses', []):
            if analysis.get('company_name') == company_name:
                company_analysis = analysis
                break
        
        if company_analysis:
            # Generate justifications based on analysis
            reasons = await self._generate_detailed_justifications(company_analysis)
        else:
            # Fallback reasons
            reasons = self._generate_fallback_reasons(company_name, total_score)
        
        # Ensure we have exactly 3-4 reasons
        if len(reasons) < 3:
            reasons.extend(self._get_additional_reasons(total_score))
        elif len(reasons) > 4:
            reasons = reasons[:4]
        
        return {
            "company": company_name,
            "total_score": total_score,
            "rank": rank,
            "reasons": reasons
        }
    
    async def _generate_detailed_justifications(self, company_analysis: Dict) -> List[str]:
        """Generate detailed Arabic justifications based on company analysis"""
        company_name = company_analysis.get('company_name', '')
        criterion_analyses = company_analysis.get('criterion_analyses', [])
        overall_analysis = company_analysis.get('overall_analysis', {})
        
        # Find the top performing criteria
        top_criteria = sorted(
            criterion_analyses,
            key=lambda x: x.get('score', 0),
            reverse=True
        )[:3]
        
        reasons = []
        
        # Generate reasons based on top criteria
        for criterion in top_criteria:
            criterion_name = criterion.get('criterion_name', '')
            score = criterion.get('score', 0)
            strengths = criterion.get('strengths', [])
            evidence = criterion.get('evidence', [])
            
            if score >= 75 and strengths:
                reason = self._format_criterion_reason(
                    criterion_name, strengths[0], score, evidence
                )
                reasons.append(reason)
        
        # Add overall strength if available
        overall_strengths = overall_analysis.get('overall_strengths', [])
        if overall_strengths:
            overall_reason = f"أظهرت الشركة {overall_strengths[0]} مما يؤكد قدرتها على تنفيذ المشروع بنجاح"
            reasons.append(overall_reason)
        
        # If we still need more reasons, use LLM
        if len(reasons) < 3 and self.llm:
            additional_reasons = await self._llm_generate_reasons(company_analysis)
            reasons.extend(additional_reasons)
        
        return reasons[:4]  # Maximum 4 reasons
    
    def _format_criterion_reason(self, criterion_name: str, strength: str, 
                                score: int, evidence: List[str]) -> str:
        """Format a single criterion-based reason"""
        score_text = "ممتازة" if score >= 85 else "جيدة" if score >= 70 else "مقبولة"
        
        base_reason = f"حققت الشركة نتائج {score_text} في معيار {criterion_name}"
        
        if strength:
            base_reason += f" حيث {strength}"
        
        # Add evidence if available and short
        if evidence and len(evidence[0]) < 100:
            base_reason += f" وقد تبين ذلك من خلال {evidence[0]}"
        
        return base_reason
    
    async def _llm_generate_reasons(self, company_analysis: Dict) -> List[str]:
        """Use LLM to generate additional justification reasons"""
        if not self.llm:
            return []
        
        company_name = company_analysis.get('company_name', '')
        criterion_analyses = company_analysis.get('criterion_analyses', [])
        
        # Prepare context for LLM
        criteria_summary = []
        for analysis in criterion_analyses:
            criteria_summary.append({
                'معيار': analysis.get('criterion_name', ''),
                'درجة': analysis.get('score', 0),
                'نقاط_قوة': analysis.get('strengths', [])
            })
        
        prompt = f"""
        أنت خبير في صياغة تبريرات اختيار الشركات في العطاءات الحكومية.
        
        الشركة: {company_name}
        تقييم المعايير: {json.dumps(criteria_summary, ensure_ascii=False)}
        
        اكتب 2-3 جمل تبريرية باللغة العربية توضح أسباب اختيار هذه الشركة.
        كل جملة يجب أن تكون:
        - واضحة ومهنية
        - تركز على نقطة قوة محددة
        - لا تتجاوز 25 كلمة
        
        أرجع النتيجة كقائمة JSON:
        ["السبب الأول", "السبب الثاني", "السبب الثالث"]
        """
        
        try:
            response = self.llm.invoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array
            import re
            json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
            if json_match:
                reasons = json.loads(json_match.group(0))
                return [r for r in reasons if isinstance(r, str) and len(r) > 10]
            
        except Exception as e:
            self.logger.warning(f"LLM justification generation failed: {e}")
        
        return []
    
    def _generate_fallback_reasons(self, company_name: str, total_score: int) -> List[str]:
        """Generate fallback reasons when detailed analysis is not available"""
        reasons = [
            f"حققت الشركة درجة إجمالية {total_score} في التقييم الفني",
            "أظهرت الشركة التزاماً بمتطلبات كراسة الشروط والمواصفات",
            "تتمتع الشركة بالمؤهلات الفنية المطلوبة لتنفيذ المشروع"
        ]
        
        # Add score-specific reason
        if total_score >= 85:
            reasons.append("حققت الشركة أداءً متميزاً في جميع معايير التقييم")
        elif total_score >= 75:
            reasons.append("أظهرت الشركة كفاءة عالية في المعايير الأساسية للمشروع")
        else:
            reasons.append("استوفت الشركة الحد الأدنى من المتطلبات الفنية")
        
        return reasons
    
    def _get_additional_reasons(self, total_score: int) -> List[str]:
        """Get additional generic reasons to fill the requirement"""
        additional_reasons = [
            "تمتلك الشركة خبرة سابقة في مجال المشروع",
            "قدمت الشركة عرضاً فنياً متكاملاً",
            "أظهرت الشركة فهماً جيداً لمتطلبات المشروع",
            "تتوافق مؤهلات الشركة مع احتياجات المشروع"
        ]
        
        return additional_reasons
    
    def _generate_evaluation_summary(self, chosen: List[Dict], not_chosen: List[Dict], 
                                   analysis_data: Dict) -> Dict[str, Any]:
        """Generate a summary of the evaluation process"""
        total_companies = len(chosen) + len(not_chosen)
        
        summary = {
            "total_companies_evaluated": total_companies,
            "companies_selected": len(chosen),
            "selection_rate": round(len(chosen) / total_companies * 100, 1) if total_companies > 0 else 0,
            "average_winning_score": round(sum(c['total_score'] for c in chosen) / len(chosen), 1) if chosen else 0,
            "score_range": {
                "highest": max(c['total_score'] for c in chosen) if chosen else 0,
                "lowest": min(c['total_score'] for c in chosen) if chosen else 0
            }
        }
        
        # Add quality assessment
        if summary["average_winning_score"] >= 85:
            summary["quality_assessment"] = "مستوى عالي من الجودة في العروض المختارة"
        elif summary["average_winning_score"] >= 75:
            summary["quality_assessment"] = "مستوى جيد من الجودة في العروض المختارة"
        else:
            summary["quality_assessment"] = "مستوى مقبول من الجودة في العروض المختارة"
        
        return summary
    
    def _validate_response_format(self, response: Dict) -> Dict[str, Any]:
        """Validate the final response format"""
        validation_issues = []
        
        # Check required keys
        if 'chosen' not in response:
            validation_issues.append("Missing 'chosen' key")
        if 'not_chosen' not in response:
            validation_issues.append("Missing 'not_chosen' key")
        
        # Validate chosen companies structure
        chosen = response.get('chosen', [])
        for i, company in enumerate(chosen):
            if not isinstance(company, dict):
                validation_issues.append(f"Chosen company {i} is not a dictionary")
                continue
            
            required_fields = ['company', 'total_score', 'rank', 'reasons']
            for field in required_fields:
                if field not in company:
                    validation_issues.append(f"Chosen company {i} missing field: {field}")
            
            # Validate reasons
            reasons = company.get('reasons', [])
            if not isinstance(reasons, list):
                validation_issues.append(f"Chosen company {i} reasons is not a list")
            elif len(reasons) < 3:
                validation_issues.append(f"Chosen company {i} has fewer than 3 reasons")
            elif len(reasons) > 4:
                validation_issues.append(f"Chosen company {i} has more than 4 reasons")
        
        # Check JSON serialization
        try:
            json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            validation_issues.append(f"Response is not JSON serializable: {e}")
        
        return {
            "is_valid": len(validation_issues) == 0,
            "issues": validation_issues,
            "total_issues": len(validation_issues)
        }
    
    async def _generate_justifications(self, task: AgentTask) -> AgentResult:
        """Generate justifications for specific companies"""
        companies = task.input_data.get('companies', [])
        analysis_data = task.input_data.get('analysis_data', {})
        
        justified_companies = []
        for company in companies:
            enhanced_company = await self._enhance_company_with_justification(
                company, analysis_data
            )
            justified_companies.append(enhanced_company)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'justified_companies': justified_companies,
                'total_companies': len(justified_companies)
            }
        )
    
    async def _format_output(self, task: AgentTask) -> AgentResult:
        """Format output according to specific requirements"""
        data = task.input_data.get('data', {})
        format_type = task.input_data.get('format_type', 'json')
        
        if format_type == 'json':
            formatted_output = json.dumps(data, ensure_ascii=False, indent=2)
        elif format_type == 'compact_json':
            formatted_output = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        else:
            formatted_output = str(data)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'formatted_output': formatted_output,
                'format_type': format_type,
                'output_size': len(formatted_output)
            }
        )
