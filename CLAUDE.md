# CLAUDE.md - Project Instructions

## Project Overview

This is a DLL hijacking and process injection framework for Windows red team operations and CTF competitions. The framework automates proxy DLL generation and implements advanced evasion techniques.

## Knowledge Base Access

This project has access to global red team knowledge bases:

- **Atomic Red Team**: `~/.claude/atomic-red-team/`
  - Practical test cases for MITRE techniques
  - Location: `D:\knowledge-base\atomic-red-team`
  
- **MITRE CTI**: `~/.claude/mitre-cti/`
  - Complete MITRE ATT&CK framework
  - Location: `D:\knowledge-base\cti`

See `~/.claude/KNOWLEDGE_BASE.md` for detailed usage instructions.

## Implemented Techniques

This project implements the following MITRE ATT&CK techniques:

- **T1055.004** - Process Injection: APC (Early Bird)
- **T1134.004** - Access Token Manipulation: Parent PID Spoofing  
- **T1574.001** - Hijack Execution Flow: DLL Search Order Hijacking

When working on this project, AI assistants should reference the knowledge base for:
- Implementation details and best practices
- Detection methods and evasion strategies
- Test cases from Atomic Red Team

## Development Guidelines

### Code Style
- Use Chinese comments for OPSEC-critical sections
- Include MITRE ATT&CK technique IDs in comments
- Document evasion techniques and their rationale

### Security Considerations
- This is for authorized testing only
- Always implement environment detection
- Include anti-analysis checks
- Document detection vectors

## Quick Reference

### Generate Proxy DLL
```bash
python generate.py -u exports.txt -n target_dll
```

### Build
- Configuration: Release
- Platform: x64
- Output: `x64/Release/dll_hook1.dll`

### Deploy
1. Rename compiled DLL to target name (e.g., `version.dll`)
2. Rename original DLL to `[name]_orig.dll`
3. Place both in application directory

## Related Resources

- MITRE ATT&CK: https://attack.mitre.org/
- Atomic Red Team: https://www.atomicredteam.io/
- Project Repository: https://github.com/2476818641/dll_sgn.git
