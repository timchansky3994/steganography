import sys
from random import randrange
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QProgressDialog
from steganography_ui import Ui_MainWindow


class EncodedDataNotFound(Exception):
    pass


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.input_file = ''
        self.data_file = ''
        self.output_file_format = ''
        self.output_data = bytes()
        self.buttonStart.clicked.connect(self.start)
        self.buttonOpenImg.clicked.connect(self.open_img)
        self.buttonOpenData.clicked.connect(self.open_data)
        self.buttonSave.clicked.connect(self.save)
        self.comboBoxMode.currentIndexChanged.connect(self.mode_changed)

    def mode_changed(self):
        if self.comboBoxMode.currentIndex() == 0:
            self.buttonOpenData.show()
            self.labelOpenedFileName.show()
            self.statusbar.show()
        else:
            self.buttonOpenData.hide()
            self.labelOpenedFileName.hide()
            self.statusbar.hide()
        self.output_data = bytes()
        pixmap = QPixmap()  # сбрасываем превью выходной картинки
        pixmap.loadFromData(b'')
        self.outputPreview.setPixmap(pixmap)

    def open_img(self):
        file_name = QFileDialog.getOpenFileName(self, 'Выбрать картинку', '', 'Картинка (*.bmp)')[0]
        if file_name != '':
            self.input_file = file_name
            self.labelOpenedImgName.setText(self.input_file.split('/')[-1])
            pixmap = QPixmap(self.input_file)
            if pixmap.width() > 341 or pixmap.height() > 329:
                pixmap = pixmap.scaled(341, 329, Qt.KeepAspectRatio)
            self.inputPreview.setPixmap(pixmap)
            self.statusbar.showMessage(f'В картинку такого размера можно зашифровать файл размером \
максимум {int(pixmap.width() * pixmap.height() * 3 / 4)} байт')

    def open_data(self):
        file_name = QFileDialog.getOpenFileName(self, 'Выбрать файл', '', 'Все файлы (*)')[0]
        if file_name != '':
            self.data_file = file_name
            self.labelOpenedFileName.setText(self.data_file.split('/')[-1])

    def save(self):
        if len(self.output_data) > 0:
            if self.comboBoxMode.currentIndex() == 0:  # режим зашифровки
                output_file = QFileDialog.getSaveFileName(self, 'Сохранить картинку', '',
                                                          'Картинка (*.bmp)')[0]
            else:  # режим дешифровки
                output_file = QFileDialog.getSaveFileName(self, 'Сохранить файл', '', f'Полученный ф\
айл (*.{self.output_file_format});;Все файлы (*)')[0]
            if output_file != '':  # если не нажата "отмена"
                with open(output_file, 'wb') as f:
                        f.write(self.output_data)
        else:
            self.noDecodedDataErrMsgBox.exec()

    def start(self):
        if self.comboBoxMode.currentIndex() == 0:  # режим зашифровки
            self.lsb_encode()
        else:  # режим дешифровки
            self.lsb_decode()

    def lsb_encode(self):  # закодировать методом least significant bit
        try:
            img_f = open(self.input_file, 'rb')
            img_data = img_f.read()
            img_f.close()
            header_len = convert_bytes_to_int(img_data[14:18]) + 14
            width = convert_bytes_to_int(img_data[18:22])
            height = convert_bytes_to_int(img_data[22:26])
            header = img_data[:header_len]
            img_data = img_data[header_len:]

            data_f = open(self.data_file, 'rb')
            data = data_f.read()
            data_f.close()

            res_data = bytes()

            progress = QProgressDialog('Зашифровка данных...', 'Отмена', 0, len(img_data) - 1, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle('Зашифровка')

            for i, data_byte in enumerate(data):
                for j in range(4):
                    if progress.wasCanceled():
                        break
                    img_byte = img_data[i * 4 + j]
                    img_byte >>= 2
                    img_byte <<= 2
                    img_byte += (data_byte & (0b11 << (2 * (3 - j)))) >> (2 * (3 - j))
                    res_data += bytes([img_byte])
                    progress.setValue(i * 4 + j)
            key = bytes([len(res_data) % 256 ** (i + 1) >> 8 * i for i in range(4)])

            progress.setLabelText('Заполнение оставшегося места шумом...')
            for i in range(len(res_data), len(img_data)):  # если остались неизменённые пиксели -
                if progress.wasCanceled():  # -              применяем шум
                    break
                img_byte = img_data[i]
                img_byte >>= 2
                img_byte <<= 2
                img_byte += randrange(0, 4)
                res_data += bytes([img_byte])
                progress.setValue(i)
            if not progress.wasCanceled():
                self.output_data = header + res_data + bytes('\n' + self.data_file.split('.')[1],
                                                             encoding='utf-8')
                # внедряем ключ в резерв
                self.output_data = self.output_data[:6] + key + self.output_data[10:]
                self.show_output_preview()
        except IndexError:
            self.fileTooBigErrMsgBox.setInformativeText(f'В картинку такого размера можно зашифроват\
ь файл размером максимум {int(width * height * 3 / 4)} байт')
            self.fileTooBigErrMsgBox.exec()
        except FileNotFoundError:
            try:
                open(self.input_file, 'rb')
            except FileNotFoundError:
                self.imgFileNotFoundErrMsgBox.exec()
            else:
                self.dataFileNotFoundErrMsgBox.exec()
        except Exception as e:
            self.unexpectedErrorMsgBox.setText('Непредвиденная ошибка %s' % e)
            self.unexpectedErrorMsgBox.exec()

    def lsb_decode(self):  # декодировать методом least significant bit
        try:
            img_f = open(self.input_file, 'rb')
            img_data = img_f.read()
            img_f.close()

            header_len = convert_bytes_to_int(img_data[14:18]) + 14
            data_size = convert_bytes_to_int(img_data[6:10])
            if data_size == 0:
                raise EncodedDataNotFound
            self.output_file_format = b''
            for i in range(len(img_data) - 1, -1, -1):
                if bytes([img_data[i]]) != b'\n':
                    self.output_file_format += bytes([img_data[i]])  # exception нет данных
                else:
                    break
            self.output_file_format = self.output_file_format.decode('utf-8')[::-1]
            img_data = img_data[header_len:]
            res_data = bytes()
            count = 0
            res_byte = 0

            progress = QProgressDialog('Расшифровка данных...', 'Отмена', 0, data_size - 1, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle('Расшифровка')

            for i in range(data_size):
                if progress.wasCanceled():
                    break
                res_byte <<= 2
                res_byte += img_data[i] & 0b11
                count += 1
                if count == 4:
                    count = 0
                    res_data += bytes([res_byte])
                    res_byte = 0
                progress.setValue(i)

            if not progress.wasCanceled():
                self.output_data = res_data
                self.show_output_preview()
        except FileNotFoundError:
            self.imgFileNotFoundErrMsgBox.exec()
        except EncodedDataNotFound:
            self.encodedDataNotFoundErrMsgBox.exec()
        except Exception as e:
            self.unexpectedErrorMsgBox.setText('Непредвиденная ошибка %s' % e)
            self.unexpectedErrorMsgBox.exec()

    def show_output_preview(self):
        pixmap = QPixmap()
        pixmap.loadFromData(self.output_data)
        if pixmap.width() == 0:
            if self.output_file_format == 'txt':
                try:
                    self.outputPreview.setText(self.output_data.decode('utf-8'))
                except UnicodeDecodeError:
                    self.outputPreview.setText('Предпросмотр не доступен')
            else:
                self.outputPreview.setText('Предпросмотр не доступен')
        else:
            if pixmap.width() > 341 or pixmap.height() > 329:
                pixmap = pixmap.scaled(341, 329, Qt.KeepAspectRatio)
            self.outputPreview.setPixmap(pixmap)


def convert_bytes_to_int(b):  # сконвертировать несколько последовательных байт в одно число
    return sum([x * 256 ** i for i, x in enumerate(b)])


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.excepthook = except_hook
    sys.exit(app.exec_())
