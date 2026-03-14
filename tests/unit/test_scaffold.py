from codeman.bootstrap import BootstrapContainer, bootstrap
from codeman.config.models import AppConfig, RuntimeConfig
from codeman.contracts.common import CommandMeta, SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope


def test_bootstrap_returns_container_with_config_and_runtime_paths() -> None:
    container = bootstrap()

    assert isinstance(container, BootstrapContainer)
    assert isinstance(container.config, AppConfig)
    assert container.runtime_paths.root.name == ".codeman"


def test_contract_placeholders_use_expected_envelopes() -> None:
    success = SuccessEnvelope(data={"command": "repo"}, meta=CommandMeta(command="repo"))
    failure = FailureEnvelope(error=ErrorDetail(code="boom", message="Boom"))

    assert success.ok is True
    assert success.meta.command == "repo"
    assert failure.ok is False
    assert failure.error.code == "boom"
    assert isinstance(RuntimeConfig(), RuntimeConfig)
