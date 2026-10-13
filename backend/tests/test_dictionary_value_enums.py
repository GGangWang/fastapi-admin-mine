"""Enum-backed dictionary values retain the existing public dictionary contract."""

import json
from dataclasses import asdict
from pathlib import Path

from app.common.dict_values import BooleanValue, DataScope, MenuType, StorageProtocol, TicketStatus
from app.common.enums import TicketTypeEnum
from app.modules.system.dict.registry import REGISTRY


def test_dictionary_values_labels_styles_and_order_are_unchanged():
    expected = json.loads((Path(__file__).parent / "fixtures/dictionary_values_before_refactor.json").read_text(encoding="utf-8"))
    from app.modules.system.dict.constants import DictType

    for name, items in expected.items():
        definition = REGISTRY.definitions[DictType[name]]
        assert len(definition.items) == len(items), name
        for actual, old in zip(definition.items, items, strict=True):
            fields = asdict(actual)
            assert type(actual.code) is type(old["code"]), name
            assert {key: fields[key] for key in old} == old, name


def test_business_enums_preserve_numeric_boolean_and_storage_identity():
    from app.modules.task.storage.core.base import StorageProtocol as AdapterProtocol

    assert AdapterProtocol is StorageProtocol
    assert StorageProtocol.FTP.value == "ftp"
    assert TicketStatus.PENDING == 0
    assert DataScope.ALL == 3
    assert MenuType.MENU == 2
    assert BooleanValue.FALSE.value is False
    assert TicketTypeEnum.BUG.value == "bug"


def test_ticket_state_transitions_use_shared_enum_values():
    from app.modules.system.ticket.service import _TICKET_STATUS_TRANSITIONS

    assert _TICKET_STATUS_TRANSITIONS[TicketStatus.PENDING] == {TicketStatus.PROCESSING, TicketStatus.CLOSED}
    assert _TICKET_STATUS_TRANSITIONS[TicketStatus.CLOSED] == {TicketStatus.PENDING}
