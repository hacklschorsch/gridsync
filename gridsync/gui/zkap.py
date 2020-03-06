# -*- coding: utf-8 -*-

import logging
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)
from twisted.internet.defer import inlineCallbacks

from gridsync.gui.charts import ZKAPBarChartView
from gridsync.gui.font import Font


class ZKAPInfoPane(QWidget):
    def __init__(self, gateway):
        super().__init__()

        self.gateway = gateway

        self.groupbox = QGroupBox()

        title = QLabel(
            f"{gateway.zkap_name_plural} ({gateway.zkap_name_abbrev}s)"
        )
        font = Font(11)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)

        subtext = QLabel(f"1 {gateway.zkap_name_abbrev} = 1 MB for 30 days")
        font = Font(10)
        font.setItalic(True)
        subtext.setFont(font)
        subtext.setAlignment(Qt.AlignCenter)

        self.text_label = QLabel(
            f"<br><i><a href>{gateway.zkap_name_plural}</a></i> -- or "
            f"<i>{gateway.zkap_name_abbrev}s</i> -- are required to store "
            f"data on the {gateway.name} grid. You currently have <b>0</b> "
            "ZKAPs. <p>In order to continue, you will need to purchase "
            "ZKAPs, or generate them by redeeming a voucher code."
        )
        self.text_label.setWordWrap(True)

        view = ZKAPBarChartView()
        view.setFixedHeight(128)
        view.setRenderHint(QPainter.Antialiasing)

        form_layout = QFormLayout()

        self.label_refill = QLabel("0")  # XXX
        self.label_refill.setAlignment(Qt.AlignRight)

        label_usage = QLabel("0")  # XXX
        label_usage.setAlignment(Qt.AlignRight)

        label_expiration = QLabel("0")  # XXX
        label_expiration.setAlignment(Qt.AlignRight)

        label_stored = QLabel("0")  # XXX
        label_stored.setAlignment(Qt.AlignRight)

        form_layout.addRow("Last Refill", self.label_refill)
        form_layout.addRow(
            f"{gateway.zkap_name_abbrev} usage (since last refill)",
            label_usage,
        )
        form_layout.addRow(
            "Next Expiration (at current usage)", label_expiration
        )
        form_layout.addRow("Total Current Amount Stored", label_stored)

        button = QPushButton(f"Purchase {gateway.zkap_name_abbrev}s")
        button.setStyleSheet("background: green; color: white")
        button.clicked.connect(self.on_button_clicked)
        # button.setFixedSize(150, 40)
        button.setFixedSize(180, 30)

        voucher_link = QLabel("<a href>I have a voucher code</a>")

        layout = QGridLayout()
        layout.addItem(QSpacerItem(0, 0, 0, QSizePolicy.Expanding), 10, 0)
        layout.addWidget(title, 20, 0)
        # layout.addWidget(subtext, 30, 0)
        layout.addWidget(self.text_label, 40, 0)
        # layout.addWidget(QLabel(" "), 50, 0)
        # layout.addItem(QSpacerItem(0, 0, 0, QSizePolicy.Expanding), 60, 0)
        layout.addLayout(form_layout, 70, 0)
        layout.addWidget(view, 80, 0)
        layout.addWidget(button, 90, 0, 1, 1, Qt.AlignCenter)
        # layout.addItem(QSpacerItem(0, 0, 0, QSizePolicy.Expanding), 100, 0)
        layout.addWidget(voucher_link, 120, 0, 1, 1, Qt.AlignCenter)
        layout.addItem(QSpacerItem(0, 0, 0, QSizePolicy.Expanding), 999, 0)

        self.groupbox.setLayout(layout)

        main_layout = QGridLayout(self)
        main_layout.addWidget(self.groupbox)

        self.gateway.monitor.zkaps_redeemed_time.connect(
            self.on_zkaps_redeemed_time
        )

    @inlineCallbacks
    def _open_zkap_payment_url(self):  # XXX
        voucher = yield self.gateway.add_voucher()
        payment_url = self.gateway.zkap_payment_url(voucher)
        logging.debug("Opening payment URL %s ...", payment_url)
        if webbrowser.open(payment_url):
            logging.debug("Browser successfully launched")
        else:  # XXX/TODO: Raise a user-facing error
            logging.error("Error launching browser")

    @Slot()
    def on_button_clicked(self):
        self._open_zkap_payment_url()

    @Slot(str)
    def on_zkaps_redeemed_time(self, timestamp):
        self.label_refill.setText(timestamp.split("T")[0])  # TODO: humanize
        self.text_label.hide()
