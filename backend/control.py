# -*- coding: utf-8 -*-
import os
import json
import pandas as pd
import numpy as np
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

    # Control关系中，relTag和src一一对应
    G = nx.DiGraph()
    # 构建初始图G, 控制人共70420个节点
    for _, row in control.iterrows():
        # 默认每个节点非根且不存在交叉持股, 具体情况后续判定
        if row["src"] not in G.nodes():
            if row["relType"] == "Control":
                G.add_node(row["src"], isRoot=0, isCross=0, isControl=1)
            else:
                G.add_node(row["src"], isRoot=0, isCross=0, isControl=0)
        elif row["relType"] == "Control":
            G.nodes[row["src"]]["isControl"] = 1
        if row["destn"] not in G.nodes():
            G.add_node(row["destn"], isRoot=0, isCross=0, isControl=0)
        G.add_edge(
            row["src"],
            row["destn"],
            rate=row["rate"],
            # relType=row["relType"],
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
    return subG


def getRootOfControlG(subG):
    """
    找到各个节点的实际控制人
    经检验, 每个子图要么无根, 要么有且仅有一个根, 因此可以简化计算
    经检验, 有根的子图均不存在交叉持股现象
    Params:
        subG: 原子图的列表
    Returns:
        rootG: 含有交叉持股关系的子图
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
        # 若图无根, 则将图逆置后仍无法拓扑排序的公司均为交叉持股, 交叉持股的公司风险绑定
        if not flag:
            tmpG = nx.DiGraph(G)
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
            for n in tmpG.nodes:
                G.nodes[n]["isCross"] = 1  # 标记无法拓扑排序的公司是交叉持股
            rootG.append(G)
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
            rootG.append(G)
        else:
            # 无交叉持股的子图拓扑排序后为空
            rootG.append(G)
    return rootG


def graphs2json(GList):
    """
    将图数据输出为json文件
    Params:
        GList: 图数据
    Outputs:
        输出转化后的json文件
    """
    controlList = {"nodes": [], "links": []}
    crossList = {"nodes": [], "links": []}
    doubleCurList = {"nodes": [], "links": []}
    multiCurList = {"nodes": [], "links": []}
    tmp = {"nodes": [], "links": []}
    i, j = 0, 0
    Gid = 0  # 子图编号
    doubleCount, multiCount = 0, 0
    for item in GList:
        tmp["nodes"], tmp["links"] = [], []
        # 初始化子图数据, 先后加点和边
        inControl, inCross = False, False
        for n in item.nodes:
            if item.nodes[n]["isControl"]:
                group, c, size = 0, "control", 5
                inControl = True
            elif item.nodes[n]["isCross"]:
                group, c, size = 1, "cross", 3
                inCross = True
            elif item.nodes[n]["isRoot"]:
                group, c, size = 2, "root", 3
            else:
                group, c, size = 3, "normal", 1
            tmp["nodes"].append(
                {"group": group, "class": c, "size": size, "Gid": Gid, "id": n}
            )
        for u, v in item.edges:
            tmp["links"].append(
                {"source": u, "target": v, "rate": item[u][v]["rate"]}
            )
        # Control关系json
        if inControl:
            controlList["nodes"] += tmp["nodes"]
            controlList["links"] += tmp["links"]
        # 交叉持股关系json
        if inCross:
            crossList["nodes"] += tmp["nodes"]
            crossList["links"] += tmp["links"]
        # 其他双节点json
        if len(tmp["nodes"]) == 2:
            doubleCount += 2
            # 每个json存储的点不超过3000个
            if doubleCount >= 3000:
                # doubleList.append(doubleCurList)
                path = "./frontend/res/control/" + "double_" + str(i) + ".json"
                with open(path, "w") as f:
                    json.dump(doubleCurList, f)
                i += 1
                doubleCount = 0
                doubleCurList["nodes"], doubleCurList["links"] = [], []
            else:
                doubleCurList["nodes"] += tmp["nodes"]
                doubleCurList["links"] += tmp["links"]
        # 其他多节点json
        else:
            multiCount += len(tmp["nodes"])
            # 每个json存储的点以2950个为阈值
            if multiCount >= 2950:
                path = "./frontend/res/control/" + "multi_" + str(j) + ".json"
                with open(path, "w") as f:
                    json.dump(multiCurList, f)
                j += 1
                multiCount = 0
                multiCurList["nodes"], multiCurList["links"] = [], []
            else:
                multiCurList["nodes"] += tmp["nodes"]
                multiCurList["links"] += tmp["links"]
        Gid += 1
    if len(tmp["nodes"]) == 2:
        doubleCurList["nodes"] += tmp["nodes"]
        doubleCurList["links"] += tmp["links"]
    else:
        multiCurList["nodes"] += tmp["nodes"]
        multiCurList["links"] += tmp["links"]
    if doubleCurList:
        path = "./frontend/res/control/" + "double_" + str(i) + ".json"
        with open(path, "w") as f:
            json.dump(doubleCurList, f)
    if multiCurList:
        path = "./frontend/res/control/" + "multi_" + str(j) + ".json"
        with open(path, "w") as f:
            json.dump(multiCurList, f)
    # 将上述数据写入文件
    with open(r"./frontend/res/control/control.json", "w") as f:
        json.dump(controlList, f)
    with open(r"./frontend/res/control/cross.json", "w") as f:
        json.dump(crossList, f)
