const speechEngine = Process.findModuleByName("SpeechEngine.dll");
const msvcrt = Process.findModuleByName("msvcrt.dll");
const dbManager = Process.findModuleByName("DataBaseManager.dll");
const seamanEXE = Process.enumerateModules().find(m => m.name.toLowerCase().includes("seaman"));

/**
 * Version 33: ULTIMATE PURITY (NO EVENT BLOCKING)
 *
 * v32 REVELATION: Look closely at the logs. The infinite growth loop
 * (event=3 and event=5 spam) completely stopped happening! The ONLY thing
 * our blocker was doing was preventing "ComeNearRelease" (event=4), which
 * actively trapped Seaman in a zoomed-in state after you tapped him or
 * finished a conversation.
 *
 * v33 FIX:
 * We are deleting the event=4 and idlerecognition DB Write blockers ENTIRELY.
 * The script will only do exactly two things:
 * 1. Maintain the "GetIndex" hook to downgrade his stage to 3, giving him
 *    conversational AI loops instead of the empty messenger branch.
 * 2. Keep the RPC / Vocab spoofing alive for debugging.
 *
 * By not blocking event=4, he should naturally zoom back out and start
 * swimming again after you call him over!
 */

// ============================================================
// STATE TRACKING
// ============================================================

let g_enginePtr = null;
let g_speechMgrPtr = null;
let g_creatureId = -1;
let g_spoofFired = false;
let g_vocabWords = new Set();
let g_currentLabel = "";
let g_vocabCollecting = false;
let g_growGetForced = 0;

// LOG DEDUPLICATION
let g_lastScenario = "";
let g_scenarioRepeatCount = 0;

function logScenario(name) {
    if (name === g_lastScenario) {
        g_scenarioRepeatCount++;
        if (g_scenarioRepeatCount % 10 === 0) {
            send(`📂 [V33] ${name} (×${g_scenarioRepeatCount})`);
        }
    } else {
        if (g_scenarioRepeatCount > 1) {
            send(`📂 [V33] ${g_lastScenario} (×${g_scenarioRepeatCount} total)`);
        }
        g_lastScenario = name;
        g_scenarioRepeatCount = 1;
        send(`📂 [V33] ${name}`);
    }
}

// ============================================================
// PHASE 1: ENGINE DISCOVERY
// ============================================================

function discoverEngine() {
    if (!seamanEXE) { return false; }
    try {
        const speechMgrAddr = seamanEXE.base.add(0x689fc);
        g_speechMgrPtr = speechMgrAddr.readPointer();
        if (g_speechMgrPtr.isNull()) return false;
        g_creatureId = g_speechMgrPtr.add(0x118).readS32();
        const engineWrapper = g_speechMgrPtr.add(0x120).readPointer();
        if (engineWrapper.isNull()) return false;
        g_enginePtr = engineWrapper.readPointer();
        if (g_enginePtr.isNull()) return false;
        return true;
    } catch(e) { return false; }
}

// ============================================================
// PHASE 2: RECOGNITION SPOOF
// ============================================================

function spoofRecognition(word) {
    if (!speechEngine) return;
    if (!discoverEngine()) return;
    const recEventAddr = speechEngine.getExportByName("RecognizedEvent");
    if (!recEventAddr) return;
    const recEvent = new NativeFunction(recEventAddr, 'void', ['pointer', 'pointer']);
    const wordPtr = Memory.allocUtf8String(word);
    send(`[V33] 🎯 SPOOFING RecognizedEvent(${g_enginePtr}, "${word}")`);
    try {
        recEvent(g_enginePtr, wordPtr);
    } catch(e) {}
}

// ============================================================
// PHASE 3: SPEECH START & VOCAB
// ============================================================

if (speechEngine) {
    const speechStartAddr = speechEngine.getExportByName("SpeechStart");
    if (speechStartAddr) {
        Interceptor.attach(speechStartAddr, {
            onEnter: function(args) {
                try {
                    const label = args[0].readAnsiString();
                    g_currentLabel = label;
                    g_vocabWords.clear();
                    g_vocabCollecting = true;
                    send(`[V33] 🎧 SpeechStart("${label}")`);
                } catch(e) {}
            }
        });
    }
}

