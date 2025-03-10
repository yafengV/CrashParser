#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                            QTextEdit, QSplitter, QMessageBox, QProgressBar,
                            QTabWidget, QGroupBox, QFormLayout, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

from crash_symbolizer import CrashSymbolizer

class SymbolizationThread(QThread):
    """用于在后台执行符号化过程的线程"""
    progress_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, archive_path=None, crash_path=None):
        super().__init__()
        self.archive_path = archive_path
        self.crash_path = crash_path
        self.symbolizer = CrashSymbolizer()
        
    def set_paths(self, archive_path, crash_path):
        self.archive_path = archive_path
        self.crash_path = crash_path
        
    def run(self):
        try:
            # 发送开始信息
            self.progress_signal.emit("开始符号化过程...\n")
            
            # 加载 archive
            self.progress_signal.emit("\n[1] 加载 Archive 文件...")
            self.symbolizer.load_archive(self.archive_path)
            self.progress_signal.emit("✓ Archive 加载成功\n")
            
            # 加载 crash 文件
            self.progress_signal.emit("\n[2] 加载 Crash 文件...")
            crash_content = self.symbolizer.load_crash_file(self.crash_path)
            self.progress_signal.emit("✓ Crash 文件加载成功\n")
            
            # 解析 crash 内容
            self.progress_signal.emit("\n[3] 解析 Crash 内容...")
            self.symbolizer.parse_crash(crash_content)
            self.progress_signal.emit("✓ Crash 内容解析成功\n")
            
            # 符号化处理
            self.progress_signal.emit("\n[4] 开始符号化...")
            result = self.symbolizer.symbolize(self.progress_signal)
            
            # 发送结果
            self.result_signal.emit(result)
            
        except Exception as e:
            self.progress_signal.emit(f"\n❌ 错误: {str(e)}\n")
        finally:
            self.finished_signal.emit()


