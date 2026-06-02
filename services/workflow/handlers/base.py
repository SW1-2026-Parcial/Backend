from abc import ABC, abstractmethod
from services.workflow.workflow_context import WorkflowContext
from services.workflow.handler_result import HandlerResult


class NodeHandler(ABC):
    @abstractmethod
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        """Procesa el nodo y retorna HandlerResult indicando qué debe hacer el motor."""
