/* VTA11 — le panneau client/devis côté TERRAIN.

   GARDE FONDATRICE (règle #4 du dépôt, reconduite ici) : `prix_achat` et toute
   marge sont GÉNÉRATEUR-SEULEMENT. Ce panneau est un écran CLIENT-FACING au
   sens le plus littéral — le commercial l'ouvre DEVANT le client, sur son
   téléphone. Le test ci-dessous n'inspecte donc pas la réponse serveur mais le
   RENDU : il balaie le texte monétaire réellement affiché (leçon #69 — scanner
   des chiffres nus produit des faux positifs et rate les vrais). */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import VisiteClientDevisPanel from './VisiteClientDevisPanel'

// Charge PIÉGÉE : le serveur ne sert pas ces clés, mais si un jour une
// régression les laissait passer, le panneau ne doit RIEN en rendre.
const CLIENT_PANEL = {
  lead_nom: 'Client Démo',
  telephone: '+212600000000',
  whatsapp: '+212600000000',
  adresse: 'Quartier Démo',
  ville: 'Bouskoura',
  gps_lat: 33.4589,
  gps_lng: -7.6528,
}

const DEVIS = [{
  id: 214,
  numero: 'DEV-202609-0012',
  statut: 'envoye',
  date: '2026-09-02',
  total_ttc: '84500.00',
  lignes: [{
    designation: 'Panneau 550 Wc',
    quantite: '12.000',
    prix_unitaire_ttc: '1850.00',
    total_ttc: '22200.00',
    // ── pièges ─────────────────────────────────────────────────────────────
    prix_achat: '1200.00',
    marge: '650.00',
    taux_marge: '35.1',
  }],
}]

describe('VisiteClientDevisPanel — prix CLIENT seulement', () => {
  it('affiche le numéro, le total TTC et les lignes au prix client', () => {
    render(<VisiteClientDevisPanel clientPanel={CLIENT_PANEL} devis={DEVIS} />)
    expect(screen.getByText('Client Démo')).toBeInTheDocument()
    expect(screen.getByText('DEV-202609-0012')).toBeInTheDocument()
    const panneau = screen.getByTestId('visite-client-devis-panel')
    // Total TTC et P.U. client présents (formatMAD insère des espaces
    // insécables : on cherche les chiffres significatifs, pas la mise en forme).
    expect(panneau.textContent.replace(/\s/g, '')).toContain('84500')
    expect(panneau.textContent.replace(/\s/g, '')).toContain('1850')
    expect(panneau.textContent).toContain('Panneau 550 Wc')
  })

  it('ne rend AUCUN prix d’achat ni aucune marge (garde règle #4)', () => {
    render(<VisiteClientDevisPanel clientPanel={CLIENT_PANEL} devis={DEVIS} />)
    const rendu = screen.getByTestId('visite-client-devis-panel').textContent
    const compact = rendu.replace(/\s/g, '')
    // 1. aucun LIBELLÉ de coût interne.
    expect(rendu).not.toMatch(/prix\s*d[’']?achat|achat|marge|coût|cout/i)
    // 2. aucune des VALEURS monétaires internes de la charge piégée.
    expect(compact).not.toContain('1200')
    expect(compact).not.toContain('650')
    expect(compact).not.toContain('35,1')
  })

  it('ne rend rien sans panneau client (pas de cadre vide)', () => {
    const { container } = render(<VisiteClientDevisPanel clientPanel={null} devis={DEVIS} />)
    expect(container).toBeEmptyDOMElement()
  })
})
