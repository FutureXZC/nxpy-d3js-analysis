import control
import guarantee
import moneyCollection

if __name__ == "__main__":
    # 控制人表
    # controlG = control.getInitControlG("./backend/res/control.csv")
    # controlRootG = control.getRootOfControlG(controlG)
    # control.graphs2json(controlRootG)

    # 担保关系表
    guaranteeG = guarantee.getInitGuaranteeG("./backend/res/guarantee.csv")
    guaranteeRiskG = guarantee.markRiskOfGuaranteeG(guaranteeG)
    guarantee.harmonicDistance(guaranteeRiskG)
    guarantee.graphs2json(guaranteeRiskG)

    # 资金归集表
    # moneyCollectionCut = moneyCollection.getInitmoneyCollectionG("./backend/res/moneyCollection.csv")
    # se, seNodes = moneyCollection.findShellEnterprise(moneyCollectionCut)
    # moneyCollection.graphs2json(moneyCollectionCut, se, seNodes)

