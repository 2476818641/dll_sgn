# DLL Hijacking & Process Injection Framework

A sophisticated DLL hijacking and process injection framework for Windows red team operations and CTF competitions. This toolkit automates the creation of proxy DLLs with advanced evasion techniques.

## Features

### Core Capabilities
- **OS-Level Export Forwarding**: Uses Windows native DLL forwarding mechanism instead of manual ASM trampolines
- **Early Bird APC Injection**: Executes payload before EDR hooks are fully initialized
- **PPID Spoofing**: Breaks process tree lineage by spoofing parent process (explorer.exe/svchost.exe)
- **Asynchronous DllMain**: Prevents loader lock and ensures host process stability
- **Environment Detection**: Identifies analysis tools and server environments before execution
- **Memory Protection Flipping**: RWX → RX transition to evade memory scanners

### OPSEC Features
- Hidden process creation (CREATE_NO_WINDOW)
- Automatic cleanup of resources
- Anti-analysis tool detection (debuggers, Wireshark, Process Hacker, etc.)
- Server environment profiling
- Minimal footprint with system-level forwarding

## Architecture

### Components

1. **generate.py**: Automated proxy DLL generator
   - Parses exported functions from target DLL
   - Generates OS-level forwarding definitions
   - Creates injection payload wrapper

2. **dllmain.cpp**: Injection payload implementation
   - Background thread execution (prevents loader lock)
   - PPID spoofing via STARTUPINFOEX
   - Early Bird APC injection technique
   - Environment safety checks

## Installation

### Prerequisites
- Windows 10/11 (x64)
- Visual Studio 2019/2022 with C++ Desktop Development workload
- Python 3.7+
- Git for Windows

### Build Instructions

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/dll_hook1.git
cd dll_hook1
```

2. **Generate proxy files**
```bash
# Interactive mode
python generate.py

# Command-line mode
python generate.py -u funcs.txt -n target_dll_name
```

3. **Configure payload**
   - Edit `dllmain.cpp` and replace the `payload[]` array with your encoded shellcode
   - Ensure payload is SGN-encoded or similar

4. **Build with Visual Studio**
   - Open `dll_hook1.sln` in Visual Studio
   - Select **Release** configuration and **x64** platform
   - Build Solution (Ctrl+Shift+B)
   - Output: `x64\Release\dll_hook1.dll`

5. **Deploy**
   - Rename compiled DLL to match target DLL name (e.g., `version.dll`)
   - Rename original DLL to `[name]_orig.dll` (e.g., `version_orig.dll`)
   - Place both DLLs in the target application directory

## Usage

### Basic Workflow

```bash
# Step 1: Extract exported functions from target DLL
# Use tools like: dumpbin /exports target.dll > funcs.txt
# Or: CFF Explorer, PE-bear, etc.

# Step 2: Generate proxy files
python generate.py -u funcs.txt -n version

# Step 3: Insert your payload into dllmain.cpp
# Replace the payload[] array with your shellcode

# Step 4: Build the project in Visual Studio (Release x64)

# Step 5: Deploy
# - Compiled DLL → version.dll
# - Original DLL → version_orig.dll
```

### Example: Hijacking version.dll

```bash
# Generate proxy for version.dll
python generate.py -u version_exports.txt -n version

# Build in Visual Studio
# Deploy:
#   your_compiled.dll → version.dll
#   original_system.dll → version_orig.dll
```

## Technical Details

### OS-Level Export Forwarding

Instead of generating ASM trampolines, the framework uses Windows native forwarding:

```def
LIBRARY "target"
EXPORTS
    FunctionName=target_orig.FunctionName
