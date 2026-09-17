export function normalizePhone(value) {
  const phone = String(value || '').replace(/\D/g, '')
  if (phone.length < 10 || phone.length > 15) {
    throw Object.assign(new Error('Número de WhatsApp inválido.'), { statusCode: 400 })
  }
  return phone
}

export function phoneJid(value) {
  return `${normalizePhone(value)}@s.whatsapp.net`
}
