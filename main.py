import sys
import os
import time
import uuid
import pytz  # New import for time zones
import numpy as np
import pyautogui
import markdown
from datetime import datetime, timedelta
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from PyQt6.QtWidgets import QAbstractScrollArea, QTabWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject, QEvent, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QScrollArea,
    QPushButton,
    QToolBar,
    QSizePolicy,
    QComboBox
)
from agent import AgentWrapper

# -------------------------------------------------------------------
# 2. Worker Thread for Sending Messages to the Agent
# -------------------------------------------------------------------
class SendMessageWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal()

    def __init__(self, agent: AgentWrapper, user_text=None, image_uris=None, memorizing=False):
        super().__init__()
        self.agent = agent
        self.user_text = user_text
        self.image_uris = image_uris
        self.memorizing = memorizing

    def run(self):

        response = self.agent.send_message(
            self.user_text,
            image_uris=self.image_uris,
            memorizing=self.memorizing
        )

        if response == "ERROR":
            self.error_signal.emit()
        elif not self.memorizing:
            self.finished_signal.emit(response)

# -------------------------------------------------------------------
# 3. Screenshot Capturing Thread
# -------------------------------------------------------------------
class ScreenshotThread(QThread):
    screenshot_signal = pyqtSignal(str, bool)

    def __init__(self, agent: AgentWrapper, interval=1.0, similarity_threshold=0.95):
        super().__init__()
        self.agent = agent
        self.interval = interval
        self.similarity_threshold = similarity_threshold
        self._running = False
        self.last_image_array = None

    def start_capturing(self):
        self._running = True
        self.start()

    def stop_capturing(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                screenshot = pyautogui.screenshot()
                screenshot_gray = screenshot.convert("L")
                screenshot_array = np.array(screenshot_gray)

                if self.last_image_array is not None and screenshot_array.shape == self.last_image_array.shape:
                    score = ssim(screenshot_array, self.last_image_array)
                else:
                    score = 0.0

                if score < self.similarity_threshold:
                    filename = f'./tmp/{uuid.uuid4()}.png'
                    os.makedirs("./tmp", exist_ok=True)
                    screenshot.save(filename)
                    self.screenshot_signal.emit(filename, True)

                self.last_image_array = screenshot_array

            except Exception as e:
                print("Error in SSIM calculation:", e)
            time.sleep(self.interval)

# -------------------------------------------------------------------
# 4. Custom Widgets for Chat Bubbles
# -------------------------------------------------------------------
class ChatBubbleUser(QWidget):
    def __init__(self, message_text: str, parent=None):
        super().__init__(parent=parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(message_text, self)
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                background-color: #3874f2;
                color: white;
                padding: 10px;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setCursor(Qt.CursorShape.IBeamCursor)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

class ChatBubbleAgent(QWidget):
    def __init__(self, message_text_md: str, parent=None):
        super().__init__(parent=parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        html = markdown.markdown(message_text_md)
        label = QLabel(self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(html)
        label.setStyleSheet("""
            QLabel {
                background-color: #444;
                color: #fff;
                padding: 10px;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setCursor(Qt.CursorShape.IBeamCursor)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

# -------------------------------------------------------------------
# 5. Main Chat Window
# -------------------------------------------------------------------
class MainChatWindow(QMainWindow):
    def __init__(self, agent: AgentWrapper, parent=None):
        super().__init__(parent=parent)
        self.agent = agent
        self.setWindowTitle("Mirix")
        self.setWindowIcon(QIcon("./assets/logo.png"))
        self.selected_model = agent.model_name
        self.worker_threads = []

        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; font-size: 16px; }
            QToolBar { background-color: #2b2b2b; }
            QPushButton { font-size: 14px; }
            QComboBox { font-size: 14px; }
            QScrollArea { background-color: #2b2b2b; }
            QTextEdit { background-color: #3a3a3a; color: #ffffff; border-radius: 8px; padding: 8px; font-size: 16px; }
        """)

        # Create a central widget and a QTabWidget to hold multiple tabs
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tab 1: Chat Interface
        self.chat_tab = QWidget()
        self.init_chat_tab()
        self.tab_widget.addTab(self.chat_tab, "Chat")

        # Tab 2: Time Zone Selection
        self.settings_tab = QWidget()
        self.init_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "Settings")

        self.resize(800, 700)

    def init_chat_tab(self):
        """Initialize the chat interface tab."""
        layout = QVBoxLayout(self.chat_tab)

        # Toolbar setup (reuse your existing toolbar code)
        self.toolbar = QToolBar("Toolbar", self)
        self.addToolBar(self.toolbar)

        self.screenshot_button = QPushButton("Screenshot Capturing: OFF")
        self.screenshot_button.setCheckable(True)
        self.screenshot_button.clicked.connect(self.toggle_screenshot_capturing)
        self.toolbar.addWidget(self.screenshot_button)

        # --- New Clear Chat Button ---
        self.clear_chat_button = QPushButton("Clear Chat")
        self.clear_chat_button.clicked.connect(self.clear_conversation)
        self.toolbar.addWidget(self.clear_chat_button)
        # ------------------------------

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.model_selector = QComboBox(self)
        self.model_selector.addItem("gemini-2.0-flash-lite")
        self.model_selector.addItem("gemini-2.0-flash")
        self.model_selector.addItem("gemini-1.5-pro")
        current_index = self.model_selector.findText(self.selected_model)
        if current_index >= 0:
            self.model_selector.setCurrentIndex(current_index)
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        self.toolbar.addWidget(self.model_selector)
        layout.addWidget(self.toolbar)

        # Chat display area
        self.chat_area_scroll = QScrollArea(self)
        self.chat_area_scroll.setWidgetResizable(True)
        self.chat_area_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.chat_area_widget = QWidget()
        self.chat_area_layout = QVBoxLayout(self.chat_area_widget)
        self.chat_area_layout.setSpacing(10)
        self.chat_area_layout.addStretch(1)
        self.chat_area_scroll.setWidget(self.chat_area_widget)
        self.chat_area_scroll.verticalScrollBar().rangeChanged.connect(self.scroll_to_bottom)
        layout.addWidget(self.chat_area_scroll, 1)

        # Input field for messages
        self.input_field = QTextEdit(self)
        self.input_field.setFixedHeight(40)
        self.input_field.installEventFilter(self)
        layout.addWidget(self.input_field, 0)

        # Initialize the screenshot thread
        self.screenshot_thread = ScreenshotThread(agent=self.agent, interval=1.0, similarity_threshold=0.95)
        self.screenshot_thread.screenshot_signal.connect(self.on_screenshot_captured)

    def init_settings_tab(self):

        layout = QVBoxLayout(self.settings_tab)

        # ---------------------------
        # 1) Time Zone Selector
        # ---------------------------
        instruction_label = QLabel("Select your time zone:", self.settings_tab)
        layout.addWidget(instruction_label)

        self.timezone_selector = QComboBox(self.settings_tab)

        # We'll store tuples of (tz_str, offset_minutes, display_str) to sort and then populate
        timezones_info = []
        for tz_str in pytz.all_timezones:
            tz = pytz.timezone(tz_str)
            now_local = datetime.now(tz)
            offset_td = now_local.utcoffset() or timedelta(0)
            offset_minutes = int(offset_td.total_seconds() // 60)

            sign = "+" if offset_minutes >= 0 else "-"
            abs_minutes = abs(offset_minutes)
            hours = abs_minutes // 60
            mins = abs_minutes % 60
            offset_formatted = f"UTC{sign}{hours:02d}:{mins:02d}"

            display_str = f"{tz_str} ({offset_formatted})"
            timezones_info.append((tz_str, offset_minutes, display_str))

        # Sort first by offset, then by tz_str
        timezones_info.sort(key=lambda x: (x[1], x[0]))

        for tz_str, offset_minutes, display_str in timezones_info:
            # Store the raw tz_str in item data if needed
            self.timezone_selector.addItem(display_str, tz_str)

        layout.addWidget(self.timezone_selector)
        self.timezone_selector.currentTextChanged.connect(self.on_timezone_changed)

        default_index = self.timezone_selector.findText(self.agent.timezone_str)
        if default_index != -1:
            self.timezone_selector.setCurrentIndex(default_index)

        # ---------------------------
        # 2) Persona Selector
        # ---------------------------
        persona_label = QLabel("Select your preferred persona:", self.settings_tab)
        layout.addWidget(persona_label)

        self.persona_selector = QComboBox(self.settings_tab)
        # Add your predefined personas
        self.persona_selector.addItem("chill_buddy", "Chill Buddy")
        self.persona_selector.addItem("concise_analyst", "Concise Analyst")
        self.persona_selector.addItem("friendly_conversationalist", "Friendly Conversationalist")
        self.persona_selector.addItem("playful_ironist", "Playful Ironist")
        self.persona_selector.addItem("project_manager", "Project Manager")

        layout.addWidget(self.persona_selector)
        # Connect a slot if you want to handle persona changes
        self.persona_selector.currentTextChanged.connect(self.on_persona_changed)

        # ---------------------------
        # Stretch at the bottom
        # ---------------------------
        layout.addStretch(1)

    def on_timezone_changed(self, timezone_str: str):
        """Handle updates when a new time zone is selected."""
        self.agent.set_timezone(timezone_str)

    def on_model_changed(self, model_name: str):
        self.selected_model = model_name
        self.agent.set_model(model_name)

    def on_persona_changed(self, persona_label: str):
        """
        Called when the user changes the persona combo box.
        persona_label will be "Engineer" or "Ironic" in this example.
        """
        index = self.persona_selector.currentIndex()
        persona_value = self.persona_selector.itemData(index)  # 'engineer' or 'ironic'
        self.agent.set_persona(persona_value)

    def line_height(self, lines=1):
        base_height = 24
        return base_height * lines

    def eventFilter(self, obj, event):
        if obj == self.input_field and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.input_field.insertPlainText("\n")
                    return True
                else:
                    self.send_user_message()
                    return True
        elif obj == self.input_field and event.type() == QEvent.Type.KeyRelease:
            doc = self.input_field.document()
            doc.setTextWidth(self.input_field.viewport().width())
            new_height = doc.size().height() + 10
            min_height = 40
            max_height = 200
            new_height = max(min(new_height, max_height), min_height)
            self.input_field.setFixedHeight(int(new_height))
        return super().eventFilter(obj, event)

    def send_user_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        self.input_field.clear()
        self.input_field.setFixedHeight(self.line_height(1))
        user_bubble = ChatBubbleUser(message_text=text)
        self.chat_area_layout.insertWidget(self.chat_area_layout.count() - 1, user_bubble)

        self.agent_worker = SendMessageWorker(
            agent=self.agent,
            user_text=text,
            image_uris=None,
            memorizing=False
        )
        self.agent_worker.finished_signal.connect(self.display_agent_message)
        self.agent_worker.finished.connect(self.cleanup_worker_thread)
        self.agent_worker.error_signal.connect(self.handle_error_and_exit)
        self.worker_threads.append(self.agent_worker)
        self.agent_worker.start()

    @pyqtSlot(str)
    def display_agent_message(self, response: str):
        agent_bubble = ChatBubbleAgent(message_text_md=response)
        self.chat_area_layout.insertWidget(self.chat_area_layout.count() - 1, agent_bubble)

    def scroll_to_bottom(self):
        self.chat_area_widget.adjustSize()  # Force the widget to recompute its size.
        QApplication.processEvents()         # Process pending events.
        self.chat_area_scroll.verticalScrollBar().setValue(
            self.chat_area_scroll.verticalScrollBar().maximum()
        )

    def clear_conversation(self):
        """Clear all chat bubbles from the chat area."""
        while self.chat_area_layout.count():
            item = self.chat_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Re-add the bottom stretch to keep layout behavior
        self.chat_area_layout.addStretch(1)

    def toggle_screenshot_capturing(self):
        if self.screenshot_button.isChecked():
            self.screenshot_button.setText("Screenshot Capturing: ON")
            self.screenshot_thread.start_capturing()
        else:
            self.screenshot_button.setText("Screenshot Capturing: OFF")
            self.screenshot_thread.stop_capturing()

    @pyqtSlot(str, bool)
    def on_screenshot_captured(self, filename: str, memorizing: bool):
        self.agent_worker = SendMessageWorker(
            agent=self.agent,
            image_uris=[filename],
            memorizing=memorizing
        )
        self.agent_worker.finished_signal.connect(self.display_agent_message)
        self.agent_worker.finished.connect(self.cleanup_worker_thread)
        self.agent_worker.error_signal.connect(self.handle_error_and_exit)
        self.worker_threads.append(self.agent_worker)
        self.agent_worker.start()

    @pyqtSlot()
    def handle_error_and_exit(self):
        print("Agent returned ERROR. Closing application...")
        self.close()

    def cleanup_worker_thread(self):
        sender = self.sender()
        if sender in self.worker_threads:
            self.worker_threads.remove(sender)

    def closeEvent(self, event):
        if hasattr(self, 'screenshot_thread'):
            self.screenshot_thread.stop_capturing()
            self.screenshot_thread.wait()
        for thread in self.worker_threads:
            thread.wait()
        super().closeEvent(event)

# -------------------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSImage
            ns_app = NSApplication.sharedApplication()
            icon_path = os.path.abspath("assets/logo_small.png")
            ns_icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            ns_app.setApplicationIconImage_(ns_icon)
        except ImportError:
            print("PyObjC is required on macOS. Install it using 'pip install pyobjc'.")
    agent = AgentWrapper('configs/mirix.yaml')
    window = MainChatWindow(agent=agent)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()