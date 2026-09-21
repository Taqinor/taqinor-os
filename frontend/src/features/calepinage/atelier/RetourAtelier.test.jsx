import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RetourAtelier from './RetourAtelier'
import { ongletsTries, ongletParChemin } from './onglets'

/* ============================================================================
   CALX55 — LE RETOUR VERS L'ATELIER, PROUVÉ SUR LE REGISTRE LUI-MÊME.
   ----------------------------------------------------------------------------
   Le test PARCOURT `atelier/onglets.js` plutôt que d'énumérer treize clés à la
   main : un panneau ajouté demain (une ligne de plus dans le registre) est
   couvert le jour même, sans qu'on ait à rouvrir ce fichier. C'est exactement
   ce que le Done de la tâche demande.

   Ce qui est prouvé :
     1. depuis CHAQUE route profonde du registre, le retour se rend et sa cible
        porte le bon `?onglet=` ;
     2. sur l'atelier lui-même, il ne rend RIEN (le fil pointerait sur la page
        qu'on regarde) ;
     3. un segment inconnu du registre ne fabrique aucun onglet ;
     4. aucun titre n'est inventé : il n'apparaît que s'il est passé.
   ========================================================================== */

const ID = 4242

const rendreSur = (chemin, props = {}) => render(
  <MemoryRouter initialEntries={[chemin]}>
    <Routes>
      <Route path="/calepinage/:id" element={<RetourAtelier {...props} />} />
      <Route path="/calepinage/:id/:panneau" element={<RetourAtelier {...props} />} />
    </Routes>
  </MemoryRouter>,
)

afterEach(() => cleanup())

describe('CALX55 — le retour vers l’atelier depuis chaque lien profond', () => {
  it('le registre porte bien les treize panneaux du module', () => {
    expect(ongletsTries().length).toBeGreaterThanOrEqual(13)
  })

  it.each(ongletsTries().map((o) => [o.cle, o.libelle]))(
    '/calepinage/:id/%s rend le retour vers l’onglet « %s »',
    (cle, libelle) => {
      rendreSur(`/calepinage/${ID}/${cle}`)

      expect(screen.getByTestId('cal-retour-atelier-lien'))
        .toHaveAttribute('href', `/calepinage/${ID}?onglet=${encodeURIComponent(cle)}`)
      expect(screen.getByTestId('cal-retour-atelier-onglet')).toHaveTextContent(libelle)
    },
  )

  it('sur l’atelier lui-même, il ne rend RIEN', () => {
    rendreSur(`/calepinage/${ID}`)
    expect(screen.queryByTestId('cal-retour-atelier')).toBeNull()
  })

  it('un segment inconnu du registre ne fabrique aucun onglet', () => {
    rendreSur(`/calepinage/${ID}/segment-qui-n-existe-pas`)
    expect(screen.queryByTestId('cal-retour-atelier')).toBeNull()
    expect(ongletParChemin(`/calepinage/${ID}/segment-qui-n-existe-pas`)).toBeNull()
  })

  it('la clé passée en prop l’emporte sur le chemin', () => {
    const premier = ongletsTries()[0]
    rendreSur(`/calepinage/${ID}`, { cle: premier.cle })

    expect(screen.getByTestId('cal-retour-atelier-lien'))
      .toHaveAttribute('href', `/calepinage/${ID}?onglet=${encodeURIComponent(premier.cle)}`)
  })

  it('aucun titre n’est inventé : il n’apparaît que s’il est passé', () => {
    const premier = ongletsTries()[0]

    rendreSur(`/calepinage/${ID}/${premier.cle}`)
    expect(screen.getByTestId('cal-retour-atelier-lien')).toHaveTextContent('← Calepinage')
    cleanup()

    rendreSur(`/calepinage/${ID}/${premier.cle}`, { titre: 'Ferme Bouskoura' })
    expect(screen.getByTestId('cal-retour-atelier-lien'))
      .toHaveTextContent('← Calepinage Ferme Bouskoura')
  })

  it('l’identifiant passé en prop l’emporte sur celui de l’URL', () => {
    const premier = ongletsTries()[0]
    rendreSur(`/calepinage/${ID}/${premier.cle}`, { calepinageId: 7 })

    expect(screen.getByTestId('cal-retour-atelier-lien'))
      .toHaveAttribute('href', `/calepinage/7?onglet=${encodeURIComponent(premier.cle)}`)
  })
})
