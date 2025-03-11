# iOS崩溃日志符号化工具

## 简介

这是一个用于解析和符号化iOS崩溃日志的桌面工具，支持传统的crash文件和iOS 13之后引入的MetricKit JSON格式崩溃报告。通过该工具，开发者可以快速将崩溃日志中的内存地址转换为有意义的函数名、文件名和行号，从而更高效地定位和解决崩溃问题。

![应用截图](screenshot.png)

## 功能特点

- **支持多种崩溃日志格式**
  - 传统的.crash文件
  - MetricKit生成的JSON格式崩溃报告
  - Xcode导出的崩溃日志

- **强大的符号化能力**
  - 自动识别并解析崩溃日志
  - 支持通过dSYM文件进行符号化
  - 支持批量处理多个崩溃日志

- **直观的用户界面**
  - 清晰展示崩溃原因和调用栈
  - 高亮显示关键崩溃信息
  - 支持导出符号化后的结果

- **高级分析功能**
  - 崩溃类型统计
  - 常见崩溃模式识别
  - 崩溃趋势分析

## 安装方法

1. 克隆仓库
   ```bash
   git clone https://github.com/yourusername/ios-crash-symbolication-tool.git
   cd ios-crash-symbolication-tool
   ```

2. 安装依赖
   ```bash
   pip3 install -r requirements.txt
   ```

3. 构建应用
   ```bash
   python3 setup.py py2app
   ```

4. 运行应用
   ```bash
   open dist/iOS崩溃日志符号化工具.app
   ```

## 使用指南

### 基本使用流程

1. **导入崩溃日志**
   - 点击"导入崩溃日志"按钮
   - 选择.crash文件或MetricKit JSON文件
   - 支持拖拽文件到应用窗口

2. **选择dSYM文件**
   - 点击"选择dSYM"按钮
   - 选择与崩溃日志对应的dSYM文件
   - 工具会自动验证UUID匹配

3. **符号化处理**
   - 点击"开始符号化"按钮
   - 等待处理完成
   - 查看符号化后的结果

4. **导出结果**
   - 点击"导出"按钮
   - 选择导出格式（文本、HTML或PDF）
   - 保存到指定位置

### 高级功能

- **批量处理**：支持同时导入多个崩溃日志文件进行批量符号化
- **自动查找dSYM**：可配置dSYM存储路径，工具会自动查找匹配的dSYM文件
- **自定义过滤**：可设置关键字过滤，快速定位特定模块的崩溃
- **历史记录**：保存近期处理过的崩溃日志，方便再次查看

## 技术原理

本工具基于以下技术原理实现崩溃日志的解析和符号化：

### 传统崩溃日志解析

1. **解析崩溃日志结构**
   - 提取头部信息、异常信息、线程回溯和二进制镜像信息
   - 识别崩溃的线程和关键调用栈

2. **地址映射**
   - 计算ASLR偏移（实际偏移 = 崩溃地址 - 二进制加载地址）
   - 通过UUID匹配正确的dSYM文件

3. **符号化过程**
   - 使用`atos`或`dwarfdump`等工具读取dSYM中的DWARF调试信息
   - 将内存地址转换为函数名、文件名和行号

### MetricKit JSON解析

1. **JSON结构解析**
   - 提取metaData、diagnosticMetrics和callStackTree信息
   - 解析崩溃类型和调用栈

2. **调用栈处理**
   - 处理树形结构的调用栈
   - 利用直接提供的偏移量（offsetIntoBinaryTextSegment）进行符号化

3. **数据整合**
   - 将符号化后的信息与原始数据整合
   - 生成可读性强的崩溃报告

更多技术细节，请参考我们的[技术博客](blog.md)。

## 常见问题

### Q: 为什么符号化后仍有部分地址没有转换为函数名？

A: 可能的原因包括：
- dSYM文件与崩溃日志不匹配（UUID不一致）
- 崩溃发生在系统库中，需要系统符号表
- 代码经过了优化，导致调试信息不完整

### Q: 工具支持哪些iOS版本的崩溃日志？

A: 本工具支持iOS 9及以上版本的传统崩溃日志，以及iOS 13及以上版本的MetricKit崩溃报告。

### Q: 如何获取dSYM文件？

A: 您可以通过以下方式获取dSYM文件：
- Xcode归档时自动生成
- 从App Store Connect下载
- 使用`dwarfdump --uuid`命令验证dSYM文件的UUID

## 贡献指南

我们欢迎社区贡献，无论是功能改进、bug修复还是文档完善。请遵循以下步骤：

1. Fork本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启Pull Request

## 许可证

本项目采用MIT许可证 - 详情请参见[LICENSE](LICENSE)文件。

## 联系方式

如有任何问题或建议，请通过以下方式联系我们：

- 提交GitHub Issue

---

感谢使用iOS崩溃日志符号化工具！希望它能帮助您更高效地解决崩溃问题，提升应用质量。 