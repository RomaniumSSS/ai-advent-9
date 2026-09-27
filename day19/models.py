"""Типы аргументов MCP, чтобы модель получила узкую схему draft."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Category = Literal["confirmed_described_case","possible_case","guide","opinion",
                   "advertisement","tool_news","not_relevant"]
Outcome = Literal["cases_found","no_confirmed_cases","empty_feed"]
CoverageLabel = Literal["complete_for_profile","partial","unknown"]
EvidenceRef = Literal["title","rss_excerpt"]

class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=65)
    attribution: str = Field(max_length=45)

class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str
    category: Category
    evidence_refs: list[EvidenceRef] = Field(min_length=1,max_length=3)
    summary: str = Field(max_length=120)
    metric_claims: list[Metric] = Field(max_length=1)

class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    outcome: Outcome
    coverage_label: CoverageLabel
    entries: list[Entry] = Field(max_length=20)
    proposed_text: str = Field(max_length=1024)
