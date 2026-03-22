import pkg from "@whiskeysockets/baileys"
const { default: makeWASocket, useMultiFileAuthState } = pkg

const link = process.argv[2]

async function run() {
    const { state } = await useMultiFileAuthState("auth")
    const sock = makeWASocket({ auth: state })

    const code = link.split("https://chat.whatsapp.com/")[1]
    await sock.groupAcceptInvite(code)
}

run()
