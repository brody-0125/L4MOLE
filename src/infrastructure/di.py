
from injector import Injector, Module, provider, singleton

from ..presentation.app_service import ApplicationService


class ApplicationModule(Module):

    def __init__(
        self,
        metadata_db_path: str = "./metadata.db",
        vector_db_path: str = "./milvus_lite.db",
    ) -> None:
        self._metadata_db_path = metadata_db_path
        self._vector_db_path = vector_db_path

    @singleton
    @provider
    def provide_application_service(self) -> ApplicationService:
        return ApplicationService(
            metadata_db_path=self._metadata_db_path,
            vector_db_path=self._vector_db_path,
        )


class AppInjector:

    _instance: "AppInjector | None" = None

    def __init__(
        self,
        metadata_db_path: str = "./metadata.db",
        vector_db_path: str = "./milvus_lite.db",
    ) -> None:
        self._module = ApplicationModule(
            metadata_db_path=metadata_db_path,
            vector_db_path=vector_db_path,
        )
        self._injector = Injector([self._module])
        self._app_service: ApplicationService | None = None

    @classmethod
    def get_instance(
        cls,
        metadata_db_path: str = "./metadata.db",
        vector_db_path: str = "./milvus_lite.db",
    ) -> "AppInjector":
        if cls._instance is None:
            cls._instance = cls(
                metadata_db_path=metadata_db_path,
                vector_db_path=vector_db_path,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None

    def get(self, cls: type) -> object:
        return self._injector.get(cls)

    def get_app_service(self) -> ApplicationService:
        if self._app_service is None:
            self._app_service = self._injector.get(ApplicationService)
        return self._app_service

    def close(self) -> None:
        if self._app_service is not None:
            self._app_service.close()
            self._app_service = None


__all__ = ["AppInjector", "ApplicationModule"]
