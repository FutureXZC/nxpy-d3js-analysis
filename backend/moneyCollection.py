import re
import json
import csv
import networkx as nx
import matplotlib.pyplot as plt

# 资金归集识别条件
# txn: transaction, recip: reciprocal
loan = {
    "code": ['EK95','8002','8003','7743'],
    "isLoan": 0,
}
txn = {
    "code": ['6101' ,'6102', '6104' , '61' , '6151' , '2202' , '6002' , '6003' ,
            '6005' , '6006' , '7641' , '7799', '7641' ,'7810', 'DK06' , 'DK05'],
    "txnAmountLimit": 100000.0,
    "isLoan": 1,
    "status": 0,
    "abstract": ['贷款还款', '委托贷款收回利息', '委托贷款收回本金',
                '现金管理子账户占用上存金额补足本次扣款', '公积金放款', '贷款并账']
}

def getInitmoneyCollectionG(path):
    """
    读取资金归集的excel表格到DataFrame, 并切分子图
    Params:
        path: 含有资金归集数据的csv表格
    Returns: 
        GList: 根据表格数据切分得到的子图集合, 每个元素都是一副子图
    """
    # 由于可能存在两个节点间重复建立交易关系, 故使用MultiDiGraph
    G = nx.MultiDiGraph()
    # 由于原csv中存在非utf-8字符，需过滤掉非uft-8字符
    with open("./backend/res/moneyCollection.csv", encoding='utf-8', errors='ignore') as f:
        # 给定的识别贷款和转账的条件
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
        i = 0
        for line in originData:
            # 忽略标题行和Id为空的行
            if line[tag["myId"]] == '' or line[tag["recipId"]] == '' or i == 0:
                i += 1
                continue
            # 贷款和转账条件筛选
            # 交易金额应大于10万
            if float(line[tag["txnAmount"]]) < txn["txnAmountLimit"]:
                continue
            # 贷款条件筛选
            if int(line[tag["isLoan"]]) == loan["isLoan"] and line[tag["txnCode"]] in loan["code"]:
                pass
            # 转账条件筛选
            elif not line[tag["status"]] == "R":
                if line[tag["txnCode"]] in txn["code"] and int(line[tag["isLoan"]]) == txn["isLoan"] and int(line[tag["status"]]) == txn["status"]:
                    flag = False
                    for item in txn["abstract"]:
                        if re.search(item, line[tag["abstract"]]):
                            flag = True
                            break
                    if flag:
                        continue                
            else:
                continue
            # 构建初始图G, 将符合条件的节点和边加入G
            if not G.has_node(line[tag["myId"]]):
                if len(line[tag["myId"]]) >= 15:
                    line[tag["myId"]] = line[tag["myId"]][:-2] + '00'
                G.add_node(line[tag["myId"]])
            if not G.has_node(line[tag["recipId"]]):
                if len(line[tag["recipId"]]) >= 15:
                    line[tag["recipId"]] = line[tag["recipId"]][:-2] + '00'
                G.add_node(line[tag["recipId"]])
            G.add_edge(
                line[tag["myId"]],
                line[tag["recipId"]],
                txnAmount=float(line[tag["txnAmount"]]),
                txnDateTime=int(line[tag["txnDateTime"]]),
                isLoan=int(line[tag["isLoan"]]),
            )
            i += 1
    print("符合条件的贷款和转账总数关系总数：", G.size())
    print("含有贷款和转账的公司数量：", nx.number_of_nodes(G))

    # 切分子图
    tmp = nx.to_undirected(G)
    GList = list()
    for c in nx.connected_components(tmp):
        GList.append(G.subgraph(c))
    return GList

def findShellEnterprise(GList):
    '''
    根据资金归集关系找到空壳企业
    Params:
        GList: 资金归集子图列表
    Returns:
        se: 企业资金归集图
        seNodes: 中间企业列表
    '''
    se = nx.MultiDiGraph()
    seNodes = list()
    for subG in GList:
        for n in subG.nodes():
            children = list(subG.neighbors(n))
            father = list(subG.predecessors(n))
            if not father or not children:
                continue
            # 上游企业
            for f in father:
                for k1 in subG[f][n]:
                    # 若入边非贷款, 直接跳过
                    if subG[f][n][k1]["isLoan"] == txn["isLoan"]:
                        continue
                    # 寻找最匹配的贷款和转账
                    bestMatchF, bestMatchRate, bestMatchC, bestMatchLoan, bestMatchTxn, bestMatchDate = "", 0.9, "", -1, -1, 0
                    # 下游企业
                    for c in children:
                        for k2 in subG[n][c]:
                            # 若出边非转账或三元组上任意两个节点相同, 直接跳过
                            if subG[n][c][k2]["isLoan"] == loan["isLoan"] or c == f or c == n or n == f:
                                continue
                            # 日期相差五天, 且金额变化在0.9-1.0范围内
                            rate = subG[n][c][k2]["txnAmount"] / subG[f][n][k1]["txnAmount"]
                            if subG[n][c][k2]["txnDateTime"] - subG[f][n][k1]["txnDateTime"] <= 5 and subG[n][c][k2]["txnDateTime"] > subG[f][n][k1]["txnDateTime"] and rate >= bestMatchRate and rate <= 1:
                                bestMatchC, bestMatchRate, bestMatchF = c, rate, f
                                bestMatchLoan, bestMatchTxn = subG[f][n][k1]["txnAmount"], subG[n][c][k2]["txnAmount"]
                                bestMatchDate = (subG[f][n][k1]["txnDateTime"], subG[n][c][k2]["txnDateTime"])
                        # 如果找到了匹配到的贷款和转账, 则修改节点属性, 将其记录到se中
                    if bestMatchC:
                        print("father: ", bestMatchF, "node: ", n, "child: ", bestMatchC)
                        print("rate: ", bestMatchRate, "贷款金额: ", bestMatchLoan, "转账金额: ", bestMatchTxn, "贷款和转账日期: ", bestMatchDate)
                        se.add_edge(bestMatchF, n, txnAmount=bestMatchLoan, isLoan=0, date=bestMatchDate[0])
                        se.add_edge(n, bestMatchC, txnAmount=bestMatchTxn, isLoan=1, date=bestMatchDate[1])
                        seNodes.append(n)
    if (nx.number_of_nodes(se)):
        print(se.size(), nx.number_of_nodes(se))
        seNodes = list(set(seNodes))
        print("具有资金归集行为的中间企业数量为：", len(seNodes))
        print("资金归集的中间企业列表：", seNodes)
    return se, seNodes

def graphs2json(se, seNodes):
    '''
    将资金归集的识别结果导出为json
    Params:
        se: 按中心企业切分的资金归集识别列表
        seNodes: 中心企业列表
    '''
    pass
