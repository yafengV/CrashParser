#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from crash_symbolizer import CrashSymbolizer

class ProgressCallback:
    def emit(self, message):
        print(message)
        sys.stdout.flush()

def main():
    try:
        # 初始化符号化器
        symbolizer = CrashSymbolizer()
        progress_callback = ProgressCallback()

        # 检查文件是否存在
        archive_path = "Stellar.xcarchive"
        json_path = "crash.json"

        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"找不到Archive文件: {archive_path}")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"找不到JSON文件: {json_path}")

        # 加载Archive文件
        print("\n[1] 加载Archive文件...")
        symbolizer.load_archive(archive_path)
        print(f"✓ Archive加载成功")
        print(f"  - 应用名称: {symbolizer.binary_name}")
        print(f"  - dSYM路径: {symbolizer.dsym_path}")
        print(f"  - UUID: {symbolizer.binary_uuid}")

        # 加载并解析MetricKit JSON
        print("\n[2] 加载MetricKit JSON文件...")
        json_size = os.path.getsize(json_path)
        print(f"  - 文件大小: {json_size} 字节")
        
        json_data = symbolizer.load_metrickit_json(json_path)
        print("✓ JSON加载成功")

        # 解析崩溃信息
        print("\n[3] 解析崩溃信息...")
        symbolizer.parse_metrickit_crash(json_data)
        print("✓ 解析完成")
        print(f"  - 设备型号: {symbolizer.device_info.get('model', 'Unknown')}")
        print(f"  - 系统版本: {symbolizer.device_info.get('os_version', 'Unknown')}")
        print(f"  - 应用名称: {symbolizer.process_info.get('name', 'Unknown')}")
        print(f"  - 应用版本: {symbolizer.process_info.get('version', 'Unknown')}")
        print(f"  - 崩溃原因: {symbolizer.crash_reason}")
        print(f"  - 二进制镜像数: {len(symbolizer.binary_images)}")
        print(f"  - 线程数: {len(symbolizer.crash_threads)}")

        # 符号化崩溃信息
        print("\n[4] 开始符号化...")
        symbolicated_content = symbolizer.symbolize_metrickit(progress_callback)

        # 保存结果
        output_file = "symbolicated_crash.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(symbolicated_content)

        print(f"\n✓ 符号化完成，结果已保存到: {output_file}")
        
        # 显示结果预览
        print("\n符号化结果预览:")
        print("="*50)
        print(symbolicated_content)
        print("="*50)

    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 