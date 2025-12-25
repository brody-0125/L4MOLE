
import tempfile
import os
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.di import AppInjector, ApplicationModule


class TestApplicationModule:

    def test_module_initialization(self):
        module = ApplicationModule(
            metadata_db_path="./test_meta.db",
            vector_db_path="./test_vector.db",
        )

        assert module._metadata_db_path == "./test_meta.db"
        assert module._vector_db_path == "./test_vector.db"

    def test_module_default_paths(self):
        module = ApplicationModule()

        assert module._metadata_db_path == "./metadata.db"
        assert module._vector_db_path == "./milvus_lite.db"


class TestAppInjector:

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        AppInjector._instance = None
        yield
        if AppInjector._instance is not None:
            try:
                AppInjector._instance.close()
            except Exception:
                pass
            AppInjector._instance = None

    def test_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meta_path = os.path.join(tmpdir, "meta.db")
            vector_path = os.path.join(tmpdir, "vector.db")

            with patch(
                "src.infrastructure.di.ApplicationService"
            ) as MockAppService:
                mock_instance = MagicMock()
                MockAppService.return_value = mock_instance

                injector = AppInjector(
                    metadata_db_path=meta_path,
                    vector_db_path=vector_path,
                )

                assert injector._module is not None
                assert injector._injector is not None
                assert injector._app_service is None

    def test_get_instance_creates_singleton(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            instance1 = AppInjector.get_instance()
            instance2 = AppInjector.get_instance()

            assert instance1 is instance2

    def test_get_instance_uses_provided_paths(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            instance = AppInjector.get_instance(
                metadata_db_path="./custom_meta.db",
                vector_db_path="./custom_vector.db",
            )

            assert instance._module._metadata_db_path == "./custom_meta.db"
            assert instance._module._vector_db_path == "./custom_vector.db"

    def test_reset_instance(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            instance1 = AppInjector.get_instance()
            AppInjector.reset_instance()
            instance2 = AppInjector.get_instance()

            assert instance1 is not instance2

    def test_reset_instance_when_none(self):
        AppInjector._instance = None

        AppInjector.reset_instance()

        assert AppInjector._instance is None

    def test_get_returns_instance(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            injector = AppInjector()

            from src.presentation.app_service import ApplicationService

            result = injector.get(ApplicationService)

            assert result is not None

    def test_get_app_service_caches_result(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            injector = AppInjector()
            injector._app_service = mock_instance

            service1 = injector.get_app_service()
            service2 = injector.get_app_service()

            assert service1 is service2
            assert service1 is mock_instance

    def test_close_cleans_up_app_service(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            injector = AppInjector()
            injector._app_service = mock_instance

            injector.close()

            mock_instance.close.assert_called_once()
            assert injector._app_service is None

    def test_close_when_no_app_service(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            injector = AppInjector()

            injector.close()

            mock_instance.close.assert_not_called()


class TestAppInjectorSingleton:

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        AppInjector._instance = None
        yield
        if AppInjector._instance is not None:
            try:
                AppInjector._instance.close()
            except Exception:
                pass
            AppInjector._instance = None

    def test_singleton_pattern(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            instance1 = AppInjector.get_instance()
            instance2 = AppInjector.get_instance()

            assert instance1 is instance2
            assert AppInjector._instance is instance1

    def test_reset_closes_existing_instance(self):
        with patch(
            "src.infrastructure.di.ApplicationService"
        ) as MockAppService:
            mock_instance = MagicMock()
            MockAppService.return_value = mock_instance

            instance = AppInjector.get_instance()
            instance._app_service = mock_instance

            AppInjector.reset_instance()

            mock_instance.close.assert_called_once()
            assert AppInjector._instance is None
