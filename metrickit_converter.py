#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import datetime
import plistlib
from pathlib import Path

class MetricKitConverter:
    """MetricKit JSON格式转换器"""
    
    def __init__(self):
        self.app_info = {}
        self.binary_images = []
        
    def load_archive(self, archive_path):
        """
        从.xcarchive文件中加载应用信息
        
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
            
        # 解析Info.plist获取应用信息
        try:
            with open(info_plist_path, 'rb') as fp:
                info_plist = plistlib.load(fp)
                self.app_info = {
                    'name': info_plist.get("CFBundleExecutable", ""),
                    'bundle_id': info_plist.get("CFBundleIdentifier", ""),
                    'version': info_plist.get("CFBundleShortVersionString", ""),
                    'build': info_plist.get("CFBundleVersion", "")
                }
                
        except Exception as e:
            raise Exception(f"解析Info.plist失败: {str(e)}")
            
    def convert_json_to_crash(self, json_path):
        """
        将MetricKit JSON格式转换为标准Crash格式
        
        Args:
            json_path: JSON文件路径
            
        Returns:
            str: 转换后的Crash内容
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                crash_data = json.load(f)
                
            # 验证JSON格式
            if not isinstance(crash_data, dict):
                raise ValueError("无效的JSON格式")
                
            # 获取crash信息
            payload = crash_data.get('payload', {})
            if not payload:
                raise ValueError("找不到crash信息")
                
            # 构建crash报告
            crash_report = []
            
            # 添加头部信息
            crash_report.append(f"Incident Identifier: {crash_data.get('diagnosticMetadata', {}).get('incidentId', 'Unknown')}")
            crash_report.append(f"CrashReporter Key:   {crash_data.get('metaData', {}).get('deviceId', 'Unknown')}")
            crash_report.append(f"Hardware Model:      {crash_data.get('metaData', {}).get('deviceType', 'Unknown')}")
            
            # 处理时间
            timestamp = crash_data.get('timeStamp', '')
            if timestamp:
                try:
                    # 将ISO格式时间转换为所需格式
                    dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.000 %z")
                    crash_report.append(f"Date/Time:           {formatted_time}")
                except:
                    crash_report.append(f"Date/Time:           {timestamp}")
                    
            # 添加应用信息
            crash_report.append(f"Process:             {self.app_info['name']} [{payload.get('processId', 'Unknown')}]")
            crash_report.append(f"Version:             {self.app_info['version']} ({self.app_info['build']})")
            crash_report.append(f"Bundle Identifier:   {self.app_info['bundle_id']}")
            crash_report.append(f"OS Version:          {crash_data.get('metaData', {}).get('osVersion', 'Unknown')}")
            
            # 添加异常信息
            exception = payload.get('exception', {})
            crash_report.append(f"Exception Type:      {exception.get('type', 'Unknown')}")
            crash_report.append(f"Exception Codes:     {exception.get('code', 'Unknown')}")
            crash_report.append(f"Exception Note:      {exception.get('signal', '')}")
            
            # 添加触发线程信息
            crash_report.append(f"Triggered by Thread: {payload.get('threadId', 0)}")
            
            # 添加线程回溯
            crash_report.append("\nThread 0 Crashed:")
            callstack = payload.get('callStack', [])
            for i, frame in enumerate(callstack):
                frame_str = f"{i: >3}  {frame.get('binaryName', 'Unknown')}  "
                frame_str += f"{frame.get('address', '0x0')}  "
                frame_str += f"+{frame.get('offsetIntoBinaryTextSegment', 0)}"
                crash_report.append(frame_str)
                
            # 添加二进制镜像信息
            crash_report.append("\nBinary Images:")
            binary_images = payload.get('binaryImages', [])
            for image in binary_images:
                image_str = f"{image.get('baseAddress', '0x0')} - "
                image_str += f"{image.get('endAddress', '0x0')}  "
                image_str += f"{image.get('name', 'Unknown')}  "
                image_str += f"{image.get('version', 'Unknown')}  "
                image_str += f"<{image.get('uuid', 'Unknown')}>"
                crash_report.append(image_str)
                
            return "\n".join(crash_report)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {str(e)}")
        except Exception as e:
            raise Exception(f"转换失败: {str(e)}")
            
    def save_crash_file(self, crash_content, output_path):
        """
        保存转换后的crash文件
        
        Args:
            crash_content: 转换后的crash内容
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(crash_content)
        except Exception as e:
            raise Exception(f"保存文件失败: {str(e)}") 