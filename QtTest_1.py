import platform
import sys
import time

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QTextEdit, QPushButton, QMenuBar, QMenu, QAction, QComboBox
#from PyQt5.QtCore import pyqtSignal, QObject
import numpy as np
import cv2
import serial.tools.list_ports
import serial
import torch
import requests
import pathlib
import threading



plt = platform.system()
if plt == 'Windows': pathlib.PosixPath = pathlib.WindowsPath  #從colab訓練好的best.pt需要這行程式才能執行

model = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)


# python detect.py --weight runs/train/exp/weights/best.pt --source faces/images/train/1.jpg --iou-thres 0.3 --conf-thres 0.5

class COMSelectionWindow(QWidget):
    def __init__(self, main_window):
        super(COMSelectionWindow, self).__init__()

        self.main_window = main_window

        layout = QtWidgets.QVBoxLayout(self)

        self.com_combo = QComboBox(self)
        self.populate_com_ports()
        layout.addWidget(self.com_combo)

        ok_button = QPushButton('確定', self)
        ok_button.clicked.connect(self.set_arduino_port)
        no_button = QPushButton('斷線', self)
        no_button.clicked.connect(self.disconnect)
        layout.addWidget(ok_button)
        layout.addWidget(no_button)
        self.setWindowTitle('COM Port Selection')
        self.setGeometry(200, 200, 300, 100)

    def populate_com_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_combo.addItems(ports)

    def set_arduino_port(self):
        selected_port = self.com_combo.currentText()
        self.main_window.arduino_port = selected_port

        # 在這裡初始化串列通訊
        #  self.main_window.serial_connection = serial.Serial(self.main_window.arduino_port, 115200)

        self.close()

    def disconnect(self):
        self.main_window.arduino_port = None


