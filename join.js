import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

async function start(links) {
    try {
        const { version } = await fetchLatestBaileysVersion();
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect } = update;

            if (connection === 'close') {
                const reason = lastDisconnect?.error?.output?.statusCode;
                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting in 5s...');
                    setTimeout(() => start(links), 5000);
                }
            } else if (connection === 'open') {
                console.log('✅ WhatsApp connected');

                let joinedCount = 0;

                for (const link of links) {
                    try {
                        const result = await sock.groupAcceptInvite(link);
                        console.log(`✅ Joined group: ${result}`);
                        joinedCount++;
                    } catch (err) {
                        console.log(`❌ Failed to join group link: ${link}`, err.message);
                    }
                }

                console.log(`🎯 Total groups joined: ${joinedCount}`);

                // Create a joined flag file for Telegram bot notification
                fs.writeFileSync("join_done.flag", `Joined ${joinedCount} group(s)`);
            }
        });
    } catch (err) {
        console.error('Error in join.js:', err);
        setTimeout(() => start(links), 5000);
    }
}

// Get links from command line arguments
const links = process.argv.slice(2);
if (!links.length) {
    console.log('❌ No group links provided!');
    process.exit(1);
}

start(links);
