# -*- coding: utf-8 -*-
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


def getInitControlG(tPath):
    """
    读取excel表格到DataFrame
    Param:
        tPath: 含有控制人数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    control = pd.read_csv(tPath, encoding="gb2312")
    # 将列名索引修改为英文
    control.columns = ["relTag", "src", "destn", "relType", "rate"]
    # 将比例大于100的异常值修正为100，并归一化
    control.rate[control.rate >= 100] = 100
    control["rate"] /= 100
    # 关系类型修正为"0: 投资, 1: 控制"
    control.relType[control.relType == "Control"] = 1
    control.relType[control.relType == "Investment"] = 0
    # print(control)

    # Control关系中，relTag和src一一对应
    # relTag共39910
    G = nx.DiGraph()
    # 控制人共70420个节点, 构建初始图G
    for _, row in control.iterrows():
        G.add_edge(
            row["src"],
            row["destn"],
            rate=row["rate"],
            relTag=row["relTag"],
            relType=row["relType"],
        )
    # 切分子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    return subG


def getSubgraphFromInitG(G):
    """
    输入初始图G, 利用并查集的思想切分子图
    Param:
        G: 初始图G, nx.DiGraph()
    Returns: 
        GDivided: 存储各个子图的数组, 元素均为nx.DiGraph()
    """
    pass


if __name__ == "__main__":
    controlG = getInitControlG("./backend/res/control.csv")
    # 各个子图的节点数量
    nodesNum = dict()
    for item in controlG:
        if len(item.nodes()) not in nodesNum:
            nodesNum[len(item.nodes())] = 0
        nodesNum[len(item.nodes())] += 1
    print(nodesNum)
    # nx.draw(
    #     controlG[5],
    #     # pos=nx.spring_layout(G),
    #     with_labels=True,
    #     label_size=1000,
    #     node_size=1000,
    #     font_size=20,
    #     # edge_labels=edge_labels,
    # )
    # plt.show()
