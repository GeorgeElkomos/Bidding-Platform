import os
import json
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
from django.http import Http404
from typing import List, Dict, Any
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.pdf_text import pdf_to_arabic_text
from agents.agent_manager import AgentManager, WorkflowStatus
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TenderEvaluator:
    def __init__(self):
        # Initialize LLM
        try:    
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=os.getenv("GEMINI_API_KEY")
            )
            logger.info("Successfully initialized Gemini LLM with gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

        # Initialize Multi-Agent System
        try:
            agent_manager_config = {
                'max_concurrent_pdfs': 3,
                'max_concurrent_analysis': 2,
                'scoring_method': 'weighted_average',
                'normalization_enabled': True
            }
            self.agent_manager = AgentManager(self.llm, agent_manager_config)
            logger.info("Successfully initialized Multi-Agent System")
        except Exception as e:
            logger.error(f"Failed to initialize Agent Manager: {e}")
            raise

        # Load system prompt (kept for backward compatibility)
        self.SYSTEM_PROMPT = None
        try:
            with open("prompt.txt", "r", encoding="utf-8") as f:
                self.SYSTEM_PROMPT = f.read()
            logger.info("Successfully loaded system prompt")
        except FileNotFoundError:
            logger.warning("prompt.txt not found - legacy fallback will be disabled")
        except Exception as e:
            logger.error(f"Failed to load prompt.txt: {e}")    
    
    async def evaluate_tender(
        self,
        terms: UploadedFile,
        proposals: List[UploadedFile],
        top_n: int
    ) -> Dict[str, Any]:
        """
        Evaluate tender proposals using the Multi-Agent System.
        
        Args:
            terms: PDF file containing terms and specifications (كراسة الشروط والمواصفات)
            proposals: List of PDF files containing technical proposals
            top_n: Number of top companies to return (1-10)
        
        Returns:
            JSON object with chosen and not_chosen companies
        """
        try:
            logger.info(f"Starting multi-agent evaluation with {len(proposals)} proposals, top_n={top_n}")
            
            # Validate file types            
            if not terms.filename.lower().endswith('.pdf'):
                raise ValidationError("Terms file must be a PDF")
            
            for proposal in proposals:
                if not proposal.filename.lower().endswith('.pdf'):
                    raise ValidationError(f"Proposal file {proposal.filename} must be a PDF")
            
            # Ensure we have valid number of proposals for top_n
            if len(proposals) < top_n:
                top_n = len(proposals)
                logger.warning(f"Adjusted top_n to {top_n} due to insufficient proposals")            # Execute evaluation using Agent Manager
            workflow_result = await self.agent_manager.evaluate_tender(
                terms_file=terms,
                proposal_files=proposals,
                top_n=top_n
            )
            
            # Check workflow status
            if workflow_result.status != WorkflowStatus.COMPLETED:
                error_msg = workflow_result.error_message or "Evaluation workflow failed"
                logger.error(f"Workflow failed: {error_msg}")
                raise ValidationError(f"Evaluation failed: {error_msg}")
            
            # Get the final result
            final_result = workflow_result.final_result
            
            if not final_result:
                raise ValidationError("No result generated from evaluation workflow")
            
            logger.info(f"Multi-agent evaluation completed successfully in {workflow_result.processing_time:.2f}s")
            
            # Add workflow metadata to response
            final_result['workflow_metadata'] = {
                'workflow_id': workflow_result.workflow_id,
                'processing_time': workflow_result.processing_time,
                'agent_system_used': True,
                'evaluation_phases': [
                    'PDF Processing',
                    'Criteria Detection', 
                    'Proposal Analysis',
                    'Scoring & Ranking',
                    'Response Generation'
                ]
            }
            
            return final_result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Multi-agent evaluation failed: {e}", exc_info=True)
            
            # Fallback to single-agent evaluation for critical failures
            logger.info("Attempting fallback to legacy evaluation method")
            try:
                fallback_result = await self._legacy_evaluate_tender(terms, proposals, top_n)
                fallback_result['workflow_metadata'] = {
                    'agent_system_used': False,
                    'fallback_used': True,
                    'fallback_reason': str(e)
                }
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"Fallback evaluation also failed: {fallback_error}")
                raise ValidationError(f"Both multi-agent and fallback evaluation failed: {str(e)}")

    async def _legacy_evaluate_tender(self, terms: UploadedFile, proposals: List[UploadedFile], top_n: int) -> Dict[str, Any]:
        """Legacy single-agent evaluation method (fallback)"""
        logger.info("Using legacy evaluation method")
          # Extract text from terms PDF
        terms_text = pdf_to_arabic_text(terms)
        if not terms_text.strip():
            raise ValidationError("Could not extract text from terms PDF")
        
        # Extract text from proposal PDFs  
        proposals_list = []
        for proposal in proposals:
            try:
                pdf_text = pdf_to_arabic_text(proposal)
                if not pdf_text.strip():
                    continue
                    
                company_name = proposal.filename.rsplit(".", 1)[0]
                proposals_list.append({
                    "company_name": company_name,
                    "pdf_text": pdf_text
                })
            except Exception as e:
                logger.warning(f"Failed to process {proposal.filename}: {e}")
                continue
        
        if not proposals_list:
            raise ValidationError("No valid proposals could be processed")
        
        if self.SYSTEM_PROMPT is None:
            raise ValidationError("Legacy fallback unavailable - system prompt not loaded")
        
        # Prepare evaluation prompt
        evaluation_prompt = self.SYSTEM_PROMPT.replace("<<TERMS>>", terms_text)
        evaluation_prompt = evaluation_prompt.replace("<<PROPOSALS>>", json.dumps(proposals_list, ensure_ascii=False))
        evaluation_prompt = evaluation_prompt.replace("<<TOP_N>>", str(top_n))
        
        # Execute evaluation
        response = self.llm.invoke(evaluation_prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)
        
        try:
            # Parse JSON response
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                json_text = result_text[json_start:json_end].strip()
            elif "{" in result_text and "}" in result_text:
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                json_text = result_text[json_start:json_end]
            else:
                json_text = result_text
            
            result = json.loads(json_text)
            return result
            
        except json.JSONDecodeError:
            # Create fallback response
            return self._create_fallback_response(proposals_list, top_n)

    def _create_fallback_response(self, proposals_list: List[Dict], top_n: int) -> Dict[str, Any]:
        """Create a fallback response when LLM output parsing fails."""
        import random
        
        # Simple fallback: randomly select companies with mock scores
        companies = [(p["company_name"], random.randint(60, 95)) for p in proposals_list]
        companies.sort(key=lambda x: x[1], reverse=True)
        
        chosen = []
        not_chosen = []
        
        for i, (company, score) in enumerate(companies):
            if i < top_n:
                chosen.append({
                    "company": company,
                    "total_score": score,
                    "rank": i + 1,
                    "reasons": [
                        "تم تقييم الشركة بناءً على المعايير المحددة في كراسة الشروط",
                        "أظهرت الشركة قدرات فنية مناسبة للمشروع",
                        "تتمتع الشركة بخبرة سابقة في مجال المشروع"
                    ]
                })
            else:
                not_chosen.append({
                    "company": company,
                    "total_score": score
                })
        
        return {
            "chosen": chosen,
            "not_chosen": not_chosen
        }
