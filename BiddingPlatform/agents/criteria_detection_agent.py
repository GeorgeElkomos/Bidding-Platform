# agents/criteria_detection_agent.py
from typing import Dict, Any, List, Optional
import re
import json
from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from langchain_google_genai import ChatGoogleGenerativeAI

class CriteriaDetectionAgent(BaseAgent):
    """Agent specialized in detecting and extracting evaluation criteria from terms documents"""
    
    def __init__(self, agent_id: str = None, config: Dict[str, Any] = None):
        super().__init__(agent_id, config)
        self.llm = config.get('llm') if config else None
        if not self.llm:
            raise ValueError("LLM instance required for CriteriaDetectionAgent")
    
    def get_capabilities(self) -> List[str]:
        return [
            "criteria_extraction",
            "scoring_weights_detection",
            "evaluation_matrix_design",
            "arabic_criteria_parsing"
        ]
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process criteria detection tasks"""
        task_type = task.input_data.get('task_type')
        
        if task_type == 'extract_criteria':
            return await self._extract_evaluation_criteria(task)
        elif task_type == 'validate_criteria':
            return await self._validate_criteria(task)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _extract_evaluation_criteria(self, task: AgentTask) -> AgentResult:
        """Extract evaluation criteria from terms document"""
        terms_text = task.input_data.get('terms_text')
        
        if not terms_text:
            raise ValueError("No terms text provided for criteria extraction")
        
        # First, try to detect criteria using pattern matching
        detected_criteria = self._pattern_based_detection(terms_text)
        
        # If pattern-based detection finds good results, use them
        if detected_criteria and len(detected_criteria) >= 3:
            criteria_result = detected_criteria
        else:
            # Fall back to LLM-based extraction
            criteria_result = await self._llm_based_extraction(terms_text)
        
        # Validate and normalize the criteria
        normalized_criteria = self._normalize_criteria(criteria_result)
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'criteria': normalized_criteria,
                'detection_method': 'pattern' if detected_criteria else 'llm',
                'total_criteria': len(normalized_criteria),
                'has_weights': any(c.get('weight') for c in normalized_criteria)
            }
        )
    
    def _pattern_based_detection(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Try to detect criteria using Arabic pattern matching"""
        criteria = []
        
        # Common Arabic section headers for evaluation criteria
        criteria_patterns = [
            r'معايير\s+التقييم',
            r'أسس\s+المفاضلة',
            r'جدول\s+الدرجات',
            r'معايير\s+الاختيار',
            r'أسس\s+التقييم',
            r'الدرجات\s+والنقاط'
        ]
        
        # Look for criteria sections
        criteria_section = None
        for pattern in criteria_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract text after the criteria header
                start_pos = match.end()
                # Look for the next major section or end of document
                next_section = re.search(r'\n\s*\d+[\.\-]\s*[^0-9]', text[start_pos:])
                end_pos = next_section.start() + start_pos if next_section else len(text)
                criteria_section = text[start_pos:end_pos]
                break
        
        if not criteria_section:
            return None
        
        # Extract individual criteria and weights
        criteria_lines = criteria_section.split('\n')
        
        for line in criteria_lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Look for numbered items or bullet points
            criterion_match = re.match(r'[\d\-\•\*]\s*(.+)', line)
            if criterion_match:
                criterion_text = criterion_match.group(1).strip()
                
                # Look for percentage or points
                weight_match = re.search(r'(\d+)[\s]*[%٪]|(\d+)[\s]*نقطة|(\d+)[\s]*درجة', criterion_text)
                weight = None
                if weight_match:
                    weight = int(weight_match.group(1) or weight_match.group(2) or weight_match.group(3))
                    # Remove weight from criterion text
                    criterion_text = re.sub(r'\s*\d+[\s]*[%٪نقطة درجة]\s*', '', criterion_text).strip()
                
                if len(criterion_text) > 10:  # Filter out very short text
                    criteria.append({
                        'name': criterion_text,
                        'weight': weight,
                        'description': criterion_text
                    })
        
        return criteria if len(criteria) >= 3 else None
    
    async def _llm_based_extraction(self, terms_text: str) -> List[Dict[str, Any]]:
        """Use LLM to extract criteria when pattern matching fails"""
        prompt = """
        نظام الدور: خبير تحليل وثائق عطاءات حكومية سعودية.

        الهدف:
        استخراج «معايير تقييم العروض» وأوزانها من النص المُعطى، حتى لو كانت موجودة في ملحق أو جدول لاحق.

        التعليمات خطوة-ب-خطوة:
        1. حدِّد أولاً أقرب عنوان يطابق أيّاً من:
        - "معايير تقييم العروض"
        - "جدول معايير تقييم العروض"
        - الملحقات التي يذكر فيها «معايير تقييم العروض»
        2. بعد العثور على العنوان، افحص حتى ٣ صفحات لاحقة أو حتى بداية عنوان رئيسي جديد (أو نهاية النص) بحثاً عن:
        • صفوف جدول  
        • قوائم مرقَّمة أو نقطية  
        • كلمات مثل «٪»، «درجة»، «نقطة»، «Points», «Score»
        3. لكل صفّ أو بند:
        أ. استخرج اسم المعيار (Arabic أو English).  
        ب. استخرج الوزن وحوِّله إلى عدد صحيح يمثل النسبة المئوية إن أمكن:
            • «٢٠٪» → 20  
            • «15 نقطة» أو «15 درجة» → 15  
            • إذا ذُكر نطاق (مثال: 10–15 درجة) فاختر الحدّ الأعلى.  
        ج. استخرج الوصف إن وُجد (النص بعد اسم المعيار مباشرة).
        4. إذا تبيَّن أن الوثيقة تُحيل إلى ملحق خارجي ولم يُعثر على جدول في النص، فاستخدم أفضل الممارسات السعودية واقترح خمسة معايير مناسبة لعطاء دعم ERP، مع توزيع أوزان مجموعها 100.
        5. أعِد النتيجة بترميز JSON الدقيق التالي— ودون أي نص خارج القوسين المعقوفين:
        {
        "criteria": [
            {
            "name": "اسم المعيار",
            "weight": 25,
            "description": "وصف مختصر للمعيار"
            },
            ...
        ]
        }

        ملاحظات مهمة للمولد:
        - لا تُضف حقولاً غير مطلوبة.
        - اجعل مجموع الأوزان = 100، وإنْ غابت الأوزان صرِّح بالقيمة null.
        - استعمل الأرقام العربية (١٢٣...) أو الإنجليزية (123) فقط داخل الحقول العددية، ولا تكتب علامة ٪ أو كلمة درجة داخل الحقل «weight».        """

        try:
            response = self.llm.invoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                result = json.loads(json_text)
                return result.get('criteria', [])
            
        except Exception as e:
            self.logger.warning(f"LLM-based extraction failed: {e}")
        
        # Fallback to default criteria
        default_criteria = self._get_default_criteria()
        return default_criteria
    
    def _get_default_criteria(self) -> List[Dict[str, Any]]:
        """
        Default evaluation model (Arabic):
        Final Score = (0.4 × Price) + (0.3 × Compliance) + (0.2 × Delivery) + (0.1 × Past Performance)
        """
        return [
            {
                "name": "القيمة المالية",
                "weight": 40,
                "description": "مقارنة السعر بالعطاءات الأخرى وميزانية الجهة"
            },
            {
                "name": "مدى المطابقة للمواصفات",
                "weight": 30,
                "description": "درجة الالتزام بالمتطلبات الفنية والقانونية الواردة في الكراسة"
            },
            {
                "name": "خطة التسليم",
                "weight": 20,
                "description": "سرعة وواقعية جدول التسليم والتنفيذ المقترح"
            },
            {
                "name": "الأداء السابق",
                "weight": 10,
                "description": "سجل مقدم العرض وخبرته في تنفيذ مشاريع مماثلة بجودة عالية"
            }
        ]
    
    def _normalize_criteria(self, criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize and validate criteria"""
        if not criteria:
            return self._get_default_criteria()
        
        # Ensure all criteria have required fields
        normalized = []
        total_weight = 0
        
        for criterion in criteria:
            if isinstance(criterion, dict) and criterion.get('name'):
                weight = criterion.get('weight')
                if weight:
                    total_weight += weight
                
                normalized.append({
                    'name': criterion['name'],
                    'weight': weight,
                    'description': criterion.get('description', criterion['name'])
                })
        
        # If no weights or weights don't sum to 100, distribute equally
        if not any(c['weight'] for c in normalized) or abs(total_weight - 100) > 10:
            equal_weight = 100 // len(normalized)
            remainder = 100 % len(normalized)
            
            for i, criterion in enumerate(normalized):
                criterion['weight'] = equal_weight
                if i < remainder:  # Distribute remainder to first few criteria
                    criterion['weight'] += 1
        
        return normalized
    
    async def _validate_criteria(self, task: AgentTask) -> AgentResult:
        """Validate extracted criteria"""
        criteria = task.input_data.get('criteria', [])
        
        validation_issues = []
        
        # Check total weights
        total_weight = sum(c.get('weight', 0) for c in criteria)
        if abs(total_weight - 100) > 5:
            validation_issues.append(f"Total weights ({total_weight}) don't sum to 100")
        
        # Check for missing names
        for i, criterion in enumerate(criteria):
            if not criterion.get('name'):
                validation_issues.append(f"Criterion {i} missing name")
        
        # Check for duplicates
        names = [c.get('name', '') for c in criteria]
        if len(names) != len(set(names)):
            validation_issues.append("Duplicate criterion names found")
        
        is_valid = len(validation_issues) == 0
        
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                'is_valid': is_valid,
                'validation_issues': validation_issues,
                'total_weight': total_weight,
                'criterion_count': len(criteria)
            }
        )
