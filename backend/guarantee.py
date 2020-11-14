import json
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


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

    def testDraw(G):
        """
        测试绘图
        """
        pos = nx.shell_layout(G)
        nx.draw(G, pos)
        node_labels = nx.get_node_attributes(G, "guarType")
        nx.draw_networkx_labels(G, pos, labels=node_labels)
        # edge_labels = nx.get_edge_attributes(G, "guarType")
        # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
        plt.show()

    testDraw(cir[5])
    return GList


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
        for n in item[0].nodes:
            if item[0].nodes[n]["isRoot"]:
                group, c, size = 0, "root", 50
            elif item[0].nodes[n]["isCross"]:
                group, c, size = 1, "cross", 30
            else:
                group, c, size = 2, "normal", 10
            if nx.number_of_nodes(item[0]) == 2:
                data1["nodes"].append(
                    {"group": group, "class": c, "size": size, "Gid": Gid, "id": n}
                )
            else:
                data2["nodes"].append(
                    {"group": group, "class": c, "size": size, "Gid": Gid, "id": n}
                )
        for u, v in item[0].edges:
            if nx.number_of_nodes(item[0]) == 2:
                data1["links"].append(
                    {
                        "source": u,
                        "target": v,
                        "rate": item[0][u][v]["rate"],
                        "relType": item[0][u][v]["relType"],
                    }
                )
            else:
                data2["links"].append(
                    {
                        "source": u,
                        "target": v,
                        "rate": item[0][u][v]["rate"],
                        "relType": item[0][u][v]["relType"],
                    }
                )
        Gid += 1
    # 将上述数据写入文件
    with open(filePath1, "w") as f1:
        json.dump(data1, f1)
    with open(filePath2, "w") as f2:
        json.dump(data2, f2)