if (speechEngine && msvcrt) {
    const stricmp = msvcrt.getExportByName("_stricmp");
    const base = speechEngine.base;
    const size = speechEngine.size;

    send("[V33] ⚡ PURE FIX: SCRIPT DOWNGRADE (NO EVENT BLOCKING) loaded");
    setTimeout(() => { discoverEngine(); }, 5000);

    Interceptor.attach(stricmp, {
        onEnter: function(args) {
            const relAddr = this.returnAddress.sub(base);
            if (relAddr.compare(0) >= 0 && relAddr.compare(size) < 0) {
                try {
                    const s1 = args[0].readAnsiString();
                    const s2 = args[1].readAnsiString();

                    if (g_vocabCollecting && s2 && s2.length > 0 && s2.length < 50) {
                        if (!s2.includes("@") && !s2.includes("\\") &&
                            s2 !== "idle" && s2 !== "-" && s2 !== "") {
                            g_vocabWords.add(s2);
                        }
                    }

                    if (relAddr.equals(0x35f2) &&
                        !s1.includes("existencecheck") && !s1.includes("idle") &&
                        s1 !== "growing" && s1 !== "gm") {
                        logScenario(s1);
                    }
                } catch (e) {}
            }
        }
    });
}

// ============================================================
// PHASE 4: GETINDEX GROW OVERRIDE (DOWNGRADE TO STAGE 3)
// ============================================================

if (seamanEXE) {
    const getIndexAddr = seamanEXE.base.add(0x12a0);
    Interceptor.attach(getIndexAddr, {
        onEnter: function(args) {
            this.path = "";
            try { this.path = args[1].readAnsiString(); } catch(e) {}
        },
        onLeave: function(retval) {
            if (!this.path) return;
            const lp = this.path.toLowerCase();

            // FORCE SCRIPT RE-ROUTING
            if (lp.includes("bio\\grow") && !lp.includes("growtime") && !lp.includes("istogrow")) {
                const oldVal = retval.toInt32();
                if (oldVal !== 3) {
                    retval.replace(3);
                    g_growGetForced++;
                    if (g_growGetForced <= 5 || g_growGetForced % 50 === 0) {
                        send(`🌱 [V33 DOWNGRADE] GetIndex("${this.path}") ${oldVal} → 3 (×${g_growGetForced})`);
                    }
                }
            }
        }
    });
}

// ============================================================
// PHASE 5: DB LOGGER ONLY (NO BLOCKS)
// ============================================================

if (dbManager) {
    Interceptor.attach(dbManager.base.add(0x217e0), {
        onEnter: function(args) {
            let path = "";
            let value = "";
            try {
                path = args[1].readAnsiString();
                value = args[2].readAnsiString();
                const lowerPath = path.toLowerCase();
                
                // Allow EVERYTHING. Just log interesting writes.
                if (lowerPath.includes("event") || value === "ComeNearRelease") {
                    send(`📝 [V33 DB ALLOWED] ${path} = ${value}`);
                }
            } catch(e) {}
        }
    });
}

// ============================================================
// PHASE 6: RPC
// ============================================================

rpc.exports = {
    spoofWord: function(word) {
        g_spoofFired = false;
        spoofRecognition(word);
        return "OK";
    },
    discoverEngine: function() {
        return discoverEngine();
    },
    getVocab: function() {
        return {
            label: g_currentLabel,
            words: [...g_vocabWords],
            collecting: g_vocabCollecting
        };
    },
    getStatus: function() {
        return {
            enginePtr: g_enginePtr ? g_enginePtr.toString() : "null",
            speechMgr: g_speechMgrPtr ? g_speechMgrPtr.toString() : "null",
            creatureId: g_creatureId,
            currentLabel: g_currentLabel,
            vocabCount: g_vocabWords.size,
            growGetForced: g_growGetForced
        };
    }
};
