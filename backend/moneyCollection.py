import json
import datetime
import pandas as pd
import networkx as nx


def getInitmoneyCollectionG(path):
    """
    读取资金归集的excel表格到DataFrame, 并切分子图
    Params:
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
    # 切分15个子图
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
