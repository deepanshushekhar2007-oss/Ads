import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import qrcode from 'qrcode';

let socketInstance = null; // Keep a single socket instance

async function start() {
    try {
        // 1️⃣ Fetch latest WA Web version
        const { version } = await fetchLatestBaileysVersion();

        // 2️⃣ Multi-file auth state
        const { state, saveCreds } = await useMultiFileAuthState('auth');

        // 3️⃣ Create WhatsApp socket only if not already running
        if (socketInstance) return socketInstance;

        const sock = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false,
            patchMessageBeforeSending: (msg) => {
                if (msg?.extendedTextMessage?.contextInfo) delete msg.extendedTextMessage.contextInfo;
                return msg;
            }
        });

        socketInstance = sock;

        // 4️⃣ Save credentials on update
        sock.ev.on('creds.update', saveCreds);

        // 5️⃣ Connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr, me } = update;

            // 🔹 QR received
            if (qr) {
                const qrDataUrl = await qrcode.toDataURL(qr);

                console.log("QR_BASE64_START");
                console.log(qrDataUrl);
                console.log("QR_BASE64_END");

                const base64Data = qrDataUrl.replace(/^data:image\/png;base64,/, "");
                fs.writeFileSync("qr.png", base64Data, "base64");
            }

            // 🔹 Connection closed
            if (connection === 'close') {
                const reason = lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.message;
                console.log('Connection closed, reason:', reason);

                if (reason !== DisconnectReason.loggedOut && reason !== 401) {
                    console.log('Reconnecting in 10 seconds...');
                    socketInstance = null;
                    setTimeout(start, 10000);
                } else {
                    console.log('Logged out. Delete auth folder and login again.');
                    socketInstance = null;
                }
            }

            // 🔹 Connection open
            else if (connection === 'open') {
                console.log('✅ WhatsApp connected');

                const userNumber = me?.user || "unknown";
                fs.writeFileSync("wa_connected.flag", userNumber);
            }
        });

        // 6️⃣ Handle incoming messages (placeholder for future features)
        sock.ev.on('messages.upsert', async (m) => {
            console.log('New message received:', m);
        });

        return sock;

    } catch (err) {
        console.error('Error starting WA socket:', err);
        console.log('Retrying in 10 seconds...');
        socketInstance = null;
        setTimeout(start, 10000);
    }
}

// Start WhatsApp bot
start();