class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.archive_path = None
        self.crash_path = None
        self.symbolized_result = ""
        self.init_ui()
        self.thread = SymbolizationThread()
        self.setup_connections()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("iOS Crash堆栈符号化解析工具")
        self.setMinimumSize(1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选择文件区域
        file_group = QGroupBox("文件选择")
        file_layout = QFormLayout()
        
        # Archive文件选择
        archive_layout = QHBoxLayout()
        self.archive_path_edit = QLineEdit()
        self.archive_path_edit.setReadOnly(True)
        archive_button = QPushButton("选择Archive文件")
        archive_button.clicked.connect(self.select_archive)
        archive_layout.addWidget(self.archive_path_edit)
        archive_layout.addWidget(archive_button)
        file_layout.addRow("Archive文件:", archive_layout)
        
        # Crash文件选择
        crash_layout = QHBoxLayout()
        self.crash_path_edit = QLineEdit()
        self.crash_path_edit.setReadOnly(True)
        crash_button = QPushButton("选择Crash文件")
        crash_button.clicked.connect(self.select_crash)
        crash_layout.addWidget(self.crash_path_edit)
        crash_layout.addWidget(crash_button)
        file_layout.addRow("Crash文件:", crash_layout)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # 创建按钮区域
        button_layout = QHBoxLayout()
        self.symbolize_button = QPushButton("开始符号化")
        self.symbolize_button.clicked.connect(self.start_symbolization)
        self.symbolize_button.setEnabled(False)
        
        self.export_button = QPushButton("导出结果")
        self.export_button.clicked.connect(self.export_result)
        self.export_button.setEnabled(False)
        
        button_layout.addWidget(self.symbolize_button)
        button_layout.addWidget(self.export_button)
        main_layout.addLayout(button_layout)
        
        # 创建内容显示区域（使用QSplitter）
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)  # 防止区域被完全折叠
        
        # 左侧：解析过程显示
        process_group = QGroupBox("解析过程")
        process_layout = QVBoxLayout()
        self.process_text = QTextEdit()
        self.process_text.setReadOnly(True)
        self.process_text.setFont(QFont("Courier New", 10))
        self.process_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: none;
            }
        """)
        process_layout.addWidget(self.process_text)
        process_group.setLayout(process_layout)
        content_splitter.addWidget(process_group)
        
        # 右侧：原始内容和符号化结果
        result_group = QGroupBox("符号化结果")
        result_layout = QVBoxLayout()
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 原始Crash内容
        self.original_crash_text = QTextEdit()
        self.original_crash_text.setReadOnly(True)
        self.original_crash_text.setFont(QFont("Courier New", 10))
        
        # 符号化后的内容
        self.symbolized_crash_text = QTextEdit()
        self.symbolized_crash_text.setReadOnly(True)
        self.symbolized_crash_text.setFont(QFont("Courier New", 10))
        
        self.tab_widget.addTab(self.original_crash_text, "原始Crash")
        self.tab_widget.addTab(self.symbolized_crash_text, "符号化结果")
        
        result_layout.addWidget(self.tab_widget)
        result_group.setLayout(result_layout)
        content_splitter.addWidget(result_group)
        
        # 设置分割器的初始大小
        content_splitter.setSizes([400, 800])
        
        main_layout.addWidget(content_splitter)
        
        # 状态栏
        self.statusBar().showMessage("准备就绪")
        
    def setup_connections(self):
        self.archive_path_edit.textChanged.connect(self.update_start_button)
        self.crash_path_edit.textChanged.connect(self.update_start_button)
        self.symbolize_button.clicked.connect(self.start_symbolization)
        self.export_button.clicked.connect(self.export_result)
        
        # 设置线程信号连接
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.result_signal.connect(self.show_result)
        self.thread.finished_signal.connect(self.symbolization_finished)
        
    def select_archive(self):
        """选择Archive文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Archive文件", "", "XCArchive文件 (*.xcarchive);;所有文件 (*)"
        )
        if file_path:
            self.archive_path = file_path
            self.archive_path_edit.setText(file_path)
            self.update_start_button()
            
    def select_crash(self):
        """选择Crash文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Crash文件", "", "Crash文件 (*.crash *.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                # 读取并显示原始内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    crash_content = f.read()
                    self.original_crash_text.setText(crash_content)
                    self.tab_widget.setCurrentIndex(0)  # 切换到原始Crash标签页
            except UnicodeDecodeError:
                try:
                    # 尝试其他编码
                    with open(file_path, 'r', encoding='latin-1') as f:
                        crash_content = f.read()
                        self.original_crash_text.setText(crash_content)
                        self.tab_widget.setCurrentIndex(0)
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"读取Crash文件失败: {str(e)}")
                    return
            except Exception as e:
                QMessageBox.warning(self, "警告", f"读取Crash文件失败: {str(e)}")
                return
                
            self.crash_path = file_path
            self.crash_path_edit.setText(file_path)
            self.update_start_button()
            
    def update_start_button(self):
        """检查是否已选择所需文件"""
        if self.archive_path and self.crash_path:
            self.symbolize_button.setEnabled(True)
        else:
            self.symbolize_button.setEnabled(False)
            
    def start_symbolization(self):
        """开始符号化过程"""
        if not self.archive_path or not self.crash_path:
            QMessageBox.warning(self, "警告", "请先选择Archive文件和Crash文件")
            return
            
        # 清空显示区域
        self.process_text.clear()
        self.symbolized_crash_text.clear()
        
        # 禁用按钮
        self.symbolize_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("正在符号化...")
        
        # 创建并启动符号化线程
        self.thread.set_paths(self.archive_path, self.crash_path)
        self.thread.start()
        
    def update_progress(self, message):
        """更新进度信息"""
        self.process_text.append(message)
        # 自动滚动到底部
        scrollbar = self.process_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def show_result(self, result):
        """显示符号化结果"""
        self.symbolized_result = result
        self.symbolized_crash_text.setText(result)
        self.tab_widget.setCurrentIndex(1)  # 切换到符号化结果标签页
        
    def symbolization_finished(self):
        """符号化过程完成"""
        self.symbolize_button.setEnabled(True)
        if self.symbolized_result:
            self.export_button.setEnabled(True)
            self.statusBar().showMessage("符号化完成")
        else:
            self.statusBar().showMessage("准备就绪")
        
    def export_result(self):
        """导出符号化结果"""
        if not self.symbolized_result:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出符号化结果", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.symbolized_result)
                QMessageBox.information(self, "成功", f"结果已成功导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 