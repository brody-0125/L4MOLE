
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Any

logger = logging.getLogger(__name__)

class TransactionState(Enum):

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

@dataclass
class TransactionStep:

    name: str
    execute: Callable[[], Any]
    compensate: Optional[Callable[[], None]] = None
    executed: bool = False
    result: Any = None

@dataclass
class TransactionResult:

    success: bool
    state: TransactionState
    completed_steps: int
    total_steps: int
    error: Optional[str] = None
    step_results: List[Any] = field(default_factory=list)

class IndexingTransaction:

    def __init__(self, name: str) -> None:
        self._name = name
        self._steps: List[TransactionStep] = []
        self._state = TransactionState.PENDING

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> TransactionState:
        return self._state

    def add_step(
        self,
        name: str,
        execute: Callable[[], Any],
        compensate: Optional[Callable[[], None]] = None,
    ) -> "IndexingTransaction":
        self._steps.append(
            TransactionStep(
                name=name,
                execute=execute,
                compensate=compensate,
            )
        )
        return self

    def execute(self) -> TransactionResult:
        if self._state != TransactionState.PENDING:
            return TransactionResult(
                success=False,
                state=self._state,
                completed_steps=0,
                total_steps=len(self._steps),
                error="Transaction already executed",
            )

        self._state = TransactionState.IN_PROGRESS
        logger.info("Starting transaction: %s (%d steps)", self._name, len(self._steps))

        completed_steps = 0
        step_results = []

        for i, step in enumerate(self._steps):
            try:
                logger.debug(
                    "Executing step %d/%d: %s",
                    i + 1,
                    len(self._steps),
                    step.name,
                )

                result = step.execute()
                step.result = result
                step.executed = True
                step_results.append(result)
                completed_steps += 1

                logger.debug("Step completed: %s", step.name)

            except Exception as err:
                logger.error(
                    "Step failed: %s - %s",
                    step.name,
                    err,
                )

                self._rollback(i)

                self._state = TransactionState.ROLLED_BACK
                return TransactionResult(
                    success=False,
                    state=self._state,
                    completed_steps=completed_steps,
                    total_steps=len(self._steps),
                    error=f"Step '{step.name}' failed: {err}",
                    step_results=step_results,
                )

        self._state = TransactionState.COMMITTED
        logger.info(
            "Transaction committed: %s (%d steps)",
            self._name,
            completed_steps,
        )

        return TransactionResult(
            success=True,
            state=self._state,
            completed_steps=completed_steps,
            total_steps=len(self._steps),
            step_results=step_results,
        )

    def _rollback(self, failed_step_index: int) -> None:
        logger.warning(
            "Rolling back transaction: %s (from step %d)",
            self._name,
            failed_step_index,
        )

        for i in range(failed_step_index, -1, -1):
            step = self._steps[i]

            if i < failed_step_index and not step.executed:
                continue

            if step.compensate is None:
                if i == failed_step_index:
                    logger.debug(
                        "No compensating action for failed step: %s",
                        step.name,
                    )
                else:
                    logger.warning(
                        "No compensating action for step: %s",
                        step.name,
                    )
                continue

            try:
                logger.debug("Compensating step: %s", step.name)
                step.compensate()
                logger.debug("Compensation completed: %s", step.name)

            except Exception as err:
                logger.error(
                    "Compensation failed for step '%s': %s",
                    step.name,
                    err,
                )
