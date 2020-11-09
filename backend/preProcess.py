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
        df: 读取excel表格得到的DataFrame
    """
    control = pd.read_csv(tPath, encoding="gb2312")
    # 将列名索引修改为英文
    control.columns = ["relTarget", "src", "destn", "relType", "rate"]
    # 将比例大于100的异常值修正为100，并归一化
    control.rate[control.rate >= 100] = 100
    control["rate"] /= 100
    # 关系类型修正为"0: 投资, 1: 控制"
    control.relType[control.relType == "Control"] = 1
    control.relType[control.relType == "Investment"] = 0
    # print(control)

    # Control关系中，关系标识和关系类型一一对应
    # 关系标志共39910

    # 控制人共70420个节点
    co = list()  # 节点名称, 下标对应节点编号
    codict = dict()  # 节点所属的子图, {节点名称: 所属子图号}
    G = nx.DiGraph()  # 原始有向图
    i = 0  # 节点编号
    for _, row in control.iterrows():
        if row["src"] not in co:
            co.append(row["src"])
            codict[row["src"]] = i
            i += 1
        if row["destn"] not in co:
            co.append(row["destn"])
            codict[row["destn"]] = i
            i += 1
        # 用节点编号作为画图的依据
        x, y = co.index(row["src"]), co.index(row["destn"])
        G.add_nodes_from([x, y])
        G.add_edge(x, y)
    # 在co内使用并查集思想划分子图, 初始所属子图即为编号
    def findFather(x):
        if codict[x] != co.index(x):
            codict[x] = findFather(co[codict[x]])
        return codict[x]

    for _, row in control.iterrows():
        x = findFather(row["src"])
        y = findFather(row["destn"])
        codict[co[x]] = y
    for c in codict:
        findFather(c)
    # 按子图编号取出各点
    subGNodes = dict()
    for c in codict:
        if codict[c] not in subGNodes:
            subGNodes[codict[c]] = list()
        subGNodes[codict[c]].append(c)
    print(subGNodes)
    print(len(subGNodes))
    subControlG = list()
    for sub in subGNodes:
        subControlG.append(nx.subgraph(G, subGNodes[sub]))
    print(subControlG)
    print(len(subControlG))
    return subControlG


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
