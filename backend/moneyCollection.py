import re
import json
# import math
import csv
import datetime
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
# import openpyxl


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
        "jioyrq": 1,  # 交易日期
        "jioysj": 3,  # 交易时间
        "txnCode": 4,  # 交易码
        "txnAmount": 7,  # 交易金额
        "isLoan": 6,  # 借贷标志
        "status": -1,  # 状态码
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
        elif line[tag["isLoan"]] == txn["isLoan"] and line[tag["status"]] == txn["status"] and line[tag["txnCode"]] in txn["code"]:
            flag = False
            for item in txn["abstract"]:
                if re.search(item, line[tag["abstract"]]):
                    flag = True
                    break
            if flag:
                continue
        else:
            continue
        ## 日期格式处理
        # 将时间处理为datetime格式，便于后期计算
        txnDate = line[tag["jioyrq"]][0:4] + "-" + line[tag["jioyrq"]][4:6] + "-" + line[tag["jioyrq"]][6:8]
        x = int(line[tag["jioysj"]])
        txnTime = str(x // 10000) + ":" + str(x % 10000 // 100) + ":" + str(x % 100)
        txnDateTime = datetime.datetime.strptime(txnDate + " " + txnTime, "%Y-%m-%d %H:%M:%S")
        moneyCollection.append({
            "myId": line[tag["myId"]],
            "recipId": line[tag["recipId"]],
            "txnDateTime": txnDateTime,
            "txnAmount": line[tag["txnAmount"]],
            "isLoan": line[tag["isLoan"]],
            "abstract": line[tag["abstract"]]
        })

    ## 构建初始图G, 17368条边
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
            abstract=row["abstract"],
        )
    # 切分67个子图
    tmp = nx.to_undirected(G)
    subG = list()
    for c in nx.connected_components(tmp):
        subG.append(G.subgraph(c))
    # 各个子图的节点数量
    nodesNum = dict()
    for item in subG:
        if len(item.nodes()) not in nodesNum:
            nodesNum[len(item.nodes())] = 0
        nodesNum[len(item.nodes())] += 1
    print(nodesNum)
    print(sum(nodesNum.values()))
    return subG

def findShellEnterprise(GList):
    '''
    根据资金归集关系找到空壳企业
    Params:
        GList: 资金归集子图列表
    Returns:
        se: Shell Enterprise, 空壳企业信息列表
    '''
    se = list()
    count = 0
    for subG in GList:
        flag = False
        for n in subG.nodes():
            children = list(subG.neighbors(n))
            father = list(subG.predecessors(n))
            # print(children, father)
            if len(children) == 0 or len(father) == 0:
                continue
            count += 1
            for f in father:
                # 寻找最匹配的贷款和转账
                bestMatchC, bestMatchRate = "", 0.9
                for c in children:
                    # 若入边非贷款出边非转账, 直接跳过
                    if not subG[f][n]["isLoan"] or subG[n][c]["isLoan"]:
                        continue
                    # 日期相差五天, 且金额变化在0.9-1.0范围内
                    rate = (subG[n][c]["txnAmount"] - subG[f][n]["txnAmount"]) / subG[f][n]["txnAmount"]
                    if (subG[n][c]["txnDateTime"] - subG[f][n]["txnDateTime"]).days < 5 and rate >= bestMatchRate:
                        bestMatchC, bestMatchRate = c, rate
                # 如果找到了匹配到的贷款和转账, 则修改节点属性 
                if bestMatchC:
                    subG.nodes[n]["matchLoan"] = f
                    subG.nodes[n]["matchTxn"] = c
                    flag = True
        # 如果该子图存在贷款和转账行为匹配, 则将其记录到se中
        if flag:
            se.append(subG)
    # 各个子图的节点数量
    nodesNum = dict()
    for item in se:
        if len(item.nodes()) not in nodesNum:
            nodesNum[len(item.nodes())] = 0
        nodesNum[len(item.nodes())] += 1
    print(nodesNum)
    print(count)
    return se

