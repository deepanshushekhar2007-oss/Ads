import { makeWASocket, fetchLatestBaileysVersion, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import fs from 'fs';
import P from 'pino';
import vcf from 'vcf';

// Read invite link from file (Telegram bot saves it here)
let inviteLink = fs.existsSync('vcf_invite_link.txt') ? fs.readFileSync('vcf_invite_link.txt', 'utf-8').trim() : null;
if(!inviteLink){
    console.log('❌ No invite link provided!');
    process.exit();
}

// Read contacts from VCF
if(!fs.existsSync('contacts.vcf')){
    console.log('❌ VCF file not found!');
    process.exit();
}

const contactsVCF = fs.readFileSync('contacts.vcf', 'utf-8');
const parsedContacts = new vcf().parse(contactsVCF); // array of contacts

// Extract numbers in international format
const numbers = parsedContacts.map(c => {
    if(c.tel){
        let t = Array.isArray(c.tel) ? c.tel[0].valueOf() : c.tel.valueOf();
        return t.replace(/[^0-9]/g,''); // remove non-digit chars
    }
}).filter(Boolean);

async function start(){
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

        let addedMembers = [];

        for(let num of numbers){
            try {
                // WhatsApp requires @s.whatsapp.net format
                let jid = `${num}@s.whatsapp.net`;
                await sock.groupAdd(inviteLink.split('/').pop(), [jid]);
                console.log(`✅ Added: ${jid}`);
                addedMembers.push(jid);
                await new Promise(r => setTimeout(r, 1500)); // avoid spam
            } catch(err){
                console.log(`❌ Failed to add ${num}: ${err.message}`);
            }
        }

        // Save result for Telegram bot
        fs.writeFileSync('added_members.json', JSON.stringify(addedMembers));
        console.log(`✅ Successfully added ${addedMembers.length} members`);

    } catch(err){
        console.error('Error in adding members:', err);
        setTimeout(start, 5000);
    }
}

// Start
start();