```

This approach:
- Reduces code complexity
- Eliminates ASM maintenance
- Improves compatibility
- Decreases detection surface

### Early Bird APC Injection

The injection sequence:

1. **PPID Spoofing**: Acquire handle to explorer.exe/svchost.exe
2. **Process Creation**: Launch conhost.exe in suspended state with spoofed parent
3. **Memory Allocation**: Allocate RWX memory in target process
4. **Payload Writing**: Write encoded shellcode to allocated memory
5. **APC Queuing**: Queue APC to main thread pointing to payload
6. **Thread Resumption**: Resume thread, triggering APC execution
7. **Protection Flip**: Change memory to RX after execution

### Asynchronous Execution

```cpp
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        
        // Non-blocking: spawn background thread and return immediately
        HANDLE hThread = CreateThread(NULL, 0, BackgroundInjectionThread, NULL, 0, NULL);
        if (hThread) CloseHandle(hThread);
    }
    return TRUE;
}
```

## Configuration

### Environment Detection

Edit the process lists in `dllmain.cpp`:

```cpp
// Server processes (whitelist)
const char* serverProcs[] = {
    "java.exe", "javaw.exe", "w3wp.exe", "httpd.exe", "nginx.exe",
    "mysqld.exe", "sqlservr.exe", "php-cgi.exe", "node.exe", "BtSoft.exe"
};

// Analysis tools (blacklist)
const char* analystProcs[] = {
    "x64dbg.exe", "x32dbg.exe", "Wireshark.exe", "ProcessHacker.exe",
    "Procmon.exe", "ida64.exe", "ollydbg.exe"
};
```

### Injection Target

Change the target process in `ExecuteEarlyBirdInjection()`:

```cpp
// Default: conhost.exe
if (GetSystemDirectoryA(targetPath, MAX_PATH)) {
    strcat_s(targetPath, "\\conhost.exe");
}

// Alternative: notepad.exe, svchost.exe, etc.
```

## Project Structure

```
dll_hook1/
├── generate.py              # Proxy generator script
├── dllmain.cpp             # Injection payload implementation
├── exports.def             # Generated export definitions
├── dll_hook1.vcxproj       # Visual Studio project file
├── dll_hook1.sln           # Visual Studio solution
├── framework.h             # Windows framework headers
├── pch.h                   # Precompiled header
└── README.md               # This file
```

## Security Considerations

### Legal Use Only
This framework is designed for:
- Authorized penetration testing
- CTF competitions
- Security research
- Educational purposes

**DO NOT** use this tool for:
- Unauthorized access to systems
- Malicious activities
- Distribution of malware

### Detection Vectors

While this framework implements multiple evasion techniques, be aware of:
- Behavioral analysis (process creation patterns)
- Memory scanning (RWX allocations)
- Parent-child process anomalies
- DLL load order monitoring
- Signature-based detection of known shellcode

## Troubleshooting

### Build Errors

**Error: LNK1106 - Invalid or corrupt file**
- Ensure you're building for x64 platform
- Clean solution and rebuild
- Check that `exports.def` is properly formatted

**Error: Cannot find original DLL**
- Verify `[name]_orig.dll` exists in the same directory
- Check file permissions
- Ensure DLL name matches exactly (case-sensitive)

### Runtime Issues

**Host application crashes on startup**
- Verify all exported functions are correctly forwarded
- Check that original DLL is not corrupted
- Ensure architecture matches (x64 vs x86)

**Payload doesn't execute**
- Check environment detection logic
- Verify payload is properly encoded
- Ensure target process has sufficient privileges

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Changelog

### v2.0.0 (Current)
- Implemented OS-level export forwarding
- Added Early Bird APC injection
- Implemented PPID spoofing
- Asynchronous DllMain execution
- Removed ASM trampoline dependency

### v1.0.0
- Initial release
- Basic proxy generation
- CreateRemoteThread injection
- Manual ASM trampolines

## License

This project is provided for educational and authorized security testing purposes only. Users are responsible for compliance with applicable laws and regulations.

## References

- [DLL Hijacking Techniques](https://attack.mitre.org/techniques/T1574/001/)
- [Process Injection: Early Bird](https://attack.mitre.org/techniques/T1055/)
- [Parent PID Spoofing](https://attack.mitre.org/techniques/T1134/004/)
- [Windows DLL Export Forwarding](https://docs.microsoft.com/en-us/cpp/build/exporting-from-a-dll)

## Contact

For questions, issues, or security concerns, please open an issue on GitHub.

---

**⚠️ WARNING**: This tool is intended for authorized security testing only. Misuse may violate laws including the Computer Fraud and Abuse Act (CFAA) and similar legislation in other jurisdictions.
