# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMenuBar, QPushButton,
    QSizePolicy, QSpacerItem, QStatusBar, QTextBrowser,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(784, 642)
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        font.setPointSize(11)
        MainWindow.setFont(font)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout_main = QVBoxLayout(self.centralwidget)
        self.verticalLayout_main.setSpacing(16)
        self.verticalLayout_main.setObjectName(u"verticalLayout_main")
        self.verticalLayout_main.setContentsMargins(20, 20, 20, 20)
        self.horizontalLayout_top = QHBoxLayout()
        self.horizontalLayout_top.setSpacing(16)
        self.horizontalLayout_top.setObjectName(u"horizontalLayout_top")
        self.groupBox_trading_info = QGroupBox(self.centralwidget)
        self.groupBox_trading_info.setObjectName(u"groupBox_trading_info")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_trading_info.sizePolicy().hasHeightForWidth())
        self.groupBox_trading_info.setSizePolicy(sizePolicy)
        self.groupBox_trading_info.setMinimumSize(QSize(185, 120))
        self.groupBox_trading_info.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #5dade2;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(90, 173, 226, 0.08);\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #5dade2;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}\n"
"")
        self.verticalLayout_trading = QVBoxLayout(self.groupBox_trading_info)
        self.verticalLayout_trading.setObjectName(u"verticalLayout_trading")
        self.horizontalLayout_spy = QHBoxLayout()
        self.horizontalLayout_spy.setObjectName(u"horizontalLayout_spy")
        self.label_spy_name = QLabel(self.groupBox_trading_info)
        self.label_spy_name.setObjectName(u"label_spy_name")
        font1 = QFont()
        font1.setBold(True)
        self.label_spy_name.setFont(font1)

        self.horizontalLayout_spy.addWidget(self.label_spy_name)

        self.label_spy_value = QLabel(self.groupBox_trading_info)
        self.label_spy_value.setObjectName(u"label_spy_value")
        self.label_spy_value.setFont(font1)

        self.horizontalLayout_spy.addWidget(self.label_spy_value)


        self.verticalLayout_trading.addLayout(self.horizontalLayout_spy)

        self.horizontalLayout_usd_cad = QHBoxLayout()
        self.horizontalLayout_usd_cad.setObjectName(u"horizontalLayout_usd_cad")
        self.label_usd_cad_name = QLabel(self.groupBox_trading_info)
        self.label_usd_cad_name.setObjectName(u"label_usd_cad_name")

        self.horizontalLayout_usd_cad.addWidget(self.label_usd_cad_name)

        self.label_usd_cad_value = QLabel(self.groupBox_trading_info)
        self.label_usd_cad_value.setObjectName(u"label_usd_cad_value")

        self.horizontalLayout_usd_cad.addWidget(self.label_usd_cad_value)


        self.verticalLayout_trading.addLayout(self.horizontalLayout_usd_cad)

        self.horizontalLayout_cad_usd = QHBoxLayout()
        self.horizontalLayout_cad_usd.setObjectName(u"horizontalLayout_cad_usd")
        self.label_cad_usd_name = QLabel(self.groupBox_trading_info)
        self.label_cad_usd_name.setObjectName(u"label_cad_usd_name")

        self.horizontalLayout_cad_usd.addWidget(self.label_cad_usd_name)

        self.label_cad_usd_value = QLabel(self.groupBox_trading_info)
        self.label_cad_usd_value.setObjectName(u"label_cad_usd_value")

        self.horizontalLayout_cad_usd.addWidget(self.label_cad_usd_value)


        self.verticalLayout_trading.addLayout(self.horizontalLayout_cad_usd)


        self.horizontalLayout_top.addWidget(self.groupBox_trading_info)

        self.groupBox_option_info = QGroupBox(self.centralwidget)
        self.groupBox_option_info.setObjectName(u"groupBox_option_info")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox_option_info.sizePolicy().hasHeightForWidth())
        self.groupBox_option_info.setSizePolicy(sizePolicy1)
        self.groupBox_option_info.setMinimumSize(QSize(270, 240))
        self.groupBox_option_info.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #5dade2;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(90, 173, 226, 0.08);\n"
