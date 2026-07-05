from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from alpha_registry import AlphaRegistry
from alpha_registry_store import AlphaRegistryStore
from decay_tracker import DecayTrackerV1
from diversification_filter import DiversificationFilterV1
from promotion_engine import PromotionDemotionEngineV1
from ranking_engine import RankingEngine
from real_validation_bridge import RealValidationBridgeV1
from research_brief_generator import ResearchBriefGeneratorV1
from revalidation_scheduler import RevalidationSchedulerV1
from validation_runner import ValidationRunnerV1


class AlphaFactoryRunner:
    def __init__(self, store_base: str | Path):
        self.registry = AlphaRegistry()
        self.store = AlphaRegistryStore(store_base)
        self.validator = ValidationRunnerV1()
        self.promoter = PromotionDemotionEngineV1()
        self.decay_tracker = DecayTrackerV1()
        self.ranker = RankingEngine()
        self.diversifier = DiversificationFilterV1()
        self.scheduler = RevalidationSchedulerV1()
        self.real_validation_bridge = RealValidationBridgeV1()
        self.brief_generator = ResearchBriefGeneratorV1(Path(store_base) / 'briefs')

    def register_alphas(self, alpha_definitions: List[Dict[str, Any]]) -> None:
        for alpha in alpha_definitions:
            saved = self.registry.add_alpha_definition(alpha)
            self.store.append('alpha_definitions', saved)

    def run_validation(self, signal_candidates: List[Dict[str, Any]], observations: Dict[str, Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
        raw_scorecards = self.validator.validate_candidates(signal_candidates, observations=observations)
        ranked = self.ranker.rank(raw_scorecards)
        for row in ranked:
            saved = self.registry.record_validation_result({k: v for k, v in row.items() if k != 'regime_panels'}, regime_panels=row.get('regime_panels', []))
            self.store.append('validation_scorecards', saved)
            for panel in row.get('regime_panels', []):
                self.store.append('regime_panels', panel)
        return ranked

    def run_real_validation(self, signal_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alpha_definitions = list(self.registry.alpha_definitions.values())
        observations = self.real_validation_bridge.build_observations(alpha_definitions)
        candidate_observations: Dict[str, Dict[str, Any]] = {}
        for candidate, alpha in zip(signal_candidates, alpha_definitions):
            obs = dict(observations.get(alpha['alpha_id'], {}))
            if obs:
                candidate_observations[candidate['signal_candidate_id']] = obs
        return self.run_validation(signal_candidates[:len(candidate_observations)], observations=candidate_observations)

    def run_promotion(self, current_states: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
        current_states = current_states or {}
        alphas = list(self.registry.alpha_definitions.values())
        latest = self.registry.latest_scorecards()
        decisions = self.promoter.batch_decide(alphas, latest, current_states=current_states)
        filtered = self.diversifier.filter_decisions(alphas, decisions, current_states=current_states)
        for decision in filtered:
            event = self.registry.record_lifecycle_decision(decision)
            self.store.append('lifecycle_events', event)
        return filtered

    def run_decay_scan(self) -> List[Dict[str, Any]]:
        by_alpha: Dict[str, List[Dict[str, Any]]] = {}
        for row in self.registry.validation_scorecards:
            by_alpha.setdefault(row['alpha_id'], []).append(row)
        profiles = []
        for alpha_id, rows in by_alpha.items():
            profile = self.decay_tracker.evaluate(alpha_id, rows)
            if profile:
                self.registry.add_decay_profile(profile)
                self.store.append('decay_profiles', profile)
                profiles.append(profile)
        return profiles

    def build_revalidation_tasks(self) -> List[Dict[str, Any]]:
        tasks = self.scheduler.create_tasks(self.registry.alpha_definitions, self.registry.lifecycle_events, self.registry.decay_profiles)
        self.registry.revalidation_tasks = tasks
        return tasks

    def generate_research_brief(self, stem: str = 'research_brief_v1') -> Dict[str, str]:
        return self.brief_generator.write_brief(self.registry, stem=stem)

    def healthcheck(self) -> Dict[str, Any]:
        latest = self.registry.latest_scorecards()
        return {
            'alpha_count': len(self.registry.alpha_definitions),
            'validation_scorecard_count': len(self.registry.validation_scorecards),
            'latest_scorecard_count': len(latest),
            'lifecycle_event_count': len(self.registry.lifecycle_events),
            'decay_profile_count': len(self.registry.decay_profiles),
            'revalidation_task_count': len(self.registry.revalidation_tasks),
            'top_alpha_id': max(latest.items(), key=lambda kv: float(kv[1].get('research_score', 0.0) or 0.0))[0] if latest else None,
        }
