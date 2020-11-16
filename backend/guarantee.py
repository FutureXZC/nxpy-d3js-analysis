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
        G.add_node(row["src"], guarType=[])
        G.add_node(row["destn"], guarType=[])
        G.add_edge(
            row["src"], row["destn"], guarType=row["guarType"], amount=row["amount"],
        )
    # 切分7158个子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    # 各个子图的节点数量
    # nodesNum = dict()
    # for item in subG:
    #     if nx.number_of_nodes(item) not in nodesNum:
    #         nodesNum[nx.number_of_nodes(item)] = 0
    #     nodesNum[nx.number_of_nodes(item)] += 1
    # print(nodesNum)
    # {2: 6573, 464: 1, 6: 93, 13: 13, 7: 53, 5: 46, 35: 1, 9: 27, 10: 24, 17: 6,
    # 15: 12, 18: 6, 27: 1, 89: 1, 22: 4, 8: 37, 3: 129, 25: 3, 14: 11, 4: 56, 45: 2,
    # 20: 6, 31: 2, 23: 1, 19: 3, 93: 2, 26: 5, 29: 2, 41: 1, 11: 12, 12: 8, 21: 2,
    # 51: 1, 24: 2, 16: 7, 47: 1, 97: 1, 33: 1, 39: 1, 61: 1}
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
            for u, v in tmpG.edges:
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
        for u, v in subG.edges:
            if not subG.nodes[u]["guarType"] or not subG.nodes[v]["guarType"]:
                if "Chain" not in subG.nodes[u]["guarType"]:
                    subG.nodes[u]["guarType"].append("Chain")
                if "Chain" not in subG.nodes[v]["guarType"]:
                    subG.nodes[v]["guarType"].append("Chain")

    # def testDraw(G):
    #     """
    #     测试绘图
    #     """
    #     # pos = nx.shell_layout(G)
    #     # nx.draw(G, pos)
    #     # node_labels = nx.get_node_attributes(G, "guarType")
    #     # nx.draw_networkx_labels(G, pos, labels=node_labels)
    #     # # edge_labels = nx.get_edge_attributes(G, "guarType")
    #     # # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
    #     # plt.show()
    #     pr = nx.pagerank(G, alpha=0.85)
    #     print(pr)
    #     nx.draw(
    #         G,
    #         pos=nx.shell_layout(G),
    #         node_size=[x * 6000 for x in pr.values()],
    #         node_color="m",
    #         with_labels=True,
    #     )
    #     plt.show()

    # testDraw(cir[2])
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


def graphs2json(GList, filePath1, filePath2):
    """
    将图数据输出为json文件
    Params:
        GList: 图数据
        filePath1: 双节点子图json的存储路径
        filePath2: 多节点子图json的存储路径
    Outputs:
        输出转化后的json文件到filePath1和filepath2下
    """
    data1 = {"links": [], "nodes": []}
    data2 = {"links": [], "nodes": []}
    Gid = 0  # 子图编号
    for item in GList:
        # 初始化子图数据, 先后加点和边
        c = list()
        for n in item[0].nodes:
            if item[0].nodes[n]["guarType"] == "Chain":
                c.append("Chain")
            if item[0].nodes[n]["guarType"] == "Mutual":
                c.append("Mutual")
            if item[0].nodes[n]["guarType"] == "Circle":
                c.append("Circle")
            if item[0].nodes[n]["guarType"] == "Cross":
                c.append("Cross")
            if item[0].nodes[n]["guarType"] == "Focus":
                c.append("Focus")
            if nx.number_of_nodes(item[0]) == 2:
                data1["nodes"].append({"class": c, "Gid": Gid, "id": n})
            else:
                data2["nodes"].append({"class": c, "Gid": Gid, "id": n})
        for u, v in item[0].edges:
            if nx.number_of_nodes(item[0]) == 2:
                data1["links"].append(
                    {"source": u, "target": v, "amount": item[0][u][v]["amount"],}
                )
            else:
                data2["links"].append(
                    {"source": u, "target": v, "amount": item[0][u][v]["amount"]}
                )
        Gid += 1
    # 将上述数据写入文件
    with open(filePath1, "w") as f1:
        json.dump(data1, f1)
    with open(filePath2, "w") as f2:
        json.dump(data2, f2)
