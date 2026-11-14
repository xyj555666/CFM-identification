"""Public field meanings shared by initial reading and located re-reading.

Descriptions only: no source inference, candidate repair, or scientific license.
Earlier request profiles remain immutable.
"""
import json
from .network_model_scope_contract import make_local_request, INFORMATION_SCOPE

CONTRACT = 'network-source-selections-information-4'

INFORMATION_COMPLETENESS = '''listed_means_are_complete_information记录原文对“逐格列明的总体均值已经穷尽可用总体信息”的声明，而不是问所有潜在均值是否已知、是否已代入数值，也不是识别判断。
true：原文提供至少一个总体均值坐标，并明确可用总体信息恰好就是这些均值。可提供精确数值，也可明确以符号提供这些总体均值；只列部分格子也可以为true。availability分别记录EXACT_POPULATION_VALUE或SYMBOLIC_POPULATION_OPERATOR，符号格子的value保持null。另有有限样本时仍原样保留样本，样本不成为总体真值。
false：原文明确没有提供总体均值信息（包括明确只有有限样本、估计值或置信区间）；或者明确还有未被这些格子表达的总体区间、聚合方程、符号联合分布等总体信息。保留这些信息，不能改成点值或删掉。符号总体均值不等同于更强的符号联合分布。
null：原文没有明确说明是否提供该表、是否穷尽总体信息，或声明尚待确认；沉默不能推成false或true。原文自身矛盾时也保留null，并在unresolved引用双方说明冲突。
明确不存在与尚不清楚不同；没有其他总体信息不自动把一个空表变成true。科学界限属于模型条件，不算另外观察到的总体信息。此字段的source_ids须共同支持表的性质及完整性声明，不能借information或study的引用补足。'''

STUDY_EVIDENCE = '''study保留研究对象、对象名称、完整边、处理及编码、结果及编码、评价期和背景。study.source_ids共同覆盖实际写出的全部内容；例如context写出的具体时期也须由study自己的引用支持，不能借target或bounded_model中的引用补证据。只引用相关材料，不堆入整份目录；未知仍保留未知，不用删掉已明确的时期来避开引用检查。'''

FIELD_RULES = (
    ('/study', STUDY_EVIDENCE),
    ('/bounded_model/listed_means_are_complete_information', INFORMATION_COMPLETENESS),
)


def field_constraints(paths):
    """Only public definitions; no reviewer prose or case-specific answer."""
    return [dict(field_path=p, description=d) for p,d in FIELD_RULES
            if any(q=='' or p==q or p.startswith(q+'/') or q.startswith(p+'/') for q in paths)]


def make_request(bundle, *, binding, assignment_semantics=None):
    request=make_local_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    # Replace the ambiguous definition instead of stacking a contradictory one.
    if request['system'].count(INFORMATION_SCOPE)!=1:
        raise ValueError('INFORMATION_SCOPE_DEFINITION_CHANGED')
    body=json.loads(request['user']);schema=body['output_schema']
    schema['properties']['study']['description']=STUDY_EVIDENCE
    schema['$defs']['BoundedModel']['properties']['listed_means_are_complete_information']['description']=INFORMATION_COMPLETENESS
    return dict(system=request['system'].replace(INFORMATION_SCOPE,INFORMATION_COMPLETENESS),
                user=json.dumps(body,ensure_ascii=False))
