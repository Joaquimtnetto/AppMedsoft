import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { SessionManager } from '../src/whatsapp/session-manager.js'


test('persiste mensagens recebidas e enviadas sem duplicar', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'medsoft-whatsapp-'))
  const logger = { warn() {}, error() {}, info() {}, child() { return this } }
  const manager = new SessionManager({
    sessionsRoot: path.join(root, 'sessions'),
    historyRoot: path.join(root, 'history'),
    logger
  })
  const entry = {
    id: '6', contacts: new Map(), receivedMessages: [], savePromise: Promise.resolve()
  }
  const messages = [
    {
      key: { id: 'IN-1', remoteJid: '5521999999999@s.whatsapp.net', fromMe: false },
      pushName: 'Paciente', messageTimestamp: 100,
      message: { conversation: 'Recebida' }
    },
    {
      key: { id: 'OUT-1', remoteJid: '5521999999999@s.whatsapp.net', fromMe: true },
      messageTimestamp: 101, message: { conversation: 'Enviada pelo celular' }
    }
  ]

  await manager.captureMessages(entry, { messages })
  await manager.captureMessages(entry, { messages })

  assert.equal(entry.receivedMessages.length, 2)
  assert.equal(entry.receivedMessages[0].direction, 'incoming')
  assert.equal(entry.receivedMessages[1].direction, 'outgoing')
  assert.deepEqual(await manager.loadMessages('6'), entry.receivedMessages)
  await fs.rm(root, { recursive: true, force: true })
})


test('converte LID para telefone ao capturar mensagens atuais', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'medsoft-whatsapp-lid-'))
  const logger = { warn() {}, error() {}, info() {}, debug() {}, child() { return this } }
  const manager = new SessionManager({
    sessionsRoot: path.join(root, 'sessions'),
    historyRoot: path.join(root, 'history'),
    logger
  })
  const entry = {
    id: '6', contacts: new Map(), receivedMessages: [], savePromise: Promise.resolve(),
    socket: {
      signalRepository: {
        lidMapping: {
          async getPNForLID(lid) {
            assert.equal(lid, '123456789@lid')
            return '5521987654321@s.whatsapp.net'
          }
        }
      }
    }
  }

  await manager.captureMessages(entry, { messages: [{
    key: { id: 'LID-1', remoteJid: '123456789@lid', fromMe: false },
    pushName: 'Paciente LID', messageTimestamp: 200,
    message: { conversation: 'Mensagem recente' }
  }] })

  assert.equal(entry.receivedMessages.length, 1)
  assert.equal(entry.receivedMessages[0].phone, '5521987654321')
  await fs.rm(root, { recursive: true, force: true })
})


test('reconstrói contatos a partir do histórico persistido', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'medsoft-whatsapp-contacts-'))
  const logger = { warn() {}, error() {}, info() {}, debug() {}, child() { return this } }
  const manager = new SessionManager({
    sessionsRoot: path.join(root, 'sessions'),
    historyRoot: path.join(root, 'history'),
    logger
  })
  await manager.saveMessages({
    id: '6', receivedMessages: [
      { id: '1', phone: '5521999999999', name: 'Paciente Um', text: 'A', timestamp: 1 },
      { id: '2', phone: '5521888888888', name: '', text: 'B', timestamp: 2 },
      { id: '3', phone: '5521999999999', name: '', text: 'C', timestamp: 3 }
    ]
  })
  const messages = await manager.loadMessages('6')
  const contacts = manager.restoreContacts(messages)

  assert.equal(contacts.size, 2)
  assert.equal(contacts.get('5521999999999@s.whatsapp.net').name, 'Paciente Um')
  await fs.rm(root, { recursive: true, force: true })
})


test('filtra a importação de mensagens por intervalo de data', async () => {
  const manager = new SessionManager({ logger: { warn() {}, error() {}, info() {} } })
  manager.sessions.set('6', {
    id: '6', receivedMessages: [
      { id: 'old', phone: '5521999999999', timestamp: 100 },
      { id: 'start', phone: '5521999999999', timestamp: 200 },
      { id: 'end', phone: '5521999999999', timestamp: 300 },
      { id: 'future', phone: '5521999999999', timestamp: 400 }
    ]
  })

  const result = await manager.messages('6', '', '200', '300')

  assert.deepEqual(result.messages.map(item => item.id), ['start', 'end'])
})


test('normaliza sufixo de dispositivo e propaga nome do contato ao histórico', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'medsoft-whatsapp-names-'))
  const manager = new SessionManager({
    sessionsRoot: path.join(root, 'sessions'), historyRoot: path.join(root, 'history'),
    logger: { warn() {}, error() {}, info() {}, debug() {} }
  })
  const entry = {
    id: '6', contacts: new Map(), receivedMessages: [
      { id: '1', phone: '5511999999999', name: '5511999999999', text: 'Olá', timestamp: 1 }
    ], savePromise: Promise.resolve()
  }

  const jid = await manager.resolvePhoneJid(entry, ['5511999999999:0@s.whatsapp.net'])
  await manager.updateContacts(entry, [{ id: jid, name: 'Maria Silva' }])

  assert.equal(jid, '5511999999999@s.whatsapp.net')
  assert.equal(entry.receivedMessages[0].name, 'Maria Silva')
  assert.equal((await manager.loadMessages('6'))[0].name, 'Maria Silva')
  await fs.rm(root, { recursive: true, force: true })
})
