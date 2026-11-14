"""Finite D1-D8/E1-E5 mean-box domain. No parameter overrides or approvals."""
from typing import Literal
from pydantic import Field
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.schemas import (
    CompleteRandomizationDesignV1,HeterogeneousBernoulliDesignV1,
    TwoGroupFixedQuotaDesignV1,ClusterBernoulliDesignV24,
    MultiGroupFixedQuotaDesignV25,TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1,RerandomizedBalancedDesignV1,
)
from .bounded_policy_contract import BoundedMeanInformation,ReviewedBoundedPolicy,StrictRecord,_validate_mean_model,fail
from .bounded_count_contract import ExactCountMean
from .bounded_contrast import ReviewedBoundedContrast
from .bounded_contrast_contract import _validate_pair,target_coordinates

POLICY_VERSION='bounded-finite-policy-1'
CONTRAST_VERSION='bounded-finite-contrast-1'
VERSIONS={'policy':POLICY_VERSION,'contrast':CONTRAST_VERSION}
SYMBOLIC_VERSIONS={'policy':'bounded-finite-policy-symbolic-1','contrast':'bounded-finite-contrast-symbolic-1'}
DESIGNS=(HeterogeneousBernoulliDesignV1,CompleteRandomizationDesignV1,
         TwoGroupFixedQuotaDesignV1,ClusterBernoulliDesignV24,
         MultiGroupFixedQuotaDesignV25,TwoStageQuotaMixtureDesignV27,
         UnequalProbabilityFixedQuotaDesignV1,RerandomizedBalancedDesignV1)
GROUPINGS=('strict_majority_ties_low','three_level_treated_neighbor_fraction',
           'pretreatment_core_collaborator_majority','exact_treated_neighbor_count','any_treated_neighbor')

class FiniteMeanInformation(BoundedMeanInformation):
    version: Literal['bounded-finite-policy-1']
    values: list[ExactCountMean]=Field(min_length=1)

class SymbolicMean(StrictRecord):
    node: str
    own: int=Field(ge=0,le=1)
    exposure: int=Field(ge=0)
    value: None

class SymbolicMeanInformation(BoundedMeanInformation):
    version: Literal['bounded-finite-policy-symbolic-1']
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR']
    values: list[SymbolicMean]=Field(min_length=1)

def is_symbolic(information,mode):
    if mode=='policy':return type(information) is SymbolicMeanInformation
    return (type(information) is dict and set(information)=={'first','second'} and
            all(type(v) is SymbolicMeanInformation for v in information.values()))

def version_for(information,mode):
    return (SYMBOLIC_VERSIONS if is_symbolic(information,mode) else VERSIONS)[mode]

class ReviewedFinitePolicy(ReviewedBoundedPolicy):
    version: Literal['bounded-finite-policy-1']

class ReviewedFiniteContrast(ReviewedBoundedContrast):
    version: Literal['bounded-finite-contrast-1']

def validate_model(inquiry,information):
    # Native R2 validation independently checks the D6 license is admitted.
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    if type(inquiry) is not FixedPolicyInquiryV21:
        fail('CHECK_BLOCKED','TYPED_BOUNDED_MODEL_REQUIRED')
    d6=type(inquiry.study.design()) is TwoStageQuotaMixtureDesignV27
    symbolic=is_symbolic(information,'policy')
    result=_validate_mean_model(inquiry,information,information_type=SymbolicMeanInformation if symbolic else FiniteMeanInformation,
        grouping=GROUPINGS,design_types=DESIGNS,domain_reason='FINITE_D1_D8_E1_E5_DOMAIN_REQUIRED',
        extra_required=('first_stage_profile_no_direct_outcome_effect',) if d6 else (),symbolic=symbolic)
    st=result[0]
    if type(st.design()) in (UnequalProbabilityFixedQuotaDesignV1,RerandomizedBalancedDesignV1) and len(st.node_order)>8:
        fail('UNSUPPORTED','EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8')
    # All model nodes require a defined signature, including zero-weight nodes.
    if inquiry.r2_signature.grouping=='three_level_treated_neighbor_fraction' and any(
            degree==0 for degree in st.network().degree_map().values()):
        fail('UNSUPPORTED','FINITE_MODEL_EXPOSURE_UNDEFINED_FOR_ISOLATE')
    return result

def validate_pair(inquiries,information):
    return _validate_pair(inquiries,information,validator=validate_model)

def inputs(inquiries,information,mode):
    if mode=='policy':
        st,target,known,bounds=validate_model(inquiries,information)
        return st,{'first':target},known,bounds,target
    if mode=='contrast':
        st,targets,known,bounds=validate_pair(inquiries,information)
        return st,targets,known,bounds,target_coordinates(inquiries)
    fail('UNSUPPORTED','FINITE_OBJECTIVE_NOT_SUPPORTED')

def input_digest(inquiries,information,mode):
    return sha(dict(version=version_for(information,mode),mode=mode,inquiries=inquiries,information=information))
