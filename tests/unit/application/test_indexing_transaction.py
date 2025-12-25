
from src.application.services.indexing_transaction import (
    IndexingTransaction,
    TransactionResult,
    TransactionState,
)

class TestIndexingTransaction:

    def test_successful_transaction(self):
        executed_steps = []

        tx = IndexingTransaction("Test transaction")
        tx.add_step(
            name="Step 1",
            execute=lambda: executed_steps.append("step1"),
            compensate=lambda: executed_steps.append("compensate1"),
        )
        tx.add_step(
            name="Step 2",
            execute=lambda: executed_steps.append("step2"),
            compensate=lambda: executed_steps.append("compensate2"),
        )
        tx.add_step(
            name="Step 3",
            execute=lambda: executed_steps.append("step3"),
            compensate=lambda: executed_steps.append("compensate3"),
        )

        result = tx.execute()

        assert result.success is True
        assert result.state == TransactionState.COMMITTED
        assert result.completed_steps == 3
        assert result.total_steps == 3
        assert executed_steps == ["step1", "step2", "step3"]

    def test_transaction_rollback_on_failure(self):
        executed_steps = []

        tx = IndexingTransaction("Failing transaction")
        tx.add_step(
            name="Step 1",
            execute=lambda: executed_steps.append("step1"),
            compensate=lambda: executed_steps.append("compensate1"),
        )
        tx.add_step(
            name="Step 2",
            execute=lambda: executed_steps.append("step2"),
            compensate=lambda: executed_steps.append("compensate2"),
        )
        tx.add_step(
            name="Step 3 (fails)",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("Simulated failure")),
            compensate=lambda: executed_steps.append("compensate3"),
        )

        result = tx.execute()

        assert result.success is False
        assert result.state == TransactionState.ROLLED_BACK
        assert result.completed_steps == 2
        assert "Simulated failure" in result.error
        assert executed_steps == ["step1", "step2", "compensate3", "compensate2", "compensate1"]

    def test_rollback_on_first_step_failure(self):
        executed_steps = []

        tx = IndexingTransaction("First step fails")
        tx.add_step(
            name="Step 1 (fails)",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("First step failed")),
            compensate=lambda: executed_steps.append("compensate1"),
        )
        tx.add_step(
            name="Step 2",
            execute=lambda: executed_steps.append("step2"),
            compensate=lambda: executed_steps.append("compensate2"),
        )

        result = tx.execute()

        assert result.success is False
        assert result.state == TransactionState.ROLLED_BACK
        assert result.completed_steps == 0
        assert executed_steps == ["compensate1"]

    def test_rollback_continues_on_compensation_failure(self):
        executed_steps = []

        def failing_compensate():
            executed_steps.append("compensate2_started")
            raise RuntimeError("Compensation failed")

        tx = IndexingTransaction("Compensation fails")
        tx.add_step(
            name="Step 1",
            execute=lambda: executed_steps.append("step1"),
            compensate=lambda: executed_steps.append("compensate1"),
        )
        tx.add_step(
            name="Step 2",
            execute=lambda: executed_steps.append("step2"),
            compensate=failing_compensate,
        )
        tx.add_step(
            name="Step 3 (fails)",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("Step failed")),
            compensate=lambda: executed_steps.append("compensate3"),
        )

        result = tx.execute()

        assert result.success is False
        assert "compensate2_started" in executed_steps
        assert "compensate1" in executed_steps

    def test_step_without_compensation(self):
        executed_steps = []

        tx = IndexingTransaction("No compensation")
        tx.add_step(
            name="Step 1",
            execute=lambda: executed_steps.append("step1"),
        )
        tx.add_step(
            name="Step 2 (fails)",
            execute=lambda: (_ for _ in ()).throw(RuntimeError("Step failed")),
        )

        result = tx.execute()

        assert result.success is False
        assert executed_steps == ["step1"]

    def test_step_result_captured(self):
        tx = IndexingTransaction("Results test")
        tx.add_step(
            name="Step 1",
            execute=lambda: "result1",
        )
        tx.add_step(
            name="Step 2",
            execute=lambda: {"key": "value"},
        )
        tx.add_step(
            name="Step 3",
            execute=lambda: 42,
        )

        result = tx.execute()

        assert result.success is True
        assert result.step_results == ["result1", {"key": "value"}, 42]

    def test_cannot_execute_twice(self):
        tx = IndexingTransaction("Double execution")
        tx.add_step(name="Step 1", execute=lambda: None)

        result1 = tx.execute()
        result2 = tx.execute()

        assert result1.success is True
        assert result2.success is False
        assert "already executed" in result2.error

    def test_method_chaining(self):
        tx = IndexingTransaction("Chaining test")

        result = (
            tx.add_step(name="Step 1", execute=lambda: 1)
            .add_step(name="Step 2", execute=lambda: 2)
            .add_step(name="Step 3", execute=lambda: 3)
            .execute()
        )

        assert result.success is True
        assert result.completed_steps == 3

