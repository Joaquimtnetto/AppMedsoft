import http from 'node:http'

function sendJson(response, status, body) {
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  })
  response.end(JSON.stringify(body))
}

async function readJson(request) {
  const chunks = []
  let size = 0
  for await (const chunk of request) {
    size += chunk.length
    if (size > 1024 * 1024) throw Object.assign(new Error('Requisição muito grande.'), { statusCode: 413 })
    chunks.push(chunk)
  }
  if (!chunks.length) return {}
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw Object.assign(new Error('JSON inválido.'), { statusCode: 400 })
  }
}

export function createApiServer(config, manager) {
  return http.createServer(async (request, response) => {
    if (request.headers.authorization !== `Bearer ${config.apiToken}`) {
      return sendJson(response, 401, { success: false, message: 'Não autorizado.' })
    }
    const pathname = new URL(request.url, `http://${config.host}`).pathname
    if (request.method === 'GET' && pathname === '/health') {
      return sendJson(response, 200, { success: true, service: 'medsoft-whatsapp', status: 'ok' })
    }
    if (request.method === 'POST' && pathname === '/service/stop') {
      sendJson(response, 200, { success: true, message: 'Serviço WhatsApp será reiniciado.' })
      setTimeout(() => process.kill(process.pid, 'SIGTERM'), 100)
      return
    }
    const match = pathname.match(/^\/sessions\/(\d+)\/(status|disconnect|reset|contacts|messages\/received|messages\/text)$/)
    if (!match) return sendJson(response, 404, { success: false, message: 'Rota não encontrada.' })

    try {
      const companyId = match[1]
      if (request.method === 'GET' && match[2] === 'status') {
        return sendJson(response, 200, await manager.status(companyId))
      }
      if (request.method === 'GET' && match[2] === 'contacts') {
        return sendJson(response, 200, await manager.contacts(companyId))
      }
      if (request.method === 'GET' && match[2] === 'messages/received') {
        const searchParams = new URL(request.url, `http://${config.host}`).searchParams
        const phone = searchParams.get('phone') || ''
        const from = searchParams.get('from') || ''
        const to = searchParams.get('to') || ''
        return sendJson(response, 200, await manager.messages(companyId, phone, from, to))
      }
      if (request.method === 'POST' && match[2] === 'disconnect') {
        return sendJson(response, 200, await manager.disconnect(companyId))
      }
      if (request.method === 'POST' && match[2] === 'reset') {
        return sendJson(response, 200, await manager.reset(companyId))
      }
      if (request.method === 'POST' && match[2] === 'messages/text') {
        const body = await readJson(request)
        return sendJson(response, 200, await manager.sendText(companyId, body.phone, body.text))
      }
      return sendJson(response, 405, { success: false, message: 'Método não permitido.' })
    } catch (error) {
      config.logger.error(error)
      return sendJson(response, error.statusCode || 500, {
        success: false,
        message: error.message || 'Erro interno.'
      })
    }
  })
}
