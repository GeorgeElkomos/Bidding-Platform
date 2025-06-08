from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.core.exceptions import ValidationError
from User.models import Notification
from Tender.models import Tender, Tender_Files
from Bit.models import Bit_Files
from .permissions import IsSuperUser
from django.http import FileResponse
from asgiref.sync import sync_to_async
import io
import logging
import asyncio
import os
import re
import json
import datetime
from typing import List, Dict, Any, Union, BinaryIO
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.pdf_text import pdf_to_arabic_text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class TenderEvaluator:
    """Enhanced Tender Evaluation class with LLM integration"""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GEMINI_API_KEY")
        )
        self.logger = logger
    
    async def extract_criteria_from_terms(self, terms_text: str) -> List[Dict[str, Any]]:
        """Extract evaluation criteria from tender terms using LLM"""
        try:
            criteria = await self._llm_based_extraction(terms_text)
            return self._normalize_criteria(criteria)
        except Exception as e:
            self.logger.error(f"Criteria extraction failed: {e}")
            return self._get_default_criteria()
    
    async def _llm_based_extraction(self, terms_text: str) -> List[Dict[str, Any]]:
        """Use LLM to extract criteria when pattern matching fails"""
        prompt = """
        نظام الدور: خبير تحليل وثائق عطاءات حكومية سعودية.

        الهدف:
        استخراج «معايير تقييم العروض» وأوزانها من النص المُعطى، حتى لو كانت موجودة في ملحق أو جدول لاحق.

        التعليمات خطوة-ب-خطوة:
        1. حدِّد أولاً أقرب عنوان يطابق أيّاً من:
        - "معايير تقييم العروض"
        - "جدول معايير تقييم العروض"
        - الملحقات التي يذكر فيها «معايير تقييم العروض»
        2. بعد العثور على العنوان، افحص حتى ٣ صفحات لاحقة أو حتى بداية عنوان رئيسي جديد (أو نهاية النص) بحثاً عن:
        • صفوف جدول  
        • قوائم مرقَّمة أو نقطية  
        • كلمات مثل «٪»، «درجة»، «نقطة»، «Points», «Score»
        3. لكل صفّ أو بند:
        أ. استخرج اسم المعيار (Arabic أو English).  
        ب. استخرج الوزن وحوِّله إلى عدد صحيح يمثل النسبة المئوية إن أمكن:
            • «٢٠٪» → 20  
            • «15 نقطة» أو «15 درجة» → 15  
            • إذا ذُكر نطاق (مثال: 10–15 درجة) فاختر الحدّ الأعلى.  
        ج. استخرج الوصف إن وُجد (النص بعد اسم المعيار مباشرة).
        4. إذا تبيَّن أن الوثيقة تُحيل إلى ملحق خارجي ولم يُعثر على جدول في النص، فاستخدم أفضل الممارسات السعودية واقترح خمسة معايير مناسبة لعطاء دعم ERP، مع توزيع أوزان مجموعها 100.
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
        - اجعل مجموع الأوزان = 100، وإنْ غابت الأوزان صرِّح بالقيمة null.
        - استعمل الأرقام العربية (١٢٣...) أو الإنجليزية (123) فقط داخل الحقول العددية، ولا تكتب علامة ٪ أو كلمة درجة داخل الحقل «weight».

        النص المراد تحليله:
        """ + terms_text[:4000] + """
        """

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
    
    async def analyze_criterion_match(self, proposal_text: str, criterion: Dict,
                                     company_name: str) -> Dict[str, Any]:
        """Analyze how well a proposal matches a specific criterion via LLM (with fallback)."""
        criterion_name = criterion.get('name', '')
        criterion_desc = criterion.get('description', '')

        # Limit text length for LLM processing
        text_sample = proposal_text[:4000]  # سمحنا بمقتطف أكبر قليلاً

        prompt = f"""
نظام الدور: أنت خبير تقييم عروض (Technical & Financial Proposal Evaluator) لدى جهة حكومية سعودية.

🧮 **الهدف**: قياس مدى استيفاء عرض شركة «{company_name}» لمعيار التقييم الموضَّح أدناه، مع تبرير الدرجة بالأدلة.

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
• الأدلة يجب أن تكون اقتباسات حقيقية من النص (يمكن تقصيرها بعلامة "…") ولا تتجاوز 200 حرف.
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
    
    async def evaluate_proposals(self, terms_text: str, proposals_data: List[Dict]) -> Dict[str, Any]:
        """Main evaluation function"""
        try:
            # Extract criteria from terms
            criteria = await self.extract_criteria_from_terms(terms_text)
            
            # Evaluate each proposal
            evaluated_proposals = []
            for proposal in proposals_data:
                proposal_evaluation = await self._evaluate_single_proposal(proposal, criteria)
                evaluated_proposals.append(proposal_evaluation)
            
            # Sort by total score descending
            evaluated_proposals.sort(key=lambda x: x['total_score'], reverse=True)
            
            return {
                'criteria': criteria,
                'evaluated_proposals': evaluated_proposals,
                'evaluation_summary': self._create_evaluation_summary(evaluated_proposals, criteria)
            }
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            raise
    
    async def _evaluate_single_proposal(self, proposal: Dict, criteria: List[Dict]) -> Dict[str, Any]:
        """Evaluate a single proposal against all criteria"""
        proposal_text = proposal.get('text', '')
        company_name = proposal.get('company_name', 'Unknown')
        budget = proposal.get('budget', 0)
        
        criterion_analyses = []
        total_weighted_score = 0
        
        for criterion in criteria:
            analysis = await self.analyze_criterion_match(proposal_text, criterion, company_name)
            criterion_analyses.append(analysis)
            
            # Calculate weighted score
            weight = criterion.get('weight', 0) / 100  # Convert percentage to decimal
            weighted_score = analysis['score'] * weight
            total_weighted_score += weighted_score
        
        return {
            'bit_id': proposal.get('bit_id'),
            'company_name': company_name,
            'budget': budget,
            'total_score': round(total_weighted_score, 2),
            'criterion_analyses': criterion_analyses,
            'budget_competitiveness': self._assess_budget_competitiveness(proposal, criteria)
        }
    
    def _assess_budget_competitiveness(self, proposal: Dict, criteria: List[Dict]) -> Dict[str, Any]:
        """Assess how competitive the proposal budget is"""
        budget = proposal.get('budget', 0)
        tender_budget = proposal.get('tender_budget', 0)
        
        if tender_budget > 0:
            budget_ratio = budget / tender_budget
            if budget_ratio <= 0.8:
                competitiveness = "ممتاز - أقل من 80% من الميزانية"
            elif budget_ratio <= 0.9:
                competitiveness = "جيد - أقل من 90% من الميزانية"
            elif budget_ratio <= 1.0:
                competitiveness = "مقبول - ضمن الميزانية"
            else:
                competitiveness = "يتجاوز الميزانية المحددة"
        else:
            competitiveness = "غير محدد"
        
        return {
            'budget_ratio': round(budget_ratio, 3) if tender_budget > 0 else None,
            'competitiveness': competitiveness,
            'savings': tender_budget - budget if tender_budget > 0 else 0
        }
    
    def _create_evaluation_summary(self, evaluated_proposals: List[Dict], criteria: List[Dict]) -> Dict[str, Any]:
        """Create a summary of the evaluation results"""
        if not evaluated_proposals:
            return {}
        
        best_proposal = evaluated_proposals[0]
        scores = [p['total_score'] for p in evaluated_proposals]
        
        return {
            'total_proposals': len(evaluated_proposals),
            'best_proposal': {
                'company_name': best_proposal['company_name'],
                'total_score': best_proposal['total_score'],
                'bit_id': best_proposal['bit_id']
            },
            'score_statistics': {
                'highest_score': max(scores),
                'lowest_score': min(scores),
                'average_score': round(sum(scores) / len(scores), 2)
            },
            'criteria_count': len(criteria)
        }


class Evaluate_Tender_By_IDView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        """
        Enhanced tender evaluation with PDF text extraction and LLM-based criteria analysis
        """
        try:
            # Get tender ID from request
            tender_id = request.data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get the top N parameter (default to 3 if not provided)
            top_n = int(request.data.get("top_n", 3))

            # Get tender and verify it exists
            try:
                tender = Tender.objects.get(tender_id=tender_id)
            except Tender.DoesNotExist:
                return Response(
                    {"message": f"Tender with ID {tender_id} not found", "data": []},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get all tender files for this tender
            tender_files = Tender_Files.objects.filter(tender=tender)
            if not tender_files.exists():
                return Response(
                    {"message": "No tender files found for this tender", "data": []},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Get the tender budget
            tender_budget = tender.budget

            # Get all bits for this tender
            from Bit.models import Bit
            bits = Bit.objects.filter(tender=tender)
            if not bits.exists():
                return Response(
                    {"message": "No bids found for this tender", "data": []},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get all proposal files from all bits for this tender
            proposal_files = Bit_Files.objects.filter(bit__tender=tender)
            if not proposal_files.exists():
                return Response(
                    {"message": "No proposal files found for this tender", "data": []},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Extract text from tender file (terms)
            tender_file = tender_files.first()
            terms_text = ""
            
            try:
                if tender_file.file_type == 'application/pdf':
                    terms_text = pdf_to_arabic_text(tender_file.file_data)
                else:
                    # For non-PDF files, try to extract text as string
                    terms_text = tender_file.file_data.decode('utf-8') if isinstance(tender_file.file_data, bytes) else str(tender_file.file_data)
                
                # Append budget information
                terms_text += f"\n\nTender Budget: ${tender_budget}"
                
            except Exception as e:
                logger.warning(f"Could not extract text from tender file: {e}")
                terms_text = f"Tender Budget: ${tender_budget}"

            # Extract text from proposal files
            proposals_data = []
            for bit_file in proposal_files:
                try:
                    proposal_text = ""
                    if bit_file.file_type == 'application/pdf':
                        proposal_text = pdf_to_arabic_text(bit_file.file_data)
                    else:
                        # For non-PDF files, try to extract text as string
                        proposal_text = bit_file.file_data.decode('utf-8') if isinstance(bit_file.file_data, bytes) else str(bit_file.file_data)
                    
                    # Get company name from bit
                    company_name = bit_file.bit.created_by.username if bit_file.bit.created_by else "Unknown Company"
                    
                    proposals_data.append({
                        'bit_id': bit_file.bit.bit_id,
                        'company_name': company_name,
                        'text': proposal_text,
                        'budget': bit_file.bit.cost,
                        'tender_budget': tender_budget,
                        'file_name': bit_file.file_name
                    })
                    
                except Exception as e:
                    logger.warning(f"Could not extract text from proposal file {bit_file.file_name}: {e}")
                    continue

            if not proposals_data:
                return Response(
                    {"message": "Could not extract text from any proposal files", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Initialize evaluator and run evaluation
            evaluator = TenderEvaluator()
            
            # Run evaluation asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                evaluation_result = loop.run_until_complete(
                    evaluator.evaluate_proposals(terms_text, proposals_data)
                )
            finally:
                loop.close()

            # Prepare response data
            top_proposals = evaluation_result['evaluated_proposals'][:top_n]
            
            response_data = {
                'tender_id': tender_id,
                'tender_title': tender.title,
                'tender_budget': tender_budget,
                'evaluation_criteria': evaluation_result['criteria'],
                'total_proposals_evaluated': len(evaluation_result['evaluated_proposals']),
                'top_proposals': top_proposals,
                'evaluation_summary': evaluation_result['evaluation_summary'],
                'evaluation_timestamp': datetime.datetime.now().isoformat()
            }

            return Response(
                {
                    "message": f"Tender evaluation completed successfully. Top {len(top_proposals)} proposals ranked.",
                    "data": response_data
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Tender evaluation failed: {e}")
            return Response(
                {"message": f"Evaluation failed: {str(e)}", "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100

class List_All_TendersView(APIView):
    """View to list all tenders with search and pagination."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get search query parameter
        search_query = request.query_params.get('search', '').strip()
        
        # Start with all tenders
        tenders = Tender.objects.all()
        
        # Apply search filter if search query is provided
        if search_query:
            tenders = tenders.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(created_by__username__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        tenders = tenders.order_by('-start_date')
        
        # Apply pagination
        paginator = StandardPagination()
        paginated_tenders = paginator.paginate_queryset(tenders, request)
        
        tender_data = [
            {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "created_by": tender.created_by.username if tender.created_by else None,
            }
            for tender in paginated_tenders
        ]
        
        return paginator.get_paginated_response({
            "message": "Tenders retrieved successfully",
            "search_query": search_query,
            "total_count": tenders.count(),
            "data": tender_data
        })

class Tender_DetailView(APIView):
    """View to get details of a specific tender by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tender_id = request.query_params.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            tender = Tender.objects.get(tender_id=tender_id)
            TenderFiles = tender.files.all().order_by("-Uploaded_At")
            
            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "created_by": tender.created_by.username if tender.created_by else None,                "files": (
                    [
                        {
                            "file_id": cert.file_id,
                            "file_name": cert.file_name,
                            "file_type": cert.file_type,
                            "file_size": cert.file_size,
                            "uploaded_at": cert.Uploaded_At,
                        }
                        for cert in TenderFiles
                    ]
                    if TenderFiles
                    else []
                ),
            }
            return Response(
                {"message": "Tender details retrieved successfully", "data": tender_data},
                status=status.HTTP_200_OK
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class Get_TenderFile_Data(APIView):
    """View to retrieve file data for a specific VAT certificate by ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
                
            tender_file = Tender_Files.objects.get(file_id=file_id)
              # For file downloads, we need to handle differently since we're returning binary data
            # We'll return metadata in a standard format when requested
            if request.query_params.get("metadata_only") == "true":
                file_metadata = {
                    "file_id": tender_file.file_id,
                    "file_name": tender_file.file_name,
                    "file_type": tender_file.file_type,
                    "file_size": tender_file.file_size,
                    "uploaded_at": tender_file.Uploaded_At
                }
                return Response(
                    {"message": "File metadata retrieved successfully", "data": file_metadata},
                    status=status.HTTP_200_OK
                )
            else:
                # For actual file download, create a file-like object and return it
                file_stream = io.BytesIO(tender_file.file_data)
                response = FileResponse(
                    file_stream, 
                    content_type=tender_file.file_type,
                    as_attachment=True,
                    filename=tender_file.file_name
                )
                return response
                
        except Tender_Files.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class Create_TenderView(APIView):
    """View to create a new tender. Only superusers can create tenders."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender = Tender.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                start_date=data.get("start_date"),
                end_date=data.get("end_date"),
                budget=data.get("budget"),
                created_by=request.user, 
            )

            # Handle file uploads
            vat_files = request.FILES.getlist("files")
            uploaded_files = []

            if vat_files:
                for file in vat_files:
                    # Read the file data
                    file_data = file.read()

                    # Create the attachment record
                    tender_file = Tender_Files.objects.create(
                        tender=tender,
                        file_name=file.name,
                        file_type=file.content_type,
                        file_size=file.size,
                        file_data=file_data,
                    )

                    uploaded_files.append({
                        "file_id": tender_file.file_id,
                        "file_name": file.name,
                        "file_type": file.content_type,
                        "file_size": file.size
                    })

            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description,
                "start_date": tender.start_date,
                "end_date": tender.end_date,
                "budget": tender.budget,
                "uploaded_files": uploaded_files,
                "files_count": len(uploaded_files)
            }
            # notify the user about the new tender creation
            Notification.send_notification(message=f"A new tender '{tender.title}' has been created.", target_type="NORMAL")
            # Notify all superusers about the new tender
            Notification.send_notification(message="A new tender has been created.", target_type="SUPER")
            return Response(
                {
                    "message": "Tender created successfully.",
                    "data": tender_data
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Update_TenderView(APIView):
    """View to update an existing tender. Only superusers can update tenders."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)

            # Only update fields that are provided in the request
            if "title" in data:
                tender.title = data["title"]
            if "description" in data:
                tender.description = data["description"]
            if "start_date" in data:
                tender.start_date = data["start_date"]
            if "end_date" in data:
                tender.end_date = data["end_date"]
            if "budget" in data:
                tender.budget = data["budget"]

            tender.save()
            
            updated_fields = [
                field
                for field in [
                    "title",
                    "description",
                    "start_date",
                    "end_date",
                    "budget",
                ]
                if field in data
            ]
            
            tender_data = {
                "tender_id": tender.tender_id,
                "updated_fields": updated_fields,
                "tender": {
                    "title": tender.title,
                    "description": tender.description,
                    "start_date": tender.start_date,
                    "end_date": tender.end_date,
                    "budget": tender.budget,
                }
            }
            # Notify the user about the tender update
            Notification.send_notification(message=f"The tender '{tender.title}' has been updated.", target_type="NORMAL")
            return Response(
                {
                    "message": "Tender updated successfully.",
                    "data": tender_data
                },
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Add_TenderFileView(APIView):
    """View to add multiple files to an existing tender."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request):
        data = request.data
        try:
            tender_id = data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)

            # Handle multiple file uploads
            files = request.FILES.getlist("files")
            if not files:
                return Response(
                    {"message": "At least one file is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            uploaded_files = []
            
            for file in files:
                # Read the file data as BLOB
                file_data = file.read()
                
                # Create unique filenames with timestamp if needed
                import datetime
                import os
                
                # Split the filename into name and extension
                file_name, file_extension = os.path.splitext(file.name)
                
                # Add current timestamp to ensure uniqueness
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                unique_filename = f"{file_name}_{timestamp}{file_extension}"

                # Create the attachment record with BLOB data
                tender_file = Tender_Files.objects.create(
                    tender=tender,
                    file_name=unique_filename,
                    file_type=file.content_type,
                    file_size=file.size,
                    file_data=file_data,
                )
                
                uploaded_files.append({
                    "file_id": tender_file.file_id,
                    "file_name": unique_filename,
                    "original_filename": file.name,
                    "file_type": file.content_type,
                    "file_size": file.size
                })

            return Response(
                {
                    "message": f"{len(uploaded_files)} file(s) uploaded successfully.",
                    "data": {
                        "uploaded_files": uploaded_files,
                        "files_count": len(uploaded_files),
                        "tender_id": tender_id
                    }
                },
                status=status.HTTP_201_CREATED,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_TenderFileView(APIView):
    """View to delete a specific tender file by ID."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def delete(self, request):
        try:
            file_id = request.query_params.get("file_id")
            if not file_id:
                return Response(
                    {"message": "file_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender_file = Tender_Files.objects.get(file_id=file_id)
            tender_file.delete()

            return Response(
                {"message": "Tender file deleted successfully.", "data": {"file_id": file_id}},
                status=status.HTTP_200_OK,
            )
        except Tender_Files.DoesNotExist:
            return Response(
                {"message": "File not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )


class Delete_TenderView(APIView):
    """View to delete a specific tender by ID."""

    permission_classes = [IsAuthenticated, IsSuperUser]

    def delete(self, request):
        try:
            tender_id = request.data.get("tender_id")
            if not tender_id:
                return Response(
                    {"message": "tender_id is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tender = Tender.objects.get(tender_id=tender_id)
            tender.delete()
            # Notify the user about the tender deletion
            Notification.send_notification(message=f"The tender '{tender.title}' has been deleted.", target_type="NORMAL")
            return Response(
                {"message": "Tender deleted successfully.", "data": {"tender_id": tender_id}},
                status=status.HTTP_200_OK,
            )
        except Tender.DoesNotExist:
            return Response(
                {"message": "Tender not found.", "data": []},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": str(e), "data": []},
                status=status.HTTP_400_BAD_REQUEST,
            )



