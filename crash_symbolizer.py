#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import tempfile
import shutil
import plistlib
from pathlib import Path
import json
from datetime import datetime


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
        self.app_name = None
        self.app_path = None
        self.crash_threads = []
        self.crash_reason = None
        self.device_info = {}
        self.process_info = {}
        self.symbol_cache = {}  # 添加符号缓存
        
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
            
        # 在加载完成后验证 UUID
        self.verify_dsym_uuid()
        
        # 预热符号缓存
        print("正在预热符号缓存...")
        self._warm_up_symbol_cache()
        
    def verify_dsym_uuid(self):
        """验证 dSYM 文件的 UUID 是否与应用匹配"""
        if not self.binary_path or not self.dsym_path:
            raise ValueError("二进制文件或dSYM文件路径未设置")
        
        # 获取二进制文件的 UUID
        binary_uuid_cmd = ["dwarfdump", "--uuid", self.binary_path]
        dsym_uuid_cmd = ["dwarfdump", "--uuid", self.dsym_path]
        
        try:
            binary_result = subprocess.run(binary_uuid_cmd, capture_output=True, text=True, check=True)
            dsym_result = subprocess.run(dsym_uuid_cmd, capture_output=True, text=True, check=True)
            
            binary_uuid = re.search(r'UUID: ([0-9A-F-]+)', binary_result.stdout)
            dsym_uuid = re.search(r'UUID: ([0-9A-F-]+)', dsym_result.stdout)
            
            if not binary_uuid or not dsym_uuid:
                raise ValueError("无法获取UUID")
            
            binary_uuid = binary_uuid.group(1).lower()
            dsym_uuid = dsym_uuid.group(1).lower()
            
            if binary_uuid != dsym_uuid:
                raise ValueError(f"UUID不匹配: 二进制文件({binary_uuid}) != dSYM文件({dsym_uuid})")
            
            self.binary_uuid = binary_uuid
            return True
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"验证UUID失败: {str(e)}")

    def _warm_up_symbol_cache(self):
        """预热符号缓存，提前加载常用符号"""
        if not self.binary_path or not self.dsym_path:
            return
        
        try:
            # 使用 nm 命令获取所有符号
            nm_cmd = ["nm", "-arch", "arm64", self.binary_path]
            result = subprocess.run(nm_cmd, capture_output=True, text=True)
            
            # 解析并缓存关键符号
            for line in result.stdout.splitlines():
                if " t " in line or " T " in line:  # 只缓存文本段的符号
                    parts = line.split(" ")
                    if len(parts) >= 3:
                        address = parts[0]
                        symbol = parts[-1]
                        cache_key = f"{address}_arm64_0x0"
                        self.symbol_cache[cache_key] = symbol
                        
        except Exception as e:
            print(f"预热符号缓存时出错: {str(e)}")

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
        
        # 首先收集所有需要符号化的地址
        addresses_to_symbolicate = {}
        for line in self.crash_lines:
            frame_match = re.search(r'^(\d+)\s+(\S+)\s+(0x[0-9a-f]+)\s+(.+)$', line.strip())
            if frame_match and (frame_match.group(2) == self.binary_name or self.binary_name in frame_match.group(2)):
                address = frame_match.group(3)
                if address not in self.symbol_cache:
                    addresses_to_symbolicate[address] = None
                    
        # 批量符号化地址
        if addresses_to_symbolicate:
            if progress_signal:
                progress_signal.emit(f"\n需要符号化 {len(addresses_to_symbolicate)} 个地址...")
                
            for arch in architectures:
                remaining_addresses = [addr for addr, symbol in addresses_to_symbolicate.items() if symbol is None]
                if not remaining_addresses:
                    break
                    
                if progress_signal:
                    progress_signal.emit(f"\n尝试使用 {arch} 架构:")
                    
                # 使用dSYM文件批量符号化
                try:
                    if progress_signal:
                        progress_signal.emit("  使用dSYM文件批量符号化...")
                        
                    cmd = ["atos", "-arch", arch, "-o", self.dsym_path, "-l", app_load_address] + remaining_addresses
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        symbols = result.stdout.strip().split("\n")
                        for addr, symbol in zip(remaining_addresses, symbols):
                            if symbol and symbol != "??" and addr not in symbol:
                                addresses_to_symbolicate[addr] = symbol
                                self.symbol_cache[addr] = symbol
                                
                except Exception as e:
                    if progress_signal:
                        progress_signal.emit(f"  ✗ dSYM批量符号化失败: {str(e)}")
                        
                # 对未成功的地址使用二进制文件尝试符号化
                remaining_addresses = [addr for addr, symbol in addresses_to_symbolicate.items() if symbol is None]
                if remaining_addresses:
                    try:
                        if progress_signal:
                            progress_signal.emit("  使用二进制文件批量符号化...")
                            
                        cmd = ["atos", "-arch", arch, "-o", self.binary_path, "-l", app_load_address] + remaining_addresses
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            symbols = result.stdout.strip().split("\n")
                            for addr, symbol in zip(remaining_addresses, symbols):
                                if symbol and symbol != "??" and addr not in symbol:
                                    addresses_to_symbolicate[addr] = symbol
                                    self.symbol_cache[addr] = symbol
                                    
                    except Exception as e:
                        if progress_signal:
                            progress_signal.emit(f"  ✗ 二进制文件批量符号化失败: {str(e)}")
                            
        # 使用符号化结果生成输出
        for line in self.crash_lines:
            frame_match = re.search(r'^(\d+)\s+(\S+)\s+(0x[0-9a-f]+)\s+(.+)$', line.strip())
            if frame_match:
                frame_count += 1
                frame_index = frame_match.group(1)
                binary_name = frame_match.group(2)
                address = frame_match.group(3)
                original_symbol = frame_match.group(4)
                
                if binary_name == self.binary_name or self.binary_name in binary_name:
                    # 使用缓存的符号
                    if address in self.symbol_cache:
                        symbolicated_count += 1
                        line = f"{frame_index} {binary_name} {address} {self.symbol_cache[address]}"
                        if progress_signal:
                            progress_signal.emit(f"✓ 帧 {frame_index} 已符号化")
                            
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

    def load_metrickit_json(self, json_path):
        """加载并解析MetricKit JSON文件"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            return json_data
        except json.JSONDecodeError as e:
            raise Exception(f"JSON格式错误: {str(e)}")
        except Exception as e:
            raise Exception(f"无法读取JSON文件: {str(e)}")
            
    def parse_metrickit_crash(self, json_data):
        """解析MetricKit JSON中的崩溃信息"""
        try:
            print("\n开始解析MetricKit JSON...")
            
            # 验证JSON数据结构
            if isinstance(json_data, list):
                print("JSON数据是数组格式，使用第一个元素")
                if not json_data:
                    raise Exception("JSON数组为空")
                json_data = json_data[0]
                
            if not isinstance(json_data, dict):
                raise Exception(f"JSON数据格式错误，当前类型: {type(json_data)}")
                
            # 尝试不同的路径查找崩溃诊断数据
            crash_diagnostic = None
            possible_paths = [
                'crashDiagnostics',
                'diagnostics',
                'payload',
                'diagnosticPayload'
            ]
            
            for path in possible_paths:
                data = json_data.get(path)
                if isinstance(data, list) and data:
                    print(f"在路径 '{path}' 找到诊断数据")
                    crash_diagnostic = data[0]
                    break
                elif isinstance(data, dict):
                    print(f"在路径 '{path}' 找到诊断数据")
                    crash_diagnostic = data
                    break
                    
            if not crash_diagnostic:
                raise Exception("未找到有效的崩溃诊断数据")
                
            # 解析调用栈
            call_stack_tree = None
            call_stack_paths = [
                'callStackTree',
                'callStacks',
                'stackFrames',
                'frames'
            ]
            
            for path in call_stack_paths:
                data = crash_diagnostic.get(path)
                if data:
                    print(f"在路径 '{path}' 找到调用栈数据")
                    call_stack_tree = data
                    break
                    
            if not call_stack_tree:
                raise Exception("未找到有效的调用栈数据")
                
            # 获取元数据
            meta_data = {}
            meta_data_paths = [
                'diagnosticMetaData',
                'metaData',
                'metadata'
            ]
            
            for path in meta_data_paths:
                data = crash_diagnostic.get(path)
                if isinstance(data, dict):
                    print(f"在路径 '{path}' 找到元数据")
                    meta_data.update(data)
                    
            # 解析设备信息
            self.device_info = {
                'model': meta_data.get('deviceType') or meta_data.get('model') or 'Unknown',
                'os_version': meta_data.get('osVersion') or meta_data.get('systemVersion') or 'Unknown',
                'timestamp': meta_data.get('timestamp') or datetime.now().isoformat()
            }
            
            # 解析应用信息
            self.process_info = {
                'name': meta_data.get('bundleIdentifier') or meta_data.get('appBundleId') or 'Unknown',
                'version': meta_data.get('appVersion') or meta_data.get('version') or 'Unknown',
                'build': meta_data.get('appBuildVersion') or meta_data.get('build') or 'Unknown'
            }
            
            # 解析崩溃原因
            exception_type = meta_data.get('exceptionType') or meta_data.get('type') or 'Unknown'
            exception_code = meta_data.get('exceptionCode') or meta_data.get('code') or 'Unknown'
            signal = meta_data.get('signal') or meta_data.get('signalType') or 'Unknown'
            
            self.crash_reason = f"Exception Type: {exception_type}, Exception Code: {exception_code}, Signal: {signal}"
            
            # 解析二进制镜像和线程信息
            self.binary_images = []
            self.crash_threads = []
            processed_binaries = set()
            
            def process_frames(frames, thread_frames, depth=0):
                if not isinstance(frames, list):
                    if isinstance(frames, dict):
                        frames = [frames]
                    else:
                        return
                        
                for frame in frames:
                    if not isinstance(frame, dict):
                        continue
                        
                    # 提取二进制信息
                    binary_info = {}
                    for key in ['binaryName', 'libraryName', 'imageName']:
                        if key in frame:
                            binary_info['name'] = frame[key]
                            break
                            
                    for key in ['binaryUUID', 'uuid', 'imageUUID']:
                        if key in frame:
                            binary_info['uuid'] = frame[key]
                            break
                            
                    if binary_info.get('name') and binary_info.get('uuid'):
                        binary_key = (binary_info['name'], binary_info['uuid'])
                        if binary_key not in processed_binaries:
                            processed_binaries.add(binary_key)
                            
                            # 计算基地址
                            address = int(frame.get('address', '0'), 16) if isinstance(frame.get('address'), str) else frame.get('address', 0)
                            offset = int(frame.get('offsetIntoBinaryTextSegment', '0'), 16) if isinstance(frame.get('offsetIntoBinaryTextSegment'), str) else frame.get('offsetIntoBinaryTextSegment', 0)
                            
                            base_address = address - offset if offset else address
                            
                            self.binary_images.append({
                                'name': binary_info['name'],
                                'uuid': binary_info['uuid'],
                                'arch': meta_data.get('platformArchitecture', 'arm64'),
                                'base': base_address,
                                'size': frame.get('size', 0)
                            })
                            
                    # 创建调用帧
                    frame_info = {
                        'binary': binary_info.get('name', 'Unknown'),
                        'address': frame.get('address', '0x0'),
                        'offset': frame.get('offsetIntoBinaryTextSegment', '0x0'),
                        'symbol': frame.get('symbolName', '') or frame.get('symbol', ''),
                        'depth': depth
                    }
                    
                    # 确保地址格式正确
                    if isinstance(frame_info['address'], int):
                        frame_info['address'] = hex(frame_info['address'])
                    if isinstance(frame_info['offset'], int):
                        frame_info['offset'] = hex(frame_info['offset'])
                        
                    thread_frames.append(frame_info)
                    
                    # 处理子帧
                    for subframes_key in ['subFrames', 'frames', 'children']:
                        if subframes_key in frame:
                            process_frames(frame[subframes_key], thread_frames, depth + 1)
                            
            # 处理调用栈
            if isinstance(call_stack_tree, dict):
                call_stacks = call_stack_tree.get('callStacks', [call_stack_tree])
            else:
                call_stacks = call_stack_tree if isinstance(call_stack_tree, list) else [call_stack_tree]
                
            for stack_index, call_stack in enumerate(call_stacks):
                thread_frames = []
                
                if isinstance(call_stack, dict):
                    root_frames = call_stack.get('callStackRootFrames') or call_stack.get('frames') or []
                    is_crashed = call_stack.get('threadAttributed', False) or call_stack.get('crashed', False)
                else:
                    root_frames = call_stack if isinstance(call_stack, list) else []
                    is_crashed = stack_index == 0  # 假设第一个线程是崩溃线程
                    
                process_frames(root_frames, thread_frames)
                
                if thread_frames:
                    self.crash_threads.append({
                        'number': stack_index,
                        'crashed': is_crashed,
                        'frames': thread_frames
                    })
                    
            if not self.crash_threads:
                raise Exception("未能解析出有效的调用帧")
                
            print(f"\n解析完成:")
            print(f"- 设备: {self.device_info['model']} ({self.device_info['os_version']})")
            print(f"- 应用: {self.process_info['name']} ({self.process_info['version']} [{self.process_info['build']}])")
            print(f"- 二进制镜像数: {len(self.binary_images)}")
            print(f"- 线程数: {len(self.crash_threads)}")
            
        except Exception as e:
            raise Exception(f"解析MetricKit JSON失败: {str(e)}")
            
    def symbolize_metrickit(self, progress_callback=None):
        """符号化MetricKit崩溃信息"""
        try:
            print("\n开始符号化MetricKit崩溃信息...")
            
            output_lines = []
            output_lines.append("崩溃报告\n")
            output_lines.append(f"设备: {self.device_info['model']} ({self.device_info['os_version']})")
            output_lines.append(f"时间: {self.device_info['timestamp']}")
            output_lines.append(f"进程: {self.process_info['name']} ({self.process_info['version']} [{self.process_info['build']}])")
            output_lines.append(f"原因: {self.crash_reason}\n")
            
            # 验证必要的文件和路径
            if not self.binary_path or not os.path.exists(self.binary_path):
                raise Exception(f"找不到二进制文件: {self.binary_path}")
            if not self.dsym_path or not os.path.exists(self.dsym_path):
                raise Exception(f"找不到dSYM文件: {self.dsym_path}")
            
            print(f"二进制文件: {self.binary_path}")
            print(f"dSYM文件: {self.dsym_path}")
            
            # 获取支持的架构
            try:
                lipo_result = subprocess.run(
                    ["lipo", "-info", self.binary_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                architectures = []
                if "Non-fat file" in lipo_result.stdout:
                    arch = lipo_result.stdout.split("architecture: ")[1].strip()
                    architectures = [arch]
                else:
                    archs = lipo_result.stdout.split("are: ")[1].strip()
                    architectures = archs.split(" ")
                print(f"支持的架构: {', '.join(architectures)}")
            except Exception as e:
                print(f"警告: 无法获取架构信息 - {str(e)}")
                architectures = ['arm64']
            
            # 符号化每个线程
            for thread in self.crash_threads:
                thread_header = f"\n{'崩溃' if thread['crashed'] else ''}线程 {thread['number']} 回溯:"
                output_lines.append(thread_header)
                print(thread_header)
                
                for i, frame in enumerate(thread['frames']):
                    # 查找对应的二进制镜像
                    binary_image = next(
                        (img for img in self.binary_images if img['name'] == frame['binary']),
                        None
                    )
                    
                    if not binary_image:
                        print(f"警告: 找不到二进制镜像 {frame['binary']}")
                        output_lines.append(f"{i:3d} {frame['binary']} {frame['address']} {frame['symbol'] or '<未知符号>'}")
                        continue
                        
                    try:
                        # 确保地址格式正确
                        if isinstance(frame['address'], str):
                            if not frame['address'].startswith('0x'):
                                frame['address'] = f"0x{frame['address']}"
                        else:
                            frame['address'] = hex(frame['address'])
                            
                        # 计算相对地址
                        frame_address = int(frame['address'], 16)
                        base_address = binary_image['base']
                        relative_address = frame_address - base_address
                        
                        if progress_callback:
                            progress_callback.emit(f"正在符号化地址: {frame['address']}...")
                            
                        print(f"符号化: {frame['binary']} @ {frame['address']} (base: {hex(base_address)})")
                        
                        # 使用缓存
                        cache_key = f"{hex(relative_address)}_{binary_image['arch']}_{hex(base_address)}"
                        if cache_key in self.symbol_cache:
                            symbol = self.symbol_cache[cache_key]
                            print(f"使用缓存的符号: {symbol}")
                        else:
                            # 尝试使用不同的符号化方法
                            symbol = None
                            
                            # 1. 首先尝试使用 atos 和 dSYM
                            try:
                                atos_cmd = [
                                    "atos",
                                    "-arch", binary_image['arch'],
                                    "-o", self.binary_path,
                                    "-l", hex(base_address)
                                ]
                                
                                if self.dsym_path:
                                    atos_cmd.extend(["-d", self.dsym_path])
                                    
                                atos_cmd.append(frame['address'])
                                
                                atos_result = subprocess.run(
                                    atos_cmd,
                                    capture_output=True,
                                    text=True,
                                    check=True
                                )
                                
                                symbol = atos_result.stdout.strip()
                                if symbol and symbol != "??" and frame['address'] not in symbol:
                                    print(f"atos 符号化成功: {symbol}")
                                else:
                                    symbol = None
                                    
                            except Exception as e:
                                print(f"atos 符号化失败: {str(e)}")
                                
                            # 2. 如果 atos 失败，尝试使用 lldb
                            if not symbol:
                                try:
                                    lldb_cmd = [
                                        "lldb",
                                        "--batch",
                                        "-o", f"image lookup --address {frame['address']}"
                                    ]
                                    
                                    lldb_result = subprocess.run(
                                        lldb_cmd,
                                        capture_output=True,
                                        text=True
                                    )
                                    
                                    if "Summary: " in lldb_result.stdout:
                                        symbol = re.search(r'Summary: (.*)', lldb_result.stdout).group(1)
                                        print(f"lldb 符号化成功: {symbol}")
                                        
                                except Exception as e:
                                    print(f"lldb 符号化失败: {str(e)}")
                                    
                            # 3. 如果都失败了，使用原始符号
                            if not symbol or symbol == "??" or frame['address'] in symbol:
                                symbol = frame['symbol'] or '<未知符号>'
                                print(f"使用原始符号: {symbol}")
                                
                            # 缓存结果
                            self.symbol_cache[cache_key] = symbol
                            
                        output_lines.append(f"{i:3d} {frame['binary']} {frame['address']} {symbol}")
                        
                    except Exception as e:
                        print(f"符号化帧 {i} 失败: {str(e)}")
                        output_lines.append(f"{i:3d} {frame['binary']} {frame['address']} {frame['symbol'] or '<符号化失败>'}")
                        
            return "\n".join(output_lines)
            
        except Exception as e:
            raise Exception(f"符号化MetricKit崩溃信息失败: {str(e)}")
            
    def _symbolicate_address(self, address, arch, load_address):
        """改进的地址符号化方法"""
        if not address:
            return "<无效地址>"
        
        # 检查缓存
        cache_key = f"{address}_{arch}_{load_address}"
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]
        
        try:
            # 计算实际地址
            slide = int(address, 16) - int(load_address, 16)
            actual_address = hex(slide)
            
            # 使用 atos 命令进行符号化
            atos_cmd = [
                "atos",
                "-arch", arch if arch else "arm64",
                "-o", self.binary_path,
                "-l", load_address,
                address
            ]
            
            if self.dsym_path:
                atos_cmd.extend(["-d", self.dsym_path])
            
            result = subprocess.run(
                atos_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            symbol = result.stdout.strip()
            
            # 如果返回的是十六进制地址，说明符号化失败
            if re.match(r'^0x[0-9a-f]+$', symbol):
                # 尝试使用 lldb 进行符号化
                lldb_cmd = [
                    "lldb",
                    "--batch",
                    "-o", f"image lookup --address {address}"
                ]
                
                lldb_result = subprocess.run(
                    lldb_cmd,
                    capture_output=True,
                    text=True
                )
                
                # 解析 lldb 输出
                if "Summary: " in lldb_result.stdout:
                    symbol = re.search(r'Summary: (.*)', lldb_result.stdout).group(1)
                    
            # 缓存结果
            self.symbol_cache[cache_key] = symbol
            return symbol
            
        except subprocess.CalledProcessError as e:
            return f"<符号化失败: {str(e)}>"
        except Exception as e:
            return f"<错误: {str(e)}>" 