import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg

import QRCode from "qrcode"
import fs from "fs"

async function start() {

    const { state, saveCreds } = await useMultiFileAuthState("auth")

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false
    })

    sock.ev.on("creds.update", saveCreds)

    sock.ev.on("connection.update", async (update) => {

        const { connection, qr } = update

        if (qr) {
            console.log("QR RECEIVED")

            try {
                const buffer = await QRCode.toBuffer(qr)
                fs.writeFileSync("qr.png", buffer)
            } catch (e) {
                console.log("QR error", e)
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
