// Seaman Position Tracker v8.1 - NETWORK-ENABLED BY DEFAULT
// Based on v7.2 stable hybrid approach
// Network streaming ON by default to 192.168.0.6:8888
// Use with bridge8_1.py for semantic labels + 3D preview

#define _WINSOCK_DEPRECATED_NO_WARNINGS
#include <winsock2.h>
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <time.h>

#pragma comment(lib, "ws2_32.lib")

// Configuration
const DWORD POLL_RATE_MS = 50;        // 20Hz refresh
const DWORD NEURAL_OFFSET = 0x131e0;  // Movement function
const DWORD INSTANCE_OFFSET = 0x250;  // param_4 offset from instance

// Networking
SOCKET g_udpSocket;
sockaddr_in g_destAddr;
bool g_networkEnabled = true;  // v8.1 DEFAULT: ON (sends to 192.168.0.6:8888)

// Bootstrap state
DWORD g_instanceAddr = 0;
BYTE g_originalByte = 0;
bool g_bpSet = false;
bool g_captured = false;

// Find process
DWORD FindProcess(const char* name) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 pe = {sizeof(pe)};
    if (Process32First(snap, &pe)) {
        do {
            if (_stricmp(pe.szExeFile, name) == 0) {
                CloseHandle(snap);
                return pe.th32ProcessID;
            }
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return 0;
}

// Float to int reinterpretation
DWORD FloatAsInt(float f) {
    return *(DWORD*)&f;
}

// Extract string from float buffer
void ExtractString(float* buffer, int startIdx, char* output, int maxLen) {
    char* bytes = (char*)&buffer[startIdx];
    int len = 0;
    for (int i = 0; i < maxLen - 1 && i < 32; i++) {
        if (bytes[i] == 0) break;
        if (bytes[i] >= 32 && bytes[i] < 127) {
            output[len++] = bytes[i];
        }
    }
    output[len] = 0;
}

int main(int argc, char* argv[]) {
    printf("========================================\n");
    printf("Seaman Tracker v8.1 - NETWORK DEFAULT\n");
    printf("========================================\n");
    printf("Method: Debug bootstrap + external reading\n");
    printf("Network: ON by default to 192.168.0.6:8888\n");
    printf("Bridge: Use bridge8_1.py for UI\n\n");

    printf("USAGE:\n");
    printf("  (no args)             Network ON by default\n");
    printf("  --csv                 Enable CSV logging\n");
    printf("  --ip=192.168.0.X      Change bridge IP (default: 192.168.0.6)\n");
    printf("\n");

    // Parse args
    char targetIP[32] = "192.168.0.6";
    bool csvMode = false;
    FILE* csvFile = NULL;

    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--ip=", 5) == 0) {
            strcpy(targetIP, argv[i] + 5);
        } else if (strcmp(argv[i], "--csv") == 0) {
            csvMode = true;
        } else if (strncmp(argv[i], "--network", 9) == 0) {
            g_networkEnabled = true;
        }
    }

    // Show active modes
    printf("ACTIVE MODES:\n");
    printf("  Console: YES (always on)\n");
    printf("  CSV:     %s\n", csvMode ? "YES" : "NO - add --csv to enable");
    printf("  Network: %s\n", g_networkEnabled ? "YES (default)" : "NO");
    if (g_networkEnabled) {
        printf("  Target:  %s:8888\n", targetIP);
    }
    printf("\n");

    // Setup network if enabled
    if (g_networkEnabled) {
        WSADATA wsa;
        WSAStartup(MAKEWORD(2, 2), &wsa);
        g_udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

        // Non-blocking socket
        u_long mode = 1;
        ioctlsocket(g_udpSocket, FIONBIO, &mode);

        g_destAddr.sin_family = AF_INET;
        g_destAddr.sin_port = htons(8888);
        g_destAddr.sin_addr.s_addr = inet_addr(targetIP);
    }

    // Setup CSV if enabled
    if (csvMode) {
        time_t now = time(NULL);
        struct tm* t = localtime(&now);
        char filename[256];
        sprintf(filename, "position_log_v8.1_%04d%02d%02d_%02d%02d%02d.csv",
                t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                t->tm_hour, t->tm_min, t->tm_sec);

        csvFile = fopen(filename, "w");
        if (csvFile) {
            // CSV header
            fprintf(csvFile, "timestamp,");

            // param_4 floats
            for (int i = 0; i < 100; i++) {
                fprintf(csvFile, "f%d,", i);
            }

            // Instance fields (84 DWORDs with ALL known fields labeled)
            fprintf(csvFile, "i_state,i_sub_state,");

            for (int i = 2; i <= 14; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_dest_x,i_dest_y,i_dest_z,");

            for (int i = 18; i <= 23; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_osc_out_x,i_osc_out_y,i_osc_out_z,");

            for (int i = 0; i < 19; i++) fprintf(csvFile, "i_osc_p%d,", i);

            for (int i = 46; i <= 54; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_local_pos,");

            for (int i = 56; i <= 57; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_timer,");
            fprintf(csvFile, "i_unk_%03x,", 0xa4 + 59*4);
            fprintf(csvFile, "i_dir_value,");

            for (int i = 61; i <= 66; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_anim_id,i_anim_counter,");

            for (int i = 69; i <= 82; i++) fprintf(csvFile, "i_unk_%03x,", 0xa4 + i*4);

            fprintf(csvFile, "i_flag_1f0,");

            // Interpreted param_4 values
            fprintf(csvFile, "f9_int,f10_int,f11_int,f20_int,f21_int,f22_int,");
            fprintf(csvFile, "f31_ptr,f33_ptr,f49_str,f65_str,f97_enum\n");

            printf("CSV logging to %s\n", filename);
            printf("Columns: 1 + 100 param_4 + 84 instance + 11 interpreted = 196 total\n");
        }
    }

    printf("\nSearching for Seaman.exe...\n");
    DWORD pid = FindProcess("Seaman.exe");
    if (!pid) {
        printf("ERROR: Seaman.exe not found!\n");
        system("pause");
        return 1;
    }

    printf("Found PID %d\n", pid);

    // Attach debugger
    printf("Attaching debugger for bootstrap...\n");
    if (!DebugActiveProcess(pid)) {
        printf("ERROR: Could not attach debugger!\n");
        system("pause");
        return 1;
    }

    HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!hProcess) {
        printf("ERROR: Could not open process!\n");
        system("pause");
        return 1;
    }

    DWORD bpAddr = 0x400000 + NEURAL_OFFSET;
    printf("Breakpoint address: 0x%08X\n", bpAddr);
    printf("Waiting for Seaman to move (click in tank)...\n\n");

    bool initialBpSeen = false;

    // Bootstrap: Wait for instance capture
    DEBUG_EVENT dbgEvent;
    while (!g_captured) {
        if (!WaitForDebugEvent(&dbgEvent, INFINITE)) break;
        DWORD continueStatus = DBG_CONTINUE;

        switch (dbgEvent.dwDebugEventCode) {
            case CREATE_PROCESS_DEBUG_EVENT:
                CloseHandle(dbgEvent.u.CreateProcessInfo.hFile);
                break;

            case LOAD_DLL_DEBUG_EVENT:
                CloseHandle(dbgEvent.u.LoadDll.hFile);
                break;

            case EXIT_PROCESS_DEBUG_EVENT:
                printf("Game exited during bootstrap\n");
                CloseHandle(hProcess);
                return 1;

            case EXCEPTION_DEBUG_EVENT:
                if (dbgEvent.u.Exception.ExceptionRecord.ExceptionCode == EXCEPTION_BREAKPOINT) {
                    // Skip initial system breakpoint from DebugActiveProcess
                    if (!initialBpSeen) {
                        initialBpSeen = true;

                        // Now set our breakpoint
                        if (!g_bpSet) {
                            SIZE_T bytesRead;
                            ReadProcessMemory(hProcess, (void*)bpAddr, &g_originalByte, 1, &bytesRead);
                            BYTE int3 = 0xCC;
                            WriteProcessMemory(hProcess, (void*)bpAddr, &int3, 1, NULL);
                            FlushInstructionCache(hProcess, (void*)bpAddr, 1);
                            g_bpSet = true;
                            printf("Breakpoint set - waiting for movement...\n");
                        }
                    }
                    // Check if it's our breakpoint
                    else if ((DWORD)dbgEvent.u.Exception.ExceptionRecord.ExceptionAddress == bpAddr) {
                        HANDLE hThread = OpenThread(THREAD_ALL_ACCESS, FALSE, dbgEvent.dwThreadId);
                        CONTEXT ctx = {CONTEXT_FULL};
                        GetThreadContext(hThread, &ctx);
                        ctx.Eip--;  // Back up to actual instruction

                        // Capture instance from ECX
                        g_instanceAddr = ctx.Ecx;

                        // Validate it
                        DWORD state = 0, animId = 0;
                        SIZE_T bytesRead;
                        ReadProcessMemory(hProcess, (void*)(g_instanceAddr + 0xa4), &state, 4, &bytesRead);
                        ReadProcessMemory(hProcess, (void*)(g_instanceAddr + 0x1b0), &animId, 4, &bytesRead);

                        printf("\n>>> Instance captured at 0x%08X\n", g_instanceAddr);
                        printf("    State: %d, AnimID: %d\n", state, animId);

                        if (state >= 0 && state <= 50 && animId > 0 && animId < 150) {
                            printf("    Validation: PASS\n");
                            g_captured = true;
                        } else {
                            printf("    Validation: FAIL (unexpected values) - will retry\n");
                            g_instanceAddr = 0;
                        }

                        // ALWAYS restore byte and single-step (even on fail, to retry)
                        WriteProcessMemory(hProcess, (void*)bpAddr, &g_originalByte, 1, NULL);
                        FlushInstructionCache(hProcess, (void*)bpAddr, 1);
                        g_bpSet = false;

                        ctx.EFlags |= 0x100;  // Single-step
                        SetThreadContext(hThread, &ctx);
                        CloseHandle(hThread);
                    }
                } else if (dbgEvent.u.Exception.ExceptionRecord.ExceptionCode == EXCEPTION_SINGLE_STEP) {
                    // Re-set breakpoint if still capturing
                    if (!g_captured && !g_bpSet) {
                        BYTE int3 = 0xCC;
                        WriteProcessMemory(hProcess, (void*)bpAddr, &int3, 1, NULL);
                        FlushInstructionCache(hProcess, (void*)bpAddr, 1);
                        g_bpSet = true;
                    }
                }
                break;
        }

        ContinueDebugEvent(dbgEvent.dwProcessId, dbgEvent.dwThreadId, continueStatus);
    }

    // Restore breakpoint if we set it and haven't restored it yet
    if (g_bpSet) {
        WriteProcessMemory(hProcess, (void*)bpAddr, &g_originalByte, 1, NULL);
        FlushInstructionCache(hProcess, (void*)bpAddr, 1);
    }

    if (!g_captured) {
        printf("ERROR: Failed to capture instance!\n");
        CloseHandle(hProcess);
        system("pause");
        return 1;
    }

    printf("========================================\n");
    printf("BOOTSTRAP COMPLETE!\n");
    printf("========================================\n");
    printf("Switching to external memory reading...\n");
    printf("Debugger stays attached but passive.\n");
    printf("Press Ctrl+C to stop.\n\n");

    DWORD param4Addr = g_instanceAddr - INSTANCE_OFFSET;
    DWORD sampleCount = 0;
    DWORD lastPrintTime = GetTickCount();
    bool gameRunning = true;

    // Main loop - handle debug events WITH timeout, poll memory between events
    while (gameRunning) {
        // Check for debug events with short timeout (non-blocking)
        DEBUG_EVENT dbg;
        if (WaitForDebugEvent(&dbg, 10)) {  // 10ms timeout
            // Handle essential events to keep debugger alive
            if (dbg.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT) {
                CloseHandle(dbg.u.LoadDll.hFile);
            } else if (dbg.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
                CloseHandle(dbg.u.CreateProcessInfo.hFile);
            } else if (dbg.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) {
                gameRunning = false;
            }
            ContinueDebugEvent(dbg.dwProcessId, dbg.dwThreadId, DBG_CONTINUE);
        }

        // Poll memory for data (this runs between debug events)
        SIZE_T bytesRead;

        // Read ALL instance fields (0xa4 to 0x1f4 = 336 bytes = 84 DWORDs)
        DWORD instanceBuffer[84];
        if (!ReadProcessMemory(hProcess, (void*)(g_instanceAddr + 0xa4), instanceBuffer, 336, &bytesRead)) {
            Sleep(50);
            continue;
        }

        // Extract known fields
        DWORD state = instanceBuffer[0];          // +0xa4
        DWORD sub_state = instanceBuffer[1];      // +0xa8
        float destX = *(float*)&instanceBuffer[15]; // +0xe0
        float destY = *(float*)&instanceBuffer[16]; // +0xe4
        float destZ = *(float*)&instanceBuffer[17]; // +0xe8
        DWORD animId = instanceBuffer[67];        // +0x1b0
        DWORD animCounter = instanceBuffer[68];   // +0x1b4

        // Read 100 floats
        float buffer[100];
        if (ReadProcessMemory(hProcess, (void*)param4Addr, buffer, 400, &bytesRead)) {
            sampleCount++;
            DWORD now = GetTickCount();

            // Interpret special fields
            DWORD f9_int = FloatAsInt(buffer[9]);
            DWORD f10_int = FloatAsInt(buffer[10]);
            DWORD f11_int = FloatAsInt(buffer[11]);
            DWORD f20_int = FloatAsInt(buffer[20]);
            DWORD f21_int = FloatAsInt(buffer[21]);
            DWORD f22_int = FloatAsInt(buffer[22]);
            DWORD f31_ptr = FloatAsInt(buffer[31]);
            DWORD f33_ptr = FloatAsInt(buffer[33]);
            DWORD f97_enum = FloatAsInt(buffer[97]);

            char str49[32], str65[32];
            ExtractString(buffer, 49, str49, sizeof(str49));
            ExtractString(buffer, 65, str65, sizeof(str65));

            // Console output every 500ms
            if (now - lastPrintTime >= 500) {
                printf("\r[%u] S:%2d A:%3d  POS:[%7.2f,%7.2f,%7.2f] DIR:[%6.2f,%6.2f,%6.2f] Pitch:%.1f Yaw:%.1f",
                       sampleCount, state, animId,
                       buffer[0], buffer[1], buffer[2],      // Position
                       buffer[6], buffer[7], buffer[8],      // Direction
                       buffer[26], buffer[27]);              // Rotation
                fflush(stdout);
                lastPrintTime = now;
            }

            // CSV logging
            if (csvFile) {
                fprintf(csvFile, "%u,", now);

                // 100 param_4 floats
                for (int i = 0; i < 100; i++) {
                    fprintf(csvFile, "%.2f,", buffer[i]);
                }

                // 84 instance DWORDs
                for (int i = 0; i < 84; i++) {
                    fprintf(csvFile, "0x%08X,", instanceBuffer[i]);
                }

                // Interpreted values
                fprintf(csvFile, "%u,%u,%u,%u,%u,%u,", f9_int, f10_int, f11_int, f20_int, f21_int, f22_int);
                fprintf(csvFile, "0x%08X,0x%08X,\"%s\",\"%s\",%u\n",
                        f31_ptr, f33_ptr, str49, str65, f97_enum);
                fflush(csvFile);
            }

            // Network streaming
            if (g_networkEnabled) {
                char packet[736];
                memcpy(packet, buffer, 400);              // 100 floats from param_4
                memcpy(packet + 400, instanceBuffer, 336); // 84 DWORDs from instance
                sendto(g_udpSocket, packet, 736, 0, (sockaddr*)&g_destAddr, sizeof(g_destAddr));
            }
        }

        // Small delay to avoid spinning CPU (debug event timeout provides most of the pacing)
        Sleep(10);
    }

    printf("\nGame exited - shutting down.\n");

    if (csvFile) fclose(csvFile);
    CloseHandle(hProcess);
    return 0;
}
