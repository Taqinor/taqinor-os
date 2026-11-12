// ADEV44 (C-ADEV-001) — le corps RÉELLEMENT construit par `submitRefus`
// (`corpsRefus`) est validé contre le contrat committé
// `apps/ventes/contract_samples/devis_refuser.json` (PACT10) : uniquement des
// clés déclarées, `motif` = le NOM du motif choisi. Test-du-test : remettre
// `motif_perte: motifId` dans le corps ⇒ « clé non déclarée » échoue.
import { describe, it, expect } from 'vitest'
import { documentContrat } from '../../../test/fixtures/contractSamples'
import { buildRelanceMessage, buildRelanceWaUrl, corpsRefus } from './devisListHelpers.js'

const CONTRAT = documentContrat('ventes', 'devis_refuser')
const MOTIFS = [
  { id: 4, nom: 'Prix trop élevé' },
  { id: 7, nom: 'Budget insuffisant' },
]

describe('ADEV44 — corps du refus selon devis_refuser.json', () => {
  it('motif = nom du motif choisi, note = détail ; aucune clé non déclarée', () => {
    const corps = corpsRefus({ motifsPerte: MOTIFS, motifId: '7', note: '  Le client attend.  ' })
    expect(corps).toEqual({ motif: 'Budget insuffisant', note: 'Le client attend.' })
    const declarees = Object.keys(CONTRAT.champs_corps)
    for (const cle of Object.keys(corps)) expect(declarees).toContain(cle)
  })

  it('la note vide n’est pas envoyée ; la note est bornée à 255 caractères', () => {
    expect(corpsRefus({ motifsPerte: MOTIFS, motifId: 4, note: '' })).toEqual({ motif: 'Prix trop élevé' })
    const longue = corpsRefus({ motifsPerte: MOTIFS, motifId: 4, note: 'x'.repeat(400) })
    expect(longue.note).toHaveLength(CONTRAT.champs_corps.note.max_longueur)
  })

  it('le corps d’exemple du contrat a la même forme que celui de l’écran', () => {
    const corps = corpsRefus({ motifsPerte: MOTIFS, motifId: 4, note: CONTRAT.corps.note })
    expect(corps.motif).toBe(CONTRAT.corps.motif)
    expect(corps.note).toBe(CONTRAT.corps.note)
  })
})

// AMSG37 (C-AMSG-022) — « Relancer » lit le texte SERVI (`message_relance`,
// gabarit `relance_devis` de la société) : jamais un texte codé dans l'écran.
describe('AMSG37 — message de relance servi par whatsapp-preview', () => {
  const waData = {
    wa_url: 'https://wa.me/212600000057?text=envoi',
    url: 'https://exemple.test/p/abc',
    message_relance: 'Bonjour Amina, petit rappel concernant votre devis Soleil (DEV-1) : https://exemple.test/p/abc',
  }

  it('le message et le lien wa.me portent le texte servi tel quel', () => {
    expect(buildRelanceMessage(waData, 'DEV-1')).toBe(waData.message_relance)
    expect(buildRelanceWaUrl(waData, 'DEV-1'))
      .toBe(`https://wa.me/212600000057?text=${encodeURIComponent(waData.message_relance)}`)
  })

  it('sans texte servi : aucun lien de relance', () => {
    expect(buildRelanceWaUrl({ wa_url: waData.wa_url }, 'DEV-1')).toBeNull()
  })
})
