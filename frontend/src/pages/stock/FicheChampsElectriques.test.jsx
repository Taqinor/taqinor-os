import { describe, it, expect, vi } from 'vitest'
import { useEffect, useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'

/* ACAL663 — les champs électriques de fiche : une liste de SKU saisie part en
   tableau, un choix non renseigné part à null. Même harnais que
   ProduitForm.calx355FicheChamps.test.jsx (Select Radix remplacé par un
   <select> natif). */
vi.mock('../../ui', async (importActual) => (await import('./ProduitForm.testHelpers.jsx')).uiMock(await importActual()))

import FicheChampsElectriques from './FicheChampsElectriques.jsx'
import { champsFichePourType, ficheFieldsVides } from './pvondFicheTechnique.js'

let dernier
function Hote({ ficheType }) {
  const [ficheFields, setFields] = useState(ficheFieldsVides())
  useEffect(() => { dernier = ficheFields })
  return (
    <FicheChampsElectriques ficheType={ficheType} ficheFields={ficheFields}
      setFicheField={(cle, v) => setFields((f) => ({ ...f, [cle]: v }))} />
  )
}

describe('FicheChampsElectriques (ACAL663)', () => {
  it('liste de SKU saisie ⇒ tableau envoyé ; vide ⇒ null', () => {
    render(<Hote ficheType="optimiseur" />)
    const champ = screen.getByLabelText('Onduleurs compatibles (SKU séparés par des virgules)')
    expect(champ.value).toBe('')
    fireEvent.change(champ, { target: { value: 'ONDU-1, ONDU-2' } })
    expect(champsFichePourType('optimiseur', dernier).opt_onduleurs_compatibles).toEqual(['ONDU-1', 'ONDU-2'])
    fireEvent.change(champ, { target: { value: '' } })
    expect(champsFichePourType('optimiseur', dernier).opt_onduleurs_compatibles).toBeNull()
  })

  it('choix MPPT non renseigné ⇒ null ; Oui ⇒ true ; champ numérique vide ⇒ null', () => {
    render(<Hote ficheType="onduleur_hybride" />)
    expect(champsFichePourType('onduleur_hybride', dernier).ond_mppt_independants).toBeNull()
    fireEvent.change(screen.getByLabelText('Entrées MPPT indépendantes'), { target: { value: 'oui' } })
    expect(champsFichePourType('onduleur_hybride', dernier).ond_mppt_independants).toBe(true)
    fireEvent.change(screen.getByLabelText('Entrées MPPT indépendantes'), { target: { value: '__none' } })
    expect(champsFichePourType('onduleur_hybride', dernier).ond_mppt_independants).toBeNull()
    expect(champsFichePourType('onduleur_hybride', dernier).ond_pnom_pente_pct_c).toBeNull()
  })

  it('module : 144 cellules en série partent en 144 ; rien pour une batterie', () => {
    const { unmount } = render(<Hote ficheType="panneau" />)
    fireEvent.change(screen.getByLabelText('Cellules en série'), { target: { value: '144' } })
    expect(champsFichePourType('panneau', dernier).cellules_serie).toBe(144)
    unmount()
    const { container } = render(<Hote ficheType="batterie" />)
    expect(container).toBeEmptyDOMElement()
  })
})
