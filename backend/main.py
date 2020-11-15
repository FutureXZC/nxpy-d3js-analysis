import control
import guarantee
import moneyCollection
import matplotlib.pyplot as plt

if __name__ == "__main__":
    # 控制人表
    # controlG = control.getInitControlG("./backend/res/control.csv")
    # controlRootG = control.getRootOfControlG(controlG)
    # control.graphs2json(
    #     controlRootG,
    #     "./frontend/res/control_double.json",
    #     "./frontend/res/control_multi.json",
    # )

    # 担保关系表
    guaranteeG = guarantee.getInitGuaranteeG("./backend/res/guarantee.csv")
    guaranteeRiskG = guarantee.markRiskOfGuaranteeG(guaranteeG)
    # guarantee.graphs2json(
    #     guaranteeRiskG,
    #     "./frontend/res/guarantee_double.json",
    #     "./frontend/res/guarantee_multi.json",
    # )

    # 资金归集表
    # moneyCollection = moneyCollection.getInitmoneyCollectionG("./backend/res/moneyCollection.csv")
