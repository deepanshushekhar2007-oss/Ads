import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';

async function start() {
    try {
        // 1️⃣ Read group links sent by Telegram
        if (!fs.existsSync('join_links.txt')) {
            console.log('❌ No links found!');
            return;
        }

        let rawLinks = fs.readFileSync('join_links.txt', 'utf-8');
        let links = rawLinks.split(/[\n,]+/).map(l => l.trim()).filter(Boolean);

        if (links.length === 0) {
            console.log('❌ No valid links found');
            return;
        }

        // 2️⃣ Connect to WhatsApp
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
                console.log('Connection closed, reason:', reason);
                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting in 5s...');
                    setTimeout(start, 5000);
                }
            } else if (connection === 'open') {
                console.log('✅ WhatsApp connected');
            }
        });

        // 3️⃣ Join groups one by one
        let success = 0;
        let failed = 0;

        for (let link of links) {
            try {
                const result = await sock.groupAcceptInvite(link.replace('https://chat.whatsapp.com/', ''));
                console.log(`✅ Joined group: ${result}`);
                success++;
            } catch (err) {
                console.error(`❌ Failed to join: ${link}`, err.message || err);
                failed++;
            }
        }

        // 4️⃣ Save summary for Telegram bot
        const summary = {
            total: links.length,
            joined: success,
            failed: failed
        };

        fs.writeFileSync('join_summary.json', JSON.stringify(summary));
        console.log('🎯 Join summary:', summary);

    } catch (err) {
        console.error('Error in join.js:', err);
        setTimeout(start, 5000);
    }
}

start();
