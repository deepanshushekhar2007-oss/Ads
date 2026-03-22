import { makeWASocket, fetchLatestBaileysVersion, useSingleFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import qrcode from 'qrcode';

// Use single-file auth state for stability
const { state, saveCreds } = useSingleFileAuthState('auth.json');

let socket;

async function start() {
    try {
        const { version } = await fetchLatestBaileysVersion();

        socket = makeWASocket({
            logger: P({ level: 'silent' }),
            auth: state,
            version,
            printQRInTerminal: false
        });

        socket.ev.on('creds.update', saveCreds);

        // Connection update
        socket.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr, me } = update;

            // QR received
            if (qr) {
                const qrDataUrl = await qrcode.toDataURL(qr);
                fs.writeFileSync("qr.png", qrDataUrl.replace(/^data:image\/png;base64,/, ""), "base64");
                console.log("QR generated. Scan within 30 seconds!");
                console.log("QR_BASE64_START\n" + qrDataUrl + "\nQR_BASE64_END");
            }

            // Connection closed
            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                console.log('Connection closed, reason:', statusCode);

                if (statusCode === DisconnectReason.loggedOut) {
                    console.log('❌ Logged out. Delete auth.json and login again.');
                    fs.unlinkSync('auth.json'); // remove old auth
                } else {
                    console.log('🔄 Reconnecting in 5s...');
                    setTimeout(() => start(), 5000); // retry
                }
            }

            // Connection open
            if (connection === 'open') {
                console.log('✅ WhatsApp connected');
                const userNumber = me?.user || 'unknown';
                fs.writeFileSync("wa_connected.flag", userNumber); // inform Telegram bot
            }
        });

        // Keep-alive ping every 25s to avoid session expiry
        setInterval(() => {
            if (socket?.ws.readyState === 1) {
                socket?.sendPresenceUpdate('available');
            }
        }, 25000);

        // Messages placeholder
        socket.ev.on('messages.upsert', (m) => {
            console.log('New message:', m);
        });

    } catch (err) {
        console.error('Error in WhatsApp bot:', err);
        setTimeout(start, 5000);
    }
}

// Start bot
start();
