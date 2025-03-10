# iOS Crash堆栈符号化解析工具

这是一个用于iOS Crash堆栈符号化解析的图形化工具，使用Python3实现。

## 功能特点

- 图形化交互界面
- 支持导入iOS archive文件和Crash文件
- 自动解析Crash堆栈并符号化
- 可视化展示解析后的堆栈信息
- 支持导出解析后的文件

## 使用方法

1. 安装依赖：
```
pip install -r requirements.txt
```

2. 运行程序：
```
python main.py
```

3. 在图形界面中：
   - 选择iOS archive文件（.xcarchive）
   - 选择Crash文件（.crash）
   - 点击"解析"按钮进行符号化解析
   - 查看解析结果
   - 可选择导出解析后的文件

## 系统要求

- Python 3.6+
- macOS系统（由于使用了部分macOS特有的工具）

## 依赖项

详见requirements.txt文件 