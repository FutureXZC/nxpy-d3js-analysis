# -*- coding: utf-8 -*-
import datetime
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


def getInitControlG(path):
    """
    读取控制人关系的excel表格到DataFrame, 并切分子图
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
    读取担保关系的excel表格到DataFrame, 并切分子图
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
        # if len(item.nodes()) == 23:
        #     nx.draw(
        #         item,
        #         # pos=nx.spring_layout(G),
        #         # with_labels=True,
        #         # label_size=1000,
        #         # node_size=1000,
        #         # font_size=20,
        #         # edge_labels=edge_labels,
        #     )
        #     plt.show()
    print(nodesNum)
    return subG


def getInitmoneyCollectionG(path):
    """
    读取资金归集的excel表格到DataFrame, 并切分子图
    Param:
        path: 含有资金归集数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    # 由于原csv中存在非utf8字符，需先将其读取为二进制文件流，过滤掉非uft8字符
    with open(path, "rb") as csv_in:
        # 过滤后的内容存在temp.csv中
        with open("./backend/res/temp.csv", "w", encoding="utf-8") as csv_temp:
            for line in csv_in:
                if not line:
                    break
                else:
                    line = line.decode("utf-8", "ignore")
                    csv_temp.write(str(line).rstrip() + "\n")
    # 通过处理完成后的temp.csv读取资金归集数据
    moneyCollection = pd.read_csv("./backend/res/temp.csv", encoding="utf8")
    # 将时间处理为datetime格式，便于后期计算
    txnDate = [
        str(x)[0:4] + "-" + str(x)[4:6] + "-" + str(x)[6:8]
        for x in moneyCollection["jioyrq"]
    ]
    txnTime = map(str, moneyCollection["jioysj"])
    txnTime = [
        str(x // 10000) + ":" + str(x % 10000 // 100) + ":" + str(x % 100)
        for x in moneyCollection["jioysj"]
    ]
    txnDateTime = [
        datetime.datetime.strptime(x[0] + " " + x[1], "%Y-%m-%d %H:%M:%S")
        for x in zip(txnDate, txnTime)
    ]

    # 仅保留有价值的列，其余数据删除
    moneyCollection = moneyCollection[
        [
            "zhangh",  # 本人账号
            "duifzh",  # 对方账户
            "jiaoym",  # 交易码
            "jio1je",  # 交易金额
            # "txnDateTime",  # 交易日期和时间
            "jiedbz",  # 借贷标志
            "jiluzt",  # 记录状态
            "zhyodm",  # 摘要
        ]
    ]
    # txn: transaction, recip: reciprocal
    moneyCollection.columns = [
        "myId",  # 本人账号
        "recipId",  # 对方账户
        "txnCode",  # 交易码
        "txnAmount",  # 交易金额
        # "txnDateTime",  # 交易日期和时间
        "isLoan",  # 借贷标志
        "status",  # 记录状态
        "abstract",  # 摘要
    ]
    moneyCollection.insert(4, "txnDateTime", txnDateTime)
    # print(moneyCollection)

    # 构建初始图G
    G = nx.DiGraph()
    for _, row in moneyCollection.iterrows():
        G.add_node(row["myId"])
        G.add_node(row["recipId"])
        G.add_edge(
            row["myId"],
            row["recipId"],
            txnCode=row["txnCode"],
            txnAmount=row["txnAmount"],
            txnDateTime=row["txnDateTime"],
            isLoan=row["isLoan"],
            status=row["status"],
            abstract=row["abstract"],
        )
    # # 切分子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    # print(len(subG))  # 个子图
    # 各个子图的节点数量
    nodesNum = dict()
    for item in subG:
        if len(item.nodes()) not in nodesNum:
            nodesNum[len(item.nodes())] = 0
        nodesNum[len(item.nodes())] += 1
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
    # guaranteeG = getInitGuaranteeG("./backend/res/guarantee.csv")
    moneyCollection = getInitmoneyCollectionG("./backend/res/moneyCollection.csv")

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
