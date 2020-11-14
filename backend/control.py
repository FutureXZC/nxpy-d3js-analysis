# -*- coding: utf-8 -*-
import json
import pandas as pd
import networkx as nx


def getInitControlG(path):
    """
    读取控制人关系的excel表格到DataFrame, 并切分子图
    Params:
        path: 含有控制人数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    control = pd.read_csv(path, encoding="gb2312")
    # 将列名索引修改为英文
    control.columns = ["relTag", "src", "destn", "relType", "rate"]
    # 将比例大于100的异常值修正为100，并将数字变为带百分号的字符串
    control.rate[control.rate >= 100] = 100
    control["rate"] = [str(x) + "%" for x in control["rate"]]
    # 关系类型修正为"0: 投资, 1: 控制"
    control.relType[control.relType == "Control"] = 1
    control.relType[control.relType == "Investment"] = 0

    # Control关系中，relTag和src一一对应
    G = nx.DiGraph()
    # 构建初始图G, 控制人共70420个节点
    for _, row in control.iterrows():
        # 默认每个节点非根且不存在交叉持股, 具体情况后续判定
        G.add_node(row["src"], isRoot=0, isCross=0)
        G.add_node(row["destn"], isRoot=0, isCross=0)
        G.add_edge(
            row["src"],
            row["destn"],
            rate=row["rate"],
            relTag=row["relTag"],  # 经检验, relTag与边一一对应, 不予考虑
            relType=row["relType"],
        )
    # 切分子图
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
    # {2: 30182, 3: 1398, 4: 179, 9: 25, 15: 10, 8: 51, 11: 17, 20: 2, 5: 106,
    # 118: 1, 41: 1, 7: 87, 6: 158, 10: 23, 17: 3, 26: 2, 12: 12, 21: 8, 14: 14,
    # 16: 6, 19: 3, 25: 1, 52: 1, 49: 1, 46: 1, 35: 2, 51: 1, 28: 2, 34: 1, 32: 1,
    # 23: 1, 91: 1, 13: 5, 24: 4, 29: 1, 31: 1, 39: 1, 22: 2, 33: 1, 30: 1}
    return subG


def getRootOfControlG(subG):
    """
    找到各个节点的实际控制人
    经检验, 每个子图要么无根, 要么有且仅有一个根, 因此可以简化计算
    经检验, 有根的子图均不存在交叉持股现象
    Params:
        subG: 原子图的列表
    Returns:
        rootG: 含有交叉持股关系的子图列表, [(subG, [交叉持股的公司集群])]
    """
    rootG = list()
    # 标记各个子图的根节点
    for G in subG:
        flag = False  # 是否有根标记
        for n in G.nodes:
            if G.in_degree(n) == 0:
                G.nodes[n]["isRoot"] = 1
                flag = True
                break  # 仅有一个根, 找到即可退出
        # 若图无根, 则全图均为交叉持股, 交叉持股的公司风险绑定
        if not flag:
            for n in G.nodes:
                G.nodes[n]["isCross"] = 1  # 标记所有公司是交叉持股
            rootG.append((G, [list(G.nodes())]))
            continue
        # 仅有一个根, 则该节点必为所有公司的实际控制人
        # 用拓扑排序判断是否存在局部的交叉持股
        tmpG = nx.DiGraph(G)  # 必须通过创建新图对象来创建副本, 直接赋值会会被冻结图对象, 无法修改
        flag = True
        while flag:
            flag = False
            s = list()
            for n in tmpG.nodes:
                if tmpG.in_degree(n) == 0:
                    s.append(n)
                    flag = True
            tmpG.remove_nodes_from(s)
        # 拓扑排序后仍有节点则这些节点构成交叉持股
        if nx.number_of_nodes(tmpG):
            # 一张子图内可能存在多个交叉持股的公司集群
            rootG.append(
                (
                    G,
                    [
                        list(tmpG.subgraph(c).nodes())
                        for c in nx.connected_components(tmpG)
                    ],
                )
            )
        else:
            # 无交叉持股的子图拓扑排序后为空
            rootG.append((G, []))
    return rootG


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
