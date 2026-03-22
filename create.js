import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg
import fs from "fs"

async function run() {
    const { state } = await useMultiFileAuthState("auth")
    const sock = makeWASocket({ auth: state })

    const name = "Group"
    const numbers = []

    const res = await sock.groupCreate(name, numbers)

    if (fs.existsSync("dp.jpg")) {
        const img = fs.readFileSync("dp.jpg")
        await sock.updateProfilePicture(res.id, img)
    }
}

run()
