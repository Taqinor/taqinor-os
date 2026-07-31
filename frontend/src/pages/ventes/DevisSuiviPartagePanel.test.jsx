import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import DevisSuiviPartagePanel from './DevisSuiviPartagePanel'

/* WIR96 — le panneau rend les deux traces marketing qui n'étaient affichées
   nulle part : « vu le … » (OuverturePartage) et la liste des relances
   (RelanceDevisAbandonne). Il ne rend JAMAIS de montant ni de coût. */

describe('DevisSuiviPartagePanel (WIR96)', () => {
  it('affiche « vu le … » et les relances consignées', () => {
    render(
      <DevisSuiviPartagePanel
        loading={false}
        data={{
          ouverture: {
            nb_ouvertures: 3,
            premier_vu_le: '2026-07-20T10:30:00Z',
            dernier_vu_le: '2026-07-22T18:05:00Z',
            cible: 'devis',
            cible_reference: 'DEV-202607-0001',
          },
          relances: [
            {
              id: 1, date_relance: '2026-07-21T09:00:00Z',
              jours_sans_reponse: 5, canal: 'email',
              note: 'Relance automatique niveau 1 (QJ4).',
            },
          ],
        }}
      />,
    )

    expect(screen.getByText(/Vu le/)).toBeInTheDocument()
    expect(screen.getByText(/3 ouvertures/)).toBeInTheDocument()
    expect(screen.getByText(/email/)).toBeInTheDocument()
    expect(screen.getByText(/5 j sans réponse/)).toBeInTheDocument()
    expect(screen.getByText(/Relance automatique niveau 1/)).toBeInTheDocument()
  })

  it('annonce clairement un lien jamais ouvert et zéro relance', () => {
    render(
      <DevisSuiviPartagePanel
        loading={false}
        data={{ ouverture: null, relances: [] }}
      />,
    )
    expect(screen.getByText(/jamais ouvert/)).toBeInTheDocument()
    expect(screen.getByText(/Aucune relance consignée/)).toBeInTheDocument()
  })

  it('affiche un état de chargement', () => {
    render(<DevisSuiviPartagePanel loading data={undefined} />)
    expect(screen.getByText('Chargement…')).toBeInTheDocument()
  })
})
