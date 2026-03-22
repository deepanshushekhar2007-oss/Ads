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

            if (qr) {
                const qrDataUrl = await qrcode.toDataURL(qr);
                console.log("QR_BASE64_START");
                console.log(qrDataUrl);
                console.log("QR_BASE64_END");

                // Save QR as image
                const base64Data = qrDataUrl.replace(/^data:image\/png;base64,/, "");
                fs.writeFileSync("qr.png", base64Data, "base64");
            }

            if (connection === 'close') {
                const reason = (lastDisconnect?.error)?.output?.statusCode;
                console.log('Connection closed, reason:', reason);
                if (reason !== DisconnectReason.loggedOut) {
                    console.log('Reconnecting...');
                    start();
                } else {
                    console.log('Logged out. Delete auth folder and login again.');
                }
            } else if (connection === 'open') {
                console.log('✅ WhatsApp connected');
            }
        });

        // ---------- Bulk group creator / other WA features ----------
        sock.ev.on('messages.upsert', async m => {
            // Placeholder: add your logic here
            // sock.groupCreate([...members], "Group Name")
            // sock.groupUpdate(groupId, { subject: "New Name", desc: "Description" })
            // sock.groupInvite(groupId, inviteCode)
            // sock.sendMessage(groupId, { image: fs.readFileSync("dp.jpg"), caption: "Group DP" })
            console.log('New message received', m);
        });

    } catch (err) {
        console.error('Error starting WA socket:', err);
        setTimeout(start, 5000);
    }
}

// Start
start();
