from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass

from posejdon.detectors.regex_support import build_entity_id
from posejdon.domain.entities import MentionProvenance, SensitiveEntity

PERSON_SEED_BLOCKLIST = frozenset({"pan", "pana", "pani", "panu"})


@dataclass(frozen=True, slots=True)
class PersonMentionCluster:
    cluster_id: str
    canonical_entity: SensitiveEntity
    members: tuple[SensitiveEntity, ...]
    first_name: str
    surname: str
    first_key: str
    surname_key: str


@dataclass(frozen=True, slots=True)
class PersonMentionVariant:
    cluster: PersonMentionCluster
    surface: str
    rule: str
    contextual: bool = False


def expand_person_mentions(text: str, entities: list[SensitiveEntity]) -> list[SensitiveEntity]:
    clusters = _cluster_person_entities(entities)
    if not clusters:
        return entities

    variants = _person_mention_variants(clusters)
    occupied = [
        (entity.start_offset, entity.end_offset)
        for entity in entities
        if entity.start_offset is not None and entity.end_offset is not None
    ]
    expanded: list[SensitiveEntity] = []

    for variant in variants:
        pattern = (
            _contextual_person_alias_pattern(variant.surface)
            if variant.contextual
            else _mention_surface_pattern(variant.surface)
        )
        if pattern is None:
            continue
        for match in pattern.finditer(text):
            if variant.contextual:
                raw_text = match.group("alias")
                start_offset = match.start("alias")
                end_offset = match.end("alias")
            else:
                raw_text = match.group(0)
                start_offset = match.start()
                end_offset = match.end()
            if _overlaps(occupied, start_offset=start_offset, end_offset=end_offset):
                continue

            entity = _build_mention_entity(
                variant=variant,
                raw_text=raw_text,
                start_offset=start_offset,
                end_offset=end_offset,
            )
            expanded.append(entity)
            occupied.append((start_offset, end_offset))

    if not expanded:
        return entities
    return sorted(
        [*entities, *expanded],
        key=lambda item: (item.start_offset or 0, item.end_offset or 0),
    )


def _cluster_person_entities(entities: list[SensitiveEntity]) -> list[PersonMentionCluster]:
    grouped: dict[tuple[str, str], list[tuple[SensitiveEntity, str, str]]] = defaultdict(list)
    for entity in entities:
        if entity.entity_type != "PERSON":
            continue
        if entity.mention_provenance() is not None:
            continue
        parts = _split_canonical_person_name(entity.raw_text)
        if parts is None:
            continue
        first_name, surname = parts
        if first_name.casefold() in PERSON_SEED_BLOCKLIST:
            continue
        first_key = _normalize_person_first_name_key(
            first_name,
            masculine_hint=_looks_like_masculine_surname(surname),
        )
        surname_key = _normalize_person_surname_key(surname)
        grouped[(first_key, surname_key)].append((entity, first_name, surname))

    clusters: list[PersonMentionCluster] = []
    for (first_key, surname_key), members in grouped.items():
        canonical, first_name, surname = max(
            members,
            key=lambda item: (
                int(item[0].metadata.get("support_count", "1")),
                item[0].confidence,
                -(item[0].start_offset or 0),
                -(item[0].end_offset or 0),
            ),
        )
        clusters.append(
            PersonMentionCluster(
                cluster_id=_person_cluster_id(f"{first_key}|{surname_key}"),
                canonical_entity=canonical,
                members=tuple(item[0] for item in members),
                first_name=first_name,
                surname=surname,
                first_key=first_key,
                surname_key=surname_key,
            )
        )
    return clusters


