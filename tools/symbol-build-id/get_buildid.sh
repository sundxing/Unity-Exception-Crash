#!/bin/bash

# 提取ELF文件BuildID的工具
# 支持Android SO文件、Linux动态库等

show_help() {
    echo "用法: $0 [选项] <文件路径或目录>"
    echo ""
    echo "选项:"
    echo "  -r, --recursive    递归扫描目录"
    echo "  -f, --format FMT   输出格式: simple|detailed|json (默认: simple)"
    echo "  -o, --output FILE  输出结果到文件"
    echo "  -h, --help         显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 libunity.so                    # 获取单个文件的BuildID"
    echo "  $0 -f detailed libunity.so        # 详细输出"
    echo "  $0 -r /path/to/symbols/           # 递归扫描目录"
    echo "  $0 -f json -o results.json /path/ # JSON格式输出到文件"
    echo ""
    echo "支持的文件类型: .so, .so.*, .dylib, .dll, 可执行文件"
}

extract_buildid() {
    local file_path="$1"
    local buildid=""
    
    if [[ ! -f "$file_path" ]]; then
        return 1
    fi
    
    # 方法1: 使用file命令 (最可靠)
    if command -v file >/dev/null 2>&1; then
        buildid=$(file "$file_path" 2>/dev/null | grep -o 'BuildID\[sha1\]=[a-f0-9]*' | cut -d= -f2)
        if [[ -n "$buildid" ]]; then
            echo "$buildid"
            return 0
        fi
    fi
    
    # 方法2: 使用readelf (Linux)
    if command -v readelf >/dev/null 2>&1; then
        buildid=$(readelf -n "$file_path" 2>/dev/null | grep "Build ID:" | awk '{print $3}' | tr -d ' ')
        if [[ -n "$buildid" ]]; then
            echo "$buildid"
            return 0
        fi
    fi
    
    # 方法3: 使用objdump
    if command -v objdump >/dev/null 2>&1; then
        local objdump_output=$(objdump -s -j .note.gnu.build-id "$file_path" 2>/dev/null)
        if [[ -n "$objdump_output" ]]; then
            # 提取BuildID的十六进制数据
            buildid=$(echo "$objdump_output" | awk '
                /^ [0-9a-f]+ / {
                    # 跳过前16字节的头信息，提取BuildID部分
                    if (NR >= 3) {
                        for(i=2; i<=5; i++) {
                            if ($i != "") printf "%s", $i
                        }
                    }
                }
            ' | sed 's/[^0-9a-f]//g')
            
            # 如果BuildID太长，截取前40字符 (SHA1长度)
            if [[ ${#buildid} -gt 40 ]]; then
                buildid=${buildid:32:40}  # 跳过前面的头部信息
            fi
            
            if [[ -n "$buildid" && ${#buildid} -eq 40 ]]; then
                echo "$buildid"
                return 0
            fi
        fi
    fi
    
    return 1
}

get_file_info() {
    local file_path="$1"
    local arch=""
    local file_type=""
    
    if command -v file >/dev/null 2>&1; then
        local file_output=$(file "$file_path" 2>/dev/null)
        
        # 提取架构信息
        if [[ "$file_output" == *"ARM aarch64"* ]]; then
            arch="arm64-v8a"
        elif [[ "$file_output" == *"Intel 80386"* ]]; then
            arch="x86"
        elif [[ "$file_output" == *"x86-64"* ]]; then
            arch="x86_64"
        elif [[ "$file_output" == *"ARM"* ]]; then
            arch="armeabi-v7a"
        else
            arch="unknown"
        fi
        
        # 提取文件类型
        if [[ "$file_output" == *"shared object"* ]]; then
            file_type="shared_library"
        elif [[ "$file_output" == *"executable"* ]]; then
            file_type="executable"
        elif [[ "$file_output" == *"relocatable"* ]]; then
            file_type="object_file"
        else
            file_type="unknown"
        fi
    fi
    
    echo "${arch}|${file_type}"
}

is_elf_file() {
    local file_path="$1"
    
    if command -v file >/dev/null 2>&1; then
        file "$file_path" 2>/dev/null | grep -q "ELF"
        return $?
    fi
    
    # 简单的魔数检查
    if [[ -f "$file_path" ]]; then
        local magic=$(hexdump -C "$file_path" 2>/dev/null | head -1 | cut -d' ' -f2-5)
        [[ "$magic" == "7f 45 4c 46" ]]
        return $?
    fi
    
    return 1
}

process_file() {
    local file_path="$1"
    local format="$2"
    
    if ! is_elf_file "$file_path"; then
        return 1
    fi
    
    local buildid=$(extract_buildid "$file_path")
    
    if [[ -z "$buildid" ]]; then
        return 1
    fi
    
    case "$format" in
        "simple")
            echo "$buildid"
            ;;
        "detailed")
            local info=$(get_file_info "$file_path")
            local arch=$(echo "$info" | cut -d'|' -f1)
            local file_type=$(echo "$info" | cut -d'|' -f2)
            local file_size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null || echo "unknown")
            
            echo "文件: $file_path"
            echo "BuildID: $buildid"
            echo "架构: $arch"
            echo "类型: $file_type"
            echo "大小: $file_size 字节"
            echo "----------------------------------------"
            ;;
        "json")
            local info=$(get_file_info "$file_path")
            local arch=$(echo "$info" | cut -d'|' -f1)
            local file_type=$(echo "$info" | cut -d'|' -f2)
            local file_size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null || echo "0")
            
            cat << EOF
{
  "file": "$file_path",
  "buildid": "$buildid",
  "architecture": "$arch",
  "type": "$file_type",
  "size": $file_size
},
EOF
            ;;
    esac
    
    return 0
}

# 解析命令行参数
RECURSIVE=false
FORMAT="simple"
OUTPUT_FILE=""
TARGET=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--recursive)
            RECURSIVE=true
            shift
            ;;
        -f|--format)
            FORMAT="$2"
            if [[ "$FORMAT" != "simple" && "$FORMAT" != "detailed" && "$FORMAT" != "json" ]]; then
                echo "错误: 无效的格式 '$FORMAT'"
                echo "支持的格式: simple, detailed, json"
                exit 1
            fi
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
        *)
            TARGET="$1"
            shift
            ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    echo "错误: 请提供文件路径或目录路径"
    show_help
    exit 1
