from common.core.container.annotate import component
from application.port.inbound.task_handler import TaskHandler
from application.domain.tasks.task import Task, TaskType, TaskState
from application.service.file_processing_service import FileProcessingService
import injector
from common.core.logger import get_logger

logger = get_logger(__name__)

@component
class FileTaskHandler(TaskHandler):

    @injector.inject
    def __init__(self, file_processing_service: FileProcessingService):
        self.file_processing_service = file_processing_service

    async def execute(self, task: Task) -> None:
        file_entity = task.data["file_entity"]
        generator_id = task.data["generator_id"]
        return await self.file_processing_service.process_file_to_chunks(generator_id, file_entity)

    def type(self) -> str:
        return TaskType.FILE_PROCESSING.value

    def state(self) -> TaskState:
        pass

    def set_state(self, state: TaskState):
        pass

    def check_stop_flag(self) -> bool:
        pass
