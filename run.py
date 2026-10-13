"""Task 02 一键运行：把作业结果直接打印出来。

用法（在任意目录下）：
    D:\\python\\python.exe run_task02.py

说明：本文件只是"展示脚本"，放在工作区里，**不属于你的仓库**，不会被提交，
也不会被 PR 的 scope check 看到。作业真正的 5 个文件在
    d:\\因果推断项目\\CFM-identification\\student_work\\task02\\
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(r"d:\因果推断项目\CFM-identification")
TASK_DIR = REPO / "student_work" / "task02"
GRAPH = REPO / "pfn_pipeline" / "_internal" / "estimation" / "data" / "fixed_er_N300_p0.02_seed12345.json"

sys.path.insert(0, str(TASK_DIR))
import support as sp          # noqa: E402
import rule as rl             # noqa: E402

LINE = "=" * 72


def main():
    print(LINE)
    print(rl.SETTING_ID)
    print(LINE)

    # --- 1. 输入：官方固定 ER 网络 + 自定 p_i ---------------------------------
    if GRAPH.exists():
        adj = sp.load_fixed_er_adjacency(GRAPH)
        source = GRAPH.name
    else:
        rng = np.random.default_rng(0)
        adj = np.triu((rng.random((300, 300)) < 0.02).astype(np.int8), 1)
        adj = adj + adj.T
        source = "本地生成的 ER 图（官方图未找到）"

    n = adj.shape[0]
    ps = np.random.default_rng(2026).uniform(0.2, 0.8, size=n)   # D1 的设计参数
    deg = np.array([sp.degree(adj, i) for i in range(n)])

    print(f"图来源      : {source}")
    print(f"节点数 N    : {n}    边数 : {int(adj.sum() // 2)}")
    print(f"度数范围    : {deg.min()} - {deg.max()}")
    print(f"p_i (D1)    : iid U(0.2, 0.8), seed = 2026")
    print()

    # --- 2. 一个正常节点：六个 arm 的 pi_i(t, s) ------------------------------
    i = int(np.argmax(deg))
    d = int(deg[i])
    pi = sp.support_D1_E2(adj, ps, i)
    rng_map = sp.e2_integer_ranges(d)
    print(LINE)
    print(f"[正常例] 节点 {i}:  d_i = {d},  N(i) = {sp.neighbours(adj, i).tolist()}")
    print(f"    E2 三档整数区间:  s=0 -> K in [{rng_map[0][0]}, {rng_map[0][1]}]"
          f"   s=1 -> K in [{rng_map[1][0]}, {rng_map[1][1]}]"
          f"   s=2 -> K in [{rng_map[2][0]}, {rng_map[2][1]}]")
    print(f"    {'':<10}s = 0        s = 1        s = 2")
    for t in (0, 1):
        print(f"    t = {t}     {pi[(t, 0)]:.6f}     {pi[(t, 1)]:.6f}     {pi[(t, 2)]:.6f}")
    print(f"    六个 arm 之和 = {sum(pi.values()):.12f}   （应当恰好为 1）")
    print()

    # --- 3. 度数为 1 的节点：medium 档不可达，必须拒绝 ------------------------
    one = [int(j) for j in range(n) if deg[j] == 1]
    print(LINE)
    print(f"[zero-support 例] 度数为 1 的节点共 {len(one)} 个: {one[:10]}")
    if one:
        j = one[0]
        pj = sp.support_D1_E2(adj, ps, j)
        print(f"    节点 {j}: d_i = 1, N(i) = {sp.neighbours(adj, j).tolist()}")
        print(f"    E2 三档区间:  s=0 -> [0, 0]   s=1 -> [{sp.e2_integer_ranges(1)[1][0]}, "
              f"{sp.e2_integer_ranges(1)[1][1]}] (空!)   s=2 -> [1, 1]")
        print(f"    pi(0, 1) = {pj[(0, 1)]:.6f}    pi(1, 1) = {pj[(1, 1)]:.6f}   <-- medium 档概率为 0")
        res = rl.try_identify_arm(adj, ps, j, 1, 1)
        print(f"    rule 判定:  status = {res.status}   functional = {res.functional!r}")
        print(f"    拒绝理由:   {res.reason[:88]}...")
    print()

    # --- 4. POINT functional 长什么样 ----------------------------------------
    print(LINE)
    print("[POINT functional] 识别结果给的是公式，不是数字：")
    print(f"    {rl.POINT_FUNCTIONAL_TEMPLATE}")
    print("    三个假设：")
    for a in rl.ASSUMPTIONS:
        print(f"      - {a}")
    print()

    # --- 5. 全图统计：多少个 arm 有 support ----------------------------------
    ok = bad = 0
    for j in range(n):
        if deg[j] == 0:
            continue
        pj = sp.support_D1_E2(adj, ps, j)
        ok += sum(1 for v in pj.values() if v > 0.0)
        bad += sum(1 for v in pj.values() if v == 0.0)
    print(LINE)
    print(f"[全图统计] 总 arm 数 = {ok + bad}  (= 6 x {n})")
    print(f"    有 support 的 arm : {ok}")
    print(f"    pi = 0 的 arm     : {bad}")
    print(LINE)
    print("结论：每一个 pi > 0 的 arm 都能写成 mu_i(t,s) = E[Y_obs | A,X,T_i=t,S_i=s]（式 3），")
    print("      右边只依赖总体可观测分布，所以是 POINT；pi = 0 的 arm 必须拒绝。")
    print(LINE)


if __name__ == "__main__":
    main()