"    padding-top: 10px;\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #5dade2;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}\n"
"")
        self.verticalLayout_option_info = QVBoxLayout(self.groupBox_option_info)
        self.verticalLayout_option_info.setObjectName(u"verticalLayout_option_info")
        self.horizontalLayout_strike_exp = QHBoxLayout()
        self.horizontalLayout_strike_exp.setObjectName(u"horizontalLayout_strike_exp")
        self.horizontalLayout_strike = QHBoxLayout()
        self.horizontalLayout_strike.setObjectName(u"horizontalLayout_strike")
        self.label_strike_name = QLabel(self.groupBox_option_info)
        self.label_strike_name.setObjectName(u"label_strike_name")

        self.horizontalLayout_strike.addWidget(self.label_strike_name)

        self.label_strike_value = QLabel(self.groupBox_option_info)
        self.label_strike_value.setObjectName(u"label_strike_value")

        self.horizontalLayout_strike.addWidget(self.label_strike_value)


        self.horizontalLayout_strike_exp.addLayout(self.horizontalLayout_strike)

        self.horizontalLayout_expiration = QHBoxLayout()
        self.horizontalLayout_expiration.setObjectName(u"horizontalLayout_expiration")
        self.label_expiration_name = QLabel(self.groupBox_option_info)
        self.label_expiration_name.setObjectName(u"label_expiration_name")

        self.horizontalLayout_expiration.addWidget(self.label_expiration_name)

        self.label_expiration_value = QLabel(self.groupBox_option_info)
        self.label_expiration_value.setObjectName(u"label_expiration_value")

        self.horizontalLayout_expiration.addWidget(self.label_expiration_value)


        self.horizontalLayout_strike_exp.addLayout(self.horizontalLayout_expiration)


        self.verticalLayout_option_info.addLayout(self.horizontalLayout_strike_exp)

        self.horizontalLayout_puts_calls = QHBoxLayout()
        self.horizontalLayout_puts_calls.setObjectName(u"horizontalLayout_puts_calls")
        self.verticalLayout_puts = QVBoxLayout()
        self.verticalLayout_puts.setObjectName(u"verticalLayout_puts")
        self.label_puts_title = QLabel(self.groupBox_option_info)
        self.label_puts_title.setObjectName(u"label_puts_title")
        self.label_puts_title.setFont(font1)

        self.verticalLayout_puts.addWidget(self.label_puts_title)

        self.horizontalLayout_put_price = QHBoxLayout()
        self.horizontalLayout_put_price.setObjectName(u"horizontalLayout_put_price")
        self.label_put_price_name = QLabel(self.groupBox_option_info)
        self.label_put_price_name.setObjectName(u"label_put_price_name")

        self.horizontalLayout_put_price.addWidget(self.label_put_price_name)

        self.label_put_price_value = QLabel(self.groupBox_option_info)
        self.label_put_price_value.setObjectName(u"label_put_price_value")
        self.label_put_price_value.setFont(font1)

        self.horizontalLayout_put_price.addWidget(self.label_put_price_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_price)

        self.horizontalLayout_put_bid = QHBoxLayout()
        self.horizontalLayout_put_bid.setObjectName(u"horizontalLayout_put_bid")
        self.label_put_bid_name = QLabel(self.groupBox_option_info)
        self.label_put_bid_name.setObjectName(u"label_put_bid_name")

        self.horizontalLayout_put_bid.addWidget(self.label_put_bid_name)

        self.label_put_bid_value = QLabel(self.groupBox_option_info)
        self.label_put_bid_value.setObjectName(u"label_put_bid_value")

        self.horizontalLayout_put_bid.addWidget(self.label_put_bid_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_bid)

        self.horizontalLayout_put_ask = QHBoxLayout()
        self.horizontalLayout_put_ask.setObjectName(u"horizontalLayout_put_ask")
        self.label_put_ask_name = QLabel(self.groupBox_option_info)
        self.label_put_ask_name.setObjectName(u"label_put_ask_name")

        self.horizontalLayout_put_ask.addWidget(self.label_put_ask_name)

        self.label_put_ask_value = QLabel(self.groupBox_option_info)
        self.label_put_ask_value.setObjectName(u"label_put_ask_value")

        self.horizontalLayout_put_ask.addWidget(self.label_put_ask_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_ask)

        self.horizontalLayout_put_delta = QHBoxLayout()
        self.horizontalLayout_put_delta.setObjectName(u"horizontalLayout_put_delta")
        self.label_put_delta_name = QLabel(self.groupBox_option_info)
        self.label_put_delta_name.setObjectName(u"label_put_delta_name")

        self.horizontalLayout_put_delta.addWidget(self.label_put_delta_name)

        self.label_put_delta_value = QLabel(self.groupBox_option_info)
        self.label_put_delta_value.setObjectName(u"label_put_delta_value")

        self.horizontalLayout_put_delta.addWidget(self.label_put_delta_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_delta)

        self.horizontalLayout_put_gamma = QHBoxLayout()
        self.horizontalLayout_put_gamma.setObjectName(u"horizontalLayout_put_gamma")
        self.label_put_gamma_name = QLabel(self.groupBox_option_info)
        self.label_put_gamma_name.setObjectName(u"label_put_gamma_name")

        self.horizontalLayout_put_gamma.addWidget(self.label_put_gamma_name)

        self.label_put_gamma_value = QLabel(self.groupBox_option_info)
        self.label_put_gamma_value.setObjectName(u"label_put_gamma_value")

        self.horizontalLayout_put_gamma.addWidget(self.label_put_gamma_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_gamma)

        self.horizontalLayout_put_theta = QHBoxLayout()
        self.horizontalLayout_put_theta.setObjectName(u"horizontalLayout_put_theta")
        self.label_put_theta_name = QLabel(self.groupBox_option_info)
        self.label_put_theta_name.setObjectName(u"label_put_theta_name")

        self.horizontalLayout_put_theta.addWidget(self.label_put_theta_name)

        self.label_put_theta_value = QLabel(self.groupBox_option_info)
        self.label_put_theta_value.setObjectName(u"label_put_theta_value")

        self.horizontalLayout_put_theta.addWidget(self.label_put_theta_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_theta)

        self.horizontalLayout_put_vega = QHBoxLayout()
        self.horizontalLayout_put_vega.setObjectName(u"horizontalLayout_put_vega")
        self.label_put_vega_name = QLabel(self.groupBox_option_info)
        self.label_put_vega_name.setObjectName(u"label_put_vega_name")

        self.horizontalLayout_put_vega.addWidget(self.label_put_vega_name)

        self.label_put_vega_value = QLabel(self.groupBox_option_info)
        self.label_put_vega_value.setObjectName(u"label_put_vega_value")

        self.horizontalLayout_put_vega.addWidget(self.label_put_vega_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_vega)

        self.horizontalLayout_put_openint = QHBoxLayout()
        self.horizontalLayout_put_openint.setObjectName(u"horizontalLayout_put_openint")
        self.label_put_openint_name = QLabel(self.groupBox_option_info)
        self.label_put_openint_name.setObjectName(u"label_put_openint_name")

        self.horizontalLayout_put_openint.addWidget(self.label_put_openint_name)

        self.label_put_openint_value = QLabel(self.groupBox_option_info)
        self.label_put_openint_value.setObjectName(u"label_put_openint_value")

        self.horizontalLayout_put_openint.addWidget(self.label_put_openint_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_openint)

        self.horizontalLayout_put_volume = QHBoxLayout()
        self.horizontalLayout_put_volume.setObjectName(u"horizontalLayout_put_volume")
        self.label_put_volume_name = QLabel(self.groupBox_option_info)
        self.label_put_volume_name.setObjectName(u"label_put_volume_name")

        self.horizontalLayout_put_volume.addWidget(self.label_put_volume_name)

        self.label_put_volume_value = QLabel(self.groupBox_option_info)
        self.label_put_volume_value.setObjectName(u"label_put_volume_value")

        self.horizontalLayout_put_volume.addWidget(self.label_put_volume_value)


        self.verticalLayout_puts.addLayout(self.horizontalLayout_put_volume)


        self.horizontalLayout_puts_calls.addLayout(self.verticalLayout_puts)

        self.verticalLayout_calls = QVBoxLayout()
        self.verticalLayout_calls.setObjectName(u"verticalLayout_calls")
        self.label_calls_title = QLabel(self.groupBox_option_info)
        self.label_calls_title.setObjectName(u"label_calls_title")
        self.label_calls_title.setFont(font1)

        self.verticalLayout_calls.addWidget(self.label_calls_title)

        self.horizontalLayout_call_price = QHBoxLayout()
        self.horizontalLayout_call_price.setObjectName(u"horizontalLayout_call_price")
        self.label_call_price_name = QLabel(self.groupBox_option_info)
        self.label_call_price_name.setObjectName(u"label_call_price_name")

        self.horizontalLayout_call_price.addWidget(self.label_call_price_name)

        self.label_call_price_value = QLabel(self.groupBox_option_info)
        self.label_call_price_value.setObjectName(u"label_call_price_value")
        self.label_call_price_value.setFont(font1)

        self.horizontalLayout_call_price.addWidget(self.label_call_price_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_price)

        self.horizontalLayout_call_bid = QHBoxLayout()
        self.horizontalLayout_call_bid.setObjectName(u"horizontalLayout_call_bid")
        self.label_call_bid_name = QLabel(self.groupBox_option_info)
        self.label_call_bid_name.setObjectName(u"label_call_bid_name")

        self.horizontalLayout_call_bid.addWidget(self.label_call_bid_name)

        self.label_call_bid_value = QLabel(self.groupBox_option_info)
        self.label_call_bid_value.setObjectName(u"label_call_bid_value")

        self.horizontalLayout_call_bid.addWidget(self.label_call_bid_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_bid)

        self.horizontalLayout_call_ask = QHBoxLayout()
        self.horizontalLayout_call_ask.setObjectName(u"horizontalLayout_call_ask")
        self.label_call_ask_name = QLabel(self.groupBox_option_info)
        self.label_call_ask_name.setObjectName(u"label_call_ask_name")

        self.horizontalLayout_call_ask.addWidget(self.label_call_ask_name)

        self.label_call_ask_value = QLabel(self.groupBox_option_info)
        self.label_call_ask_value.setObjectName(u"label_call_ask_value")

        self.horizontalLayout_call_ask.addWidget(self.label_call_ask_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_ask)

        self.horizontalLayout_call_delta = QHBoxLayout()
        self.horizontalLayout_call_delta.setObjectName(u"horizontalLayout_call_delta")
        self.label_call_delta_name = QLabel(self.groupBox_option_info)
        self.label_call_delta_name.setObjectName(u"label_call_delta_name")

        self.horizontalLayout_call_delta.addWidget(self.label_call_delta_name)

        self.label_call_delta_value = QLabel(self.groupBox_option_info)
        self.label_call_delta_value.setObjectName(u"label_call_delta_value")

        self.horizontalLayout_call_delta.addWidget(self.label_call_delta_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_delta)

        self.horizontalLayout_call_gamma = QHBoxLayout()
        self.horizontalLayout_call_gamma.setObjectName(u"horizontalLayout_call_gamma")
        self.label_call_gamma_name = QLabel(self.groupBox_option_info)
        self.label_call_gamma_name.setObjectName(u"label_call_gamma_name")

        self.horizontalLayout_call_gamma.addWidget(self.label_call_gamma_name)

        self.label_call_gamma_value = QLabel(self.groupBox_option_info)
        self.label_call_gamma_value.setObjectName(u"label_call_gamma_value")

        self.horizontalLayout_call_gamma.addWidget(self.label_call_gamma_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_gamma)

        self.horizontalLayout_call_theta = QHBoxLayout()
        self.horizontalLayout_call_theta.setObjectName(u"horizontalLayout_call_theta")
        self.label_call_theta_name = QLabel(self.groupBox_option_info)
        self.label_call_theta_name.setObjectName(u"label_call_theta_name")

        self.horizontalLayout_call_theta.addWidget(self.label_call_theta_name)

        self.label_call_theta_value = QLabel(self.groupBox_option_info)
        self.label_call_theta_value.setObjectName(u"label_call_theta_value")

        self.horizontalLayout_call_theta.addWidget(self.label_call_theta_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_theta)

        self.horizontalLayout_call_vega = QHBoxLayout()
        self.horizontalLayout_call_vega.setObjectName(u"horizontalLayout_call_vega")
        self.label_call_vega_name = QLabel(self.groupBox_option_info)
        self.label_call_vega_name.setObjectName(u"label_call_vega_name")

        self.horizontalLayout_call_vega.addWidget(self.label_call_vega_name)

        self.label_call_vega_value = QLabel(self.groupBox_option_info)
        self.label_call_vega_value.setObjectName(u"label_call_vega_value")

        self.horizontalLayout_call_vega.addWidget(self.label_call_vega_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_vega)

        self.horizontalLayout_call_openint = QHBoxLayout()
        self.horizontalLayout_call_openint.setObjectName(u"horizontalLayout_call_openint")
        self.label_call_openint_name = QLabel(self.groupBox_option_info)
        self.label_call_openint_name.setObjectName(u"label_call_openint_name")

        self.horizontalLayout_call_openint.addWidget(self.label_call_openint_name)

        self.label_call_openint_value = QLabel(self.groupBox_option_info)
        self.label_call_openint_value.setObjectName(u"label_call_openint_value")

        self.horizontalLayout_call_openint.addWidget(self.label_call_openint_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_openint)

        self.horizontalLayout_call_volume = QHBoxLayout()
        self.horizontalLayout_call_volume.setObjectName(u"horizontalLayout_call_volume")
        self.label_call_volume_name = QLabel(self.groupBox_option_info)
        self.label_call_volume_name.setObjectName(u"label_call_volume_name")

        self.horizontalLayout_call_volume.addWidget(self.label_call_volume_name)

        self.label_call_volume_value = QLabel(self.groupBox_option_info)
        self.label_call_volume_value.setObjectName(u"label_call_volume_value")

        self.horizontalLayout_call_volume.addWidget(self.label_call_volume_value)


        self.verticalLayout_calls.addLayout(self.horizontalLayout_call_volume)


        self.horizontalLayout_puts_calls.addLayout(self.verticalLayout_calls)


        self.verticalLayout_option_info.addLayout(self.horizontalLayout_puts_calls)


        self.horizontalLayout_top.addWidget(self.groupBox_option_info)

        self.groupBox_ai_insights = QGroupBox(self.centralwidget)
        self.groupBox_ai_insights.setObjectName(u"groupBox_ai_insights")
        self.groupBox_ai_insights.setMinimumSize(QSize(200, 120))
        self.groupBox_ai_insights.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #4a90e2;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(74, 144, 226, 0.08);\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #4a90e2;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}")
        self.verticalLayout_ai = QVBoxLayout(self.groupBox_ai_insights)
        self.verticalLayout_ai.setSpacing(12)
        self.verticalLayout_ai.setObjectName(u"verticalLayout_ai")
        self.verticalLayout_ai.setContentsMargins(-1, 20, -1, -1)
        self.horizontalLayout_ai_bias = QHBoxLayout()
        self.horizontalLayout_ai_bias.setObjectName(u"horizontalLayout_ai_bias")
        self.label_ai_bias_name = QLabel(self.groupBox_ai_insights)
        self.label_ai_bias_name.setObjectName(u"label_ai_bias_name")

        self.horizontalLayout_ai_bias.addWidget(self.label_ai_bias_name)

        self.label_ai_bias_value = QLabel(self.groupBox_ai_insights)
        self.label_ai_bias_value.setObjectName(u"label_ai_bias_value")

        self.horizontalLayout_ai_bias.addWidget(self.label_ai_bias_value)


        self.verticalLayout_ai.addLayout(self.horizontalLayout_ai_bias)

        self.horizontalLayout_ai_strategy = QHBoxLayout()
        self.horizontalLayout_ai_strategy.setObjectName(u"horizontalLayout_ai_strategy")
        self.label_ai_strategy_name = QLabel(self.groupBox_ai_insights)
        self.label_ai_strategy_name.setObjectName(u"label_ai_strategy_name")

        self.horizontalLayout_ai_strategy.addWidget(self.label_ai_strategy_name)

        self.textbrowser_ai_strategy_value = QTextBrowser(self.groupBox_ai_insights)
        self.textbrowser_ai_strategy_value.setObjectName(u"textbrowser_ai_strategy_value")

        self.horizontalLayout_ai_strategy.addWidget(self.textbrowser_ai_strategy_value)


        self.verticalLayout_ai.addLayout(self.horizontalLayout_ai_strategy)

        self.horizontalLayout_ai_keylevel = QHBoxLayout()
        self.horizontalLayout_ai_keylevel.setObjectName(u"horizontalLayout_ai_keylevel")
        self.label_ai_keylevel_name = QLabel(self.groupBox_ai_insights)
        self.label_ai_keylevel_name.setObjectName(u"label_ai_keylevel_name")

        self.horizontalLayout_ai_keylevel.addWidget(self.label_ai_keylevel_name)

        self.label_ai_keylevel_value = QLabel(self.groupBox_ai_insights)
        self.label_ai_keylevel_value.setObjectName(u"label_ai_keylevel_value")

        self.horizontalLayout_ai_keylevel.addWidget(self.label_ai_keylevel_value)


        self.verticalLayout_ai.addLayout(self.horizontalLayout_ai_keylevel)

        self.horizontalLayout_ai_alert = QHBoxLayout()
        self.horizontalLayout_ai_alert.setObjectName(u"horizontalLayout_ai_alert")
        self.label_ai_alert_name = QLabel(self.groupBox_ai_insights)
        self.label_ai_alert_name.setObjectName(u"label_ai_alert_name")

        self.horizontalLayout_ai_alert.addWidget(self.label_ai_alert_name)

        self.textbrowser_ai_alert_value = QTextBrowser(self.groupBox_ai_insights)
        self.textbrowser_ai_alert_value.setObjectName(u"textbrowser_ai_alert_value")

        self.horizontalLayout_ai_alert.addWidget(self.textbrowser_ai_alert_value)


        self.verticalLayout_ai.addLayout(self.horizontalLayout_ai_alert)


        self.horizontalLayout_top.addWidget(self.groupBox_ai_insights)


        self.verticalLayout_main.addLayout(self.horizontalLayout_top)

        self.groupBox_active_contract = QGroupBox(self.centralwidget)
        self.groupBox_active_contract.setObjectName(u"groupBox_active_contract")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.groupBox_active_contract.sizePolicy().hasHeightForWidth())
        self.groupBox_active_contract.setSizePolicy(sizePolicy2)
        self.groupBox_active_contract.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #f39c12;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(243, 156, 18, 0.08);\n"
