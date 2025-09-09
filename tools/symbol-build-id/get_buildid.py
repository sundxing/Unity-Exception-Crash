#!/usr/bin/env python3
"""
BuildID提取工具
专门用于提取ELF文件的BuildID，支持Android SO文件、Linux动态库等
"""

import os
import sys
import json
import subprocess
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class BuildIDExtractor:
    """BuildID提取器"""
    
    def __init__(self):
        self.supported_extensions = ['.so', '.dylib', '.dll']
    
    def extract_buildid(self, file_path: str) -> Optional[str]:
        """
        提取文件的BuildID
        返回BuildID字符串，如果失败返回None
        """
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None
        
        # 方法1: 使用file命令 (最可靠)
        buildid = self._extract_with_file_command(file_path)
        if buildid:
            return buildid
        
        # 方法2: 使用readelf
        buildid = self._extract_with_readelf(file_path)
        if buildid:
            return buildid
        
        # 方法3: 使用objdump
        buildid = self._extract_with_objdump(file_path)
        if buildid:
            return buildid
        
        return None
    
    def _extract_with_file_command(self, file_path: str) -> Optional[str]:
        """使用file命令提取BuildID"""
        try:
            result = subprocess.run(['file', file_path], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # 查找BuildID[sha1]=...模式
                match = re.search(r'BuildID\[sha1\]=([a-f0-9]+)', result.stdout)
                if match:
                    return match.group(1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None
    
    def _extract_with_readelf(self, file_path: str) -> Optional[str]:
        """使用readelf提取BuildID"""
        try:
            result = subprocess.run(['readelf', '-n', file_path], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # 查找Build ID:行
                for line in result.stdout.split('\n'):
                    if 'Build ID:' in line:
                        parts = line.split('Build ID:')
                        if len(parts) > 1:
                            buildid = parts[1].strip()
                            # 移除空格
                            buildid = re.sub(r'\s+', '', buildid)
                            if buildid and re.match(r'^[a-f0-9]+$', buildid):
                                return buildid
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None
    
    def _extract_with_objdump(self, file_path: str) -> Optional[str]:
        """使用objdump提取BuildID"""
        try:
            result = subprocess.run(['objdump', '-s', '-j', '.note.gnu.build-id', file_path], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                buildid_data = []
                
                for line in lines:
                    # 跳过标题行
                    if line.startswith(' ') and re.match(r'^ [0-9a-f]+', line):
                        parts = line.split()
                        if len(parts) >= 2:
                            # 提取十六进制数据 (跳过地址)
                            for hex_group in parts[1:5]:  # 最多取4组
                                if re.match(r'^[0-9a-f]+$', hex_group):
                                    buildid_data.append(hex_group)
                
                if buildid_data:
                    # 合并所有十六进制数据
                    combined = ''.join(buildid_data)
                    # BuildID通常在头部信息之后，尝试提取
                    if len(combined) > 32:
                        # 跳过前16字节的ELF note头部信息
                        buildid = combined[32:]
                        # SHA1 BuildID应该是40字符
                        if len(buildid) >= 40:
                            return buildid[:40]
                        elif len(buildid) >= 32:
                            return buildid
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None
    
    def get_file_info(self, file_path: str) -> Dict[str, str]:
        """获取文件的详细信息"""
        info = {
            'architecture': 'unknown',
            'file_type': 'unknown',
            'file_size': '0',
            'has_debug_info': False,
            'is_stripped': True
        }
        
        try:
            result = subprocess.run(['file', file_path], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # 架构检测
                if 'arm aarch64' in output:
                    info['architecture'] = 'arm64-v8a'
                elif 'intel 80386' in output or 'i386' in output:
                    info['architecture'] = 'x86'
                elif 'x86-64' in output or 'x86_64' in output:
                    info['architecture'] = 'x86_64'
                elif 'arm' in output:
                    info['architecture'] = 'armeabi-v7a'
                
                # 文件类型检测
                if 'shared object' in output:
                    info['file_type'] = 'shared_library'
                elif 'executable' in output:
                    info['file_type'] = 'executable'
                elif 'relocatable' in output:
                    info['file_type'] = 'object_file'
                
                # Debug信息检测
                if 'with debug_info' in output:
                    info['has_debug_info'] = True
                if 'not stripped' in output:
                    info['is_stripped'] = False
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 文件大小
        try:
            info['file_size'] = str(os.path.getsize(file_path))
        except OSError:
            pass
        
        return info
    
    def is_elf_file(self, file_path: str) -> bool:
        """检查文件是否为ELF格式"""
        try:
            with open(file_path, 'rb') as f:
                magic = f.read(4)
                return magic == b'\x7fELF'
        except (OSError, IOError):
            return False
    
    def should_process_file(self, file_path: str) -> bool:
        """判断是否应该处理此文件"""
        if not os.path.isfile(file_path):
            return False
        
        file_path_lower = file_path.lower()
        
        # 检查扩展名
        for ext in self.supported_extensions:
            if file_path_lower.endswith(ext) or f'{ext}.' in file_path_lower:
                return True
        
        # 检查是否为ELF文件
        return self.is_elf_file(file_path)

def scan_files(path: str, recursive: bool = False) -> List[str]:
    """扫描文件，返回需要处理的文件列表"""
    extractor = BuildIDExtractor()
    files = []
    
    if os.path.isfile(path):
        if extractor.should_process_file(path):
            files.append(path)
    elif os.path.isdir(path):
        if recursive:
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    if extractor.should_process_file(file_path):
                        files.append(file_path)
        else:
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if extractor.should_process_file(item_path):
                        files.append(item_path)
            except OSError:
                pass
    
    return files

def format_output(results: List[Dict], format_type: str) -> str:
    """格式化输出结果"""
    if not results:
        return ""
    
    if format_type == 'simple':
        return '\n'.join(result['buildid'] for result in results if result['buildid'])
    
    elif format_type == 'detailed':
        output = []
        for result in results:
            if result['buildid']:
                output.append(f"文件: {result['file']}")
                output.append(f"BuildID: {result['buildid']}")
                output.append(f"架构: {result['info']['architecture']}")
                output.append(f"类型: {result['info']['file_type']}")
                output.append(f"大小: {result['info']['file_size']} 字节")
                output.append(f"Debug信息: {'是' if result['info']['has_debug_info'] else '否'}")
                output.append(f"已剥离符号: {'是' if result['info']['is_stripped'] else '否'}")
                output.append("-" * 50)
        return '\n'.join(output)
    
    elif format_type == 'json':
        # 过滤出有BuildID的结果
        valid_results = [r for r in results if r['buildid']]
        return json.dumps(valid_results, indent=2, ensure_ascii=False)
    
    return ""

def main():
    parser = argparse.ArgumentParser(description='提取ELF文件的BuildID')
    parser.add_argument('path', help='文件路径或目录路径')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='递归扫描目录')
    parser.add_argument('-f', '--format', choices=['simple', 'detailed', 'json'],
                       default='simple', help='输出格式')
    parser.add_argument('-o', '--output', help='输出结果到文件')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='静默模式，只输出BuildID')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"错误: 路径不存在 {args.path}", file=sys.stderr)
        sys.exit(1)
    
    # 扫描文件
    files = scan_files(args.path, args.recursive)
    
    if not files:
        if not args.quiet:
            print("未找到任何ELF文件", file=sys.stderr)
        sys.exit(1)
    
    # 处理文件
    extractor = BuildIDExtractor()
    results = []
    
    for file_path in files:
        buildid = extractor.extract_buildid(file_path)
        info = extractor.get_file_info(file_path) if args.format != 'simple' else {}
        
        results.append({
            'file': file_path,
            'buildid': buildid,
            'info': info
        })
    
    # 过滤出有BuildID的结果
    valid_results = [r for r in results if r['buildid']]
    
    if not valid_results:
        if not args.quiet:
            print("未找到任何包含BuildID的文件", file=sys.stderr)
        sys.exit(1)
    
    # 格式化输出
    output = format_output(valid_results, args.format)
    
    # 输出结果
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            if not args.quiet:
                print(f"找到 {len(valid_results)} 个文件，结果已保存到: {args.output}")
        except IOError as e:
            print(f"写入文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output)

if __name__ == "__main__":
    main()
