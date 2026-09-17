import test from 'node:test'
import assert from 'node:assert/strict'
import { once } from 'node:events'
import { createApiServer } from '../src/http/api-server.js'

async function withServer(callback) {
  const manager = {
    status: async id => ({ success: true, connected: id === '8' }),
    sendText: async (id, phone, text) => ({ success: true, companyId: id, recipient: phone, text }),
    disconnect: async () => ({ success: true })
  }
  const server = createApiServer({ apiToken: 'test-token', host: '127.0.0.1', logger: { error() {} } }, manager)
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  try {
    await callback(`http://127.0.0.1:${server.address().port}`)
  } finally {
    server.close()
    await once(server, 'close')
  }
}

test('protege a API com token interno', async () => withServer(async base => {
  const response = await fetch(`${base}/sessions/8/status`)
  assert.equal(response.status, 401)
}))

test('encaminha envio de texto para a sessão da empresa', async () => withServer(async base => {
  const response = await fetch(`${base}/sessions/8/messages/text`, {
    method: 'POST',
    headers: { Authorization: 'Bearer test-token', 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone: '5521999999999', text: 'Olá' })
  })
  assert.equal(response.status, 200)
  const result = await response.json()
  assert.equal(result.companyId, '8')
  assert.equal(result.text, 'Olá')
}))
