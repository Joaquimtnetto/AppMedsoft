import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizePhone, phoneJid } from '../src/whatsapp/phone.js'

test('normaliza e cria JID de telefone internacional', () => {
  assert.equal(normalizePhone('+55 (21) 99999-9999'), '5521999999999')
  assert.equal(phoneJid('5521999999999'), '5521999999999@s.whatsapp.net')
})

test('rejeita telefone inválido', () => {
  assert.throws(() => normalizePhone('1234'), /inválido/)
})
