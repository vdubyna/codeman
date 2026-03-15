"""Helpers for resolving retrieval-profile selectors consistently."""

from __future__ import annotations

from codeman.application.ports.retrieval_profile_store_port import (
    RetrievalStrategyProfileStorePort,
)
from codeman.config.profile_errors import (
    RetrievalStrategyProfileAmbiguousError,
    RetrievalStrategyProfileNotFoundError,
)
from codeman.contracts.configuration import RetrievalStrategyProfileRecord


def resolve_retrieval_strategy_profile_selector(
    store: RetrievalStrategyProfileStorePort,
    selector: str,
) -> RetrievalStrategyProfileRecord:
    """Resolve one selector against exact-name and exact-id matches."""

    name_match = store.get_by_name(selector)
    id_matches = store.list_by_profile_id(selector)

    distinct_matches: dict[tuple[str, str], RetrievalStrategyProfileRecord] = {}
    if name_match is not None:
        distinct_matches[(name_match.name, name_match.profile_id)] = name_match
    for match in id_matches:
        distinct_matches[(match.name, match.profile_id)] = match

    if not distinct_matches:
        raise RetrievalStrategyProfileNotFoundError(
            f"Retrieval strategy profile was not found: {selector}",
            details={"selector": selector},
        )

    if len(distinct_matches) > 1:
        raise RetrievalStrategyProfileAmbiguousError(
            f"Retrieval strategy profile selector is ambiguous: {selector}",
            details={
                "selector": selector,
                "matches": [
                    {"name": match.name, "profile_id": match.profile_id}
                    for match in distinct_matches.values()
                ],
            },
        )

    return next(iter(distinct_matches.values()))
