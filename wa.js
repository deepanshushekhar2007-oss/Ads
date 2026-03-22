import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import qrcode from 'qrcode';

async function start() {
    const { version } = await fetchLatestBaileysVersion();
    const { state, saveCreds } = await useMultiFileAuthState('auth');

    const sock = makeWASocket({
        logger: P({ level: 'silent' }),
        printQRInTerminal: false,
        auth: state,
        version
    });

    sock.ev.on('creds.update', saveCreds);

    // Listen for connection updates
    sock.ev.on('connection.update', async (update) => {
        const { connection, qr, lastDisconnect } = update;

        if (qr) {
            // Convert QR to base64
            const qrDataUrl = await qrcode.toDataURL(qr);
            console.log("QR_BASE64_START");
            console.log(qrDataUrl);
            console.log("QR_BASE64_END");
        }

        if (connection === 'close') {
            const reason = (lastDisconnect.error)?.output?.statusCode;
            if (reason !== DisconnectReason.loggedOut) {
                start(); // reconnect
            }
        } else if (connection === 'open') {
            console.log('WhatsApp connected');
        }
    });

    // ---------- Bulk group creator ----------
    sock.ev.on('messages.upsert', async m => {
        // Add your group creation / join / add via VCF logic here
        // Use sock.groupCreate, sock.groupUpdate, sock.groupInvite, sock.sendMessage etc.
    });
}

start();
