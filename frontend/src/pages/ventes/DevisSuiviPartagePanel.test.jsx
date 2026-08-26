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

/* ANALYT1 (audit item 64, 26/08/2026) — bloc « Lecture par le client » :
   visites distinctes par section + alerte de friction. Analytics INTERNES —
   jamais de taux/pourcentage de conversion affiché. */

describe('DevisSuiviPartagePanel — Lecture par le client (ANALYT1)', () => {
  const baseData = { ouverture: null, relances: [] }

  it("n'affiche rien quand lectureClient est absent (rôle non responsable/admin)", () => {
    render(<DevisSuiviPartagePanel loading={false} data={baseData} />)
    expect(screen.queryByText(/Lecture par le client/)).not.toBeInTheDocument()
  })

  it("n'affiche rien quand lectureClient est vide (aucun beacon reçu)", () => {
    render(
      <DevisSuiviPartagePanel
        loading={false} data={baseData}
        lectureClient={{ sections: {}, friction: null }}
      />,
    )
    expect(screen.queryByText(/Lecture par le client/)).not.toBeInTheDocument()
  })

  it('liste les sections avec leur nombre de visites', () => {
    render(
      <DevisSuiviPartagePanel
        loading={false} data={baseData}
        lectureClient={{
          sections: {
            options: { seconds: 40, hits: 3, visits: 3 },
            sld: { seconds: 10, hits: 1, visits: 1 },
          },
          friction: null,
        }}
      />,
    )
    expect(screen.getByText(/Lecture par le client/)).toBeInTheDocument()
    expect(screen.getByText(/options/)).toBeInTheDocument()
    expect(screen.getByText(/relu 3×/)).toBeInTheDocument()
    expect(screen.getByText(/schéma électrique/)).toBeInTheDocument()
    expect(screen.getByText(/1 visite/)).toBeInTheDocument()
  })

  it("affiche l'alerte de friction quand présente, jamais un taux de conversion", () => {
    render(
      <DevisSuiviPartagePanel
        loading={false} data={baseData}
        lectureClient={{
          sections: { options: { seconds: 40, hits: 3, visits: 3 } },
          friction: { section: 'options', declenche_le: '2026-08-26T10:00:00Z' },
        }}
      />,
    )
    expect(screen.getByText(/Signal de friction/)).toBeInTheDocument()
    expect(screen.getByText(/un appel peut débloquer la décision/)).toBeInTheDocument()
    // Zéro chiffre de conversion/pourcentage inventé dans ce bloc.
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/taux/i)).not.toBeInTheDocument()
  })

  it('reste silencieux (aucune section listée) quand seule la friction est servie', () => {
    render(
      <DevisSuiviPartagePanel
        loading={false} data={baseData}
        lectureClient={{
          sections: {},
          friction: { section: 'sld', declenche_le: '2026-08-26T10:00:00Z' },
        }}
      />,
    )
    expect(screen.getByText(/Lecture par le client/)).toBeInTheDocument()
    expect(screen.getByText(/schéma électrique/)).toBeInTheDocument()
  })
})
