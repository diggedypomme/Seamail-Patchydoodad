/**
 * frida_menu_translate_v24.js
 * - All v20 DrawTextA translations
 * - Restored missing v7 strings (本文, 確認, etc.)
 * - Added new dialog strings
 * - ExtTextOutA hook: logs hex for tab label discovery (no translation yet)
 */

const drawTextMap = [
    // Error / UI
    { target: '835c83508362836790da91b182c98eb8', english: 'Socket connection failed.' },
    { target: '8354815b836f815b90da91b183478389', english: 'Server error. POP server not found.' },
    { target: '8381815b838b8354815b836f815b82d6', english: 'Failed to connect to mail server.' },
    { target: '8341836283768366815b83678354815b', english: 'Cannot connect to update server.' },
    { target: '83418376838a8350815b835683878393', english: 'Application Error' },

    // Restored from v7
    { target: '967b95b6', english: 'Message' },
    { target: '90dd92e88e9e8ad4', english: 'Wait Time' },

    // Tap menu items (from Tap.sdp)
    { target: '836c836283678341834e835a8358', english: 'Net Access' },
    { target: '8341837c82cc91c59066', english: 'Set Appt.' },
    { target: '4d656d6f82f08a4a82ad', english: 'Open Memo' },
    { target: '41646472657373426f6f6b82f08a4a82ad', english: 'Open Addr.Book' },
    { target: '4c6574746572426f7882f08a4a82ad', english: 'Open LetterBox' },
    { target: '507265666572656e636582f08a4a82ad', english: 'Open Prefs' },
    { target: '89e696ca82cc838a8374838c836283568385', english: 'Refresh Screen' },
    { target: '8e9f82cc975c92e882cc8a6d9446', english: 'Check Schedule' },

    // Sex dropdown values
    { target: '926a', english: 'Male' },
    { target: '8f97', english: 'Female' },

    // Relationship dropdown values
    { target: '974692428ad68c57', english: 'Friends' },
    { target: '97f688a48ad68c57', english: 'Romantic' },
    { target: '8e648e968ad68c57', english: 'Work' },
    { target: '8a778d5a8ad68c57', english: 'School' },
    { target: '836f834383678ad68c57', english: 'Part-time' },
    { target: '957695778ad68c57', english: 'Married' },
    { target: '89c691b08ad68c57', english: 'Family' },
    { target: '82bb82cc91bc8ad68c57', english: 'Other' },

    // Address Book column headers
    { target: '955c8ea696bc', english: 'Name' },
    { target: '8ad68c57', english: 'Relationship' },
    { target: '8381815b838b83418368838c8358', english: 'Email Address' },
    { target: '944e97ee', english: 'Age' },
    { target: '90ab95ca', english: 'Gender' },
    { target: '90458bc6', english: 'Occupation' },
    { target: '926190b693fa', english: 'Birthday' },
    { target: '8c8c89748c5e', english: 'Blood Type' },
    { target: '83898393834e', english: 'Rank' },
    { target: '58588c5e', english: 'XX Type' },

    // Menu dialog labels (DrawTextA ANSI)
    { target: '914991f082b582c482ad82be82b382a2', english: 'Please Select' },
    { target: '82a082c882bd82cc94ad8cbe', english: 'Your Statement' },

    // Dialogs
    { target: '8a6d9446', english: 'Confirm' },
    { target: '8da18ce3814182b182cc83818362835a815b835782f0955c8ea682b582c882a2', english: "Don't show this again" },
    { target: '936f985e928682cc8366815b835e82cd96b38cf882c982c882e882dc82b7814', english: 'Data will be lost. Cancel anyway?' },

    // Address Book new entry window
    { target: '82608284828482928285829382938261828f828f828b90568b4b936f985e', english: 'New Address Book Entry' },

    // Section headers
    { target: '81755365614d61696c817681408fee95f1', english: 'SeaMail Info' },
    { target: '81a1208f6f93fc82e88bd68e7e90dd92e8', english: 'Block Settings' },

    // Warnings / help text
    { target: '928d88d32081462090ab95ca82c6944e', english: 'Select Gender and Age first to enable Relationship.' },
    { target: '8169825895b68e9a82dc82c5816a', english: '(Max 9 chars)' },
    { target: '81a6936f985e82f0834c83838393835a', english: 'Canceling registration will also cancel the appointment.' },
];

