"""Opt-in D2/E4 mean-box declarations. No automatic approvals or D/E overrides."""
from typing import Literal
from pydantic import Field
from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import (
    ExactMean, BoundedMeanInformation, ReviewedBoundedPolicy, _validate_mean_model, fail,
)
from .bounded_contrast_contract import _validate_pair, target_coordinates
from .bounded_contrast import ReviewedBoundedContrast

POLICY_VERSION = 'bounded-count-policy-1'
CONTRAST_VERSION = 'bounded-count-contrast-1'
VERSIONS = {'policy': POLICY_VERSION, 'contrast': CONTRAST_VERSION}


class ExactCountMean(ExactMean):
    exposure: int = Field(ge=0, le=11)  # Degree is separately checked from the actual graph.


class CountMeanInformation(BoundedMeanInformation):
    version: Literal['bounded-count-policy-1']
    values: list[ExactCountMean] = Field(min_length=1)


class ReviewedCountPolicy(ReviewedBoundedPolicy):
    version: Literal['bounded-count-policy-1']


class ReviewedCountContrast(ReviewedBoundedContrast):
    version: Literal['bounded-count-contrast-1']


def validate_model(inquiry, information):
    return _validate_mean_model(inquiry, information, information_type=CountMeanInformation,
        grouping='exact_treated_neighbor_count', domain_reason='BOUNDED_D2_E4_FINITE_DOMAIN_REQUIRED')


def validate_pair(inquiries, information):
    return _validate_pair(inquiries, information, validator=validate_model)


def inputs(inquiries, information, mode):
    if mode == 'policy':
        st, target, known, bounds = validate_model(inquiries, information)
        return st, {'first': target}, known, bounds, target
    if mode == 'contrast':
        st, targets, known, bounds = validate_pair(inquiries, information)
        return st, targets, known, bounds, target_coordinates(inquiries)
    fail('UNSUPPORTED', 'COUNT_OBJECTIVE_NOT_SUPPORTED')


def input_digest(inquiries, information, mode):
    return sha(dict(version=VERSIONS[mode], mode=mode, inquiries=inquiries, information=information))
