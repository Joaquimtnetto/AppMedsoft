import path from 'node:path'
import fs from 'node:fs/promises'
import QRCode from 'qrcode'
import makeWASocket, {
  Browsers,
  DisconnectReason,
  useMultiFileAuthState
} from '@whiskeysockets/baileys'
import { phoneJid } from './phone.js'

export class SessionManager {
  constructor(config) {
    this.config = config
    this.sessions = new Map()
  }

  validateId(value) {
    const id = String(value || '')
    if (!/^\d+$/.test(id) || Number(id) <= 0) {
      throw Object.assign(new Error('Empresa inválida.'), { statusCode: 400 })
    }
    return id
  }

  authDirectory(id) {
    return path.join(this.config.sessionsRoot, `empresa-${this.validateId(id)}`)
  }

  historyFile(id) {
    return path.join(this.config.historyRoot, `empresa-${this.validateId(id)}.json`)
  }

  async loadMessages(id) {
    try {
      const content = await fs.readFile(this.historyFile(id), 'utf8')
      const messages = JSON.parse(content)
      return Array.isArray(messages) ? messages.slice(-5000) : []
    } catch (error) {
      if (error.code !== 'ENOENT') this.config.logger.warn({ companyId: id, error }, 'Falha ao carregar histórico')
      return []
    }
  }

  async saveMessages(entry) {
    await fs.mkdir(this.config.historyRoot, { recursive: true })
    const target = this.historyFile(entry.id)
    const temporary = `${target}.tmp`
    await fs.writeFile(temporary, JSON.stringify(entry.receivedMessages.slice(-5000)), 'utf8')
    await fs.rename(temporary, target)
  }

  restoreContacts(messages = []) {
    const contacts = new Map()
    for (const message of messages) {
      const phone = String(message?.phone || '').replace(/\D/g, '')
      if (!phone) continue
      const jid = `${phone}@s.whatsapp.net`
      const current = contacts.get(jid)
      contacts.set(jid, {
        jid,
        phone,
        name: message?.name || current?.name || phone,
        source: 'history'
      })
    }
    return contacts
  }

  publicState(entry) {
    return {
      success: true,
      status: entry?.status || 'starting',
      qr: entry?.qr || null,
      connected: entry?.status === 'connected',
      phone: entry?.phone || null,
      syncingHistory: !!entry?.syncingHistory,
      pendingNotificationsReceived: !!entry?.pendingNotificationsReceived,
      message: entry?.message || ''
    }
  }

