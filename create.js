import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

let rawData = fs.existsSync('group_data.json') 
    ? JSON.parse(fs.readFileSync('group_data.json')) 
    : null;

async function start() {
    if (!rawData) {
        console.log('❌ No group data found!');
        return;
    }

    try {
        const { version } = await fetchLatestBaileysVersion();
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect } = update;
            if(connection === 'close'){
                const reason = (lastDisconnect?.error)?.output?.statusCode;
                if(reason !== DisconnectReason.loggedOut){
                    console.log('Reconnecting in 5s...');
                    setTimeout(start, 5000);
                } else {
                    console.log('❌ Logged out. Delete auth folder and login again.');
                }
            } else if(connection === 'open'){
                console.log('✅ WhatsApp connected for group creation');
            }
        });

        let groupLinks = [];

        for (let i = 1; i <= rawData.count; i++) {
            const groupName = rawData.name + (rawData.count > 1 ? ` #${i}` : '');
            const participants = rawData.numbers
                .split(',')
                .map(n => n.trim() + '@s.whatsapp.net');

            const desc = rawData.desc || '';
            let dpBuffer = null;

            if (rawData.dp && fs.existsSync('dp.jpg')) {
                dpBuffer = fs.readFileSync('dp.jpg');
            }

            // Create group
            let response;
            try {
                response = await sock.groupCreate(groupName, participants, desc);
                const groupId = response.gid;
                console.log(`✅ Group created: ${groupName} (${groupId})`);

                // Optional: Set DP
                if (dpBuffer) {
                    await sock.updateProfilePicture(groupId, dpBuffer);
                    console.log(`🖼️ DP applied for ${groupName}`);
                }

                // Apply settings toggles
                if (rawData.settings) {
                    const { restrictAdminOnly, restrictInvite, restrictMsg, restrictMedia } = rawData.settings;

                    if (typeof restrictMsg !== 'undefined') {
                        await sock.groupSettingUpdate(groupId, 'announcement', restrictMsg);
                    }
                    if (typeof restrictAdminOnly !== 'undefined') {
                        await sock.groupSettingUpdate(groupId, 'edit', restrictAdminOnly);
                    }
                    // Add other toggles here if needed
                }

                // Get invite link
                let inviteCode = await sock.groupInviteCode(response.gid);
                groupLinks.push(`https://chat.whatsapp.com/${inviteCode}`);
            } catch (err) {
                console.log(`❌ Failed to create group "${groupName}": ${err.message}`);
            }
        }

        // Save all group links for bot notification
        fs.writeFileSync('group_links.json', JSON.stringify(groupLinks, null, 2));
        console.log('🎯 All groups processed ✅');
        console.log('Group links:', groupLinks);

    } catch (err) {
        console.error('Error creating groups:', err);
        setTimeout(start, 5000);
    }
}

start();
