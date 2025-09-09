# BuildID 提取工具

专门用于提取ELF文件（如Android SO文件、Linux动态库）的BuildID，用于crash堆栈解析。

## 工具概述

提供了两个版本的BuildID提取工具：

### 1. Shell版本 (`get_buildid.sh`)
- **特点**: 轻量级、快速、无Python依赖
- **适用**: 简单的BuildID提取任务
- **位置**: `/Users/sundxing/get_buildid.sh`

### 2. Python版本 (`get_buildid.py`)  
- **特点**: 功能全面、错误处理完善、支持多种输出格式
- **适用**: 复杂的批量处理任务
- **位置**: `/Users/sundxing/get_buildid.py`

## 使用方法

### 基本用法

```bash
# Shell版本 - 简单提取
./get_buildid.sh libunity.so
# 输出: 4fd2e1e632c546266bda832117510859911f0d13

# Python版本 - 简单提取  
python3 get_buildid.py libunity.so
# 输出: 4fd2e1e632c546266bda832117510859911f0d13
```

### 详细信息输出

```bash
# Shell版本
./get_buildid.sh -f detailed libunity.so

# Python版本
python3 get_buildid.py -f detailed libunity.so
```

输出示例：
```
文件: /path/to/libunity.so
BuildID: 4fd2e1e632c546266bda832117510859911f0d13
架构: arm64-v8a
类型: shared_library
大小: 30815936 字节
Debug信息: 是
已剥离符号: 否
```

### 批量处理

```bash
# 扫描目录中的所有so文件
./get_buildid.sh /path/to/symbols/

# 递归扫描所有子目录
./get_buildid.sh -r /path/to/project/

# 输出到文件
python3 get_buildid.py -r -o buildids.json -f json /path/to/symbols/
```

### JSON格式输出

```bash
python3 get_buildid.py -f json libunity.so
```

输出示例：
```json
[
  {
    "file": "/path/to/libunity.so",
    "buildid": "4fd2e1e632c546266bda832117510859911f0d13",
    "info": {
      "architecture": "arm64-v8a",
      "file_type": "shared_library",
      "file_size": "30815936",
      "has_debug_info": true,
      "is_stripped": false
    }
  }
]
```

## 命令行选项

### Shell版本选项
```
-r, --recursive    递归扫描目录
-f, --format FMT   输出格式: simple|detailed|json
-o, --output FILE  输出结果到文件
-h, --help         显示帮助信息
```

### Python版本选项
```
-r, --recursive    递归扫描目录  
-f, --format       输出格式: simple|detailed|json
-o, --output       输出结果到文件
-q, --quiet        静默模式，只输出BuildID
-h, --help         显示帮助信息
```

## 工作原理

工具会按优先级尝试多种方法提取BuildID：

### 1. file 命令（推荐）
```bash
file libunity.so | grep -o 'BuildID\[sha1\]=[a-f0-9]*'
```
- **优点**: 最可靠，跨平台兼容性好
- **缺点**: 需要较新版本的file命令

### 2. readelf 命令（Linux）
```bash  
readelf -n libunity.so | grep "Build ID:"
```
- **优点**: 标准ELF工具，精确
- **缺点**: macOS默认不可用

### 3. objdump 命令
```bash
objdump -s -j .note.gnu.build-id libunity.so
```
- **优点**: 广泛可用
- **缺点**: 输出复杂，需要解析

## 支持的文件类型

- `.so` - Linux共享库
- `.so.*` - 版本化的Linux共享库（如libssl.so.1.1）
- `.dylib` - macOS动态库  
- `.dll` - Windows动态库
- 可执行文件（基于ELF魔数检测）

## Crash堆栈解析工作流

### 1. 获取BuildID
```bash
./get_buildid.sh libunity.so
# 输出: 4fd2e1e632c546266bda832117510859911f0d13
```

### 2. 验证BuildID匹配
确保crash日志中的BuildID与debug符号文件匹配：
```
Crash日志: Build ID: 4fd2e1e632c546266bda832117510859911f0d13  
符号文件: BuildID: 4fd2e1e632c546266bda832117510859911f0d13  ✓
```

### 3. 进行符号化解析
```bash
# 使用addr2line
addr2line -e libunity.so -f -C 0x123456

# 使用atos (macOS)
atos -o MyApp.app.dSYM/Contents/Resources/DWARF/MyApp -l 0x100000000 0x123456

# 使用llvm-symbolizer
llvm-symbolizer -obj=libunity.so 0x123456
```

## 实际使用示例

### Android Crash分析
```bash
# 1. 从symbols目录提取所有BuildID
python3 get_buildid.py -r -f json -o buildids.json /path/to/symbols/

# 2. 查找特定BuildID对应的文件
grep "4fd2e1e632c546266bda832117510859911f0d13" buildids.json

# 3. 进行堆栈符号化
addr2line -e arm64-v8a/libunity.so -f -C 0x1a2b3c4
```

### 批量验证
```bash
# 检查整个项目的BuildID
./get_buildid.sh -r -f detailed /path/to/project/ > project_buildids.txt

# 统计不同架构的文件数量
python3 get_buildid.py -r -f json /path/to/symbols/ | \
jq '.[] | .info.architecture' | sort | uniq -c
```

## 常见问题

### Q: 提取不到BuildID？
**A**: 检查以下几点：
1. 文件是否为ELF格式：`file yourfile.so`
2. 文件是否包含BuildID段：`objdump -h yourfile.so | grep build-id`
3. 是否有足够的读取权限

### Q: BuildID格式不一致？
**A**: BuildID通常是40字符的SHA1哈希值。如果格式不同：
- 检查是否为其他哈希类型（MD5、SHA256）
- 某些构建系统可能使用自定义BuildID格式

### Q: macOS上readelf不可用？
**A**: macOS默认不包含readelf，可以：
1. 使用Homebrew安装：`brew install binutils`
2. 使用工具的file命令方法（推荐）

### Q: 处理大量文件时性能慢？
**A**: 
- 使用Python版本，有更好的并发处理
- 先用find筛选文件再处理：
```bash
find /path -name "*.so" | xargs python3 get_buildid.py
```

## 集成到CI/CD

### GitHub Actions示例
```yaml
- name: Extract BuildIDs
  run: |
    python3 get_buildid.py -r -f json -o buildids.json symbols/
    # 上传BuildID信息到构建artifacts
```

### Jenkins Pipeline示例  
```groovy
stage('Extract BuildIDs') {
    steps {
        sh 'python3 get_buildid.py -r symbols/ > buildids.txt'
        archiveArtifacts artifacts: 'buildids.txt'
    }
}
```

## 高级用法

### 与其他工具配合
```bash
# 与nm配合检查符号
./get_buildid.sh libunity.so && nm -D libunity.so | grep "main"

# 与strings配合查找特定字符串  
./get_buildid.sh libunity.so && strings libunity.so | grep "version"

# 与gdb配合调试
gdb -batch -ex "info files" ./libunity.so
```

### 自定义脚本集成
```bash
#!/bin/bash
# crash_analyze.sh
BUILDID=$(./get_buildid.sh "$1")
echo "Processing crash with BuildID: $BUILDID"
addr2line -e "$1" -f -C $2
```

---

**工具位置**:
- Shell版本: `/Users/sundxing/get_buildid.sh`
- Python版本: `/Users/sundxing/get_buildid.py`
- 说明文档: `/Users/sundxing/BuildID_Tools_README.md`