"    padding-top: 10px;\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #f39c12;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}\n"
"")
        self.horizontalLayout_active = QHBoxLayout(self.groupBox_active_contract)
        self.horizontalLayout_active.setObjectName(u"horizontalLayout_active")
        self.horizontalLayout_symbol = QHBoxLayout()
        self.horizontalLayout_symbol.setObjectName(u"horizontalLayout_symbol")
        self.label_symbol_name = QLabel(self.groupBox_active_contract)
        self.label_symbol_name.setObjectName(u"label_symbol_name")

        self.horizontalLayout_symbol.addWidget(self.label_symbol_name)

        self.label_symbol_value = QLabel(self.groupBox_active_contract)
        self.label_symbol_value.setObjectName(u"label_symbol_value")

        self.horizontalLayout_symbol.addWidget(self.label_symbol_value)


        self.horizontalLayout_active.addLayout(self.horizontalLayout_symbol)

        self.horizontalLayout_quantity = QHBoxLayout()
        self.horizontalLayout_quantity.setObjectName(u"horizontalLayout_quantity")
        self.label_quantity_name = QLabel(self.groupBox_active_contract)
        self.label_quantity_name.setObjectName(u"label_quantity_name")

        self.horizontalLayout_quantity.addWidget(self.label_quantity_name)

        self.label_quantity_value = QLabel(self.groupBox_active_contract)
        self.label_quantity_value.setObjectName(u"label_quantity_value")

        self.horizontalLayout_quantity.addWidget(self.label_quantity_value)


        self.horizontalLayout_active.addLayout(self.horizontalLayout_quantity)

        self.horizontalLayout_pl_dollar = QHBoxLayout()
        self.horizontalLayout_pl_dollar.setObjectName(u"horizontalLayout_pl_dollar")
        self.label_pl_dollar_name = QLabel(self.groupBox_active_contract)
        self.label_pl_dollar_name.setObjectName(u"label_pl_dollar_name")

        self.horizontalLayout_pl_dollar.addWidget(self.label_pl_dollar_name)

        self.label_pl_dollar_value = QLabel(self.groupBox_active_contract)
        self.label_pl_dollar_value.setObjectName(u"label_pl_dollar_value")

        self.horizontalLayout_pl_dollar.addWidget(self.label_pl_dollar_value)


        self.horizontalLayout_active.addLayout(self.horizontalLayout_pl_dollar)

        self.horizontalLayout_pl_percent = QHBoxLayout()
        self.horizontalLayout_pl_percent.setObjectName(u"horizontalLayout_pl_percent")
        self.label_pl_percent_name = QLabel(self.groupBox_active_contract)
        self.label_pl_percent_name.setObjectName(u"label_pl_percent_name")

        self.horizontalLayout_pl_percent.addWidget(self.label_pl_percent_name)

        self.label_pl_percent_value = QLabel(self.groupBox_active_contract)
        self.label_pl_percent_value.setObjectName(u"label_pl_percent_value")

        self.horizontalLayout_pl_percent.addWidget(self.label_pl_percent_value)


        self.horizontalLayout_active.addLayout(self.horizontalLayout_pl_percent)


        self.verticalLayout_main.addWidget(self.groupBox_active_contract)

        self.horizontalLayout_bottom = QHBoxLayout()
        self.horizontalLayout_bottom.setSpacing(16)
        self.horizontalLayout_bottom.setObjectName(u"horizontalLayout_bottom")
        self.groupBox_account_metrics = QGroupBox(self.centralwidget)
        self.groupBox_account_metrics.setObjectName(u"groupBox_account_metrics")
        self.groupBox_account_metrics.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #27ae60;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(39, 174, 96, 0.08);\n"
