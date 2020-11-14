import control
import guarantee
import moneyCollection
import matplotlib.pyplot as plt

if __name__ == "__main__":
    controlG = control.getInitControlG("./backend/res/control.csv")
    controlRootG = control.getRootOfControlG(controlG)
    control.graphs2json(
        controlRootG,
        "./frontend/res/control_double.json",
        "./frontend/res/control_multi.json",
    )

    # guaranteeG = guarantee.getInitGuaranteeG("./backend/res/guarantee.csv")
    # guarantee.markRiskOfGuaranteeG(guaranteeG)

    # moneyCollection = moneyCollection.getInitmoneyCollectionG("./backend/res/moneyCollection.csv")

    # nx.draw(
    #     tmp[10],
    #     # pos=nx.spring_layout(G),
    #     with_labels=True,
    #     label_size=1000,
    #     node_size=1000,
    #     font_size=20,
    #     # edge_labels=edge_labels,
    # )
    # plt.show()
