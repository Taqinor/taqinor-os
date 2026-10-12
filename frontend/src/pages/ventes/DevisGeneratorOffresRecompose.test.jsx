// QJR548 — appliquer une taille d'offre RECOMPOSE le devis côté serveur
// (pipeline RECONCILIER). L'écran doit alors relire CE devis par son chargeur
// `?edit=` : sinon il gardait ses anciennes lignes (10 panneaux) et le
// prochain « Enregistrer » annulait en silence la taille appliquée (12).
//
// L'écran RÉEL est rendu ; seul <DevisOffresTailles> est remplacé par un
// bouton qui appelle `onDevisRecompose` (son propre comportement — confirmation,
// appels réseau — est couvert par DevisOffresTailles.test.jsx).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorOffresRecompose.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('./DevisOffresTailles', () => ({
  default: ({ onDevisRecompose, modifiable }) => (
    <button type="button" data-testid="stub-appliquer-taille"
            data-modifiable={String(modifiable)}
            onClick={() => onDevisRecompose && onDevisRecompose()}>
      Appliquer la taille (stub)
    </button>
  ),
}))
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
// QJR540 — le bloc calepinage de l'Édition complète lit lui-même le devis
// (getDevisById) : neutralisé ici, ce test compte les RECHARGEMENTS de l'écran.
vi.mock('../../features/ventes/BlocCalepinageDevis', () => ({ default: () => null }))
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, bancEdition } from './devisGenerator.testHelpers.jsx'

const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'Recompose', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devis(nbPanneaux) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, lead: LEAD.id, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: String(nbPanneaux),
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  }
}

const { renderEdition } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR548 — une taille appliquée recharge l\'écran depuis le devis recomposé', () => {
  it('10 panneaux, puis 12 après « appliquer » → l\'Enregistrer suivant envoie 12', async () => {
    const id = devis(10).data.id
    ventesApi.getDevisById
      .mockResolvedValueOnce(devis(10))
      .mockResolvedValueOnce(devis(12))
    renderEdition(id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const stub = await screen.findByTestId('stub-appliquer-taille')
    // Le verdict SERVI (QJR516) descend jusqu'au bouton des tailles.
    expect(stub.getAttribute('data-modifiable')).toBe('true')

    await userEvent.click(stub)
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledTimes(2))
    expect(String(ventesApi.getDevisById.mock.calls.at(-1)[0])).toBe(String(id))

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    const panneaux = lignes.filter(l => Number(l.produit) === PANNEAU.id)
    expect(panneaux).toHaveLength(1)
    expect(Number(panneaux[0].quantite)).toBe(12)
  })
})