class TestTransactionIntegrationScenarios:

    def test_indexing_scenario_success(self):
        vector_store = []
        chunks_db = []
        file_status = {"status": "pending"}

        tx = IndexingTransaction("Index document.txt")

        tx.add_step(
            name="Insert vectors",
            execute=lambda: vector_store.extend(["v1", "v2", "v3"]),
            compensate=lambda: vector_store.clear(),
        )

        tx.add_step(
            name="Save chunks",
            execute=lambda: chunks_db.extend(["c1", "c2", "c3"]),
            compensate=lambda: chunks_db.clear(),
        )

        tx.add_step(
            name="Update file status",
            execute=lambda: file_status.update({"status": "indexed"}),
            compensate=lambda: file_status.update({"status": "pending"}),
        )

        result = tx.execute()

        assert result.success is True
        assert vector_store == ["v1", "v2", "v3"]
        assert chunks_db == ["c1", "c2", "c3"]
        assert file_status["status"] == "indexed"

    def test_indexing_scenario_chunk_save_failure(self):
        vector_store = []
        chunks_db = []
        file_status = {"status": "pending"}

        tx = IndexingTransaction("Index with chunk failure")

        tx.add_step(
            name="Insert vectors",
            execute=lambda: vector_store.extend(["v1", "v2", "v3"]),
            compensate=lambda: vector_store.clear(),
        )

        def failing_chunk_save():
            chunks_db.append("c1")
            raise RuntimeError("Database connection lost")

        tx.add_step(
            name="Save chunks (fails)",
            execute=failing_chunk_save,
            compensate=lambda: chunks_db.clear(),
        )

        tx.add_step(
            name="Update file status",
            execute=lambda: file_status.update({"status": "indexed"}),
            compensate=lambda: file_status.update({"status": "pending"}),
        )

        result = tx.execute()

        assert result.success is False
        assert vector_store == []
        assert chunks_db == []
        assert file_status["status"] == "pending"

    def test_indexing_scenario_file_update_failure(self):
        vector_store = []
        chunks_db = []
        file_status = {"status": "pending"}

        tx = IndexingTransaction("Index with file update failure")

        tx.add_step(
            name="Insert vectors",
            execute=lambda: vector_store.extend(["v1", "v2"]),
            compensate=lambda: vector_store.clear(),
        )

        tx.add_step(
            name="Save chunks",
            execute=lambda: chunks_db.extend(["c1", "c2"]),
            compensate=lambda: chunks_db.clear(),
        )

        def failing_file_update():
            raise RuntimeError("Disk full")

        tx.add_step(
            name="Update file status (fails)",
            execute=failing_file_update,
            compensate=lambda: file_status.update({"status": "pending"}),
        )

        result = tx.execute()

        assert result.success is False
        assert result.state == TransactionState.ROLLED_BACK
        assert vector_store == []
        assert chunks_db == []
        assert file_status["status"] == "pending"