def _person_mention_variants(clusters: list[PersonMentionCluster]) -> list[PersonMentionVariant]:
    first_name_counts: dict[str, int] = defaultdict(int)
    surname_counts: dict[str, int] = defaultdict(int)
    initial_surname_counts: dict[str, int] = defaultdict(int)
    for cluster in clusters:
        first_name_counts[cluster.first_key] += 1
        surname_counts[cluster.surname_key] += 1
        initial_surname_counts[_initial_surname_key(cluster.first_name, cluster.surname)] += 1

    variants: list[PersonMentionVariant] = []
    for cluster in clusters:
        variants.extend(
            PersonMentionVariant(cluster=cluster, surface=member.raw_text, rule="full_name_repeat")
            for member in cluster.members
        )
        if first_name_counts[cluster.first_key] == 1:
            variants.extend(
                PersonMentionVariant(cluster=cluster, surface=surface, rule=rule)
                for rule, surface in _first_name_variants(cluster.first_name).items()
            )
            variants.append(
                PersonMentionVariant(
                    cluster=cluster,
                    surface=cluster.first_name,
                    rule="contextual_account_phone_first_name",
                    contextual=True,
                )
            )
        if surname_counts[cluster.surname_key] == 1:
            surname_variants = _surname_variants(cluster.surname)
            variants.extend(
                PersonMentionVariant(cluster=cluster, surface=surface, rule=rule)
                for rule, surface in surname_variants.items()
            )
            variants.extend(
                PersonMentionVariant(cluster=cluster, surface=surface, rule=rule)
                for rule, surface in _honorific_variants(cluster.surname, surname_variants).items()
            )
        if initial_surname_counts[_initial_surname_key(cluster.first_name, cluster.surname)] == 1:
            variants.extend(
                PersonMentionVariant(cluster=cluster, surface=surface, rule=rule)
                for rule, surface in _initial_surname_variants(
                    cluster.first_name,
                    cluster.surname,
                ).items()
            )

    deduped: dict[tuple[str, str, bool], PersonMentionVariant] = {}
    for variant in sorted(
        variants,
        key=lambda item: (-len(item.surface), item.rule, item.cluster.cluster_id),
    ):
        deduped.setdefault(
            (variant.cluster.cluster_id, variant.surface, variant.contextual),
            variant,
        )
    return list(deduped.values())


def _build_mention_entity(
    *,
    variant: PersonMentionVariant,
    raw_text: str,
    start_offset: int,
    end_offset: int,
) -> SensitiveEntity:
    seed = variant.cluster.canonical_entity
    entity_id = build_entity_id(
        entity_type="PERSON",
        normalized_text=f"{variant.cluster.cluster_id}|{raw_text}",
        start_offset=start_offset,
        end_offset=end_offset,
    )
    provenance = MentionProvenance(
        canonical_entity_id=seed.entity_id,
        mention_cluster_id=variant.cluster.cluster_id,
        derived_from=seed.entity_id,
        mention_source="memory",
        mention_rule=variant.rule,
    )
    return SensitiveEntity(
        entity_id=entity_id,
        entity_type="PERSON",
        raw_text=raw_text,
        normalized_text=raw_text.strip(),
        confidence=max(seed.confidence, 0.95),
        source_detector="mention_memory",
        start_offset=start_offset,
        end_offset=end_offset,
        metadata={
            "support_count": seed.metadata.get("support_count", "1"),
            "supporting_detectors": seed.metadata.get("supporting_detectors", seed.source_detector),
        },
    ).with_mention_provenance(provenance)


def _split_canonical_person_name(text: str) -> tuple[str, str] | None:
    parts = [part for part in " ".join(text.split()).split(" ") if part]
    if len(parts) != 2:
        return None
    if any(not part.replace("-", "").isalpha() for part in parts):
        return None
    return parts[0], parts[1]


def _normalize_person_first_name_key(first_name: str, *, masculine_hint: bool) -> str:
    lowered = first_name.casefold()
    if masculine_hint:
        if lowered.endswith("wła"):
            return f"{lowered[:-3]}weł"
        if lowered.endswith("włem"):
            return f"{lowered[:-4]}weł"
        if lowered.endswith("owi"):
            return lowered[:-3]
        if lowered.endswith("em"):
            return lowered[:-2]
        if lowered.endswith("a"):
            return lowered[:-1]
        return lowered
    if lowered.endswith(("ą", "ę")):
        return f"{lowered[:-1]}a"
    if lowered.endswith("ie"):
        return f"{lowered[:-2]}a"
    if lowered.endswith("y"):
        return f"{lowered[:-1]}a"
    return lowered


