# -*- coding: utf-8 -*-
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


def getInitControlG(path):
    """
    读取控制人关系的excel表格到DataFrame
    Param:
        path: 含有控制人数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    control = pd.read_csv(path, encoding="gb2312")
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
    G = nx.DiGraph()
    # 构建初始图G, 控制人共70420个节点
    for _, row in control.iterrows():
        G.add_node(row["src"], isRoot="0")
        G.add_node(row["destn"], isRoot="0")
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
    # 各个子图的节点数量
    # nodesNum = dict()
    # for item in subG:
    #     if len(item.nodes()) not in nodesNum:
    #         nodesNum[len(item.nodes())] = 0
    #     nodesNum[len(item.nodes())] += 1
    # print(nodesNum)
    return subG


def getInitGuaranteeG(path):
    """
    读取担保关系的excel表格到DataFrame
    Param:
        path: 含有担保关系数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    guarantee = pd.read_csv(path, encoding="gb2312")
    guarantee.columns = ["src", "destn", "time", "guarType", "amount"]
    # 每个样本的担保时间都相同, 没有分析意义, 直接删除
    guarantee.drop(["time"], axis=1)
    # 担保金额为0的样本视为无效的担保, 直接删去
    guarantee = guarantee[~guarantee["amount"].isin([0])]
    # print(guarantee)

    # 构建初始图G, 一共18711个节点, 14494条边
    G = nx.DiGraph()
    for _, row in guarantee.iterrows():
        G.add_node(row["src"])
        G.add_node(row["destn"])
        G.add_edge(
            row["src"], row["destn"], guarType=row["guarType"], amount=row["amount"],
        )
    # 切分子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    # print(len(subG))  # 7158个子图
    # 各个子图的节点数量
    nodesNum = dict()
    for item in subG:
        if len(item.nodes()) not in nodesNum:
            nodesNum[len(item.nodes())] = 0
        nodesNum[len(item.nodes())] += 1
        if len(item.nodes()) == 23:
            nx.draw(
                item,
                # pos=nx.spring_layout(G),
                # with_labels=True,
                # label_size=1000,
                # node_size=1000,
                # font_size=20,
                # edge_labels=edge_labels,
            )
            plt.show()
    print(nodesNum)
    return subG


def getRoot(subG, metric, threshold):
    """
    根据指标获取子图的根节点
    Params:
        subG: 原子图的列表
        metric: 判断的指标
        threshold: 指标的阈值
    Returns:
        subG: 更新根节点标记的子图
    """
    # 标记各个子图的根节点
    for G in subG:
        # 仅含有2个节点的子图
        if nx.number_of_nodes(G) <= 2:
            for n in G.nodes:
                if G.in_degree(n) == 0:
                    G.nodes[n]["isRoot"] = 1
                    break  # 仅有一个根, 找到即可退出
        # 含有3个节点的子图
        if nx.number_of_nodes(G) <= 2:
            for u, v in G.edges_iter():
                if G.in_degree(u) == 0 and G[u][v][metric] >= threshold:
                    G.nodes[n]["isRoot"] = 1  # 可能存在2个根
                    # print(n, G.nodes[n]["isRoot"])
        # 含有3个节点以上的子图
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
    # controlG = getInitControlG("./backend/res/control.csv")
    # controlG = getRoot(controlG, "rate", 0.5)
    guaranteeG = getInitGuaranteeG("./backend/res/guarantee.csv")

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
