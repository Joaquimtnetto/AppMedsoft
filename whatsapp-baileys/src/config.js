import path from 'node:path'
import { fileURLToPath } from 'node:url'
import pino from 'pino'

const root = path.dirname(fileURLToPath(new URL('../server.js', import.meta.url)))
const apiToken = process.env.MEDSOFT_BAILEYS_TOKEN || 'r4n0n9iHK2b13XOfgOzGz7pO-s6Zt8zZd8zro5DlwuY'

if (!apiToken) throw new Error('MEDSOFT_BAILEYS_TOKEN é obrigatório.')

export const config = {
  host: process.env.MEDSOFT_BAILEYS_HOST || '127.0.0.1',
  port: Number(process.env.MEDSOFT_BAILEYS_PORT || process.env.PORT || 3001),
  apiToken,
  sessionsRoot: path.resolve(process.env.MEDSOFT_BAILEYS_SESSIONS || path.join(root, 'sessions')),
  historyRoot: path.resolve(process.env.MEDSOFT_BAILEYS_HISTORY || path.join(root, 'message-history')),
  logger: pino({ level: process.env.MEDSOFT_BAILEYS_LOG_LEVEL || 'info' })
}
