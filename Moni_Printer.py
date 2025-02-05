# Monitoramento Gomaq

import sys
import threading
import time
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QIcon
from selenium import webdriver
import schedule


# Classe que representa a janela de pop-up
class PopupWindow(QtWidgets.QWidget):
    def __init__(self, mensagem):
        super().__init__()
        self.initUI(mensagem)

    def initUI(self, mensagem):
        self.setWindowTitle("Solicitar Suprimentos GOMAQ")
        self.setMinimumSize(450, 300)

        layout = QtWidgets.QVBoxLayout()

        # Define o ícone da janela
        self.setWindowIcon(QIcon('Impressora.ico'))

        self.label = QtWidgets.QLabel(mensagem, self)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont()
        font.setPointSize(14)
        self.label.setFont(font)
        layout.addWidget(self.label)

        self.button = QtWidgets.QPushButton("Fechar", self)
        self.button.clicked.connect(self.close)
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.show()


# Classe principal da aplicação
class MainWindow(QtWidgets.QMainWindow):
    # Sinais personalizados para comunicação entre threads
    show_popup_signal = QtCore.pyqtSignal(str)
    update_log_signal = QtCore.pyqtSignal(str)
    update_timer_signal = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor de Suprimentos")
        self.setWindowIcon(QIcon('Impressora.ico'))
        self.setMinimumSize(800, 300)

        self.monitor_thread = None
        self.popups = []
        self.next_check_time = None

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QtWidgets.QVBoxLayout(self.central_widget)

        self.status_label = QtWidgets.QLabel("Status: Parado")
        font = QtGui.QFont()
        font.setPointSize(12)  # Define o tamanho da fonte
        self.status_label.setFont(font)

        # Barra de progresso para indicar o monitoramento
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(0)  # Indeterminado
        self.progress_bar.setMinimum(0)
        self.progress_bar.setVisible(False)  # Começa invisível

        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        layout.addLayout(status_layout)

        self.timer_label = QtWidgets.QLabel("Próximo teste em: --:--:--")
        self.timer_label.setFont(font)
        layout.addWidget(self.timer_label)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text)

        self.stop_button = QtWidgets.QPushButton("Parar")
        self.stop_button.setFont(font)
        self.stop_button.setEnabled(False)  # Começa desabilitado
        self.stop_button.clicked.connect(self.stop_monitor)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        # Conecta sinais personalizados a slots
        self.show_popup_signal.connect(self.exibir_popup)
        self.update_log_signal.connect(self.update_log)
        self.update_timer_signal.connect(self.update_timer)

        # Inicia o monitoramento automaticamente
        self.start_monitor()

        # Inicia o temporizador
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # Atualiza a cada segundo

    # Função para iniciar o monitoramento
    def start_monitor(self):
        self.monitor_thread = threading.Thread(target=self.monitorar)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.status_label.setText("Status: Monitorando")
        self.progress_bar.setVisible(True)
        self.stop_button.setEnabled(True)
        self.schedule_checks()

    # Função para parar o monitoramento
    def stop_monitor(self):
        if self.monitor_thread:
            self.monitor_thread.do_run = False
            self.monitor_thread.join()
        self.status_label.setText("Status: Parado")
        self.progress_bar.setVisible(False)
        self.stop_button.setEnabled(False)

    # Função para exibir pop-ups
    def exibir_popup(self, mensagem):
        popup = PopupWindow(mensagem)
        self.popups.append(popup)
        popup.destroyed.connect(lambda: self.popups.remove(popup))

    # Função para atualizar o log de eventos
    def update_log(self, message):
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        self.log_text.append(f"[{now}] {message}")

    # Função para atualizar o temporizador
    def update_timer(self):
        if self.next_check_time:
            remaining_time = self.next_check_time - datetime.now()
            if remaining_time.total_seconds() > 0:
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.timer_label.setText(f"Próximo teste em: {hours:02}:{minutes:02}:{seconds:02}")
            else:
                self.timer_label.setText("Próximo teste em: 00:00:00")

    # Função para agendar verificações
    def schedule_checks(self):
        now = datetime.now()
        if now.hour < 8 or (now.hour == 8 and now.minute < 30):
            next_check = now.replace(hour=8, minute=30, second=0, microsecond=0)
        elif now.hour < 16 or (now.hour == 15 and now.minute < 1):
            next_check = now.replace(hour=15, minute=0, second=0, microsecond=0)
        else:
            next_check = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)

        self.next_check_time = next_check
        self.update_timer()

    # Função principal de monitoramento
    def monitorar(self):
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        driver = webdriver.Chrome(options=options)
        urls = ["https://172.20.20.23/#/Status", "https://172.20.20.24/#/Status"]
        driver.maximize_window()

        self.monitor_thread.do_run = True

        while getattr(self.monitor_thread, "do_run", True):
            current_time = datetime.now()

            if current_time >= self.next_check_time:
                try:
                    for url in urls:
                        driver.get(url)
                        time.sleep(5)

                        # Scripts para extrair os valores de toner, Unidade de imagem e Fusor
                        script_tonner = """
                            const tonnerElement = document.querySelector('.progress-inner');
                            return tonnerElement ? tonnerElement.getAttribute('title') : null;
                            """
                        tonner_value = driver.execute_script(script_tonner)

                        script_drum = """
                            const drumElement = document.querySelector("#PCDrumStatus > div > div > div.contentBody > div > div");
                            return drumElement ? drumElement.getAttribute('title') : null;
                            """
                        drum_value = driver.execute_script(script_drum)

                        script_fuser = """
                            const fuserElement = document.querySelector("#FuserSuppliesStatus > div > div > div.contentBody > div > div");
                            return fuserElement ? fuserElement.getAttribute('title') : null;
                            """
                        fuser_value = driver.execute_script(script_fuser)

                        # Função para extrair o valor percentual de título
                        def extract_percent(value):
                            if value:
                                return int(value.strip('%'))
                            return None

                        tonner_percentual = extract_percent(tonner_value)
                        drum_percentual = extract_percent(drum_value)
                        fuser_percentual = extract_percent(fuser_value)

                        log_message = (f"URL: {url}\n"
                                       f"Percentual de Tonner encontrado: {tonner_percentual}%\n"
                                       f"Percentual da Unidade de Imagem encontrado: {drum_percentual}%\n"
                                       f"Percentual do Kit de Manuntenção encontrado: {fuser_percentual}%\n")
                        self.update_log_signal.emit(log_message)

                        # Verificar os percentuais e emitir alertas se necessário
                        if tonner_percentual is not None and 15 < tonner_percentual <= 20:
                            mensagem = f"Alerta: TONNER ESTÁ ACABANDO! Percentual: {tonner_percentual}%"
                            self.show_popup_signal.emit(mensagem)
                        if drum_percentual is not None and 8 < drum_percentual <= 10:
                            mensagem = f"Alerta: UNIDADE DE IMAGEM ESTÁ ACABANDO! Percentual: {drum_percentual}%"
                            self.show_popup_signal.emit(mensagem)
                        if fuser_percentual is not None and fuser_percentual <= 5:
                            mensagem = f"Alerta: KIT DE MANUTENÇÃO PRECISA SER TROCADOR na impressora: {fuser_percentual}%"
                            self.show_popup_signal.emit(mensagem)

                except Exception as e:
                    self.update_log_signal.emit(f"Erro na URL {url}: {e}")

                # Atualiza o próximo tempo de verificação
                self.schedule_checks()

            # Calcula o tempo restante para a próxima verificação
            time_remaining = (self.next_check_time - datetime.now()).total_seconds()
            if time_remaining > 0:
                time.sleep(time_remaining)
            else:
                time.sleep(1)

# Ponto de entrada da aplicação
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