def _normalize_person_surname_key(surname: str) -> str:
    lowered = surname.casefold()
    suffix_rules = {
        "skiego": "ski",
        "skiemu": "ski",
        "skim": "ski",
        "ckiego": "cki",
        "ckiemu": "cki",
        "ckim": "cki",
        "dzkiego": "dzki",
        "dzkiemu": "dzki",
        "dzkim": "dzki",
    }
    for suffix, replacement in suffix_rules.items():
        if lowered.endswith(suffix):
            return f"{lowered[: -len(suffix)]}{replacement}"
    return lowered


def _first_name_variants(first_name: str) -> dict[str, str]:
    variants = {"first_name_exact_unique": first_name}
    if first_name.endswith("a"):
        stem = first_name[:-1]
        variants["first_name_genitive_feminine"] = f"{stem}y"
        variants["first_name_dative_feminine"] = f"{stem}ie"
        variants["first_name_accusative_feminine"] = f"{stem}ę"
        return variants
    lowered = first_name.casefold()
    if lowered.endswith("eł"):
        stem = first_name[:-2]
        variants["first_name_genitive_el"] = f"{stem}ła"
        variants["first_name_dative_el"] = f"{stem}łowi"
        variants["first_name_instrumental_el"] = f"{stem}łem"
        return variants
    if lowered.endswith("ek"):
        return variants
    variants["first_name_genitive_simple"] = f"{first_name}a"
    variants["first_name_dative_simple"] = f"{first_name}owi"
    variants["first_name_instrumental_simple"] = f"{first_name}em"
    return variants


def _surname_variants(surname: str) -> dict[str, str]:
    variants = {"surname_exact_unique": surname}
    lowered = surname.casefold()
    if lowered.endswith(("ski", "cki", "dzki")):
        stem = surname[:-1]
        variants["surname_genitive_ski"] = f"{surname}ego"
        variants["surname_dative_ski"] = f"{surname}emu"
        variants["surname_instrumental_ski"] = f"{stem}im"
    return variants


def _honorific_variants(surname: str, surname_variants: dict[str, str]) -> dict[str, str]:
    variants = {
        "honorific_pan_surname_unique": f"pan {surname}",
        "honorific_pan_surname_unique_title": f"Pan {surname}",
    }
    dative = surname_variants.get("surname_dative_ski")
    if dative is not None:
        variants["honorific_panu_surname_dative_ski"] = f"panu {dative}"
        variants["honorific_panu_surname_dative_ski_title"] = f"Panu {dative}"
    return variants


def _initial_surname_variants(first_name: str, surname: str) -> dict[str, str]:
    if not first_name or not surname:
        return {}
    return {
        "person_initial_surname_unique": f"{first_name[:1].upper()}. {surname}",
    }


def _mention_surface_pattern(text: str) -> re.Pattern[str] | None:
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    parts = cleaned.split(" ")
    if any(not any(char.isalpha() for char in part) for part in parts):
        return None
    escaped = [re.escape(part) for part in parts]
    return re.compile(r"(?<!\w)" + r"\s+".join(escaped) + r"(?!\w)")


def _contextual_person_alias_pattern(text: str) -> re.Pattern[str] | None:
    cleaned = " ".join(text.split())
    if not cleaned or not cleaned.replace("-", "").isalpha():
        return None
    return re.compile(
        r"(?i)(?<!\w)(?:konto|telefon|telefo)\s+(?P<alias>" + re.escape(cleaned) + r")(?!\w)"
    )


def _overlaps(
    occupied: list[tuple[int | None, int | None]],
    *,
    start_offset: int,
    end_offset: int,
) -> bool:
    for existing_start, existing_end in occupied:
        if existing_start is None or existing_end is None:
            continue
        if not (existing_end <= start_offset or end_offset <= existing_start):
            return True
    return False


def _looks_like_masculine_surname(surname: str) -> bool:
    lowered = surname.casefold()
    return lowered.endswith(("ski", "cki", "dzki", "skiego", "skiemu", "ckiego", "ckiemu"))


def _initial_surname_key(first_name: str, surname: str) -> str:
    return hashlib.sha1(
        f"{first_name[:1].casefold()}|{_normalize_person_surname_key(surname)}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]


def _person_cluster_id(normalized_person_text: str) -> str:
    digest = hashlib.sha1(
        f"person_cluster|{normalized_person_text.strip().casefold()}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"person-cluster-{digest}"
