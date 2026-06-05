from abc import ABC, abstractmethod
from modules.engine.workflow.workflow_context import WorkflowContext
from modules.engine.workflow.handler_result import HandlerResult


class NodeHandler(ABC):
    @abstractmethod
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        """Procesa el nodo y retorna HandlerResult indicando qué debe hacer el motor."""
