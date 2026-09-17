import { createApiServer } from './src/http/api-server.js'
import { config } from './src/config.js'
import { SessionManager } from './src/whatsapp/session-manager.js'

const manager = new SessionManager(config)
const server = createApiServer(config, manager)

server.listen(config.port, config.host, () => {
  config.logger.info(`Serviço WhatsApp disponível em http://${config.host}:${config.port}`)
})

async function shutdown(signal) {
  config.logger.info({ signal }, 'Encerrando serviço WhatsApp')
  server.close()
  await manager.closeAll()
  process.exit(0)
}

process.on('SIGTERM', () => shutdown('SIGTERM'))
process.on('SIGINT', () => shutdown('SIGINT'))
