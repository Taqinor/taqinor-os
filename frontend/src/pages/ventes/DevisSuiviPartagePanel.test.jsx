import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import DevisSuiviPartagePanel from './DevisSuiviPartagePanel'

/* ANALYT1 (audit item 64, 26/08/2026) — bloc « Lecture par le client » :
   visites distinctes par section + alerte de friction. Analytics INTERNES —
   jamais de taux/pourcentage de conversion affiché.
   SOLMVP41 — le suivi marketing (WIR96 : « vu le … »/relances,
   `ventesApi.getSuiviPartageDevis`) est parti avec l'app marketing ; ce
   panneau ne rend plus que le bloc ANALYT1 ci-dessous. */

describe('DevisSuiviPartagePanel — Lecture par le client (ANALYT1)', () => {
  it("n'affiche rien quand lectureClient est absent (rôle non responsable/admin)", () => {
    const { container } = render(<DevisSuiviPartagePanel />)
    expect(container).toBeEmptyDOMElement()
  })

  it("n'affiche rien quand lectureClient est vide (aucun beacon reçu)", () => {
    render(<DevisSuiviPartagePanel lectureClient={{ sections: {}, friction: null }} />)
    expect(screen.queryByText(/Lecture par le client/)).not.toBeInTheDocument()
  })

  it('liste les sections avec leur nombre de visites', () => {
    render(
      <DevisSuiviPartagePanel
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
