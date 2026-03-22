import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import qrcode from 'qrcode';

async function start() {
    try {
        // 1️⃣ Fetch latest WA Web version
        const { version } = await fetchLatestBaileysVersion();

        // 2️⃣ Multi-file auth state (auth folder)
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        // 3️⃣ Create WhatsApp socket
        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false
        });

        // 4️⃣ Save credentials on update
        sock.ev.on('creds.update', saveCreds);

        // 5️⃣ Connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr, me } = update;

            // 🔹 QR received
            if (qr) {
                const qrDataUrl = await qrcode.toDataURL(qr);

                // Save QR as base64 for Telegram bot
                console.log("QR_BASE64_START");
                console.log(qrDataUrl);
                console.log("QR_BASE64_END");

                // Also save PNG for Telegram photo
                const base64Data = qrDataUrl.replace(/^data:image\/png;base64,/, "");
                fs.writeFileSync("qr.png", base64Data, "base64");
            }

            // 🔹 Connection closed
            if (connection === 'close') {
                const reason = lastDisconnect?.error?.output?.statusCode;
                console.log('Connection closed, reason:', reason);

                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting in 5 seconds...');
                    setTimeout(start, 5000);
                } else {
                    console.log('Logged out. Delete auth folder and login again.');
                }
            }

            // 🔹 Connection open
            else if (connection === 'open') {
                console.log('✅ WhatsApp connected');

                // Create a flag file for Telegram bot
                const userNumber = me?.user || "unknown";
                fs.writeFileSync("wa_connected.flag", userNumber);
            }
        });

        // 6️⃣ Handle incoming messages (placeholder for future features)
        sock.ev.on('messages.upsert', async m => {
            console.log('New message received:', m);
            // Example placeholders for group automation:
            // sock.groupCreate([...members], "Group Name")
            // sock.groupUpdate(groupId, { subject: "New Name", desc: "Description" })
            // sock.groupInvite(groupId, inviteCode)
            // sock.sendMessage(groupId, { image: fs.readFileSync("dp.jpg"), caption: "Group DP" })
        });

    } catch (err) {
        console.error('Error starting WA socket:', err);
        console.log('Retrying in 5 seconds...');
        setTimeout(start, 5000);
    }
}

// Start WhatsApp bot
start();
