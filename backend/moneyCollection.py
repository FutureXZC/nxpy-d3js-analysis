import re
import json
import csv
import datetime
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


def getInitmoneyCollectionG(path):
    """
    读取资金归集的excel表格到DataFrame, 并切分子图
    Params:
        path: 含有资金归集数据的excel表格
    Returns: 
        subG: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    # 由于原csv中存在非utf-8字符，需先将其读取为二进制文件流，过滤掉非uft-8字符
    f = open("./backend/res/moneyCollection.csv", encoding='utf-8', errors='ignore')
    # 给定的识别贷款和转账的条件
    # txn: transaction, recip: reciprocal
    loan = {
        "code": ['EK95','8002','8003','7743'],
        "isLoan": "0",
    }
    txn = {
        "code": ['6101' ,'6102', '6104' , '61' , '6151' , '2202' , '6002' , '6003' ,
                '6005' , '6006' , '7641' , '7799', '7641' ,'7810', 'DK06' , 'DK05'],
        "txnAmountLimit": 100000.0,
        "isLoan": "1",
        "status": "0",
        "abstract": ['贷款还款', '委托贷款收回利息', '委托贷款收回本金',
                    '现金管理子账户占用上存金额补足本次扣款', '公积金放款', '贷款并账']
    }
    originData = csv.reader(f)
    tag = {
        "myId": 0,  # 本人账户
        "recipId": 29,  # 对方账户
        "txnDateTime": 1,  # 交易日期
        "txnCode": 4,  # 交易码
        "txnAmount": 7,  # 交易金额
        "isLoan": 6,  # 借贷标志
        "status": 33,  # 状态码
        "abstract": 21  # 摘要
    }
    moneyCollection = list()
    for line in originData:
        ## 忽略标题行
        if line[0] == 'zhangh':
            continue
        ## 贷款和转账条件筛选
        # 交易金额应大于10万
        if float(line[tag["txnAmount"]]) < txn["txnAmountLimit"]:
            continue
        # 贷款条件筛选
        if line[tag["isLoan"]] == loan["isLoan"] and line[tag["txnCode"]] in loan["code"]:
            pass
        # 转账条件筛选
        elif not line[tag["status"]] == "R":
            if line[tag["txnCode"]] in txn["code"] and int(line[tag["isLoan"]]) == int(txn["isLoan"]) and int(line[tag["status"]]) == int(txn["status"]):
                flag = False
                for item in txn["abstract"]:
                    if re.search(item, line[tag["abstract"]]):
                        flag = True
                        break
                if flag:
                    continue                
        else:
            continue

        moneyCollection.append({
            "myId": line[tag["myId"]],
            "recipId": line[tag["recipId"]],
            "txnDateTime": int(line[tag["txnDateTime"]]),
            "txnAmount": float(line[tag["txnAmount"]]),
            "isLoan": int(line[tag["isLoan"]]),
        })

    ## 构建初始图G
    G = nx.DiGraph()
    for row in moneyCollection:
        if row["myId"] not in G.nodes():
            G.add_node(row["myId"], matchLoan="", matchTxn="")
        if row["recipId"] not in G.nodes():
            G.add_node(row["recipId"], matchLoan="", matchTxn="")
        G.add_edge(
            row["myId"],
            row["recipId"],
            txnAmount=row["txnAmount"],
            txnDateTime=row["txnDateTime"],
            isLoan=row["isLoan"],
        )
    # print(G.size())
    # 切分子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    # 各个子图的节点数量
    # nodesNum = dict()
    # edgesNum = dict()
    # for item in subG:
    #     if len(item.nodes()) not in nodesNum:
    #         nodesNum[len(item.nodes())] = 0
    #     nodesNum[len(item.nodes())] += 1
    #     if item.size() not in edgesNum:
    #         edgesNum[item.size()] = 0
    #     edgesNum[item.size()] += 1
    # print(nodesNum)
    # print(sum(nodesNum.keys()))
    # print(edgesNum)
    # print(sum(edgesNum.keys()))
    return subG

def findShellEnterprise(GList):
    '''
    根据资金归集关系找到空壳企业
    Params:
        GList: 资金归集子图列表
    Returns:
        se: 空壳企业信息图
    '''
    se = nx.DiGraph()
    for subG in GList:
        for n in subG.nodes():
            children = list(subG.neighbors(n))
            father = list(subG.predecessors(n))
            if not father or not children:
                continue
            for f in father:
                # 寻找最匹配的贷款和转账
                bestMatchF, bestMatchRate, bestMatchC = "", 0.9, ""
                for c in children:
                    # 若入边非贷款出边非转账, 直接跳过
                    if subG[f][n]["isLoan"] == 1 or subG[n][c]["isLoan"] == 0:
                        continue
                    # 日期相差五天, 且金额变化在0.9-1.0范围内
                    rate = subG[n][c]["txnAmount"] / subG[f][n]["txnAmount"]
                    if subG[n][c]["txnDateTime"] - subG[f][n]["txnDateTime"] <= 5 and rate >= bestMatchRate and rate <= 1:
                        bestMatchC, bestMatchRate, bestMatchF = c, rate, f
                # 如果找到了匹配到的贷款和转账, 则修改节点属性, 将其记录到se中
                if bestMatchC:
                    print(bestMatchF, n, bestMatchC, bestMatchRate)
                    subG.nodes[n]["matchLoan"] = bestMatchF
                    subG.nodes[n]["matchTxn"] = bestMatchC
                    se.add_edge(
                        bestMatchF, n,
                        txnAmount=subG[f][n]["txnAmount"]
                    )
                    se.add_edge(
                        n, bestMatchC,
                        txnAmount=subG[n][c]["txnAmount"]
                    )
    def testDraw(G):
        """
        测试绘图
        """
        pos = nx.shell_layout(G)
        nx.draw(G, pos)
        # node_labels = nx.get_node_attributes(G, "guarType")
        nx.draw_networkx_labels(G, pos)
        # edge_labels = nx.get_edge_attributes(G, "guarType")
        nx.draw_networkx_edge_labels(G, pos)
        plt.show()

    # testDraw(se)
    # print(se.size())
    return se