class MaskRecognitionApp(QMainWindow):
    def __init__(self):
        super(MaskRecognitionApp, self).__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.arduino_port = None
        self.serial_connection = None
        self.com_selection_window = COMSelectionWindow(self)

        self.ui.pushButton.clicked.connect(self.start_recognition)
        self.ui.action_COM_Select.triggered.connect(self.show_com_selection_window)
        self.tempbox = None

        self.timer = QTimer(self)
        self.timer2 = QTimer(self)
        self.timer.timeout.connect(self.update_frames)
        #self.timer2.timeout.connect(self.TEST_AMG8833)
        AMG8833 = threading.Thread(target=self.TEST_AMG8833) #執行續
        AMG8833.start()
        self.timer.start(30)
        self.timer2.start(40)
        self.video_capture = cv2.VideoCapture(0)
        # self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        # self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 320)

    def start_recognition(self):
        ret1, framebox = self.video_capture.read()
       # framebox = cv2.resize(framebox, (320, 320))
        if ret1:
            try:
                # 使用Yolov5進行辨識
                results = model(framebox)

                # 列印信心值大於0.9的項目名字
                labels = results.pandas().xyxy[0]
                filtered_labels = labels[labels['confidence'] > 0.7]['name'].tolist()
                # print(filtered_labels or False)
                textbox = filtered_labels or False
                print(textbox)
                print(self.tempbox)
                if str(textbox) == "False":
                    self.ui.textEdit.setPlainText("查無此人" + "\n")
                elif str(textbox) == "['nomask']":
                    self.ui.textEdit.setPlainText(" 沒戴口罩 溫度" + str(self.tempbox) + "\n")
                    self.POSTapi("邱鈺晟", "沒戴口罩", self.tempbox)
                elif str(textbox) == "['mask']":
                    self.ui.textEdit.setPlainText(" 有戴口罩 溫度" + str(self.tempbox) + "\n")
                    self.POSTapi("邱鈺晟", "有戴口罩", self.tempbox)
            except Exception as e:
                print(f"Error: {e}")
                pass

    def POSTapi(self, name, status, temp):
        data = {
            "name": name,
            "status": status,
            "temp": temp
        }

        # 發送 POST 請求到 PHP API
        response = requests.post(' http://127.0.0.1/class/api.php', data=data)

        # 檢查請求是否成功
        if response.status_code == 200:
            print('請求成功')
        else:
            print('請求失敗')

    def TEST_AMG8833(self):
        while 1:
            time.sleep(1)
            if self.arduino_port is not None:
                while 1:
                    try:
                        arduino = serial.Serial(self.arduino_port, 115200, timeout=0.5)
                        arduino.flush()
                        # print(f"Connected to Arduino on {self.arduino_port}")

                        # 在這裡實現與 Arduino 的通訊邏輯
                        # 例如，向 Arduino 寫入資料：
                        # arduino.write(b'K\n')

                        # 讀取來自 Arduino 的資料：
                        # data = arduino.readline().decode('utf-8').strip()
                        data = arduino.readline().decode('utf-8', 'ignore').strip()
                        try:
                            # print(data)
                            data_list = list(map(float, data[0:-1].split(','))) #MLX90640的像素數值結尾是, 導致偵錯失敗寫了[0:-1]讀取到最後第一行
                            # print(data_list)

                            self.tempbox = max(data_list) #取像素陣列最大值
                            # 將資料轉換成24x32的矩陣
                            matrix_data = np.array(data_list).reshape((24,32))


                            # self.tempbox = (matrix_data[11][15] + matrix_data[11][16] + matrix_data[12][15] + matrix_data[12][16]) / 4
                            # 將矩陣的大小調整為384x384
                            resized_data = cv2.resize(matrix_data, (384,384))

                            heatmap = cv2.applyColorMap(np.uint8(255 * (resized_data - np.min(resized_data)) / (
                                    np.max(resized_data) - np.min(resized_data))),
                                                        cv2.COLORMAP_JET)
                            heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
                            h, w, ch = heatmap.shape
                            bytes_per_line2 = ch * w
                            qt_image2 = QImage(heatmap.data, w, h, bytes_per_line2, QImage.Format_RGB888)
                            pixmap2 = QPixmap.fromImage(qt_image2)
                            self.ui.label_2.setPixmap(pixmap2)


                        except Exception as e:
                            print(f"Error: {e}")
                            pass

                    except serial.SerialException as e:
                        print(f"Error: {e}")
                        pass

                    finally:
                        # 關閉串列埠連接
                        if 'arduino' in locals():
                            arduino.close()
                            # print("Disconnected from Arduino")
            else:
                pass


    def show_com_selection_window(self):
        self.com_selection_window.show()

    def update_frames(self): #設定鏡頭
        ret, frame = self.video_capture.read(1)
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.flip(frame, 1)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self.ui.label.setPixmap(pixmap)

    def closeEvent(self, event):
        # Release the video capture
        self.timer.stop()
        self.video_capture.release()
        event.accept()


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(917, 697)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 500, 400))
        self.label.setText("")
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setGeometry(QtCore.QRect(510, 7, 384, 384))
        self.label_2.setText("")
        self.label_2.setObjectName("label_2")
        self.textEdit = QtWidgets.QTextEdit(self.centralwidget)
        self.textEdit.setGeometry(QtCore.QRect(0, 410, 901, 121))
        self.textEdit.setObjectName("textEdit")
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setGeometry(QtCore.QRect(290, 540, 311, 111))
        font = QtGui.QFont()
        font.setFamily("Agency FB")
        font.setPointSize(26)
        self.textEdit.setFont(font)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 917, 21))
        self.menubar.setObjectName("menubar")
        self.menu_option = QtWidgets.QMenu(self.menubar)
        self.menu_option.setObjectName("menu_option")
        self.menu_option.setTitle("Option")
        self.action_COM_Select = QtWidgets.QAction(MainWindow)
        self.action_COM_Select.setObjectName("action_COM_Select")
        self.action_COM_Select.setText("COM_Select")
        self.menu_option.addAction(self.action_COM_Select)
        self.menubar.addAction(self.menu_option.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "口罩辨識點名系統"))
        self.pushButton.setText(_translate("MainWindow", "開始點名"))
        self.menu_option.setTitle(_translate("MainWindow", "Option"))
        self.action_COM_Select.setText(_translate("MainWindow", "COM_Select"))



if __name__ == "__main__":
    try:
        app = QtWidgets.QApplication(sys.argv)
        MainWindow = MaskRecognitionApp()
        MainWindow.setGeometry(100, 100, 917, 697)
        MainWindow.setWindowTitle('口罩辨識點名系統')
        MainWindow.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error: {e}")
        pass
