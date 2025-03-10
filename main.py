#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                           QRadioButton, QButtonGroup, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from crash_symbolizer import CrashSymbolizer

class ProgressCallback(QObject):
    progress_signal = pyqtSignal(str)
    
    def emit(self, message):
        self.progress_signal.emit(message)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('iOS崩溃日志符号化工具')
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中心部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部控制区域
        top_layout = QVBoxLayout()
        
        # 创建解析方式选择区域
        parse_type_group = QButtonGroup(self)
        parse_type_layout = QHBoxLayout()
        
        self.crash_radio = QRadioButton("Crash解析")
        self.json_radio = QRadioButton("JSON解析")
        parse_type_group.addButton(self.crash_radio)
        parse_type_group.addButton(self.json_radio)
        self.crash_radio.setChecked(True)
        
        parse_type_layout.addWidget(QLabel("解析方式:"))
        parse_type_layout.addWidget(self.crash_radio)
        parse_type_layout.addWidget(self.json_radio)
        parse_type_layout.addStretch()
        
        top_layout.addLayout(parse_type_layout)
        
        # 创建文件选择区域
        file_select_layout = QHBoxLayout()
        
        # Archive文件选择
        self.archive_path_label = QLabel("未选择文件")
        select_archive_btn = QPushButton("选择Archive文件")
        select_archive_btn.clicked.connect(self.select_archive_file)
        
        file_select_layout.addWidget(QLabel("Archive文件:"))
        file_select_layout.addWidget(self.archive_path_label)
        file_select_layout.addWidget(select_archive_btn)
        
        top_layout.addLayout(file_select_layout)
        
        # Crash/JSON文件选择
        self.crash_json_layout = QHBoxLayout()
        self.crash_json_label = QLabel("未选择文件")
        self.select_crash_json_btn = QPushButton("选择Crash/JSON文件")
        self.select_crash_json_btn.clicked.connect(self.select_crash_json_file)
        
        self.crash_json_layout.addWidget(QLabel("Crash/JSON文件:"))
        self.crash_json_layout.addWidget(self.crash_json_label)
        self.crash_json_layout.addWidget(self.select_crash_json_btn)
        
        top_layout.addLayout(self.crash_json_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 开始按钮
        start_btn = QPushButton("开始符号化")
        start_btn.clicked.connect(self.start_symbolization)
        button_layout.addWidget(start_btn)
        
        # 导出按钮
        self.export_btn = QPushButton("导出解析结果")
        self.export_btn.clicked.connect(self.export_result)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)
        
        top_layout.addLayout(button_layout)
        
        main_layout.addLayout(top_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 中间区域：原始文件和解析结果的水平分割
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 原始文件显示区域
        original_widget = QWidget()
        original_layout = QVBoxLayout(original_widget)
        original_layout.addWidget(QLabel("原始文件内容"))
        self.original_text = QTextEdit()
        self.original_text.setReadOnly(True)
        original_layout.addWidget(self.original_text)
        content_splitter.addWidget(original_widget)
        
        # 解析结果显示区域
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.addWidget(QLabel("解析结果"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        content_splitter.addWidget(result_widget)
        
        # 设置内容区域的初始大小比例
        content_splitter.setSizes([400, 400])
        
        # 底部进度显示区域
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.addWidget(QLabel("解析进度"))
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        progress_layout.addWidget(self.progress_text)
        
        # 将内容区域和进度区域添加到垂直分割器
        splitter.addWidget(content_splitter)
        splitter.addWidget(progress_widget)
        
        # 设置垂直分割器的初始大小比例
        splitter.setSizes([500, 200])
        
        main_layout.addWidget(splitter)
        
        # 连接单选按钮信号
        self.crash_radio.toggled.connect(self.update_file_selection)
        self.json_radio.toggled.connect(self.update_file_selection)
        
        # 初始化文件路径和符号化结果
        self.archive_path = None
        self.crash_json_path = None
        self.symbolicated_content = None
        
        # 创建符号化器和进度回调
        self.symbolizer = CrashSymbolizer()
        self.progress_callback = ProgressCallback()
        self.progress_callback.progress_signal.connect(self.update_progress)
        
    def update_file_selection(self):
        """更新文件选择按钮的文本"""
        is_crash = self.crash_radio.isChecked()
        self.select_crash_json_btn.setText("选择Crash文件" if is_crash else "选择JSON文件")
        if self.crash_json_path:
            self.crash_json_path = None
            self.crash_json_label.setText("未选择文件")
            self.original_text.clear()
            
    def select_archive_file(self):
        """选择Archive文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Archive文件",
            "",
            "Archive文件 (*.xcarchive)"
        )
        if file_path:
            self.archive_path = file_path
            self.archive_path_label.setText(os.path.basename(file_path))
            
    def select_crash_json_file(self):
        """选择Crash或JSON文件"""
        file_filter = "Crash文件 (*.crash *.ips)" if self.crash_radio.isChecked() else "JSON文件 (*.json)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            file_filter
        )
        if file_path:
            self.crash_json_path = file_path
            self.crash_json_label.setText(os.path.basename(file_path))
            # 显示原始文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.original_text.setText(content)
            except Exception as e:
                self.original_text.setText(f"无法读取文件内容: {str(e)}")
            
    def update_progress(self, message):
        """更新进度显示"""
        self.progress_text.append(message)
        # 滚动到底部
        scrollbar = self.progress_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_all(self):
        """清空所有显示区域"""
        self.progress_text.clear()
        self.original_text.clear()
        self.result_text.clear()
        self.symbolicated_content = None
        self.export_btn.setEnabled(False)
        
    def export_result(self):
        """导出解析结果"""
        if not self.symbolicated_content:
            self.update_progress("错误: 没有可导出的解析结果")
            return
            
        default_name = os.path.splitext(os.path.basename(self.crash_json_path))[0] + "_symbolicated.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出解析结果",
            default_name,
            "文本文件 (*.txt)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.symbolicated_content)
                self.update_progress(f"\n✓ 解析结果已导出到: {file_path}")
            except Exception as e:
                self.update_progress(f"\n导出文件时出错: {str(e)}")
            
    def start_symbolization(self):
        """开始符号化过程"""
        if not self.archive_path or not self.crash_json_path:
            self.update_progress("错误: 请先选择所需的文件")
            return
            
        self.progress_text.clear()
        self.result_text.clear()
        self.symbolicated_content = None
        self.export_btn.setEnabled(False)
        self.update_progress("开始符号化过程...\n")
        
        try:
            # 加载Archive文件
            self.update_progress("[1] 加载Archive文件...")
            self.symbolizer.load_archive(self.archive_path)
            self.update_progress(f"✓ Archive加载成功")
            self.update_progress(f"  - 应用名称: {self.symbolizer.binary_name}")
            self.update_progress(f"  - dSYM路径: {self.symbolizer.dsym_path}")
            self.update_progress(f"  - UUID: {self.symbolizer.binary_uuid}\n")
            
            # 根据选择的解析方式处理文件
            if self.crash_radio.isChecked():
                # Crash文件解析
                self.update_progress("[2] 加载Crash文件...")
                crash_content = self.symbolizer.load_crash_file(self.crash_json_path)
                self.update_progress("✓ Crash文件加载成功")
                self.update_progress(f"  - 文件大小: {len(crash_content)} 字节\n")
                
                self.update_progress("[3] 解析Crash信息...")
                self.symbolizer.parse_crash(crash_content)
                self.update_progress("✓ 解析完成\n")
                
                self.update_progress("[4] 开始符号化...")
                self.symbolicated_content = self.symbolizer.symbolize(self.progress_callback)
            else:
                # JSON文件解析
                self.update_progress("[2] 加载MetricKit JSON文件...")
                json_data = self.symbolizer.load_metrickit_json(self.crash_json_path)
                self.update_progress("✓ JSON文件加载成功")
                self.update_progress(f"  - 文件大小: {os.path.getsize(self.crash_json_path)} 字节\n")
                
                self.update_progress("[3] 解析崩溃信息...")
                self.symbolizer.parse_metrickit_crash(json_data)
                crash_info = self.symbolizer.get_crash_info()
                self.update_progress("✓ 解析完成")
                if crash_info:
                    self.update_progress(f"  - 设备型号: {crash_info.get('deviceType', 'Unknown')}")
                    self.update_progress(f"  - 系统版本: {crash_info.get('osVersion', 'Unknown')}")
                    self.update_progress(f"  - 应用版本: {crash_info.get('appVersion', 'Unknown')}\n")
                
                self.update_progress("[4] 开始符号化...")
                self.symbolicated_content = self.symbolizer.symbolize_metrickit(self.progress_callback)
            
            # 显示结果
            if self.symbolicated_content:
                self.result_text.setText(self.symbolicated_content)
                self.export_btn.setEnabled(True)
                self.update_progress("\n✓ 符号化过程完成")
            
        except Exception as e:
            self.update_progress(f"\n错误: {str(e)}")
            import traceback
            self.update_progress(traceback.format_exc())

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 