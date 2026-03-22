import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason, proto } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

// Load group creation data sent from bot
let rawData = fs.existsSync('group_data.json') ? JSON.parse(fs.readFileSync('group_data.json')) : null;

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
                    console.log('Reconnecting...');
                    setTimeout(start, 5000);
                }
            }
        });

        // Loop through each group
        let groupLinks = [];

        for(let i=1; i<=rawData.count; i++){
            const groupName = rawData.name + (rawData.count > 1 ? ` #${i}` : '');
            const participants = rawData.numbers.split(',').map(n => n.trim() + '@s.whatsapp.net'); // single participant
            const desc = rawData.desc || '';
            const dpBuffer = fs.existsSync('dp.jpg') && rawData.dp === true ? fs.readFileSync('dp.jpg') : null;

            // Create group
            let response = await sock.groupCreate(groupName, participants, desc);
            const groupId = response.gid;
            console.log(`✅ Group created: ${groupName} (${groupId})`);

            // Set group profile picture if DP exists
            if(dpBuffer){
                await sock.updateProfilePicture(groupId, dpBuffer);
            }

            // Apply group settings toggles
            if(rawData.settings){
                const { restrictAdminOnly, restrictInvite, restrictMsg, restrictMedia } = rawData.settings;
                // Example: restrict messages
                await sock.groupSettingUpdate(groupId, 'announcement', restrictMsg ? true : false);
                // Additional settings toggles can be applied here
            }

            // Get invite link
            let inviteCode = await sock.groupInviteCode(groupId);
            groupLinks.push(`https://chat.whatsapp.com/${inviteCode}`);
        }

        // Save links to a file for bot to read
        fs.writeFileSync('group_links.json', JSON.stringify(groupLinks));
        console.log('All groups created ✅');
        console.log('Group links:', groupLinks);

    } catch (err) {
        console.error('Error creating groups:', err);
        setTimeout(start, 5000);
    }
}

start();
