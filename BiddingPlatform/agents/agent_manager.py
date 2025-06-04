# agents/agent_manager.py
import asyncio
import uuid
import time
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from .pdf_processor_agent import PDFProcessorAgent
from .criteria_detection_agent import CriteriaDetectionAgent
from .proposal_analysis_agent import ProposalAnalysisAgent
from .scoring_agent import ScoringAgent
from .response_generation_agent import ResponseGenerationAgent

class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class WorkflowResult:
    """Result of a complete evaluation workflow"""
    workflow_id: str
    status: WorkflowStatus
    final_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    agent_results: Optional[Dict[str, AgentResult]] = None
    metadata: Optional[Dict[str, Any]] = None

class AgentManager:
    """
    Central manager that orchestrates all specialized agents to complete
    the tender evaluation workflow
    """
    
    def __init__(self, llm_instance, config: Dict[str, Any] = None):
        self.config = config or {}
        self.llm = llm_instance
        self.logger = logging.getLogger("agent_manager")
        
        # Initialize all specialized agents
        self.agents = self._initialize_agents()
        
        # Workflow tracking
        self.active_workflows: Dict[str, WorkflowResult] = {}
        self.completed_workflows: List[WorkflowResult] = []
        
        # Performance metrics
        self.total_workflows_processed = 0
        self.total_processing_time = 0.0
        self.success_count = 0
        self.failure_count = 0
        
    def _initialize_agents(self) -> Dict[str, BaseAgent]:
        """Initialize all specialized agents with their configurations"""
        agent_config = {
            'llm': self.llm,
            **self.config.get('agent_config', {})
        }
        
        agents = {
            'pdf_processor': PDFProcessorAgent(
                config={
                    **agent_config,
                    'max_concurrent_pdfs': self.config.get('max_concurrent_pdfs', 3)
                }
            ),
            'criteria_detector': CriteriaDetectionAgent(config=agent_config),
            'proposal_analyzer': ProposalAnalysisAgent(
                config={
                    **agent_config,
                    'max_concurrent_analysis': self.config.get('max_concurrent_analysis', 2)
                }
            ),
            'scorer': ScoringAgent(
                config={
                    **agent_config,
                    'scoring_method': self.config.get('scoring_method', 'weighted_average'),
                    'normalization_enabled': self.config.get('normalization_enabled', True)
                }
            ),
            'response_generator': ResponseGenerationAgent(
                config={
                    **agent_config,
                    'language': 'arabic'
                }
            )
        }
        
        self.logger.info(f"Initialized {len(agents)} specialized agents")
        return agents
    
    async def evaluate_tender(self, terms_file, proposal_files: List, top_n: int) -> WorkflowResult:
        """
        Main entry point for tender evaluation using the multi-agent system
        
        Args:
            terms_file: PDF file containing terms and specifications
            proposal_files: List of proposal PDF files
            top_n: Number of top companies to select
            
        Returns:
            WorkflowResult containing the evaluation results
        """
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        
        self.logger.info(f"Starting tender evaluation workflow {workflow_id}")
        
        # Initialize workflow tracking
        workflow_result = WorkflowResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            agent_results={},
            metadata={
                'start_time': start_time,
                'terms_file': getattr(terms_file, 'filename', 'unknown'),
                'proposal_count': len(proposal_files),
                'top_n': top_n
            }
        )
        
        self.active_workflows[workflow_id] = workflow_result
        
        try:
            # Execute the evaluation workflow
            result = await self._execute_evaluation_workflow(
                workflow_id, terms_file, proposal_files, top_n
            )
            
            # Update workflow result
            workflow_result.status = WorkflowStatus.COMPLETED
            workflow_result.final_result = result
            workflow_result.processing_time = time.time() - start_time
            
            # Update metrics
            self.total_workflows_processed += 1
            self.total_processing_time += workflow_result.processing_time
            self.success_count += 1
            
            self.logger.info(f"Workflow {workflow_id} completed successfully in {workflow_result.processing_time:.2f}s")
            
        except Exception as e:
            # Handle workflow failure
            workflow_result.status = WorkflowStatus.FAILED
            workflow_result.error_message = str(e)
            workflow_result.processing_time = time.time() - start_time
            
            self.failure_count += 1
            self.logger.error(f"Workflow {workflow_id} failed: {e}", exc_info=True)
        
        finally:
            # Move to completed workflows
            self.active_workflows.pop(workflow_id, None)
            self.completed_workflows.append(workflow_result)
            
            # Keep only last 100 completed workflows
            if len(self.completed_workflows) > 100:
                self.completed_workflows = self.completed_workflows[-100:]
        
        return workflow_result
    
    async def _execute_evaluation_workflow(self, workflow_id: str, terms_file, 
                                         proposal_files: List, top_n: int) -> Dict[str, Any]:
        """Execute the complete evaluation workflow using specialized agents"""
        
        # Phase 1: PDF Processing
        self.logger.info(f"[{workflow_id}] Phase 1: PDF Processing")
        pdf_results = await self._phase_pdf_processing(terms_file, proposal_files)
        
        # Phase 2: Criteria Detection
        self.logger.info(f"[{workflow_id}] Phase 2: Criteria Detection")
        criteria_results = await self._phase_criteria_detection(pdf_results['terms_text'])
        
        # Phase 3: Proposal Analysis
        self.logger.info(f"[{workflow_id}] Phase 3: Proposal Analysis")
        analysis_results = await self._phase_proposal_analysis(
            pdf_results['proposals'], criteria_results['criteria']
        )
        
        # Phase 4: Scoring and Ranking
        self.logger.info(f"[{workflow_id}] Phase 4: Scoring and Ranking")
        scoring_results = await self._phase_scoring_and_ranking(
            analysis_results['successful_analyses'], criteria_results['criteria'], top_n
        )
          # Phase 5: Response Generation
        self.logger.info(f"[{workflow_id}] Phase 5: Response Generation")
        final_response = await self._phase_response_generation(
            scoring_results['chosen'], scoring_results['not_chosen'], 
            analysis_results, criteria_results['criteria']
        )
        
        return final_response['final_response']
    
    async def _phase_pdf_processing(self, terms_file, proposal_files: List) -> Dict[str, Any]:
        """Phase 1: Process all PDF files to extract text"""
        
        # Process terms PDF
        terms_task = AgentTask(
            task_id=f"terms_{uuid.uuid4().hex[:8]}",
            agent_type="pdf_processor",
            input_data={
                'task_type': 'extract_terms',
                'pdf_file': terms_file
            }
        )
        
        terms_result = await self.agents['pdf_processor'].execute_task(terms_task)
        
        if terms_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Terms PDF processing failed: {terms_result.error_message}")
        
        # Process proposal PDFs
        proposals_task = AgentTask(
            task_id=f"proposals_{uuid.uuid4().hex[:8]}",
            agent_type="pdf_processor",
            input_data={
                'task_type': 'extract_proposals',
                'proposals': proposal_files
            }
        )
        
        proposals_result = await self.agents['pdf_processor'].execute_task(proposals_task)
        
        if proposals_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Proposals PDF processing failed: {proposals_result.error_message}")
        
        # Validate we have enough successful extractions
        successful_proposals = proposals_result.output_data['successful_extractions']
        if not successful_proposals:
            raise Exception("No proposal PDFs could be processed successfully")
        
        return {
            'terms_text': terms_result.output_data['text'],
            'proposals': successful_proposals,
            'failed_proposals': proposals_result.output_data['failed_extractions']
        }
    
    async def _phase_criteria_detection(self, terms_text: str) -> Dict[str, Any]:
        """Phase 2: Detect evaluation criteria from terms document"""
        
        criteria_task = AgentTask(
            task_id=f"criteria_{uuid.uuid4().hex[:8]}",
            agent_type="criteria_detector",
            input_data={
                'task_type': 'extract_criteria',
                'terms_text': terms_text
            }
        )
        
        criteria_result = await self.agents['criteria_detector'].execute_task(criteria_task)
        
        if criteria_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Criteria detection failed: {criteria_result.error_message}")
        
        criteria = criteria_result.output_data['criteria']
        if not criteria:
            raise Exception("No evaluation criteria could be extracted")
        
        # Validate criteria
        validation_task = AgentTask(
            task_id=f"validation_{uuid.uuid4().hex[:8]}",
            agent_type="criteria_detector",
            input_data={
                'task_type': 'validate_criteria',
                'criteria': criteria
            }
        )
        
        validation_result = await self.agents['criteria_detector'].execute_task(validation_task)
        
        return {
            'criteria': criteria,
            'detection_method': criteria_result.output_data['detection_method'],
            'validation_result': validation_result.output_data
        }
    
    async def _phase_proposal_analysis(self, proposals: List[Dict], criteria: List[Dict]) -> Dict[str, Any]:
        """Phase 3: Analyze all proposals against criteria"""
        
        analysis_task = AgentTask(
            task_id=f"analysis_{uuid.uuid4().hex[:8]}",
            agent_type="proposal_analyzer",
            input_data={
                'task_type': 'analyze_batch_proposals',
                'proposals': proposals,
                'criteria': criteria
            }
        )
        
        analysis_result = await self.agents['proposal_analyzer'].execute_task(analysis_task)
        
        if analysis_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Proposal analysis failed: {analysis_result.error_message}")
        
        successful_analyses = analysis_result.output_data['successful_analyses']
        if not successful_analyses:
            raise Exception("No proposals could be analyzed successfully")
        
        return analysis_result.output_data
    
    async def _phase_scoring_and_ranking(self, analyses: List[Dict], criteria: List[Dict], 
                                       top_n: int) -> Dict[str, Any]:
        """Phase 4: Calculate scores and rank companies"""
        
        # Calculate total scores
        scoring_task = AgentTask(
            task_id=f"scoring_{uuid.uuid4().hex[:8]}",
            agent_type="scorer",
            input_data={
                'task_type': 'calculate_scores',
                'analyses': analyses,
                'criteria': criteria
            }
        )
        
        scoring_result = await self.agents['scorer'].execute_task(scoring_task)
        
        if scoring_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Scoring failed: {scoring_result.error_message}")
        
        # Rank companies
        ranking_task = AgentTask(
            task_id=f"ranking_{uuid.uuid4().hex[:8]}",
            agent_type="scorer",
            input_data={
                'task_type': 'rank_companies',
                'company_scores': scoring_result.output_data['company_scores'],
                'top_n': top_n
            }
        )
        ranking_result = await self.agents['scorer'].execute_task(ranking_task)
        
        if ranking_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Ranking failed: {ranking_result.error_message}")
        
        return ranking_result.output_data
    
    async def _phase_response_generation(self, chosen: List[Dict], not_chosen: List[Dict], 
                                       analysis_data: Dict, criteria: List[Dict]) -> Dict[str, Any]:
        """Phase 5: Generate final formatted response"""
        
        response_task = AgentTask(
            task_id=f"response_{uuid.uuid4().hex[:8]}",
            agent_type="response_generator",
            input_data={
                'task_type': 'generate_final_response',
                'chosen': chosen,
                'not_chosen': not_chosen,
                'analysis_data': analysis_data,
                'criteria': criteria
            }
        )
        
        response_result = await self.agents['response_generator'].execute_task(response_task)
        
        if response_result.status != AgentStatus.COMPLETED:
            raise Exception(f"Response generation failed: {response_result.error_message}")
        
        return response_result.output_data
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all agents"""
        metrics = {
            'manager_metrics': {
                'total_workflows_processed': self.total_workflows_processed,
                'total_processing_time': self.total_processing_time,
                'average_processing_time': (
                    self.total_processing_time / self.total_workflows_processed
                    if self.total_workflows_processed > 0 else 0
                ),
                'success_count': self.success_count,
                'failure_count': self.failure_count,
                'success_rate': (
                    self.success_count / max(self.total_workflows_processed, 1)
                ),
                'active_workflows': len(self.active_workflows)
            },
            'agent_metrics': {}
        }
        
        # Get metrics from each agent
        for agent_name, agent in self.agents.items():
            metrics['agent_metrics'][agent_name] = agent.get_metrics()
        
        return metrics
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Get the status of a specific workflow"""
        # Check active workflows
        if workflow_id in self.active_workflows:
            return self.active_workflows[workflow_id]
        
        # Check completed workflows
        for workflow in self.completed_workflows:
            if workflow.workflow_id == workflow_id:
                return workflow
        
        return None
    
    def get_recent_workflows(self, limit: int = 10) -> List[WorkflowResult]:
        """Get recent workflow results"""
        all_workflows = []
        all_workflows.extend(self.active_workflows.values())
        all_workflows.extend(self.completed_workflows)
        
        # Sort by start time (most recent first)
        all_workflows.sort(
            key=lambda w: w.metadata.get('start_time', 0) if w.metadata else 0,
            reverse=True
        )
        
        return all_workflows[:limit]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on all agents"""
        health_status = {
            'manager_status': 'healthy',
            'llm_connection': 'unknown',
            'agent_health': {},
            'total_agents': len(self.agents),
            'healthy_agents': 0
        }
        
        # Test LLM connection
        try:
            test_response = self.llm.invoke("مرحبا")
            health_status['llm_connection'] = 'connected'
        except Exception as e:
            health_status['llm_connection'] = f'error: {str(e)}'
            health_status['manager_status'] = 'degraded'
        
        # Check each agent
        for agent_name, agent in self.agents.items():
            try:
                # Simple health check - verify agent can get capabilities
                capabilities = agent.get_capabilities()
                metrics = agent.get_metrics()
                
                agent_health = {
                    'status': 'healthy',
                    'capabilities_count': len(capabilities),
                    'error_rate': metrics.get('error_rate', 0),
                    'current_status': agent.status.value
                }
                
                if metrics.get('error_rate', 0) > 0.5:  # High error rate
                    agent_health['status'] = 'degraded'
                
                health_status['agent_health'][agent_name] = agent_health
                
                if agent_health['status'] == 'healthy':
                    health_status['healthy_agents'] += 1
                    
            except Exception as e:
                health_status['agent_health'][agent_name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Overall health assessment
        healthy_ratio = health_status['healthy_agents'] / health_status['total_agents']
        if healthy_ratio < 0.8:
            health_status['manager_status'] = 'degraded'
        elif health_status['llm_connection'] != 'connected':
            health_status['manager_status'] = 'degraded'
        
        return health_status
    
    def reset_metrics(self):
        """Reset all performance metrics"""
        self.total_workflows_processed = 0
        self.total_processing_time = 0.0
        self.success_count = 0
        self.failure_count = 0
        
        # Reset agent metrics
        for agent in self.agents.values():
            agent.reset_metrics()
        
        self.logger.info("All metrics have been reset")
    
    def shutdown(self):
        """Gracefully shutdown the agent manager"""
        self.logger.info("Shutting down Agent Manager")
        
        # Log final metrics
        metrics = self.get_agent_metrics()
        self.logger.info(f"Final metrics: {metrics['manager_metrics']}")
        
        # Clear workflows
        self.active_workflows.clear()
        self.completed_workflows.clear()
