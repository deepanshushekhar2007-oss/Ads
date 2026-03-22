import makeWASocket from "@whiskeysockets/baileys"
import { useMultiFileAuthState, fetchLatestBaileysVersion } from "@whiskeysockets/baileys"
import QRCode from "qrcode"
import fs from "fs"

async function start() {
    try {
        const { state, saveCreds } = await useMultiFileAuthState("./auth")

        const { version } = await fetchLatestBaileysVersion()

        const sock = makeWASocket({
            auth: state,
            version,
            printQRInTerminal: true
        })

        sock.ev.on("creds.update", saveCreds)

        sock.ev.on("connection.update", async (update) => {
            const { connection, qr } = update

            if (qr) {
                console.log("QR RECEIVED")
                const buffer = await QRCode.toBuffer(qr)
                fs.writeFileSync("qr.png", buffer)
            }

            if (connection === "open") {
                console.log("WhatsApp Connected")
            }

            if (connection === "close") {
                console.log("Connection closed")
            }
        })

    } catch (err) {
        console.log("WA ERROR:", err)
    }
}

start()