const extTextOutMap = [
    { target: '20837c834383938367', english: ' Points' },
];

// UTF-16LE patterns for ExtTextOutW menu items
const extTextOutWMap = [
    { target: 'cd30c330c830a230af30bb30b930', english: 'Net Access' },
    { target: 'a230dd306e3053623a8a', english: 'Set Appt.' },
    { target: '4d0065006d006f0092308b954f30', english: 'Open Memo' },
    { target: '410064006400720065007300730042006f006f006b0092308b954f30', english: 'Open Addr.Book' },
    { target: '4c006500740074006500720042006f00780092308b954f30', english: 'Open LetterBox' },
    { target: '50007200650066006500720065006e006300650092308b954f30', english: 'Open Prefs' },
    { target: '3b7562976e30ea30d530ec30c330b730e530', english: 'Refresh Screen' },
    { target: '216b6e30884e9a5b6e30ba788d8a', english: 'Check Schedule' },
];

function isAscii(hex) {
    for (let i = 0; i < hex.length; i += 2) {
        if (parseInt(hex.substr(i, 2), 16) > 0x7e) return false;
    }
    return true;
}

function applyMap(map, hex, args, strIdx, lenIdx, encoding, ctx) {
    if (isAscii(hex)) return false;
    for (let i = 0; i < map.length; i++) {
        if (hex === map[i].target || hex.startsWith(map[i].target)) {
            console.log('[+] -> "' + map[i].english + '"');
            const newBuf = (encoding === 'ansi') ? Memory.allocAnsiString(map[i].english) : Memory.allocUtf16String(map[i].english);
            if (ctx) ctx._buf = newBuf; // keep reference so GC doesn't free before render
            args[strIdx] = newBuf;
            if (lenIdx !== null) args[lenIdx] = ptr(map[i].english.length);
            return true;
        }
    }
    return false;
}

