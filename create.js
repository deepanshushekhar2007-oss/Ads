import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

async function start() {
    try {
        // Load group data from Telegram
        if (!fs.existsSync('group_data.json')) {
            console.log('❌ No group data found!');
            return;
        }

        const rawData = JSON.parse(fs.readFileSync('group_data.json'));

        // 1️⃣ WhatsApp connection
        const { version } = await fetchLatestBaileysVersion();
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect } = update;
            if (connection === 'close') {
                const reason = (lastDisconnect?.error)?.output?.statusCode;
                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting in 5s...');
                    setTimeout(start, 5000);
                }
            } else if (connection === 'open') {
                console.log('✅ WhatsApp connected');
            }
        });

        // 2️⃣ Create groups
        let groupLinks = [];

        for (let i = 1; i <= rawData.count; i++) {
            const groupName = rawData.name + (rawData.count > 1 ? ` #${i}` : '');
            const participants = rawData.numbers.split(',').map(n => n.trim() + '@s.whatsapp.net'); // Single participant

            const desc = rawData.desc || '';
            let dpBuffer = null;
            if (rawData.dp && fs.existsSync('dp.jpg')) {
                dpBuffer = fs.readFileSync('dp.jpg');
            }

            try {
                const response = await sock.groupCreate(groupName, participants, desc);
                const groupId = response.gid;
                console.log(`✅ Group created: ${groupName} (${groupId})`);

                // Apply DP
                if (dpBuffer) {
                    await sock.updateProfilePicture(groupId, dpBuffer);
                }

                // Apply group settings toggles
                if (rawData.settings) {
                    const { restrict_msg, restrict_invite, restrict_admin, restrict_media } = rawData.settings;

                    if (restrict_msg) await sock.groupSettingUpdate(groupId, 'announcement', true);
                    if (restrict_invite) await sock.groupSettingUpdate(groupId, 'edit_group_info', true);
                    if (restrict_admin) await sock.groupSettingUpdate(groupId, 'restrict', true);
                    if (restrict_media) await sock.groupSettingUpdate(groupId, 'restrict', true); // placeholder
                }

                // Get invite link
                const inviteCode = await sock.groupInviteCode(groupId);
                groupLinks.push(`https://chat.whatsapp.com/${inviteCode}`);

            } catch (err) {
                console.error(`❌ Failed to create group ${groupName}:`, err);
            }
        }

        // Save all group links for Telegram bot
        fs.writeFileSync('group_links.json', JSON.stringify(groupLinks));
        console.log('✅ All groups created');
        console.log('Group links:', groupLinks);

    } catch (err) {
        console.error('Error in create.js:', err);
        setTimeout(start, 5000);
    }
}

start();
