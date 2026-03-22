import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg
import fs from "fs"

const link = process.argv[2]

function parseVCF() {
    const data = fs.readFileSync("contacts.vcf", "utf-8")
    const numbers = []

    const matches = data.match(/TEL[^:]*:(.+)/g)

    matches.forEach(m => {
        const num = m.split(":")[1].replace(/\D/g, "")
        numbers.push(num + "@s.whatsapp.net")
    })

    return numbers
}

async function run() {
    const { state } = await useMultiFileAuthState("auth")
    const sock = makeWASocket({ auth: state })

    const code = link.split("https://chat.whatsapp.com/")[1]
    const gid = await sock.groupAcceptInvite(code)

    const numbers = parseVCF()

    for (let n of numbers) {
        try {
            await sock.groupParticipantsUpdate(gid, [n], "add")
            await new Promise(r => setTimeout(r, 4000))
        } catch {}
    }
}

run()
