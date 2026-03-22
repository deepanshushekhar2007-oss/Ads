import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg
import qrcode from "qrcode-terminal"

async function startWA() {
    const { state, saveCreds } = await useMultiFileAuthState("auth")

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true
    })

    sock.ev.on("creds.update", saveCreds)

    sock.ev.on("connection.update", (update) => {
        if (update.connection === "open") {
            console.log("WA_CONNECTED")
        }
    })
}

startWA()
