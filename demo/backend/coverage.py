"""Public coverage descriptions. Presentation only; never selects or admits a method."""
from .capabilities import inventory


def summary():
    from cfm_id.bounded_policy_contract import MAX_N
    from cfm_id.network_bounded_dispatch import DESIGNS, EXPOSURES
    from cfm_id_llm.network_files import MAX_NODES, MAX_EDGES

    registered = {m['id']: m['label'] for r in inventory() for m in r['methods']}
    groups = [
        ('网络中的直接与同伴效应',
         '比较本人或同伴的参与状态；也可求一个指定状态下的平均结果。其余人的安排按所声明的分配规律平均。',
         ('R1A_RANDOMIZED_ARM', 'R1A_COMPOSITION')),
        ('完整方案的平均结果与差值',
         '说明每个对象在方案中做什么，计算一份方案的平均结果，或两份方案的差。也支持明确列出的有限随机方案。',
         ('R1B_FULL_ASSIGNMENT', 'R2_MEAN_SIGNATURE', 'R1B_ENDPOINT_DIFFERENCE', 'R2_ENDPOINT_DIFFERENCE', 'R1B_FINITE_POLICY')),
        ('观察性网络问题',
         '处理不是随机分配时，支持已实现的固定背景、共同分层及本人和邻居特征调整。必须另行确认排除混杂的条件。',
         ('R3_FULL_ASSIGNMENT', 'R3_MEAN_SIGNATURE', 'R3_P_STANDARDIZED_EFFECTS', 'R3_EXPOSURE_ADJUSTED_EFFECTS', 'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS')),
        ('有限网络的上下界 · PARTIAL',
         '一份完整方案的均值、两份方案的均值差。需明确总体信息、结果或均值范围，以及采用的模型条件。可给出界限公式；有总体数值时再代入。',
         ('BOUNDED_POLICY_MEAN_D2_E1', 'BOUNDED_POLICY_MEAN_D2_E4', 'BOUNDED_POLICY_MEAN_FINITE',
          'BOUNDED_POLICY_CONTRAST_D2_E1', 'BOUNDED_POLICY_CONTRAST_D2_E4', 'BOUNDED_POLICY_CONTRAST_FINITE', 'MEAN_ORDER_D2_E1')),
        ('变量因果图 · DAG',
         '支持经典后门、调整和单变量经典前门。这里的图描述变量之间的因果关系，不是人或门店之间的联系。',
         ('DAG_CLASSICAL_BACKDOOR', 'DAG_ADJUSTMENT', 'DAG_CLASSICAL_FRONTDOOR')),
    ]
    shown = {method for _, _, methods in groups for method in methods}
    if shown != registered.keys():
        raise ValueError('WEB_COVERAGE_PRESENTATION_MISMATCH')
    return dict(
        groups=[dict(title=title, description=text, methods=[dict(id=m, label=registered[m]) for m in methods])
                for title, text, methods in groups],
        import_limits=dict(nodes=MAX_NODES, edges=MAX_EDGES),
        finite_partial=dict(max_nodes=MAX_N, extended_design_max_nodes=8,
                            designs=list(DESIGNS), exposures=list(EXPOSURES)),
        notes=[
            '是否适用，仍由本次问题、材料、假设和支持条件决定；列在这里不代表任意输入都能识别。',
            '网络入口主要处理：处理前已知且固定的无向关系、单期二元处理。上传关系表目前不接收方向或边权。',
            '均值顺序界限目前限固定名额、过半分组（D2/E1）和数值总体均值；一般额外等式、混合符号与数值信息尚不支持。',
            'IV 和一般 DAG ID 已有专门研究接口，尚未接入此网页的自由文本流程。',
            '这是研究演示入口；不同路线的审核权限不同。合成示例模式不等于确认真实数据或现实中的假设。',
        ],
    )
