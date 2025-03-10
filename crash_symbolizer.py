#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import tempfile
import shutil
import plistlib
from pathlib import Path


class CrashSymbolizer:
    """iOS Crash堆栈符号化解析器"""
    
    def __init__(self):
        self.dsym_path = None
        self.binary_path = None
        self.binary_name = None
        self.binary_uuid = None
        self.crash_content = None
        self.crash_lines = []
        self.binary_images = []
        self.thread_backtraces = []
        self.crash_info = {}
        
    def load_archive(self, archive_path):
        """
        从.xcarchive文件中加载dSYM文件和二进制文件
        
        Args:
            archive_path: .xcarchive文件的路径
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive文件不存在: {archive_path}")
            
        # 查找应用包
        products_path = os.path.join(archive_path, "Products", "Applications")
        if not os.path.exists(products_path):
            raise FileNotFoundError(f"Applications目录不存在: {products_path}")
            
        # 查找.app文件
        app_files = [f for f in os.listdir(products_path) if f.endswith('.app')]
        if not app_files:
            raise FileNotFoundError("找不到.app文件")
            
        app_path = os.path.join(products_path, app_files[0])
        
        # 获取应用包中的Info.plist文件
        info_plist_path = os.path.join(app_path, "Info.plist")
        if not os.path.exists(info_plist_path):
            raise FileNotFoundError(f"Info.plist文件不存在: {info_plist_path}")
            
        # 解析Info.plist获取应用名称
        try:
            with open(info_plist_path, 'rb') as fp:
                info_plist = plistlib.load(fp)
                app_name = info_plist.get("CFBundleExecutable")
                if not app_name:
                    raise ValueError("无法从Info.plist获取应用名称(CFBundleExecutable)")
                    
                self.binary_name = app_name
                
                # 查找应用的二进制文件
                binary_path = os.path.join(app_path, app_name)
                if not os.path.exists(binary_path):
                    raise FileNotFoundError(f"找不到应用的二进制文件: {binary_path}")
                    
                self.binary_path = binary_path
                
        except Exception as e:
            raise Exception(f"解析Info.plist失败: {str(e)}")
            
        # 查找dSYM文件
        dsyms_path = os.path.join(archive_path, "dSYMs")
        if not os.path.exists(dsyms_path):
            raise FileNotFoundError(f"dSYMs目录不存在: {dsyms_path}")
            
        # 查找应用的dSYM文件
        app_dsym = None
        dsym_name = f"{app_name}.app.dSYM"
        dsym_path = os.path.join(dsyms_path, dsym_name)
        if os.path.exists(dsym_path):
            app_dsym = dsym_path
        else:
            # 尝试查找其他匹配的dSYM文件
            for dsym in os.listdir(dsyms_path):
                if dsym.endswith(".dSYM") and app_name in dsym:
                    app_dsym = os.path.join(dsyms_path, dsym)
                    break
                    
        if not app_dsym:
            raise FileNotFoundError(f"找不到应用的dSYM文件: {dsym_name}")
            
        self.dsym_path = app_dsym
        
        # 获取二进制文件的UUID
        try:
            result = subprocess.run(
                ["dwarfdump", "--uuid", self.dsym_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 解析UUID
            uuid_match = re.search(r'UUID: ([0-9A-F-]+)', result.stdout)
            if uuid_match:
                self.binary_uuid = uuid_match.group(1).lower()
            else:
                raise ValueError("无法获取二进制文件的UUID")
                
        except subprocess.CalledProcessError as e:
            raise Exception(f"获取UUID失败: {str(e)}")
            
    def load_crash_file(self, crash_path):
        """
        加载Crash文件
        
        Args:
            crash_path: Crash文件的路径
            
        Returns:
            str: Crash文件的内容
        """
        if not os.path.exists(crash_path):
            raise FileNotFoundError(f"Crash文件不存在: {crash_path}")
            
        try:
            with open(crash_path, 'r', encoding='utf-8') as f:
                self.crash_content = f.read()
                return self.crash_content
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(crash_path, 'r', encoding='latin-1') as f:
                    self.crash_content = f.read()
                    return self.crash_content
            except Exception as e:
                raise Exception(f"读取Crash文件失败: {str(e)}")
        except Exception as e:
            raise Exception(f"读取Crash文件失败: {str(e)}")
            
    def parse_crash(self, crash_content):
        """
        解析Crash文件内容
        
        Args:
            crash_content: Crash文件的内容
        """
        if not crash_content:
            raise ValueError("Crash内容为空")
            
        self.crash_lines = crash_content.splitlines()
        
        # 解析Crash基本信息
        self._parse_crash_info()
        
        # 解析二进制镜像信息
        self._parse_binary_images()
        
        # 解析线程回溯信息
        self._parse_thread_backtraces()
        
    def _parse_crash_info(self):
        """解析Crash基本信息"""
        for line in self.crash_lines:
            # 解析进程名称
            if "Process:" in line:
                match = re.search(r'Process:\s+(\S+)\s+\[(\d+)\]', line)
                if match:
                    self.crash_info['process_name'] = match.group(1)
                    self.crash_info['process_id'] = match.group(2)
                    
            # 解析版本信息
            elif "Version:" in line:
                match = re.search(r'Version:\s+(.*?)\s+\((\S+)\)', line)
                if match:
                    self.crash_info['version'] = match.group(1)
                    self.crash_info['build'] = match.group(2)
                    
            # 解析OS版本
            elif "OS Version:" in line:
                match = re.search(r'OS Version:\s+(.*?)\s+\((\S+)\)', line)
                if match:
                    self.crash_info['os_version'] = match.group(1)
                    self.crash_info['os_build'] = match.group(2)
                    
            # 解析异常类型
            elif "Exception Type:" in line:
                match = re.search(r'Exception Type:\s+(.*)', line)
                if match:
                    self.crash_info['exception_type'] = match.group(1)
                    
            # 解析异常代码
            elif "Exception Codes:" in line:
                match = re.search(r'Exception Codes:\s+(.*)', line)
                if match:
                    self.crash_info['exception_codes'] = match.group(1)
                    
            # 解析触发线程
            elif "Triggered by Thread:" in line:
                match = re.search(r'Triggered by Thread:\s+(\d+)', line)
                if match:
                    self.crash_info['triggered_thread'] = int(match.group(1))
                    
    def _parse_binary_images(self):
        """解析二进制镜像信息"""
        binary_section_start = False
        
        for line in self.crash_lines:
            if "Binary Images:" in line:
                binary_section_start = True
                continue
                
            if binary_section_start:
                # 匹配二进制镜像行
                match = re.search(r'(0x[0-9a-f]+)\s+-\s+(0x[0-9a-f]+)\s+(\S+)\s+(\S+)\s+<([0-9a-f-]+)>', line)
                if match:
                    image = {
                        'load_address': match.group(1),
                        'end_address': match.group(2),
                        'name': match.group(3),
                        'version': match.group(4),
                        'uuid': match.group(5)
                    }
                    self.binary_images.append(image)
                elif line.strip() == "":
                    # 空行表示二进制镜像部分结束
                    break
                    
    def _parse_thread_backtraces(self):
        """解析线程回溯信息"""
        current_thread = None
        
        for line in self.crash_lines:
            # 匹配线程开始
            thread_match = re.search(r'^Thread (\d+)( Crashed)?:', line)
            if thread_match:
                thread_id = int(thread_match.group(1))
                is_crashed = bool(thread_match.group(2))
                
                current_thread = {
                    'id': thread_id,
                    'is_crashed': is_crashed,
                    'frames': []
                }
                
                self.thread_backtraces.append(current_thread)
                continue
                
            # 匹配堆栈帧
            if current_thread:
                frame_match = re.search(r'^\d+\s+(\S+)\s+(0x[0-9a-f]+)\s+(.+)$', line.strip())
                if frame_match:
                    frame = {
                        'binary_name': frame_match.group(1),
                        'address': frame_match.group(2),
                        'symbol': frame_match.group(3)
                    }
                    current_thread['frames'].append(frame)
                elif line.strip() == "":
                    current_thread = None
                    
    def symbolize(self, progress_signal=None):
        """
        符号化堆栈信息
        
        Args:
            progress_signal: 用于发送进度信息的信号
            
        Returns:
            str: 符号化后的Crash内容
        """
        if not self.crash_lines:
            raise ValueError("没有Crash内容可供符号化")
            
        if progress_signal:
            progress_signal.emit("\n" + "="*50)
            progress_signal.emit("开始符号化过程")
            progress_signal.emit("="*50)
        
        # 获取应用的加载地址和结束地址
        app_load_address = None
        app_end_address = None
        app_image = None
        
        if progress_signal:
            progress_signal.emit("\n[1] 查找应用二进制镜像信息...")
            
        for image in self.binary_images:
            if self.binary_name in image['name']:
                app_load_address = image['load_address']
                app_end_address = image['end_address']
                app_image = image
                if progress_signal:
                    progress_signal.emit("✓ 找到应用镜像:")
                    progress_signal.emit(f"  - 名称: {image['name']}")
                    progress_signal.emit(f"  - UUID: {image['uuid']}")
                    progress_signal.emit(f"  - 版本: {image['version']}")
                    progress_signal.emit(f"  - 加载地址: {app_load_address}")
                    progress_signal.emit(f"  - 结束地址: {app_end_address}")
                break
                
        if not app_load_address:
            raise ValueError(f"在Crash日志中找不到应用 {self.binary_name} 的加载地址")
            
        if progress_signal:
            progress_signal.emit("\n[2] 检查dSYM文件...")
            progress_signal.emit(f"  - 路径: {self.dsym_path}")
            progress_signal.emit(f"  - UUID: {self.binary_uuid}")
        
        # 获取可用的架构
        if progress_signal:
            progress_signal.emit("\n[3] 获取二进制文件支持的架构...")
            
        try:
            result = subprocess.run(
                ["lipo", "-info", self.binary_path],
                capture_output=True,
                text=True,
                check=True
            )
            architectures = []
            if "Non-fat file" in result.stdout:
                arch = result.stdout.split("architecture: ")[1].strip()
                architectures = [arch]
            else:
                archs = result.stdout.split("are: ")[1].strip()
                architectures = archs.split(" ")
            if progress_signal:
                progress_signal.emit(f"✓ 支持的架构: {', '.join(architectures)}")
        except subprocess.CalledProcessError as e:
            if progress_signal:
                progress_signal.emit(f"⚠️ 无法获取架构信息，将使用默认架构列表")
            architectures = ['arm64e', 'arm64', 'x86_64']
            
        # 使用 atos 命令进行符号化
        if progress_signal:
            progress_signal.emit("\n[4] 开始符号化堆栈...")
            
        symbolicated_lines = []
        frame_count = 0
        symbolicated_count = 0
        
        for line in self.crash_lines:
            # 检查是否是堆栈帧行
            frame_match = re.search(r'^(\d+)\s+(\S+)\s+(0x[0-9a-f]+)\s+(.+)$', line.strip())
            if frame_match:
                frame_count += 1
                frame_index = frame_match.group(1)
                binary_name = frame_match.group(2)
                address = frame_match.group(3)
                original_symbol = frame_match.group(4)
                
                # 只对应用自身的符号进行符号化
                if binary_name == self.binary_name or self.binary_name in binary_name:
                    if progress_signal:
                        progress_signal.emit(f"\n符号化第 {frame_index} 帧:")
                        progress_signal.emit(f"  原始行: {line.strip()}")
                    
                    try:
                        symbolicated_symbol = None
                        
                        for arch in architectures:
                            if progress_signal:
                                progress_signal.emit(f"  尝试 {arch} 架构:")
                            
                            # 首先尝试使用 dSYM 文件
                            try:
                                if progress_signal:
                                    progress_signal.emit(f"    使用dSYM文件...")
                                result = subprocess.run(
                                    [
                                        "atos",
                                        "-arch", arch,
                                        "-o", self.dsym_path,
                                        "-l", app_load_address,
                                        address
                                    ],
                                    capture_output=True,
                                    text=True,
                                    check=True
                                )
                                
                                symbol = result.stdout.strip()
                                if symbol and symbol != "??" and address not in symbol:
                                    symbolicated_symbol = symbol
                                    if progress_signal:
                                        progress_signal.emit(f"    ✓ 成功: {symbol}")
                                    break
                                elif progress_signal:
                                    progress_signal.emit(f"    ⚠️ 未找到符号")
                                    
                            except subprocess.CalledProcessError as e:
                                if progress_signal:
                                    progress_signal.emit(f"    ✗ 失败: {str(e)}")
                                
                            # 如果 dSYM 失败，尝试使用二进制文件
                            if not symbolicated_symbol:
                                try:
                                    if progress_signal:
                                        progress_signal.emit(f"    使用二进制文件...")
                                    result = subprocess.run(
                                        [
                                            "atos",
                                            "-arch", arch,
                                            "-o", self.binary_path,
                                            "-l", app_load_address,
                                            address
                                        ],
                                        capture_output=True,
                                        text=True,
                                        check=True
                                    )
                                    
                                    symbol = result.stdout.strip()
                                    if symbol and symbol != "??" and address not in symbol:
                                        symbolicated_symbol = symbol
                                        if progress_signal:
                                            progress_signal.emit(f"    ✓ 成功: {symbol}")
                                        break
                                    elif progress_signal:
                                        progress_signal.emit(f"    ⚠️ 未找到符号")
                                        
                                except subprocess.CalledProcessError as e:
                                    if progress_signal:
                                        progress_signal.emit(f"    ✗ 失败: {str(e)}")
                                    
                        # 如果成功获取到符号，替换原始行
                        if symbolicated_symbol:
                            symbolicated_count += 1
                            line = f"{frame_index} {binary_name} {address} {symbolicated_symbol}"
                            if progress_signal:
                                progress_signal.emit(f"  ✓ 符号化结果: {line}")
                        elif progress_signal:
                            progress_signal.emit(f"  ✗ 符号化失败，保留原始行")
                            
                    except Exception as e:
                        if progress_signal:
                            progress_signal.emit(f"  ✗ 符号化过程出错: {str(e)}")
                        
            symbolicated_lines.append(line)
            
        if progress_signal:
            progress_signal.emit("\n" + "="*50)
            progress_signal.emit(f"符号化完成")
            progress_signal.emit(f"总帧数: {frame_count}")
            progress_signal.emit(f"成功符号化: {symbolicated_count}")
            progress_signal.emit(f"失败: {frame_count - symbolicated_count}")
            progress_signal.emit("="*50 + "\n")
        
        # 生成符号化后的内容
        symbolicated_content = "\n".join(symbolicated_lines)
        
        # 添加符号化信息
        symbolicated_content += "\n\n符号化信息:\n"
        symbolicated_content += f"应用名称: {self.binary_name}\n"
        symbolicated_content += f"UUID: {self.binary_uuid}\n"
        symbolicated_content += f"dSYM路径: {self.dsym_path}\n"
        symbolicated_content += f"二进制文件路径: {self.binary_path}\n"
        symbolicated_content += f"加载地址: {app_load_address}\n"
        symbolicated_content += f"结束地址: {app_end_address}\n"
        symbolicated_content += f"支持的架构: {', '.join(architectures)}\n"
        symbolicated_content += f"总帧数: {frame_count}\n"
        symbolicated_content += f"成功符号化: {symbolicated_count}\n"
        symbolicated_content += f"失败: {frame_count - symbolicated_count}\n"
        
        return symbolicated_content
            
    def get_crash_info(self):
        """
        获取Crash基本信息
        
        Returns:
            dict: Crash基本信息
        """
        return self.crash_info 