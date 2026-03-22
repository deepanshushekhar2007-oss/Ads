import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import vcf from 'vcf';

async function start(groupInviteLink) {
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
                    setTimeout(() => start(groupInviteLink), 5000);
                }
            } else if (connection === 'open') {
                console.log('✅ WhatsApp connected');

                // Load VCF
                const vcfData = fs.readFileSync('contacts.vcf', 'utf-8');
                const contacts = new vcf().parse(vcfData);

                const numbers = contacts.map(c => {
                    if (c.get('TEL')) return c.get('TEL').valueOf().replace(/\D/g, '') + "@s.whatsapp.net";
                }).filter(Boolean);

                console.log(`Total contacts to add: ${numbers.length}`);

                // Accept group invite
                const groupMeta = await sock.groupAcceptInvite(groupInviteLink);
                console.log(`Joined group: ${groupMeta}`);

                // Add members one by one
                for (const num of numbers) {
                    try {
                        await sock.groupAdd(groupMeta, [num]);
                        console.log(`✅ Added ${num}`);
                    } catch (err) {
                        console.log(`❌ Failed to add ${num}`, err.message);
                    }
                }

                fs.writeFileSync("add_done.flag", `Added ${numbers.length} contacts to group`);
            }
        });
    } catch (err) {
        console.error('Error in add.js:', err);
        setTimeout(() => start(groupInviteLink), 5000);
    }
}

// Get group invite link from command line
const groupInviteLink = process.argv[2];
if (!groupInviteLink) {
    console.log('❌ No group invite link provided!');
    process.exit(1);
}

start(groupInviteLink);
