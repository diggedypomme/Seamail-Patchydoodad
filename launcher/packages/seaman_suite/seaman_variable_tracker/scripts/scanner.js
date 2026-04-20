/**
 * GEM Var Tracker - Frida Scanner Agent
 * Handles memory reads from global pointers and nested offsets.
 */

let baseAddr = null;
const modules = Process.enumerateModules();
for (let i = 0; i < modules.length; i++) {
    if (modules[i].name.toLowerCase().includes('seaman')) {
        baseAddr = modules[i].base;
        console.log('[Scanner] Found Seaman module: ' + modules[i].name + ' at ' + baseAddr);
        break;
    }
}

if (!baseAddr) {
    console.error('[Scanner] Could not find any Seaman-related module!');
}

/**
 * Resolve a nested pointer chain.
 * @param {NativePointer} base 
 * @param {Array<number>} offsets 
 * @returns {NativePointer}
 */
function resolvePointer(base, offsets) {
    let addr = base;
    try {
        for (let i = 0; i < offsets.length; i++) {
            addr = addr.readPointer().add(offsets[i]);
        }
    } catch (e) {
        return null;
    }
    return addr;
}

rpc.exports = {
    /**
     * Read a variable from memory.
     * @param {string} baseStr Hex string address
     * @param {Array<number>} offsets Array of offsets
     * @param {string} type 'int' | 'float' | 'pointer'
     */
    readVariable: function (baseStr, offsets, type) {
        const base = ptr(baseStr);
        const target = resolvePointer(base, offsets);
        
        if (!target || target.isNull()) {
            return { status: 'error', msg: 'Null or invalid pointer' };
        }

        try {
            let value = null;
            if (type === 'int') {
                value = target.readS32();
            } else if (type === 'float') {
                value = target.readFloat();
            } else if (type === 'pointer') {
                value = target.readPointer().toString();
            } else if (type === 'byte') {
                value = target.readU8();
            }
            
            return { status: 'ok', value: value, address: target.toString() };
        } catch (e) {
            return { status: 'error', msg: e.message };
        }
    },

    /**
     * Bulk read multiple variables to reduce RPC overhead.
     */
    bulkRead: function (variables) {
        const results = {};
        for (const key in variables) {
            const v = variables[key];
            const res = this.readVariable(v.address, v.offsets, v.type);
            results[key] = res;
        }
        return results;
    }
};