function hookAll() {
    // Sort maps longest-first so short patterns don't match prefixes of longer ones
    drawTextMap.sort((a, b) => b.target.length - a.target.length);
    extTextOutMap.sort((a, b) => b.target.length - a.target.length);

    const user32 = Process.getModuleByName('user32.dll');
    const drawTextA = user32.findExportByName('DrawTextA');
    const gdi32 = Process.getModuleByName('gdi32.dll');
    const extTextOutA = gdi32.findExportByName('ExtTextOutA');

    // DrawTextA hook
    if (drawTextA) {
        Interceptor.attach(drawTextA, {
            onEnter: function (args) {
                const lpString = args[1];
                if (lpString.isNull()) return;
                let cbCount = args[2].toInt32();
                const readLen = Math.min((cbCount === -1) ? 256 : Math.abs(cbCount), 256);
                if (readLen === 0) return;
                const buffer = lpString.readByteArray(readLen);
                const hex = Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
                const ansi = lpString.readAnsiString(readLen) || '[binary]';
                console.log('[D] "' + ansi + '" | ' + hex);
                applyMap(drawTextMap, hex, args, 1, 2, 'ansi', this);
            }
        });
        console.log('[+] DrawTextA hooked.');
    }

    // ExtTextOutA hook — log only for now to discover tab label hex
    if (extTextOutA) {
        Interceptor.attach(extTextOutA, {
            onEnter: function (args) {
                const lpString = args[5];
                if (!lpString || lpString.isNull()) return;
                const count = args[6].toInt32();
                if (count <= 0 || count > 256) return;
                try {
                    const buffer = lpString.readByteArray(count);
                    const hex = Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
                    // Only log if contains high bytes (potential Japanese)
                    if (!/[89a-f][0-9a-f]/.test(hex)) return;
                    const ansi = lpString.readAnsiString(count) || '[binary]';
                    console.log('[E] "' + ansi + '" | ' + hex);
                    if (extTextOutMap.length > 0) applyMap(extTextOutMap, hex, args, 5, null, 'ansi');
                } catch(e) {}
            }
        });
        console.log('[+] ExtTextOutA hooked (logging).');
    }

    // ExtTextOutW hook — menu items rendered as real UTF-16 (not glyph indices)
    const extTextOutW = gdi32.findExportByName('ExtTextOutW');
    if (extTextOutW) {
        Interceptor.attach(extTextOutW, {
            onEnter: function (args) {
                const fuOptions = args[3].toInt32();
                if (fuOptions & 0x10) return; // ETO_GLYPH_INDEX — skip, unreadable
                const lpString = args[5];
                if (!lpString || lpString.isNull()) return;
                const count = args[6].toInt32();
                if (count <= 0 || count > 64) return;
                try {
                    const buffer = lpString.readByteArray(count * 2);
                    const hex = Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
                    // Sort longest-first
                    extTextOutWMap.sort((a, b) => b.target.length - a.target.length);
                    for (let i = 0; i < extTextOutWMap.length; i++) {
                        if (hex.startsWith(extTextOutWMap[i].target)) {
                            console.log('[EW] -> "' + extTextOutWMap[i].english + '"');
                            const newBuf = Memory.allocUtf16String(extTextOutWMap[i].english);
                            this._buf = newBuf;
                            args[5] = newBuf;
                            args[6] = ptr(extTextOutWMap[i].english.length);
                            return;
                        }
                    }
                } catch(e) {}
            }
        });
        console.log('[+] ExtTextOutW hooked.');
    }

    // TextOutA hook
    const textOutA = gdi32.findExportByName('TextOutA');
    if (textOutA) {
        Interceptor.attach(textOutA, {
            onEnter: function (args) {
                const lpString = args[3];
                if (!lpString || lpString.isNull()) return;
                const count = args[4].toInt32();
                if (count <= 0 || count > 32) return;
                try {
                    const buffer = lpString.readByteArray(count);
                    const hex = Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
                    if (isAscii(hex)) return;
                    const ansi = lpString.readAnsiString(count) || '[binary]';
                    console.log('[T] "' + ansi + '" | ' + hex);
                    applyMap(drawTextMap, hex, args, 3, 4, 'ansi', this);
                } catch(e) {}
            }
        });
        console.log('[+] TextOutA hooked.');
    }

    // SetWindowTextA hook — menu list items go through this
    const setWindowTextA = user32.findExportByName('SetWindowTextA');
    if (setWindowTextA) {
        Interceptor.attach(setWindowTextA, {
            onEnter: function (args) {
                const lpString = args[1];
                if (!lpString || lpString.isNull()) return;
                try {
                    const ansi = lpString.readAnsiString(256);
                    if (!ansi) return;
                    const buf = lpString.readByteArray(ansi.length);
                    const hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
                    if (isAscii(hex)) return;
                    console.log('[SW] "' + ansi + '" | ' + hex);
                    applyMap(drawTextMap, hex, args, 1, null, 'ansi', this);
                } catch(e) {}
            }
        });
        console.log('[+] SetWindowTextA hooked.');
    }

    // SendMessageA hook — listbox LB_ADDSTRING (0x180)
    const sendMessageA = user32.findExportByName('SendMessageA');
    if (sendMessageA) {
        Interceptor.attach(sendMessageA, {
            onEnter: function (args) {
                const msg = args[1].toInt32();
                if (msg !== 0x180) return; // LB_ADDSTRING only
                const lpString = args[3];
                if (!lpString || lpString.isNull()) return;
                try {
                    const ansi = lpString.readAnsiString(256);
                    if (!ansi) return;
                    const hex = Array.from(lpString.readByteArray(ansi.length)).map(b => b.toString(16).padStart(2, '0')).join('');
                    if (isAscii(hex)) return;
                    console.log('[LB] "' + ansi + '" | ' + hex);
                    applyMap(drawTextMap, hex, args, 3, null, 'ansi', this);
                } catch(e) {}
            }
        });
        console.log('[+] SendMessageA hooked (LB_ADDSTRING).');
    }

    // TextOutW hook — combobox may use wide version
    const textOutW = gdi32.findExportByName('TextOutW');
    if (textOutW) {
        Interceptor.attach(textOutW, {
            onEnter: function (args) {
                const lpString = args[3];
                if (!lpString || lpString.isNull()) return;
                const count = args[4].toInt32();
                if (count <= 0 || count > 32) return;
                try {
                    const s = lpString.readUtf16String(count) || '';
                    if (!s || s.trim().length === 0) return;
                    console.log('[TW] "' + s + '"');
                } catch(e) {}
            }
        });
        console.log('[+] TextOutW hooked (logging).');
    }

    console.log('[+] V24 Active.');
}

setImmediate(hookAll);