  async status(companyId) {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id) || await this.connect(id)
    return this.publicState(entry)
  }

  async connect(companyId) {
    const id = this.validateId(companyId)
    let entry = this.sessions.get(id)
    if (entry?.starting || entry?.socket) return entry

    const receivedMessages = await this.loadMessages(id)
    const restoredContacts = this.restoreContacts(receivedMessages)

    entry = {
      id, status: 'starting', qr: null, message: 'Iniciando conexão...',
      starting: true, socket: null, reconnectTimer: null, phone: null,
      contacts: restoredContacts, receivedMessages,
      syncingHistory: true, pendingNotificationsReceived: false,
      historyLatest: false, messageStore: new Map(),
      savePromise: Promise.resolve()
    }
    this.sessions.set(id, entry)

    try {
      const directory = this.authDirectory(id)
      await fs.mkdir(directory, { recursive: true })
      const { state, saveCreds } = await useMultiFileAuthState(directory)
      const socket = makeWASocket({
        auth: state,
        browser: Browsers.ubuntu('Chrome'),
        printQRInTerminal: false,
        markOnlineOnConnect: false,
        syncFullHistory: true,
        shouldSyncHistoryMessage: () => true,
        getMessage: async key => entry.messageStore.get(`${key?.remoteJid || ''}:${key?.id || ''}`),
        logger: this.config.logger.child({ companyId: id })
      })
      entry.socket = socket
      entry.starting = false
      socket.ev.on('creds.update', saveCreds)
      socket.ev.on('connection.update', update => this.onConnectionUpdate(entry, update))
      socket.ev.on('contacts.upsert', contacts => {
        this.updateContacts(entry, contacts).catch(error => this.config.logger.error({ companyId: id, error }, 'Falha ao atualizar contatos'))
      })
      socket.ev.on('contacts.update', contacts => {
        this.updateContacts(entry, contacts).catch(error => this.config.logger.error({ companyId: id, error }, 'Falha ao atualizar contatos'))
      })
      socket.ev.on('messages.upsert', event => {
        this.captureMessages(entry, event).catch(error => this.config.logger.error({ companyId: id, error }, 'Falha ao registrar mensagens'))
      })
      socket.ev.on('messaging-history.set', async history => {
        await this.updateContacts(entry, history.contacts || [])
        this.updateChats(entry, history.chats || [])
        await this.captureMessages(entry, { messages: history.messages || [] })
        if (history.isLatest === true) entry.historyLatest = true
        this.config.logger.info({
          companyId: id,
          syncType: history.syncType,
          messages: (history.messages || []).length,
          contacts: (history.contacts || []).length
        }, 'Histórico WhatsApp processado')
      })
      return entry
    } catch (error) {
      entry.starting = false
      entry.socket = null
      entry.status = 'error'
      entry.message = error.message || 'Falha ao iniciar o WhatsApp.'
      throw error
    }
  }

  async resolvePhoneJid(entry, candidates = []) {
    const values = candidates.filter(Boolean).map(value => String(value))
    const direct = values.find(jid => jid.endsWith('@s.whatsapp.net'))
    if (direct) return `${direct.split('@')[0].split(':')[0]}@s.whatsapp.net`
    const lid = values.find(jid => jid.endsWith('@lid'))
    if (!lid || !entry.socket?.signalRepository?.lidMapping) return ''
    try {
      const mapped = await entry.socket.signalRepository.lidMapping.getPNForLID(lid) || ''
      return mapped ? `${mapped.split('@')[0].split(':')[0]}@s.whatsapp.net` : ''
    } catch (error) {
      this.config.logger.debug({ companyId: entry.id, lid, error }, 'LID ainda não possui telefone associado')
      return ''
    }
  }

  async updateContacts(entry, contacts = []) {
    let messagesChanged = false
    for (const contact of contacts) {
      const jid = await this.resolvePhoneJid(entry, [
        contact?.jid, contact?.phoneNumber, contact?.id, contact?.lid, contact?.lidJid
      ])
      if (!jid) continue
      const phone = jid.split('@')[0].split(':')[0]
      const candidateName = contact.notify || contact.name || contact.verifiedName || contact.pushName || ''
      const name = candidateName && candidateName !== phone ? candidateName : (entry.contacts.get(jid)?.name || phone)
      entry.contacts.set(jid, {
        jid,
        phone,
        name
      })
      if (name && name !== phone) {
        for (const message of entry.receivedMessages) {
          if (message.phone === phone && (!message.name || message.name === phone)) {
            message.name = name
            messagesChanged = true
          }
        }
      }
    }
    if (messagesChanged) {
      entry.savePromise = entry.savePromise.catch(() => undefined).then(() => this.saveMessages(entry))
      await entry.savePromise
    }
  }

  updateChats(entry, chats = []) {
    for (const chat of chats) {
      const rawJid = String(chat?.id || '')
      if (!rawJid.endsWith('@s.whatsapp.net')) continue
      const jid = `${rawJid.split('@')[0].split(':')[0]}@s.whatsapp.net`
      const current = entry.contacts.get(jid)
      entry.contacts.set(jid, {
        jid,
        phone: jid.split('@')[0],
        name: chat.name || current?.name || jid.split('@')[0]
      })
    }
  }

  async captureMessages(entry, event = {}) {
    let changed = false
    if (!entry.messageStore) entry.messageStore = new Map()
    for (const item of event.messages || []) {
      const jid = await this.resolvePhoneJid(entry, [
        item?.key?.remoteJidAlt,
        item?.key?.participantAlt,
        item?.key?.remoteJid,
        item?.key?.participant
      ])
      if (!jid) continue
      const current = entry.contacts.get(jid)
      entry.contacts.set(jid, {
        jid, phone: jid.split('@')[0],
        name: item.pushName || current?.name || jid.split('@')[0]
      })
      const message = item.message || {}
      if (item?.key?.id && item?.key?.remoteJid && item.message) {
        entry.messageStore.set(`${item.key.remoteJid}:${item.key.id}`, item.message)
        while (entry.messageStore.size > 1000) entry.messageStore.delete(entry.messageStore.keys().next().value)
      }
      const text = message.conversation || message.extendedTextMessage?.text ||
        message.imageMessage?.caption || message.videoMessage?.caption || ''
      if (!text) continue
      const messageId = item.key.id || ''
      const phone = jid.split('@')[0].split(':')[0]
      const contactName = item.pushName || current?.name || ''
      const savedMessage = messageId
        ? entry.receivedMessages.find(saved => saved.id === messageId && saved.phone === phone)
        : null
      if (savedMessage) {
        if (!savedMessage.name && contactName) {
          savedMessage.name = contactName
          changed = true
        }
        continue
      }
      entry.receivedMessages.push({
        id: messageId, phone, name: contactName, text,
        timestamp: Number(item.messageTimestamp || Math.floor(Date.now() / 1000)),
        direction: item.key.fromMe ? 'outgoing' : 'incoming'
      })
      changed = true
    }
    entry.receivedMessages.sort((left, right) => Number(left.timestamp || 0) - Number(right.timestamp || 0))
    if (entry.receivedMessages.length > 5000) entry.receivedMessages.splice(0, entry.receivedMessages.length - 5000)
    if (changed) {
      entry.savePromise = entry.savePromise
        .catch(() => undefined)
        .then(() => this.saveMessages(entry))
      await entry.savePromise
    }
  }

  async contacts(companyId) {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id) || await this.connect(id)
    const contacts = Array.from(entry.contacts.values())
    const connectedPhone = String(entry.socket?.user?.id || '').split(':')[0].split('@')[0]
    if (connectedPhone && !contacts.some(item => item.phone === connectedPhone)) {
      contacts.unshift({ jid: `${connectedPhone}@s.whatsapp.net`, phone: connectedPhone, name: 'Telefone conectado' })
    }
    return { success: true, contacts: contacts.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR')) }
  }

  async messages(companyId, phone = '', from = '', to = '') {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id) || await this.connect(id)
    const digits = String(phone || '').replace(/\D/g, '')
    const start = Number(from)
    const end = Number(to)
    const messages = entry.receivedMessages.filter(item => {
      const matchesPhone = !digits || item.phone === digits || item.phone.endsWith(digits)
      const timestamp = Number(item.timestamp || 0)
      const matchesStart = !Number.isFinite(start) || start <= 0 || timestamp >= start
      const matchesEnd = !Number.isFinite(end) || end <= 0 || timestamp <= end
      return matchesPhone && matchesStart && matchesEnd
    })
    return { success: true, messages }
  }

  async onConnectionUpdate(entry, { connection, qr, lastDisconnect, receivedPendingNotifications }) {
    if (receivedPendingNotifications === true) {
      entry.pendingNotificationsReceived = true
      entry.syncingHistory = false
      if (entry.status === 'connected') entry.message = 'WhatsApp conectado e mensagens sincronizadas.'
    }
    if (qr) {
      entry.qr = await QRCode.toDataURL(qr, { width: 320, margin: 2 })
      entry.status = 'qr'
      entry.message = 'Leia o QR Code pelo WhatsApp do celular.'
    }
    if (connection === 'open') {
      entry.qr = null
      const rawPhone = String(entry.socket?.user?.id || '').split(':')[0].split('@')[0]
      entry.phone = rawPhone ? this.formatPhone(rawPhone) : null
      entry.status = 'connected'
      entry.syncingHistory = !entry.pendingNotificationsReceived
      entry.message = entry.syncingHistory ? 'WhatsApp conectado. Sincronizando mensagens...' : 'WhatsApp conectado.'
      this.config.logger.info({ companyId: entry.id }, 'WhatsApp conectado')
    }
    if (connection !== 'close') return

    entry.socket = null
    entry.qr = null
    const code = lastDisconnect?.error?.output?.statusCode
    const disconnectMessage = lastDisconnect?.error?.message || 'Motivo não informado.'
    this.config.logger.warn(
      { companyId: entry.id, code, error: lastDisconnect?.error },
      'Conexão WhatsApp encerrada'
    )
    if (code === DisconnectReason.loggedOut) {
      entry.status = 'disconnected'
      entry.message = 'WhatsApp desconectado. Gere um novo QR Code.'
      return
    }
    entry.status = 'reconnecting'
    entry.message = `Reconectando ao WhatsApp... (${code || 'sem código'}: ${disconnectMessage})`
    clearTimeout(entry.reconnectTimer)
    entry.reconnectTimer = setTimeout(() => {
      this.connect(entry.id).catch(error => this.config.logger.error(error))
    }, 2000)
  }

  formatPhone(value) {
    const digits = String(value || '').replace(/\D/g, '')
    if (digits.startsWith('55') && digits.length >= 12) {
      const local = digits.slice(2)
      const numberStart = local.length === 11 ? 7 : 6
      return `+55 (${local.slice(0, 2)}) ${local.slice(2, numberStart)}-${local.slice(numberStart)}`
    }
    return digits ? `+${digits}` : ''
  }

  async sendText(companyId, phone, text) {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id) || await this.connect(id)
    if (entry.status !== 'connected' || !entry.socket) {
      throw Object.assign(new Error('WhatsApp da empresa não está conectado.'), { statusCode: 409 })
    }
    const message = String(text || '').trim()
    if (!message) throw Object.assign(new Error('A mensagem está vazia.'), { statusCode: 400 })
    if (message.length > 10000) throw Object.assign(new Error('A mensagem excede o limite permitido.'), { statusCode: 400 })

    const jid = phoneJid(phone)
    const [availability] = await entry.socket.onWhatsApp(jid)
    if (!availability?.exists) {
      throw Object.assign(new Error('O número informado não possui WhatsApp.'), { statusCode: 400 })
    }
    const result = await entry.socket.sendMessage(jid, { text: message })
    if (result?.key?.id && result?.key?.remoteJid && result.message) {
      entry.messageStore.set(`${result.key.remoteJid}:${result.key.id}`, result.message)
    }
    return {
      success: true,
      status: 'sent',
      messageId: result?.key?.id || null,
      recipient: jid.split('@')[0],
      message: 'Mensagem enviada pelo WhatsApp.'
    }
  }

  async disconnect(companyId) {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id)
    clearTimeout(entry?.reconnectTimer)
    if (entry?.socket) await entry.socket.logout()
    this.sessions.delete(id)
    await fs.rm(this.authDirectory(id), { recursive: true, force: true })
    return { success: true, status: 'disconnected', connected: false, qr: null, message: 'WhatsApp desconectado.' }
  }

  async reset(companyId) {
    const id = this.validateId(companyId)
    const entry = this.sessions.get(id)
    clearTimeout(entry?.reconnectTimer)
    if (entry?.socket) entry.socket.end(undefined)
    this.sessions.delete(id)
    await fs.rm(this.authDirectory(id), { recursive: true, force: true })
    const fresh = await this.connect(id)
    return this.publicState(fresh)
  }

  async closeAll() {
    for (const entry of this.sessions.values()) {
      clearTimeout(entry.reconnectTimer)
      entry.socket?.end(undefined)
    }
    this.sessions.clear()
  }
}