fi

if [[ ! -e "$TARGET" ]]; then
    echo "错误: 路径不存在 $TARGET"
    exit 1
fi

# 输出重定向
if [[ -n "$OUTPUT_FILE" ]]; then
    exec > "$OUTPUT_FILE"
fi

# JSON格式需要特殊处理
if [[ "$FORMAT" == "json" ]]; then
    echo "["
fi

found_files=0

if [[ -f "$TARGET" ]]; then
    # 处理单个文件
    if process_file "$TARGET" "$FORMAT"; then
        found_files=$((found_files + 1))
    fi
elif [[ -d "$TARGET" ]]; then
    # 处理目录
    if $RECURSIVE; then
        # 递归扫描
        while IFS= read -r -d '' file; do
            if process_file "$file" "$FORMAT"; then
                found_files=$((found_files + 1))
            fi
        done < <(find "$TARGET" -type f \( -name "*.so" -o -name "*.so.*" -o -name "*.dylib" -o -name "*.dll" -o -executable \) -print0 2>/dev/null)
    else
        # 只扫描当前目录
        for file in "$TARGET"/*; do
            if [[ -f "$file" ]] && (is_elf_file "$file" || [[ "$file" == *.so ]] || [[ "$file" == *.so.* ]] || [[ "$file" == *.dylib ]] || [[ "$file" == *.dll ]]); then
                if process_file "$file" "$FORMAT"; then
                    found_files=$((found_files + 1))
                fi
            fi
        done
    fi
fi

# JSON格式收尾
if [[ "$FORMAT" == "json" ]]; then
    echo "]"
fi

if [[ "$found_files" -eq 0 ]]; then
    if [[ -z "$OUTPUT_FILE" ]]; then
        echo "未找到任何包含BuildID的ELF文件" >&2
    fi
    exit 1
fi

if [[ -n "$OUTPUT_FILE" ]]; then
    echo "找到 $found_files 个文件，结果已保存到: $OUTPUT_FILE" >&2
fi
