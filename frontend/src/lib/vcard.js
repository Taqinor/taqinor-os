// VX246(d) — vCard 3.0 (.vcf) : util PUR, zéro dépendance. Sérialise un contact
// (nom, société, téléphone, email, adresse) en un fichier .vcf importable dans
// le carnet d'adresses du téléphone d'un seul appui — complément terrain aux
// liens tel:/wa.me de VX108 (lib/contactLinks.js).

/** Échappe une valeur de propriété vCard (RFC 6350 §3.4 / vCard 3.0) :
 *  backslash, virgule, point-virgule et sauts de ligne. */
function escapeValue(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;')
}

/**
 * Construit une chaîne vCard 3.0. `contact` = { nom, prenom, fullName?, org?,
 * tel?, mobile?, email?, adresse? }. Renvoie une chaîne `BEGIN:VCARD … END:VCARD`
 * (CRLF entre les lignes, comme l'exige la spec). Aucune propriété vide n'est émise.
 */
export function buildVCard(contact = {}) {
  const { nom = '', prenom = '', fullName, org, tel, mobile, email, adresse } = contact
  const displayName = (fullName ?? [prenom, nom].filter(Boolean).join(' ')).trim()
  const lines = ['BEGIN:VCARD', 'VERSION:3.0']
  // N = structuré (Famille;Prénom;;;) ; FN = nom affiché (obligatoire en 3.0).
  lines.push(`N:${escapeValue(nom)};${escapeValue(prenom)};;;`)
  lines.push(`FN:${escapeValue(displayName || nom || prenom || 'Contact')}`)
  if (org) lines.push(`ORG:${escapeValue(org)}`)
  if (mobile) lines.push(`TEL;TYPE=CELL:${escapeValue(mobile)}`)
  if (tel) lines.push(`TEL;TYPE=WORK,VOICE:${escapeValue(tel)}`)
  if (email) lines.push(`EMAIL;TYPE=INTERNET:${escapeValue(email)}`)
  // ADR structuré : ;;rue;ville;;;pays — on met tout dans le champ « rue ».
  if (adresse) lines.push(`ADR;TYPE=WORK:;;${escapeValue(adresse)};;;;`)
  lines.push('END:VCARD')
  return lines.join('\r\n')
}

/** Nom de fichier .vcf assaini à partir du nom du contact. */
export function vCardFileName(contact = {}) {
  const base = (contact.fullName
    ?? [contact.prenom, contact.nom].filter(Boolean).join(' ')
    ?? '').trim() || 'contact'
  const safe = base.replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '') || 'contact'
  return `${safe}.vcf`
}

/** Déclenche le téléchargement du .vcf du contact (Blob + <a download>). */
export function downloadVCard(contact = {}) {
  const vcf = buildVCard(contact)
  const blob = new Blob([vcf], { type: 'text/vcard;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = vCardFileName(contact)
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
