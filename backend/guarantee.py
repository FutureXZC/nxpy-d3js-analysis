import os
import json
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict


def getInitGuaranteeG(path):
    """
    读取担保关系的excel表格到DataFrame, 并切分子图
    Params:
        path: 含有担保关系数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    guarantee = pd.read_csv(path, encoding="gb2312")
    guarantee.columns = ["src", "destn", "time", "guarType", "amount"]
    # 每个样本的担保时间都相同, 没有分析意义, 直接删除
    guarantee.drop(["time"], axis=1, inplace=True)
    # 担保金额为0的样本视为无效的担保, 直接删去, 可减少870个样本
    guarantee = guarantee[~guarantee["amount"].isin([0])]

    # 构建初始图G, 一共18711个节点, 13478条边
    G = nx.DiGraph()
    for _, row in guarantee.iterrows():
        G.add_node(row["src"], guarType=[], m=0.0, std=0.0)
        G.add_node(row["destn"], guarType=[], m=0.0, std=0.0)
        G.add_edge(
            row["src"],
            row["destn"],
            guarType=row["guarType"],
            amount=row["amount"],
            mij=0,
        )
    # 切分7158个子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    return subG


def markRiskOfGuaranteeG(GList):
    """
    标记担保关系图的风险
    Params:
        GList: 担保关系子图列表
    Output:
        GList: 更新担保关系的列表
    """
    cir = list()
    for subG in GList:
        # 双节点的子图, 仅可能为担保链或互保
        if subG.number_of_nodes() == 2:
            # 担保链判定
            if nx.is_tree(subG):
                for n in subG.nodes():
                    subG.nodes[n]["guarType"].append("Chain")
            # 互保判定
            else:
                for n in subG.nodes():
                    subG.nodes[n]["guarType"].append("Mutual")
        # 多于2个节点的情形, 标记节点所属的担保关系类型
        for u, v in subG.edges:
            # 贪心策略: u为源点，则认为u更有可能为Cross; v为终点，则认为v更有可能成为Focus
            # 原图中标记为Cross的边, 形如u为交通枢纽, 即u的度较大
            # 一保多(星型担保 or 担保公司)
            if subG.out_degree(u) >= 3 and "Cross" not in subG.nodes[u]["guarType"]:
                subG.nodes[u]["guarType"].append("Cross")
            # 原图中标记为Focus的边, 形如多个节点指向一个节点
            # 多保一(联合担保)
            if subG.in_degree(v) >= 3 and "Focus" not in subG.nodes[v]["guarType"]:
                subG.nodes[v]["guarType"].append("Focus")
        # 担保圈, 直接通过边属性检查, 经检验只有两个子图含有Circle标记, 但元数据的标记不准确
        # 分别进行正向和逆向的拓扑排序检查, 可以找到遗漏的担保圈和互保关系
        tmpG = nx.DiGraph(subG)
        flag = True
        while flag:
            flag = False
            l = list()
            for n in tmpG.nodes():
                if tmpG.in_degree(n) == 0:
                    l.append(n)
                    flag = True
            tmpG.remove_nodes_from(l)
        # 将边逆向, 再次拓扑排序
        tmpG = nx.reverse(tmpG)
        flag = True
        while flag:
            flag = False
            l = list()
            for n in tmpG.nodes():
                if tmpG.in_degree(n) == 0:
                    l.append(n)
                    flag = True
            tmpG.remove_nodes_from(l)
        # 拓扑排序后图非空说明含有担保圈或互保关系
        if nx.number_of_nodes(tmpG):
            # 互保判定
            for u, v in tmpG.edges():
                if tmpG.has_edge(v, u):
                    if "Mutual" not in subG.nodes[u]["guarType"]:
                        subG.nodes[u]["guarType"].append("Mutual")
                    if "Mutual" not in subG.nodes[v]["guarType"]:
                        subG.nodes[v]["guarType"].append("Mutual")
            # 担保圈判定
            visited = list()
            trace = list()

            def dfs2FindCircle(node):
                """
                用回溯法找环
                Params:
                    node: 子图的起始搜索节点
                """
                if node in visited:
                    if node in trace:
                        trace_index = trace.index(node)
                        # 双节点的互保不作为担保圈进行标记
                        if len(trace) - trace_index > 2:
                            for i in range(trace_index, len(trace)):
                                if "Circle" not in subG.nodes[trace[i]]["guarType"]:
                                    subG.nodes[trace[i]]["guarType"].append("Circle")
                    return
                visited.append(node)
                trace.append(node)
                for child in list(tmpG.neighbors(node)):
                    dfs2FindCircle(child)
                trace.pop()

            dfs2FindCircle(list(tmpG.nodes())[0])
            cir.append(subG)
        # 担保链: 若节点均不属于上述情况则该节点为担保链上的点
        for u, v in subG.edges():
            if not subG.nodes[u]["guarType"] or not subG.nodes[v]["guarType"]:
                if "Chain" not in subG.nodes[u]["guarType"]:
                    subG.nodes[u]["guarType"].append("Chain")
                if "Chain" not in subG.nodes[v]["guarType"]:
                    subG.nodes[v]["guarType"].append("Chain")
    return GList


def find_communities(G, T, r=0.05):
    """
    SLPA社区/集群发现算法
    Params:
        G: 要进行社区/集群划分的图
        T: 最大迭代次数
        r: 默认r值
    Returns:
        communities: 记录社区/集群信息的字典列表
    """
    # 第一步: 初始化
    memory = {i: {i: 1} for i in G.nodes()}
    # 第二步: 递进
    for _ in range(T):
        listenersOrder = list(G.nodes())
        np.random.shuffle(listenersOrder)
        for listener in listenersOrder:
            speakers = G[listener].keys()
            if len(speakers) == 0:
                continue
            labels = defaultdict(int)
            for _, speaker in enumerate(speakers):
                # Speaker规则
                total = float(sum(memory[speaker].values()))
                labels[
                    list(memory[speaker].keys())[
                        np.random.multinomial(
                            1, [freq / total for freq in memory[speaker].values()]
                        ).argmax()
                    ]
                ] += 1
            # Listener规则
            acceptedLabel = max(labels, key=labels.get)
            # 更新listener缓存
            if acceptedLabel in memory[listener]:
                memory[listener][acceptedLabel] += 1
            else:
                memory[listener][acceptedLabel] = 1
    # 第三步
    for node, mem in memory.items():
        delabel = list()
        for label, freq in mem.items():
            if freq / float(T + 1) < r:
                delabel.append(label)
        for item in delabel:
            del mem[item]
    # 找到节点间的关系
    communities = {}
    for node, mem in memory.items():
        for label in mem.keys():
            if label in communities:
                communities[label].add(node)
            else:
                communities[label] = set([node])
    # 移除嵌套社区
    nestedCommunities = set()
    keys = list(communities.keys())
    for i, label0 in enumerate(keys[:-1]):
        comm0 = communities[label0]
        for label1 in keys[i + 1 :]:
            comm1 = communities[label1]
            if comm0.issubset(comm1):
                nestedCommunities.add(label0)
            elif comm0.issuperset(comm1):
                nestedCommunities.add(label1)
    for comm in nestedCommunities:
        del communities[comm]
    return communities


def harmonicDistance(subG):
    """
    标记节点的风险值m
    Params:
        G: 子图列表
    Outputs:
        G: 标记各个节点风险值m后的子图列表
    """
    for G in subG:
        # G = nx.reverse(G)
        m = pd.DataFrame(columns=G.nodes())
        maxmij = max(nx.get_edge_attributes(G, "amount").values())
        dis = dict(nx.all_pairs_dijkstra_path_length(G))
        for i in G.nodes():
            mij = dict()
            for j in dis[i]:
                if i == j:
                    mij[j] = 0
                if dis[i][j]:
                    mij[j] = sum(np.array(list(dis[i].values())) / dis[i][j])
            for j in G.nodes():
                if j not in mij:
                    mij[j] = maxmij
            m.loc[i] = mij
        # m矩阵第i行的行和代表了节点i对图中其他节点的风险大小
        mRowSum = m.apply(lambda x: x.sum(), axis=1)
        # m矩阵第j列的列和代表了节点j受到图中其他节点的风险大小
        # mColSum = m.apply(lambda x: x.sum())
        for n in G.nodes():
            G.nodes[n]["m"] = mRowSum[n]
            # G.nodes[n]["mIn"] = mColSum[n]
        # mij代表节点i对节点j的担保关系紧密程度
        for u, v in G.edges():
            G[u][v]["mij"] = m.loc[u, v]
        mList = nx.get_node_attributes(G, 'm')
        maxM, minM = max(mList.values()), min(mList.values())
        if maxM == minM:
            for n in G.nodes():
                G.nodes[n]["std"] = 15
        else:
            k = 20/(maxM - minM)
            for n in G.nodes():
                G.nodes[n]["std"] = 5 + k * (G.nodes[n]["m"] - minM)



def graphs2json(GList):
    """
    将图数据输出为json文件
    Params:
        GList: 图数据
    Outputs:
        输出转化后的json文件到filePath1和filepath2下
    """
    circleList = {"links": [], "nodes": []}
    MutualList = {"links": [], "nodes": []}
    crossList = {"links": [], "nodes": []}
    focusList = {"links": [], "nodes": []}
    doubleNormalList = {"links": [], "nodes": []}
    multiNormalList = {"links": [], "nodes": []}
    Gid = 0  # 子图编号
    doubleCount = 0
    i = 0
    c = ["doubleRisk", "tripleRisk", "quadraRisk", "pentaRisk"]
    single = ["circle", "mutual", "cross", "focus", "chain"]
    for item in GList:
        # 初始化子图数据, 先后加点和边
        isMutual, isCircle, isCross, isFocus, isUnusual = False, False, False, False, False
        offset = 0
        for n in item.nodes:
            riskCount = len(item.nodes[n]["guarType"]) - 1
            if "Mutual" in item.nodes[n]["guarType"]:
                isMutual, isUnusual = True, True
                if riskCount == 0:
                    offset = 1
            elif "Circle" in item.nodes[n]["guarType"]:
                isCircle, isUnusual = True, True
                if riskCount == 0:
                    offset = 0
            elif "Cross" in item.nodes[n]["guarType"]:
                isCross, isUnusual = True, True
                if riskCount == 0:
                    offset = 2
            elif "Focus" in item.nodes[n]["guarType"]:
                isFocus, isUnusual = True, True
                if riskCount == 0:
                    offset = 3
            else:
                offset = 4
            if riskCount > 0:
                tmpNode = {"group": riskCount, "class": c[riskCount-1], "size": item.nodes[n]["std"], "ctx": ', '.join(item.nodes[n]["guarType"]), "Gid": Gid, "id": n, "m": item.nodes[n]["m"]}
            else:
                tmpNode = {"group": riskCount, "class": single[offset], "size": item.nodes[n]["std"], "ctx": ', '.join(item.nodes[n]["guarType"]), "Gid": Gid, "id": n, "m": item.nodes[n]["m"]}
            if isUnusual:
                if isCircle:
                    circleList["nodes"].append(tmpNode)
                if isMutual:
                    MutualList["nodes"].append(tmpNode)
                if isCross:
                    crossList["nodes"].append(tmpNode)
                if isFocus:
                    focusList["nodes"].append(tmpNode)
            else:
                if nx.number_of_nodes(item) == 2:
                    doubleCount += 2
                    if doubleCount < 2950:
                        doubleNormalList["nodes"].append(tmpNode)
                    else:
                        with open("./frontend/res/guarantee/doubleNormal_" + str(i) + ".json", "w") as f:
                            json.dump(doubleNormalList, f)
                        i += 1
                        doubleCount = 0
                        doubleNormalList = {"links": [], "nodes": []}
                else:
                    multiNormalList["nodes"].append(tmpNode)
        for u, v in item.edges:
            tmpLink = {"source": u, "target": v, "amount": item[u][v]["amount"], "Gid": Gid}
            if isUnusual:
                if isCircle:
                    circleList["links"].append(tmpLink)
                if isMutual:
                    MutualList["links"].append(tmpLink)
                if isCross:
                    crossList["links"].append(tmpLink)
                if isFocus:
                    focusList["links"].append(tmpLink)
            else:
                if nx.number_of_nodes(item) == 2:
                    doubleNormalList["links"].append(tmpLink)
                else:
                    multiNormalList["links"].append(tmpLink)
        Gid += 1
    print("circleList", len(circleList["nodes"]))
    print("MutualList", len(MutualList["nodes"]))
    print("crossList", len(crossList["nodes"]))
    print("focusList", len(focusList["nodes"]))
    print("doubleNormalList", len(doubleNormalList["nodes"]))
    print("multiNormalList", len(multiNormalList["nodes"]))
    # 将上述数据写入文件
    with open(r"./frontend/res/guarantee/circle.json", "w") as f:
        json.dump(circleList, f)
    with open(r"./frontend/res/guarantee/mutual.json", "w") as f:
        json.dump(MutualList, f)
    with open(r"./frontend/res/guarantee/cross.json", "w") as f:
        json.dump(crossList, f)
    with open(r"./frontend/res/guarantee/focus.json", "w") as f:
        json.dump(focusList, f)
    # with open(r"./frontend/res/guarantee/doubleNormal.json", "w") as f:
    #     json.dump(doubleNormalList, f)
    with open(r"./frontend/res/guarantee/multiNormal.json", "w") as f:
        json.dump(multiNormalList, f)