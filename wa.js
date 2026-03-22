import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import qrcode from 'qrcode';

async function start() {
    try {
        // Fetch latest WA Web version
        const { version } = await fetchLatestBaileysVersion();

        // Auth state
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        // Create socket
        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false
        });

        // Save creds on update
        sock.ev.on('creds.update', saveCreds);

        // Connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            // 1️⃣ QR code event
            if (qr) {
                const qrDataUrl = await qrcode.toDataURL(qr);

                // Save as base64 text for Telegram bot
                console.log("QR_BASE64_START");
                console.log(qrDataUrl);
                console.log("QR_BASE64_END");

                // Also save as image for preview
                const base64Data = qrDataUrl.replace(/^data:image\/png;base64,/, "");
                fs.writeFileSync("qr.png", base64Data, "base64");
            }

            // 2️⃣ Connection closed
            if (connection === 'close') {
                const reason = lastDisconnect?.error?.output?.statusCode;
                console.log('Connection closed, reason:', reason);
                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting in 5s...');
                    setTimeout(start, 5000);
                } else {
                    console.log('Logged out. Delete auth folder and login again.');
                }
            }

            // 3️⃣ Connection open
            else if (connection === 'open') {
                console.log('✅ WhatsApp connected');

                // Create a flag file to inform Telegram bot
                fs.writeFileSync("wa_connected.flag", "connected");
            }
        });

        // ---------- Bulk group creator / add members / join via link ----------
        sock.ev.on('messages.upsert', async m => {
            console.log('New message received', m);
            // TODO: Add your WA features here
            // sock.groupCreate([...members], "Group Name")
            // sock.groupUpdate(groupId, { subject: "New Name", desc: "Description" })
            // sock.groupInvite(groupId, inviteCode)
            // sock.sendMessage(groupId, { image: fs.readFileSync("dp.jpg"), caption: "Group DP" })
        });

    } catch (err) {
        console.error('Error starting WA socket:', err);
        setTimeout(start, 5000);
    }
}

// Start the bot
start();