"    padding-top: 10px;\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #27ae60;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}\n"
"")
        self.verticalLayout_account = QVBoxLayout(self.groupBox_account_metrics)
        self.verticalLayout_account.setObjectName(u"verticalLayout_account")
        self.horizontalLayout_account_value = QHBoxLayout()
        self.horizontalLayout_account_value.setObjectName(u"horizontalLayout_account_value")
        self.label_account_value_name = QLabel(self.groupBox_account_metrics)
        self.label_account_value_name.setObjectName(u"label_account_value_name")

        self.horizontalLayout_account_value.addWidget(self.label_account_value_name)

        self.label_account_value_value = QLabel(self.groupBox_account_metrics)
        self.label_account_value_value.setObjectName(u"label_account_value_value")

        self.horizontalLayout_account_value.addWidget(self.label_account_value_value)


        self.verticalLayout_account.addLayout(self.horizontalLayout_account_value)

        self.horizontalLayout_starting_value = QHBoxLayout()
        self.horizontalLayout_starting_value.setObjectName(u"horizontalLayout_starting_value")
        self.label_starting_value_name = QLabel(self.groupBox_account_metrics)
        self.label_starting_value_name.setObjectName(u"label_starting_value_name")

        self.horizontalLayout_starting_value.addWidget(self.label_starting_value_name)

        self.label_starting_value_value = QLabel(self.groupBox_account_metrics)
        self.label_starting_value_value.setObjectName(u"label_starting_value_value")

        self.horizontalLayout_starting_value.addWidget(self.label_starting_value_value)


        self.verticalLayout_account.addLayout(self.horizontalLayout_starting_value)

        self.horizontalLayout_high_water = QHBoxLayout()
        self.horizontalLayout_high_water.setObjectName(u"horizontalLayout_high_water")
        self.label_high_water_name = QLabel(self.groupBox_account_metrics)
        self.label_high_water_name.setObjectName(u"label_high_water_name")

        self.horizontalLayout_high_water.addWidget(self.label_high_water_name)

        self.label_high_water_value = QLabel(self.groupBox_account_metrics)
        self.label_high_water_value.setObjectName(u"label_high_water_value")

        self.horizontalLayout_high_water.addWidget(self.label_high_water_value)


        self.verticalLayout_account.addLayout(self.horizontalLayout_high_water)

        self.horizontalLayout_daily_pl = QHBoxLayout()
        self.horizontalLayout_daily_pl.setObjectName(u"horizontalLayout_daily_pl")
        self.label_daily_pl_name = QLabel(self.groupBox_account_metrics)
        self.label_daily_pl_name.setObjectName(u"label_daily_pl_name")

        self.horizontalLayout_daily_pl.addWidget(self.label_daily_pl_name)

        self.label_daily_pl_value = QLabel(self.groupBox_account_metrics)
        self.label_daily_pl_value.setObjectName(u"label_daily_pl_value")

        self.horizontalLayout_daily_pl.addWidget(self.label_daily_pl_value)


        self.verticalLayout_account.addLayout(self.horizontalLayout_daily_pl)

        self.horizontalLayout_daily_pl_percent = QHBoxLayout()
        self.horizontalLayout_daily_pl_percent.setObjectName(u"horizontalLayout_daily_pl_percent")
        self.label_daily_pl_percent_name = QLabel(self.groupBox_account_metrics)
        self.label_daily_pl_percent_name.setObjectName(u"label_daily_pl_percent_name")

        self.horizontalLayout_daily_pl_percent.addWidget(self.label_daily_pl_percent_name)

        self.label_daily_pl_percent_value = QLabel(self.groupBox_account_metrics)
        self.label_daily_pl_percent_value.setObjectName(u"label_daily_pl_percent_value")

        self.horizontalLayout_daily_pl_percent.addWidget(self.label_daily_pl_percent_value)


        self.verticalLayout_account.addLayout(self.horizontalLayout_daily_pl_percent)


        self.horizontalLayout_bottom.addWidget(self.groupBox_account_metrics)

        self.groupBox_trade_statistics = QGroupBox(self.centralwidget)
        self.groupBox_trade_statistics.setObjectName(u"groupBox_trade_statistics")
        self.groupBox_trade_statistics.setStyleSheet(u"QGroupBox {\n"
"    border: 2px solid #e67e22;\n"
"    border-radius: 12px;\n"
"    margin-top: 1ex;\n"
"    font-weight: bold;\n"
"    color: #2c3e50;\n"
"    background-color: #fafdff;\n"
"    box-shadow: 0 2px 8px rgba(230, 126, 34, 0.08);\n"
"    padding-top: 10px;\n"
"}\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    left: 10px;\n"
"    padding: 0 8px 0 8px;\n"
"    background-color: #e67e22;\n"
"    color: white;\n"
"    border-radius: 6px;\n"
"}\n"
"")
        self.verticalLayout_stats = QVBoxLayout(self.groupBox_trade_statistics)
        self.verticalLayout_stats.setObjectName(u"verticalLayout_stats")
        self.horizontalLayout_win_rate = QHBoxLayout()
        self.horizontalLayout_win_rate.setObjectName(u"horizontalLayout_win_rate")
        self.label_win_rate_name = QLabel(self.groupBox_trade_statistics)
        self.label_win_rate_name.setObjectName(u"label_win_rate_name")

        self.horizontalLayout_win_rate.addWidget(self.label_win_rate_name)

        self.label_win_rate_value = QLabel(self.groupBox_trade_statistics)
        self.label_win_rate_value.setObjectName(u"label_win_rate_value")

        self.horizontalLayout_win_rate.addWidget(self.label_win_rate_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_win_rate)

        self.horizontalLayout_total_wins_count = QHBoxLayout()
        self.horizontalLayout_total_wins_count.setObjectName(u"horizontalLayout_total_wins_count")
        self.label_total_wins_count_name = QLabel(self.groupBox_trade_statistics)
        self.label_total_wins_count_name.setObjectName(u"label_total_wins_count_name")

        self.horizontalLayout_total_wins_count.addWidget(self.label_total_wins_count_name)

        self.label_total_wins_count_value = QLabel(self.groupBox_trade_statistics)
        self.label_total_wins_count_value.setObjectName(u"label_total_wins_count_value")

        self.horizontalLayout_total_wins_count.addWidget(self.label_total_wins_count_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_total_wins_count)

        self.horizontalLayout_total_wins_sum = QHBoxLayout()
        self.horizontalLayout_total_wins_sum.setObjectName(u"horizontalLayout_total_wins_sum")
        self.label_total_wins_sum_name = QLabel(self.groupBox_trade_statistics)
        self.label_total_wins_sum_name.setObjectName(u"label_total_wins_sum_name")

        self.horizontalLayout_total_wins_sum.addWidget(self.label_total_wins_sum_name)

        self.label_total_wins_sum_value = QLabel(self.groupBox_trade_statistics)
        self.label_total_wins_sum_value.setObjectName(u"label_total_wins_sum_value")

        self.horizontalLayout_total_wins_sum.addWidget(self.label_total_wins_sum_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_total_wins_sum)

        self.horizontalLayout_total_losses_count = QHBoxLayout()
        self.horizontalLayout_total_losses_count.setObjectName(u"horizontalLayout_total_losses_count")
        self.label_total_losses_count_name = QLabel(self.groupBox_trade_statistics)
        self.label_total_losses_count_name.setObjectName(u"label_total_losses_count_name")

        self.horizontalLayout_total_losses_count.addWidget(self.label_total_losses_count_name)

        self.label_total_losses_count_value = QLabel(self.groupBox_trade_statistics)
        self.label_total_losses_count_value.setObjectName(u"label_total_losses_count_value")

        self.horizontalLayout_total_losses_count.addWidget(self.label_total_losses_count_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_total_losses_count)

        self.horizontalLayout_total_losses_sum = QHBoxLayout()
        self.horizontalLayout_total_losses_sum.setObjectName(u"horizontalLayout_total_losses_sum")
        self.label_total_losses_sum_name = QLabel(self.groupBox_trade_statistics)
        self.label_total_losses_sum_name.setObjectName(u"label_total_losses_sum_name")

        self.horizontalLayout_total_losses_sum.addWidget(self.label_total_losses_sum_name)

        self.label_total_losses_sum_value = QLabel(self.groupBox_trade_statistics)
        self.label_total_losses_sum_value.setObjectName(u"label_total_losses_sum_value")

        self.horizontalLayout_total_losses_sum.addWidget(self.label_total_losses_sum_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_total_losses_sum)

        self.horizontalLayout_total_trades = QHBoxLayout()
        self.horizontalLayout_total_trades.setObjectName(u"horizontalLayout_total_trades")
        self.label_total_trades_name = QLabel(self.groupBox_trade_statistics)
        self.label_total_trades_name.setObjectName(u"label_total_trades_name")

        self.horizontalLayout_total_trades.addWidget(self.label_total_trades_name)

        self.label_total_trades_value = QLabel(self.groupBox_trade_statistics)
        self.label_total_trades_value.setObjectName(u"label_total_trades_value")

        self.horizontalLayout_total_trades.addWidget(self.label_total_trades_value)


        self.verticalLayout_stats.addLayout(self.horizontalLayout_total_trades)


        self.horizontalLayout_bottom.addWidget(self.groupBox_trade_statistics)


        self.verticalLayout_main.addLayout(self.horizontalLayout_bottom)

        self.horizontalLayout_status_area = QHBoxLayout()
        self.horizontalLayout_status_area.setObjectName(u"horizontalLayout_status_area")
        self.label_status_icons = QLabel(self.centralwidget)
        self.label_status_icons.setObjectName(u"label_status_icons")

        self.horizontalLayout_status_area.addWidget(self.label_status_icons)

        self.label_connection_status = QLabel(self.centralwidget)
        self.label_connection_status.setObjectName(u"label_connection_status")
        font2 = QFont()
        font2.setPointSize(9)
        self.label_connection_status.setFont(font2)

        self.horizontalLayout_status_area.addWidget(self.label_connection_status)

        self.horizontalSpacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_status_area.addItem(self.horizontalSpacer)

        self.button_refresh_ai = QPushButton(self.centralwidget)
        self.button_refresh_ai.setObjectName(u"button_refresh_ai")
        self.button_refresh_ai.setMinimumSize(QSize(100, 25))
        font3 = QFont()
        font3.setPointSize(8)
        font3.setBold(True)
        self.button_refresh_ai.setFont(font3)
        self.button_refresh_ai.setStyleSheet(u"QPushButton {\n"
"    background-color: #27ae60;\n"
"    color: white;\n"
"    border: none;\n"
"    border-radius: 4px;\n"
"    padding: 7px 16px;\n"
"    font-weight: bold;\n"
"    font-size: 8pt;\n"
"    transition: background 0.2s;\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #229954;\n"
"}\n"
"QPushButton:pressed {\n"
"    background-color: #1e8449;\n"
"}")

        self.horizontalLayout_status_area.addWidget(self.button_refresh_ai)

        self.button_ai_prompt = QPushButton(self.centralwidget)
        self.button_ai_prompt.setObjectName(u"button_ai_prompt")
        self.button_ai_prompt.setMinimumSize(QSize(0, 0))
        self.button_ai_prompt.setFont(font3)
        self.button_ai_prompt.setStyleSheet(u"QPushButton {\n"
"    background-color: #3498db;\n"
"    color: white;\n"
"    border: none;\n"
"    border-radius: 4px;\n"
"    padding: 7px 16px;\n"
"    font-weight: bold;\n"
"    font-size: 8pt;\n"
"    transition: background 0.2s;\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: #2980b9;\n"
"}\n"
"QPushButton:pressed {\n"
"    background-color: #21618c;\n"
"}")

        self.horizontalLayout_status_area.addWidget(self.button_ai_prompt)

        self.label_time = QLabel(self.centralwidget)
        self.label_time.setObjectName(u"label_time")
        font4 = QFont()
        font4.setPointSize(8)
        self.label_time.setFont(font4)

        self.horizontalLayout_status_area.addWidget(self.label_time)


        self.verticalLayout_main.addLayout(self.horizontalLayout_status_area)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 784, 21))
        self.menuMain = QMenu(self.menubar)
        self.menuMain.setObjectName(u"menuMain")
        self.menuSetting = QMenu(self.menubar)
        self.menuSetting.setObjectName(u"menuSetting")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setLayoutDirection(Qt.LeftToRight)
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuMain.menuAction())
        self.menubar.addAction(self.menuSetting.menuAction())

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"IB Trading GUI", None))
#if QT_CONFIG(tooltip)
        self.groupBox_trading_info.setToolTip(QCoreApplication.translate("MainWindow", u"Displays current trading information including SPY and currency rates.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_trading_info.setTitle(QCoreApplication.translate("MainWindow", u"Trading Information", None))
        self.label_spy_name.setText(QCoreApplication.translate("MainWindow", u"SPY:", None))
        self.label_spy_value.setText(QCoreApplication.translate("MainWindow", u"$498.33", None))
        self.label_usd_cad_name.setText(QCoreApplication.translate("MainWindow", u"USD/CAD:", None))
        self.label_usd_cad_value.setText(QCoreApplication.translate("MainWindow", u"1.3750", None))
        self.label_cad_usd_name.setText(QCoreApplication.translate("MainWindow", u"CAD/USD:", None))
        self.label_cad_usd_value.setText(QCoreApplication.translate("MainWindow", u"0.7272", None))
#if QT_CONFIG(tooltip)
        self.groupBox_option_info.setToolTip(QCoreApplication.translate("MainWindow", u"Shows detailed information for the selected option contract.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_option_info.setTitle(QCoreApplication.translate("MainWindow", u"Option Information", None))
        self.label_strike_name.setText(QCoreApplication.translate("MainWindow", u"Strike:", None))
        self.label_strike_value.setText(QCoreApplication.translate("MainWindow", u"$502", None))
        self.label_expiration_name.setText(QCoreApplication.translate("MainWindow", u"Expiration:", None))
        self.label_expiration_value.setText(QCoreApplication.translate("MainWindow", u"2025-08-07", None))
        self.label_puts_title.setText(QCoreApplication.translate("MainWindow", u"Puts", None))
        self.label_put_price_name.setText(QCoreApplication.translate("MainWindow", u"Price:", None))
        self.label_put_price_value.setText(QCoreApplication.translate("MainWindow", u"$2.80", None))
        self.label_put_bid_name.setText(QCoreApplication.translate("MainWindow", u"Bid:", None))
        self.label_put_bid_value.setText(QCoreApplication.translate("MainWindow", u"$2.79", None))
        self.label_put_ask_name.setText(QCoreApplication.translate("MainWindow", u"Ask:", None))
        self.label_put_ask_value.setText(QCoreApplication.translate("MainWindow", u"$2.81", None))
        self.label_put_delta_name.setText(QCoreApplication.translate("MainWindow", u"Delta:", None))
        self.label_put_delta_value.setText(QCoreApplication.translate("MainWindow", u"-0.45", None))
        self.label_put_gamma_name.setText(QCoreApplication.translate("MainWindow", u"Gamma:", None))
        self.label_put_gamma_value.setText(QCoreApplication.translate("MainWindow", u"0.04", None))
        self.label_put_theta_name.setText(QCoreApplication.translate("MainWindow", u"Theta:", None))
        self.label_put_theta_value.setText(QCoreApplication.translate("MainWindow", u"-0.05", None))
        self.label_put_vega_name.setText(QCoreApplication.translate("MainWindow", u"Vega:", None))
        self.label_put_vega_value.setText(QCoreApplication.translate("MainWindow", u"0.13", None))
        self.label_put_openint_name.setText(QCoreApplication.translate("MainWindow", u"Open Int:", None))
        self.label_put_openint_value.setText(QCoreApplication.translate("MainWindow", u"18,765", None))
        self.label_put_volume_name.setText(QCoreApplication.translate("MainWindow", u"Volume:", None))
        self.label_put_volume_value.setText(QCoreApplication.translate("MainWindow", u"4,321", None))
        self.label_calls_title.setText(QCoreApplication.translate("MainWindow", u"Calls", None))
        self.label_call_price_name.setText(QCoreApplication.translate("MainWindow", u"Price:", None))
        self.label_call_price_value.setText(QCoreApplication.translate("MainWindow", u"$3.10", None))
        self.label_call_bid_name.setText(QCoreApplication.translate("MainWindow", u"Bid:", None))
        self.label_call_bid_value.setText(QCoreApplication.translate("MainWindow", u"$3.09", None))
        self.label_call_ask_name.setText(QCoreApplication.translate("MainWindow", u"Ask:", None))
        self.label_call_ask_value.setText(QCoreApplication.translate("MainWindow", u"$3.11", None))
        self.label_call_delta_name.setText(QCoreApplication.translate("MainWindow", u"Delta:", None))
        self.label_call_delta_value.setText(QCoreApplication.translate("MainWindow", u"0.55", None))
        self.label_call_gamma_name.setText(QCoreApplication.translate("MainWindow", u"Gamma:", None))
        self.label_call_gamma_value.setText(QCoreApplication.translate("MainWindow", u"0.04", None))
        self.label_call_theta_name.setText(QCoreApplication.translate("MainWindow", u"Theta:", None))
        self.label_call_theta_value.setText(QCoreApplication.translate("MainWindow", u"-0.06", None))
        self.label_call_vega_name.setText(QCoreApplication.translate("MainWindow", u"Vega:", None))
        self.label_call_vega_value.setText(QCoreApplication.translate("MainWindow", u"0.13", None))
        self.label_call_openint_name.setText(QCoreApplication.translate("MainWindow", u"Open Int:", None))
        self.label_call_openint_value.setText(QCoreApplication.translate("MainWindow", u"12,345", None))
        self.label_call_volume_name.setText(QCoreApplication.translate("MainWindow", u"Volume:", None))
        self.label_call_volume_value.setText(QCoreApplication.translate("MainWindow", u"6,789", None))
#if QT_CONFIG(tooltip)
        self.groupBox_ai_insights.setToolTip(QCoreApplication.translate("MainWindow", u"AI-generated insights, strategies, and alerts for your trading session.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_ai_insights.setTitle(QCoreApplication.translate("MainWindow", u"\ud83e\udd16 AI Insights", None))
        self.label_ai_bias_name.setText(QCoreApplication.translate("MainWindow", u"Bias:", None))
        self.label_ai_bias_value.setText(QCoreApplication.translate("MainWindow", u"Bullish", None))
        self.label_ai_strategy_name.setText(QCoreApplication.translate("MainWindow", u"Strategy:", None))
        self.textbrowser_ai_strategy_value.setProperty(u"text", QCoreApplication.translate("MainWindow", u"Consider a bull call spread: Buy SPY 500C, sell SPY 510C. Target profit $400, max risk $200. Monitor for breakout above $502. Adjust stop to $497 if volatility increases.", None))
        self.label_ai_keylevel_name.setText(QCoreApplication.translate("MainWindow", u"Key Level:", None))
        self.label_ai_keylevel_value.setText(QCoreApplication.translate("MainWindow", u"$502.00", None))
        self.label_ai_alert_name.setText(QCoreApplication.translate("MainWindow", u"Alert:", None))
        self.textbrowser_ai_alert_value.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">\n"
"<p align=\"justify\" style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>", None))
        self.textbrowser_ai_alert_value.setProperty(u"text", QCoreApplication.translate("MainWindow", u"\u26a0\ufe0f Unusual options volume detected in SPY 500C. Watch for sharp price swings at market open. Consider reducing position size if implied volatility rises above 25%.", None))
#if QT_CONFIG(tooltip)
        self.groupBox_active_contract.setToolTip(QCoreApplication.translate("MainWindow", u"Information about the currently active contract in your portfolio.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_active_contract.setTitle(QCoreApplication.translate("MainWindow", u"Active Contract", None))
        self.label_symbol_name.setText(QCoreApplication.translate("MainWindow", u"Symbol:", None))
        self.label_symbol_value.setText(QCoreApplication.translate("MainWindow", u"SPY 500C", None))
        self.label_quantity_name.setText(QCoreApplication.translate("MainWindow", u"Quantity:", None))
        self.label_quantity_value.setText(QCoreApplication.translate("MainWindow", u"10", None))
        self.label_pl_dollar_name.setText(QCoreApplication.translate("MainWindow", u"P/L ($):", None))
        self.label_pl_dollar_value.setText(QCoreApplication.translate("MainWindow", u"$0.00", None))
        self.label_pl_percent_name.setText(QCoreApplication.translate("MainWindow", u"P/L (%):", None))
        self.label_pl_percent_value.setText(QCoreApplication.translate("MainWindow", u"0.00%", None))
#if QT_CONFIG(tooltip)
        self.groupBox_account_metrics.setToolTip(QCoreApplication.translate("MainWindow", u"Key account metrics including value, high water mark, and daily P&L.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_account_metrics.setTitle(QCoreApplication.translate("MainWindow", u"Account Metrics", None))
        self.label_account_value_name.setText(QCoreApplication.translate("MainWindow", u"Account Value:", None))
        self.label_account_value_value.setText(QCoreApplication.translate("MainWindow", u"$105,123.45", None))
        self.label_starting_value_name.setText(QCoreApplication.translate("MainWindow", u"Starting Value:", None))
        self.label_starting_value_value.setText(QCoreApplication.translate("MainWindow", u"$100,000.00", None))
        self.label_high_water_name.setText(QCoreApplication.translate("MainWindow", u"High Water Mark:", None))
        self.label_high_water_value.setText(QCoreApplication.translate("MainWindow", u"$106,543.21", None))
        self.label_daily_pl_name.setText(QCoreApplication.translate("MainWindow", u"Daily P&L:", None))
        self.label_daily_pl_value.setText(QCoreApplication.translate("MainWindow", u"$5,123.45", None))
        self.label_daily_pl_percent_name.setText(QCoreApplication.translate("MainWindow", u"Daily P&L %:", None))
        self.label_daily_pl_percent_value.setText(QCoreApplication.translate("MainWindow", u"5.12%", None))
#if QT_CONFIG(tooltip)
        self.groupBox_trade_statistics.setToolTip(QCoreApplication.translate("MainWindow", u"Summary of your trading performance and statistics.", None))
#endif // QT_CONFIG(tooltip)
        self.groupBox_trade_statistics.setTitle(QCoreApplication.translate("MainWindow", u"Trade Statistics", None))
        self.label_win_rate_name.setText(QCoreApplication.translate("MainWindow", u"Win Rate:", None))
        self.label_win_rate_value.setText(QCoreApplication.translate("MainWindow", u"75.00%", None))
        self.label_total_wins_count_name.setText(QCoreApplication.translate("MainWindow", u"Total Wins (count):", None))
        self.label_total_wins_count_value.setText(QCoreApplication.translate("MainWindow", u"15", None))
        self.label_total_wins_sum_name.setText(QCoreApplication.translate("MainWindow", u"Total Wins (sum):", None))
        self.label_total_wins_sum_value.setText(QCoreApplication.translate("MainWindow", u"$7,500.00", None))
        self.label_total_losses_count_name.setText(QCoreApplication.translate("MainWindow", u"Total Losses (count):", None))
        self.label_total_losses_count_value.setText(QCoreApplication.translate("MainWindow", u"5", None))
        self.label_total_losses_sum_name.setText(QCoreApplication.translate("MainWindow", u"Total Losses (sum):", None))
        self.label_total_losses_sum_value.setText(QCoreApplication.translate("MainWindow", u"$2,500.00", None))
        self.label_total_trades_name.setText(QCoreApplication.translate("MainWindow", u"Total Trades:", None))
        self.label_total_trades_value.setText(QCoreApplication.translate("MainWindow", u"20", None))
        self.label_status_icons.setText(QCoreApplication.translate("MainWindow", u"\u2699\ufe0f \u25a2 \u25a2", None))
        self.label_connection_status.setText(QCoreApplication.translate("MainWindow", u"Connection: Connected", None))
#if QT_CONFIG(tooltip)
        self.button_refresh_ai.setToolTip(QCoreApplication.translate("MainWindow", u"Refresh the AI insights and recommendations.", None))
#endif // QT_CONFIG(tooltip)
        self.button_refresh_ai.setText(QCoreApplication.translate("MainWindow", u"\ud83d\udd04 Refresh AI", None))
#if QT_CONFIG(tooltip)
        self.button_ai_prompt.setToolTip(QCoreApplication.translate("MainWindow", u"Open the AI prompt dialog to ask for trading insights or strategies.", None))
#endif // QT_CONFIG(tooltip)
        self.button_ai_prompt.setText(QCoreApplication.translate("MainWindow", u"\ud83d\udcac AI Prompt", None))
        self.label_time.setText(QCoreApplication.translate("MainWindow", u"09:42:49 PM", None))
        self.menuMain.setTitle(QCoreApplication.translate("MainWindow", u"Main", None))
        self.menuSetting.setTitle(QCoreApplication.translate("MainWindow", u"Setting", None))
    # retranslateUi

