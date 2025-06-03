# agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import time
import uuid

class AgentStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class AgentTask:
    """Represents a task for an agent"""
    task_id: str
    agent_type: str
    input_data: Dict[str, Any]
    priority: int = 1
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

@dataclass
class AgentResult:
    """Represents the result of an agent's work"""
    task_id: str
    agent_id: str
    status: AgentStatus
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class BaseAgent(ABC):
    """Base class for all specialized agents"""
    
    def __init__(self, agent_id: str = None, config: Dict[str, Any] = None):
        self.agent_id = agent_id or f"{self.__class__.__name__}_{uuid.uuid4().hex[:8]}"
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"agent.{self.agent_id}")
        self.current_task: Optional[AgentTask] = None
        
        # Performance metrics
        self.total_tasks_processed = 0
        self.total_processing_time = 0.0
        self.error_count = 0
        
    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a specific task. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent provides."""
        pass
    
    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a task with error handling and metrics"""
        start_time = time.time()
        self.current_task = task
        self.status = AgentStatus.PROCESSING
        
        try:
            self.logger.info(f"Starting task {task.task_id}")
            result = await self.process_task(task)
            
            result.processing_time = time.time() - start_time
            self.total_processing_time += result.processing_time
            self.total_tasks_processed += 1
            self.status = AgentStatus.COMPLETED
            
            self.logger.info(f"Completed task {task.task_id} in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            self.error_count += 1
            self.status = AgentStatus.ERROR
            error_msg = f"Task {task.task_id} failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                error_message=error_msg,
                processing_time=time.time() - start_time
            )
        finally:
            self.current_task = None
            if self.status != AgentStatus.ERROR:
                self.status = AgentStatus.IDLE
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this agent"""
        avg_processing_time = (
            self.total_processing_time / self.total_tasks_processed 
            if self.total_tasks_processed > 0 else 0
        )
        
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "total_tasks_processed": self.total_tasks_processed,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": avg_processing_time,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.total_tasks_processed, 1)
        }
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.total_tasks_processed = 0
        self.total_processing_time = 0.0
        self.error_count = 0
