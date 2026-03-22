import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

// Read links from file (Telegram bot will save them here)
let rawLinks = fs.existsSync('join_links.json') ? JSON.parse(fs.readFileSync('join_links.json')) : null;
if(!rawLinks || rawLinks.length === 0){
    console.log('❌ No links provided!');
    process.exit();
}

async function start() {
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

        let joinedGroups = [];

        for(let link of rawLinks){
            try {
                // Join group via invite link
                let res = await sock.groupAcceptInvite(link.split('/').pop());
                console.log(`✅ Joined group: ${res}`);
                joinedGroups.push(res);
            } catch(err){
                console.log(`❌ Failed to join ${link}:`, err.message);
            }
        }

        // Save joined groups for Telegram bot to read
        fs.writeFileSync('joined_groups.json', JSON.stringify(joinedGroups));
        console.log(`✅ Successfully joined ${joinedGroups.length} groups`);

    } catch(err) {
        console.error('Error in joining groups:', err);
        setTimeout(start, 5000);
    }
}

// Start
start();
