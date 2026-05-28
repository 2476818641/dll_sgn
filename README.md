# .NET AppDomainManager Config Hijack Framework

.NET 白加黑框架，利用 AppDomainManager 注入实现 CLR 级代码执行。配合 [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye) 快速发现可劫持的 .NET 目标，一键生成武器化套件。

## 功能特性

- **AppDomainManager 注入** — CLR 在 Main() 之前加载 payload，绕过强签名限制
- **AMSI Bypass** — Patch AmsiScanBuffer，阻止内存扫描检测 payload
- **ETW Patch** — Patch EtwEventWrite，致盲 EDR 的 assembly 加载事件上报
- **D/Invoke 动态解析** — 运行时解析 API 地址，绕过 IAT hook 和静态 P/Invoke 检测
- **RW→RX 内存策略** — 先 RW 写入再翻转为 RX，避免 RWX 分配特征
- **Delegate 回调执行** — 无 CreateThread API 调用，通过函数指针委托直接执行
- **环境检测** — 自动识别分析工具（dnSpy/ILSpy/x64dbg/Wireshark 等）
- **命名伪装** — namespace/class 伪装为系统组件名称

## 对抗改进说明

| 改进项 | 绕过目标 | 原理 |
|--------|----------|------|
| AMSI Bypass | Windows Defender / AMSI 扫描 | Patch AmsiScanBuffer 返回 E_INVALIDARG |
| ETW Patch | EDR assembly 加载监控 | Patch EtwEventWrite 返回 STATUS_SUCCESS |
| D/Invoke | 用户态 API hook | GetProcAddress 动态解析，不走 IAT |
| RW→RX | 内存扫描器 RWX 检测 | 分配时仅 RW，写入后翻转为 RX |
| Delegate 执行 | CreateThread 行为检测 | Marshal.GetDelegateForFunctionPointer 直接调用 |

## 原理

```
┌─────────────────────────────────────────────────────────────┐
│  执行流程                                                    │
│                                                             │
│  1. CLR 读取 .exe.config → 加载 payload DLL                 │
│  2. CLR 调用 InitializeNewDomain() → 启动后台线程            │
│  3. 环境检测 → 通过后继续                                    │
│  4. Patch AMSI (AmsiScanBuffer → E_INVALIDARG)              │
│  5. Patch ETW (EtwEventWrite → STATUS_SUCCESS)              │
│  6. D/Invoke 解析 VirtualAlloc / VirtualProtect             │
│  7. VirtualAlloc(RW) → Marshal.Copy → VirtualProtect(RX)   │
│  8. Delegate 回调执行 shellcode                              │
│  9. 宿主程序 Main() 正常启动                                 │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Windows 10/11
- .NET Framework 4.x (csc.exe)
- Python 3.7+
- **推荐**: [ZeroEye 5.0](https://github.com/ImCoriander/ZeroEye)

### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用 ZeroEye 发现可劫持的 .NET 目标                        │
│    ZeroEye.exe -p c:\ -t dotnet                             │
│                                                             │
│ 2. 生成劫持套件                                              │
│    python generate_dotnet.py -t Target.exe                  │
│    → 生成 Target.exe.config + payload.cs                    │
│                                                             │
│ 3. 在 payload.cs 中填入 SGN 编码后的 shellcode               │
│    private static byte[] buf = new byte[] {0xfc,0x48,...};  │
│                                                             │
│ 4. 编译                                                     │
│    csc /target:library /out:Microsoft.Configuration.        │
│        Helper.dll payload.cs                                │
│                                                             │
│ 5. 部署: config + DLL 放到目标同目录，运行即触发              │
└─────────────────────────────────────────────────────────────┘
```

### 命令行用法

```bash
# 基本用法
python generate_dotnet.py -t MyApp.exe

# 保留原始 assemblyBinding (推荐)
python generate_dotnet.py -t MyApp.exe -c MyApp.exe.config

# 自定义 payload DLL 名称
python generate_dotnet.py -t MyApp.exe -o CustomName

# 交互模式
python generate_dotnet.py
```

## 编译

```bash
# 标准编译 (.NET Framework 4.x csc)
csc /target:library /out:Microsoft.Configuration.Helper.dll payload.cs

# 或使用 Visual Studio Developer Command Prompt
csc /target:library /optimize /out:Microsoft.Configuration.Helper.dll payload.cs
```

## 注意事项

- Shellcode 必须经过编码 (推荐 SGN)，AMSI bypass 在 payload 加载后执行
- 仅适用于 .NET Framework 4.x（.NET Core/5+ 不支持 AppDomainManager 注入）
- 使用 `-c` 参数保留原始 assemblyBinding 确保宿主正常运行
- Delegate 执行是同步的，shellcode 应自行创建线程（如 beacon）或快速返回
- 仅用于授权渗透测试和 CTF 竞赛
- 原生 DLL 代理版本请切换到 `main` 分支

## 相关技术

- [T1574.001 - Hijack Execution Flow](https://attack.mitre.org/techniques/T1574/001/)
- [AppDomainManager Injection](https://www.rapid7.com/blog/post/2023/07/11/appdomain-manager-injection-new-techniques-for-red-teams/)
- [AMSI Bypass Techniques](https://attack.mitre.org/techniques/T1562/001/)
- [ETW Patching](https://attack.mitre.org/techniques/T1562/006/)
