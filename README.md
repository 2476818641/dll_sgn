# DLL Proxy + Process Injection Framework

Windows 白加黑 DLL 代理框架，集成 Early Bird APC 注入 + PPID 欺骗。配合 [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye) 快速获取目标 DLL 导出模板，一键生成可编译的注入工程。

## 功能特性

- **OS-Level Export Forwarding** — 使用 `.def` 文件系统级转发，无需 ASM trampoline
- **Early Bird APC Injection** — 在 EDR hook 初始化前执行 payload (T1055.004)
- **PPID Spoofing** — 伪造父进程为 explorer.exe，打断进程树溯源 (T1134.004)
- **异步 DllMain** — 后台线程执行注入，避免 Loader Lock 死锁
- **环境检测** — 自动识别分析工具（x64dbg/Wireshark/IDA 等），发现则静默退出
- **内存权限翻转** — 执行后 RWX → RX，降低内存扫描器检出率

## 快速开始

### 前置条件

- Windows 10/11 x64
- Visual Studio 2022 (v143 工具集, C++ 桌面开发)
- Python 3.7+
- **推荐**: [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye) 用于快速提取目标 DLL 导出表

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用 ZeroEye 提取目标 DLL 导出函数模板                      │
│    ZeroEye.exe -d target.dll                                │
│    → 生成 target_exports.cpp (或 target_pragma.cpp)          │
│                                                             │
│ 2. 使用 generate.py 生成编译套件                              │
│    python generate.py -u target_exports.cpp -n target       │
│    → 生成 exports.def + dllmain.cpp                         │
│                                                             │
│ 3. 在 dllmain.cpp 中填入 SGN 编码后的 shellcode               │
│    unsigned char payload[] = "\xfc\x48\x83...";             │
│                                                             │
│ 4. Visual Studio 编译 (Release x64)                         │
│    → 输出 x64/Release/dll_hook1.dll                         │
│                                                             │
│ 5. 部署                                                     │
│    dll_hook1.dll → 重命名为 target.dll (黑文件)              │
│    原始 target.dll → 重命名为 target_orig.dll (白文件)        │
│    两个文件放在目标程序同目录                                  │
└─────────────────────────────────────────────────────────────┘
```

### 命令行用法

```bash
# 使用 ZeroEye 生成的 _exports.cpp 模板
python generate.py -u libcurl_exports.cpp -n libcurl

# 使用 ZeroEye 生成的 _pragma.cpp (C++ 修饰名 DLL)
python generate.py -u target_pragma.cpp -n target

# 使用 dumpbin 输出
dumpbin /exports target.dll > exports.txt
python generate.py -u exports.txt -n target

# 交互模式
python generate.py
```

### 支持的输入格式

| 格式 | 来源 | 说明 |
|------|------|------|
| extern C | ZeroEye `-d` 生成的 `_exports.cpp` | 纯 C 导出 DLL (推荐) |
| pragma | ZeroEye `-d` 生成的 `_pragma.cpp` | C++ 修饰名 DLL |
| dumpbin | `dumpbin /exports target.dll` | Visual Studio 自带工具 |
| 简单列表 | 每行一个函数名 | 手动编写 |

脚本会自动检测输入格式，无需手动指定。

## 推荐搭配: ZeroEye 5.0

[ZeroEye](https://github.com/ImCoriander/ZeroEye) 是一款自动化白加黑扫描工具，可以：

- **扫描目录** 自动发现可劫持的 DLL (`-p` 参数)
- **生成代理模板** 一键提取目标 DLL 的所有导出函数 (`-d` 参数)
- **支持 C++ DLL** 自动处理 MSVC 修饰名，生成 pragma 转发模板
- **支持 .NET** 自动生成 AppDomainManager 注入 config

典型用法:
```bash
# 扫描 C 盘寻找可劫持目标
ZeroEye.exe -p c:\ -s -x 64

# 对目标 DLL 生成代理模板
ZeroEye.exe -d libcurl.dll
# → 生成 libcurl_exports.cpp, libcurl_pragma.cpp, libcurl_class.cpp

# 将模板喂给本项目
python generate.py -u libcurl_exports.cpp -n libcurl
```

## 项目结构

```
dll_sgn/
├── generate.py          # 代理 DLL 生成器 (多格式输入)
├── dllmain.cpp          # 注入 payload 实现 (生成产物)
├── exports.def          # 导出转发定义 (生成产物)
├── dll_hook1.sln        # Visual Studio 解决方案
├── dll_hook1.vcxproj    # 工程配置 (Release x64, /MT)
├── framework.h          # Windows 框架头
└── pch.h                # 预编译头
```

## 编译配置

- **Configuration**: Release
- **Platform**: x64
- **Runtime Library**: /MT (静态链接，无 vcruntime 依赖)
- **Character Set**: MultiByte
- **Module Definition**: exports.def

## 注意事项

- Payload 必须经过编码 (推荐 SGN)，否则静态特征明显
- `conhost.exe` 作为注入目标进程，可在 `dllmain.cpp` 中修改
- 环境检测的进程黑名单可根据实际场景调整
- 仅用于授权渗透测试和 CTF 竞赛

## 相关技术

- [T1574.001 - DLL Search Order Hijacking](https://attack.mitre.org/techniques/T1574/001/)
- [T1055.004 - Process Injection: APC](https://attack.mitre.org/techniques/T1055/004/)
- [T1134.004 - Parent PID Spoofing](https://attack.mitre.org/techniques/T1134/004/)
