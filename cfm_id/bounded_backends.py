"""Internal typed dispatch for finite box extensions; never selected by LLM labels."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BoundedBackend:
    version: str
    route: str
    information_type: type
    review_type: type
    validate: Callable
    solve: Callable
    replay: Callable
    analyze: Callable | None = None


def policy_backend(information):
    from . import bounded_policy as legacy
    from . import bounded_count_contract as count
    from . import bounded_finite_contract as finite
    if type(information) is finite.FiniteMeanInformation:
        from .bounded_finite_solver import solve_policy
        from .bounded_finite_verify import replay_policy
        return BoundedBackend(finite.POLICY_VERSION,'BOUNDED_POLICY_MEAN_FINITE',
            finite.FiniteMeanInformation,finite.ReviewedFinitePolicy,
            finite.validate_model,solve_policy,replay_policy)
    if type(information) is count.CountMeanInformation:
        from .bounded_count_solver import solve_policy
        from .bounded_count_verify import replay_policy
        return BoundedBackend(count.POLICY_VERSION, 'BOUNDED_POLICY_MEAN_D2_E4',
            count.CountMeanInformation, count.ReviewedCountPolicy,
            count.validate_model, solve_policy, replay_policy)
    return BoundedBackend(legacy.VERSION, 'BOUNDED_POLICY_MEAN_D2_E1',
        legacy.BoundedMeanInformation, legacy.ReviewedBoundedPolicy,
        legacy.validate_model, legacy.solve, legacy.replay)


def contrast_backend(information):
    from . import bounded_contrast as legacy
    from . import bounded_count_contract as count
    from . import bounded_finite_contract as finite
    if (type(information) is dict and set(information)=={'first','second'}
            and all(type(v) is finite.FiniteMeanInformation for v in information.values())):
        from .bounded_finite_solver import solve_contrast,analyze
        from .bounded_finite_verify import replay_contrast
        return BoundedBackend(finite.CONTRAST_VERSION,'BOUNDED_POLICY_CONTRAST_FINITE',
            finite.FiniteMeanInformation,finite.ReviewedFiniteContrast,
            finite.validate_pair,solve_contrast,replay_contrast,analyze)
    if (type(information) is dict and set(information) == {'first','second'}
            and all(type(v) is count.CountMeanInformation for v in information.values())):
        from .bounded_count_solver import solve_contrast, analyze
        from .bounded_count_verify import replay_contrast
        return BoundedBackend(count.CONTRAST_VERSION, 'BOUNDED_POLICY_CONTRAST_D2_E4',
            count.CountMeanInformation, count.ReviewedCountContrast,
            count.validate_pair, solve_contrast, replay_contrast, analyze)
    from .bounded_policy_contract import BoundedMeanInformation
    return BoundedBackend(legacy.VERSION, legacy.ROUTE, BoundedMeanInformation,
        legacy.ReviewedBoundedContrast, legacy.validate_pair,
        legacy.solve, legacy.replay, legacy.analyze)
