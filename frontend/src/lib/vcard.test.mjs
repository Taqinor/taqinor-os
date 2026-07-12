import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildVCard, vCardFileName } from './vcard.js'

// VX246(d) — vCard 3.0 (.vcf) : util pur, importable dans le carnet d'adresses.

test('buildVCard: enveloppe BEGIN/VERSION/END + FN obligatoire', () => {
  const v = buildVCard({ nom: 'Kasri', prenom: 'Reda' })
  const lines = v.split('\r\n')
  assert.equal(lines[0], 'BEGIN:VCARD')
  assert.equal(lines[1], 'VERSION:3.0')
  assert.equal(lines.at(-1), 'END:VCARD')
  assert.ok(lines.includes('N:Kasri;Reda;;;'))
  assert.ok(lines.includes('FN:Reda Kasri'))
})

test('buildVCard: n émet que les propriétés fournies', () => {
  const v = buildVCard({ nom: 'Benani' })
  assert.ok(!v.includes('ORG:'))
  assert.ok(!v.includes('TEL'))
  assert.ok(!v.includes('EMAIL'))
  assert.ok(!v.includes('ADR'))
  assert.ok(v.includes('FN:Benani'))
})

test('buildVCard: échappe ; , \\ et \\n (RFC 6350)', () => {
  const v = buildVCard({ fullName: 'A, B', org: 'Taq; SARL', adresse: '12 rue,\nRabat' })
  assert.ok(v.includes('FN:A\\, B'))
  assert.ok(v.includes('ORG:Taq\\; SARL'))
  assert.ok(v.includes('ADR;TYPE=WORK:;;12 rue\\,\\nRabat;;;;'))
})

test('buildVCard: TEL CELL (mobile) et WORK (fixe) distincts + EMAIL', () => {
  const v = buildVCard({ nom: 'X', mobile: '+212612345678', tel: '0537000000', email: 'a@b.ma' })
  assert.ok(v.includes('TEL;TYPE=CELL:+212612345678'))
  assert.ok(v.includes('TEL;TYPE=WORK,VOICE:0537000000'))
  assert.ok(v.includes('EMAIL;TYPE=INTERNET:a@b.ma'))
})

test('vCardFileName: assaini + extension .vcf, repli « contact »', () => {
  assert.equal(vCardFileName({ prenom: 'Reda', nom: 'Kasri' }), 'Reda-Kasri.vcf')
  assert.equal(vCardFileName({}), 'contact.vcf')
  assert.equal(vCardFileName({ fullName: 'Société  ///  A' }), 'Soci-t-A.vcf')
})
