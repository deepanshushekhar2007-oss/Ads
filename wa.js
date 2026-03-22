import makeWASocket, { 
    useMultiFileAuthState,
    fetchLatestBaileysVersion
} from "@whiskeysockets/baileys"

import QRCode from "qrcode"
import fs from "fs"

async function start() {

    const { state, saveCreds } = await useMultiFileAuthState("auth")

    const { version } = await fetchLatestBaileysVersion()

    const sock = makeWASocket({
        auth: state,
        version,
        printQRInTerminal: false
    })

    sock.ev.on("creds.update", saveCreds)

    sock.ev.on("connection.update", async (update) => {
        const { qr, connection } = update

        if (qr) {
            console.log("QR RECEIVED")

            try {
                const buffer = await QRCode.toBuffer(qr)
                fs.writeFileSync("qr.png", buffer)
            } catch (e) {
                console.log("QR error:", e)
            }
        }

        if (connection === "open") {
            console.log("WhatsApp Connected")
        }

        if (connection === "close") {
            console.log("Connection closed")
        }
    })
}

start()
