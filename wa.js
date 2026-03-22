import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg
import QRCode from "qrcode"
import fs from "fs"

async function start() {
    const { state, saveCreds } = await useMultiFileAuthState("auth")

    const sock = makeWASocket({ auth: state })

    sock.ev.on("creds.update", saveCreds)

    sock.ev.on("connection.update", async ({ qr }) => {
        if (qr) {
            const img = await QRCode.toBuffer(qr)
            fs.writeFileSync("qr.png", img)
        }
    })
}

start()
