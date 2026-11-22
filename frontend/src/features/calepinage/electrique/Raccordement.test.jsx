/* CALX244 — le panneau « Raccordement réseau » de l'atelier.

   Ce qui est prouvé ici :
     1. les NEUF champs de la saisie sont demandés, et remplis avec ce que le
        serveur publie (exemple COMMITTÉ `calepinage_raccordement.json`,
        CALX205, relu par `node:fs` — jamais recopié à la main) ;
     2. les SIX verdicts sont rendus PAR LEUR CODE, jamais par leur position,
        et un verdict `omis` affiche le MOTIF du serveur — jamais une pastille
        « Conforme », jamais un chiffre à la place du motif ;
     3. une valeur `null` du bloc `calcul` rend un TIRET, jamais un `0` ;
     4. l'enregistrement poste les neuf clés (un champ vidé vaut `null`) et
        AFFICHE la réponse : aucun second appel de lecture n'est enchaîné ;
     5. un refus 400 pose le message SOUS le champ que le serveur NOMME, et le
        bandeau le nomme aussi (règle fondateur du 08/09/2026). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const CONTRAT = documentContrat('calepinage', 'calepinage_raccordement')

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { raccordement: vi.fn(), enregistrerRaccordement: vi.fn(), explications: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import Raccordement from './Raccordement'
import { CHAMPS, corpsDeSaisie, erreursParChamp, libelleStatut } from './Raccordement.helpers'
import { documentContrat } from '../../../test/fixtures/contractSamples'

const servir = (data) => {
  calepinageApi.calepinages.raccordement.mockResolvedValue({ data })
}

const rendre = () => render(
  <MemoryRouter><Raccordement calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Raccordement (CALX244)', () => {
  it('demande les champs du contrat, et rien de plus', async () => {
    servir(CONTRAT.exemple)

    rendre()

    await screen.findByTestId('calx244-panneau')
    expect(CHAMPS.map((c) => c.cle).sort())
      .toEqual(Object.keys(CONTRAT.exemple.saisie).sort())
    for (const { cle } of CHAMPS) {
      expect(document.getElementById(`calx244-champ-${cle}`)).not.toBeNull()
    }
  })

  it('remplit la saisie avec ce que le SERVEUR publie', async () => {
    servir(CONTRAT.exemple)

    rendre()

    await screen.findByTestId('calx244-panneau')
    expect(document.getElementById('calx244-champ-puissance_souscrite_kva').value)
      .toBe(String(CONTRAT.exemple.saisie.puissance_souscrite_kva))
    expect(document.getElementById('calx244-champ-source_cos_phi').value)
      .toBe(CONTRAT.exemple.saisie.source_cos_phi)
  })

  it('rend les SIX verdicts, lus par leur CODE', async () => {
    servir(CONTRAT.exemple)

    rendre()

    await screen.findByTestId('calx244-verdicts')
    for (const verdict of CONTRAT.exemple.verdicts) {
      expect(screen.getByTestId(`calx244-verdict-${verdict.code}`))
        .toBeInTheDocument()
      expect(screen.getByTestId(`calx244-detail-${verdict.code}`))
        .toHaveTextContent(verdict.detail.slice(0, 40))
    }
  })

  it('un verdict `omis` rend son MOTIF, jamais une pastille « Conforme »', async () => {
    servir(CONTRAT.exemple)
    const omis = CONTRAT.exemple.verdicts.find((v) => v.statut === 'omis')

    rendre()

    await screen.findByTestId('calx244-verdicts')
    const statut = screen.getByTestId(`calx244-statut-${omis.code}`)
    expect(statut).toHaveTextContent(libelleStatut('omis'))
    expect(statut.textContent).not.toContain(libelleStatut('ok'))
    expect(screen.getByTestId(`calx244-detail-${omis.code}`).textContent.trim())
      .not.toBe('')
  })

  it('état vide : aucune grandeur n’est rendue `0`, six verdicts omis', async () => {
    servir(CONTRAT.exemple_vide)

    rendre()

    await screen.findByTestId('calx244-calcul')
    for (const cle of ['elevation', 'marge', 'injectee', 'desequilibre']) {
      expect(screen.getByTestId(`calx244-${cle}`)).toHaveTextContent('—')
    }
    for (const verdict of CONTRAT.exemple_vide.verdicts) {
      expect(screen.getByTestId(`calx244-statut-${verdict.code}`))
        .toHaveTextContent(libelleStatut('omis'))
    }
  })

  it('poste les neuf clés et affiche la réponse, sans seconde lecture', async () => {
    servir(CONTRAT.exemple_vide)
    calepinageApi.calepinages.enregistrerRaccordement
      .mockResolvedValue({ data: CONTRAT.exemple_limite_saisie })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.type(
      document.getElementById('calx244-champ-puissance_souscrite_kva'), '12')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => {
      expect(calepinageApi.calepinages.enregistrerRaccordement)
        .toHaveBeenCalledTimes(1)
    })
    const [, corps] = calepinageApi.calepinages
      .enregistrerRaccordement.mock.calls[0]
    expect(Object.keys(corps).sort())
      .toEqual(Object.keys(CONTRAT.exemple.saisie).sort())
    expect(corps.puissance_souscrite_kva).toBe('12')
    expect(corps.source_limite).toBeNull()
    // La réponse du POST est le raccordement recalculé : aucune relecture.
    expect(calepinageApi.calepinages.raccordement).toHaveBeenCalledTimes(1)
    await waitFor(() => {
      expect(screen.getByTestId('calx244-marge')).not.toHaveTextContent('—')
    })
  })

  it('un refus nomme le champ : message SOUS lui et bandeau qui y renvoie', async () => {
    servir(CONTRAT.exemple_vide)
    calepinageApi.calepinages.enregistrerRaccordement.mockRejectedValue({
      response: { status: 400, data: CONTRAT.refus_limite_sans_source },
    })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    const sousLeChamp = await screen.findByTestId('calx244-erreur-source_limite')
    expect(sousLeChamp)
      .toHaveTextContent(CONTRAT.refus_limite_sans_source.source_limite.slice(0, 40))
    expect(screen.getByTestId('calx244-bandeau'))
      .toHaveTextContent('Source de la limite')
    expect(document.getElementById('calx244-champ-source_limite'))
      .toHaveAttribute('aria-invalid', 'true')
  })

  it('le bandeau renvoie au champ fautif d’un clic', async () => {
    servir(CONTRAT.exemple_vide)
    calepinageApi.calepinages.enregistrerRaccordement.mockRejectedValue({
      response: { status: 400, data: CONTRAT.refus_cos_phi_sans_source },
    })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await userEvent.click(await screen.findByTestId('calx244-aller-source_cos_phi'))
    expect(document.activeElement)
      .toBe(document.getElementById('calx244-champ-source_cos_phi'))
  })

  it('une lecture en panne le DIT, sans inventer un raccordement', async () => {
    calepinageApi.calepinages.raccordement.mockRejectedValue(new Error('boum'))

    rendre()

    expect(await screen.findByTestId('calx244-erreur')).toBeInTheDocument()
    expect(screen.queryByTestId('calx244-panneau')).toBeNull()
  })
})

describe('Raccordement — plafond d’injection (ACAL156)', () => {
  it('poste les neuf champs et relit la saisie persistée : « utilisé par la simulation »', async () => {
    servir(CONTRAT.exemple_vide)
    const persistee = {
      ...CONTRAT.exemple,
      saisie: {
        ...CONTRAT.exemple.saisie,
        plafond_injection_kw: 3,
        plafond_injection_justification: 'Contrat de raccordement du site (essai)',
      },
    }
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValue({ data: persistee })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    expect(screen.queryByTestId('acal156-simulation-plafond_injection_kw')).toBeNull()
    await userEvent.type(document.getElementById('calx244-champ-plafond_injection_kw'), '3')
    await userEvent.type(
      document.getElementById('calx244-champ-plafond_injection_justification'),
      'Contrat de raccordement du site (essai)')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalledTimes(1))
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(Object.keys(corps).sort()).toEqual(Object.keys(CONTRAT.exemple.saisie).sort())
    expect(corps.plafond_injection_kw).toBe('3')
    // La saisie PERSISTÉE (réponse du serveur) est relue : le plafond porte sa mention.
    expect(await screen.findByTestId('acal156-simulation-plafond_injection_kw'))
      .toHaveTextContent('utilisé par la simulation')
    expect(screen.getByTestId('acal156-note-simulation')).toHaveTextContent('Production')
  })

  it('plafond sans justification refusé sous le champ', async () => {
    servir(CONTRAT.exemple_vide)
    calepinageApi.calepinages.enregistrerRaccordement.mockRejectedValue({
      response: { status: 400, data: CONTRAT.refus_plafond_sans_justification },
    })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.type(document.getElementById('calx244-champ-plafond_injection_kw'), '3')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    expect(await screen.findByTestId('calx244-erreur-plafond_injection_justification'))
      .toHaveTextContent(CONTRAT.refus_plafond_sans_justification.plafond_injection_justification.slice(0, 40))
  })

  it('un champ vidé envoie null, jamais 0', async () => {
    servir(CONTRAT.exemple)
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValue({ data: CONTRAT.exemple_vide })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.clear(document.getElementById('calx244-champ-puissance_souscrite_kva'))
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(corps.puissance_souscrite_kva).toBeNull()
  })
})

describe('Raccordement — valeurs du lead (ACAL158)', () => {
  const PROPOSITION = CONTRAT.exemple.proposition_lead
  const vide = () => ({ ...CONTRAT.exemple_vide, proposition_lead: PROPOSITION })

  it('reprendre remplit sans enregistrer', async () => {
    servir(vide())

    rendre()
    await screen.findByTestId('acal158-proposition')
    expect(screen.getByTestId('acal158-source')).toHaveTextContent(PROPOSITION.source)
    await userEvent.click(screen.getByTestId('acal158-reprendre'))

    expect(document.getElementById('calx244-champ-puissance_souscrite_kva'))
      .toHaveValue(PROPOSITION.puissance_souscrite_kva)
    expect(document.getElementById('calx244-champ-phases')).toHaveValue(PROPOSITION.phases)
    // Rien n'est enregistré avant « Enregistrer ».
    expect(calepinageApi.calepinages.enregistrerRaccordement).not.toHaveBeenCalled()
  })

  it('saisie existante non écrasée : la proposition est lisible, sans bouton', async () => {
    servir({ ...CONTRAT.exemple, proposition_lead: { ...PROPOSITION, puissance_souscrite_kva: 99 } })

    rendre()
    await screen.findByTestId('acal158-proposition')
    expect(screen.queryByTestId('acal158-reprendre')).toBeNull()
    expect(document.getElementById('calx244-champ-puissance_souscrite_kva'))
      .toHaveValue(CONTRAT.exemple.saisie.puissance_souscrite_kva)
  })

  it('proposition nulle = pas de bouton', async () => {
    servir({ ...CONTRAT.exemple_vide, proposition_lead: null })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    expect(screen.queryByTestId('acal158-proposition')).toBeNull()
    expect(screen.queryByTestId('acal158-reprendre')).toBeNull()
  })

  it('après « Reprendre » puis « Enregistrer », le corps posté porte les valeurs du lead', async () => {
    servir(vide())
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValue({ data: CONTRAT.exemple })

    rendre()
    await userEvent.click(await screen.findByTestId('acal158-reprendre'))
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalledTimes(1))
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(corps.puissance_souscrite_kva).toBe(PROPOSITION.puissance_souscrite_kva)
    expect(corps.phases).toBe(PROPOSITION.phases)
  })
})

describe('Raccordement — régime 82-21 et injection (ACAL784)', () => {
  it('les deux lignes se lisent sur l’exemple du contrat, avec le voyant au-delà du plafond', async () => {
    servir(CONTRAT.exemple)

    rendre()

    const regime = await screen.findByTestId('acal784-regime')
    expect(regime.textContent).toBe(
      'Régime 82-21 : Accord de raccordement — puissance retenue 12 kW, base à confirmer avec le distributeur',
    )
    expect(screen.getByTestId('acal784-injection').textContent)
      .toContain('Injection simulée : 35 % de la production annuelle ; plafond légal 20 %')
    expect(screen.getByTestId('acal784-voyant')).toBeTruthy()
    expect(screen.getByTestId('acal784-avertissement').textContent)
      .toBe(CONTRAT.exemple.injection.avertissement)
  })

  it('sans dépassement, aucun voyant ni avertissement', async () => {
    servir({ ...CONTRAT.exemple, injection: { ...CONTRAT.exemple.injection, depasse: false, avertissement: null } })

    rendre()

    await screen.findByTestId('acal784-injection')
    expect(screen.queryByTestId('acal784-voyant')).toBeNull()
    expect(screen.queryByTestId('acal784-avertissement')).toBeNull()
  })

  it('sans simulation : le motif du serveur ; régime à qualifier : puissance inconnue', async () => {
    servir(CONTRAT.exemple_vide)

    rendre()

    expect((await screen.findByTestId('acal784-regime')).textContent)
      .toBe('Régime à qualifier : puissance du site inconnue')
    expect(screen.getByTestId('acal784-injection').textContent)
      .toBe(CONTRAT.exemple_vide.injection_motif)
  })

  it('un bloc sans régime ni injection ne rend aucune ligne', async () => {
    const { regime, injection, injection_motif: motif, ...ancien } = CONTRAT.exemple
    expect([regime, injection, motif]).not.toContain(undefined)
    servir(ancien)

    rendre()

    await screen.findByTestId('calx244-panneau')
    expect(screen.queryByTestId('acal784-regime-injection')).toBeNull()
  })
})

describe('Fonctions pures (CALX244)', () => {
  it('erreursParChamp retire le préfixe que le serveur pose', () => {
    expect(erreursParChamp(CONTRAT.refus_limite_sans_source))
      .toEqual({ source_limite: CONTRAT.refus_limite_sans_source.source_limite })
    expect(erreursParChamp({ 'raccordement.phases': 'x' })).toEqual({ phases: 'x' })
  })

  it('corpsDeSaisie rend `null` pour un champ vidé, jamais une chaîne vide', () => {
    const corps = corpsDeSaisie({ phases: '3', source_limite: '' })
    expect(corps.phases).toBe('3')
    expect(corps.source_limite).toBeNull()
    expect(corps.cos_phi_impose).toBeNull()
  })

  it('libelleStatut NOMME un statut inconnu plutôt que de le taire', () => {
    expect(libelleStatut('inconnu')).toContain('inconnu')
  })
})

describe('Raccordement (ACAL874) — le « ? » des grandeurs électriques', () => {
  it('l’élévation de tension porte un « ? » dont la phrase contient la valeur servie', async () => {
    const { readFileSync } = await import('node:fs')
    const { join } = await import('node:path')
    const { fichierContrat } = await import('../../../test/fixtures/contractSamples')
    const { remplirPhrase } = await import('../commun/useExplications')
    const registre = JSON.parse(readFileSync(
      join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8')).entrees
    calepinageApi.calepinages.explications.mockResolvedValue({ data: { entrees: registre } })
    servir(CONTRAT.exemple)
    rendre()
    await screen.findByTestId('calx244-panneau')
    const cles = ['elevation_tension', 'marge_limite', 'puissance_injectee', 'desequilibre_phases']
    for (const cle of cles) {
      expect(document.querySelector(`[data-grandeur="electrique.${cle}"]`)).not.toBeNull()
    }
    await userEvent.click(document.querySelector('[data-grandeur="electrique.elevation_tension"]'))
    const entree = registre.find((e) => e.cle === 'electrique.elevation_tension')
    const phrase = remplirPhrase(entree, CONTRAT.exemple)
    expect(phrase).toContain('0,82 %')
    expect(phrase).toContain('limite du gestionnaire de réseau')
    expect(await screen.findByText(phrase)).toBeInTheDocument()
  })
})

describe('Raccordement — limites du distributeur (ACAL830)', () => {
  it('16 A, une plage 16-18 h, soutirage 6 kW : corps posté, kW converti rendu, refus sous le champ', async () => {
    servir(CONTRAT.exemple_vide)
    const persistee = {
      ...CONTRAT.exemple,
      saisie: {
        ...CONTRAT.exemple.saisie,
        plafond_injection_a: 16,
        plages_plafond_injection: [{ debut_h: 16, fin_h: 18, plafond_kw: 2 }],
      },
      calcul: {
        ...CONTRAT.exemple.calcul,
        plafond_injection_kw_converti: 11.085,
        plafond_injection_conversion: 'Monophasé : 230 V × 16 A',
      },
    }
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValueOnce({ data: persistee })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    expect(screen.getByTestId('acal830-limites')).not.toHaveAttribute('open')
    await userEvent.type(document.getElementById('calx244-champ-plafond_injection_a'), '16')
    await userEvent.click(screen.getByTestId('acal830-ajouter-plage'))
    const plages = screen.getByTestId('acal830-plages')
    const cases = plages.querySelectorAll('input')
    await userEvent.type(cases[0], '16')
    await userEvent.type(cases[1], '18')
    await userEvent.type(cases[2], '2')
    await userEvent.type(document.getElementById('calx244-champ-plafond_soutirage_kw'), '6')
    await userEvent.type(document.getElementById('calx244-champ-plafond_soutirage_justification'), 'Contrat (essai)')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalledTimes(1))
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(Object.keys(corps).sort()).toEqual(Object.keys(CONTRAT.exemple.saisie).sort())
    expect(corps.plafond_injection_a).toBe('16')
    expect(corps.plages_plafond_injection).toEqual([{ debut_h: 16, fin_h: 18, plafond_kw: 2 }])
    expect(corps.plafond_soutirage_kw).toBe('6')
    expect(await screen.findByTestId('acal830-conversion')).toHaveTextContent('Monophasé : 230 V × 16 A')
    expect(screen.getByTestId('acal830-conversion').textContent).toMatch(/= 11,085\s?kW/)

    calepinageApi.calepinages.enregistrerRaccordement.mockRejectedValueOnce({
      response: { status: 400, data: { 'raccordement.plages_plafond_injection[0]': 'Cette plage chevauche une autre plage.' } },
    })
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))
    expect(await screen.findByTestId('calx244-erreur-plages_plafond_injection[0]'))
      .toHaveTextContent('chevauche')
    expect(screen.getByTestId('calx244-bandeau')).toHaveTextContent('plages_plafond_injection[0]')
  })

  it('aucune plage ni valeur : null postés, section repliée ; la quatrième plage est refusée par le bouton masqué', async () => {
    servir(CONTRAT.exemple_vide)
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValue({ data: CONTRAT.exemple_vide })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(corps.plages_plafond_injection).toBeNull()
    expect(corps.plafond_injection_a).toBeNull()
    for (let i = 0; i < 3; i += 1) await userEvent.click(screen.getByTestId('acal830-ajouter-plage'))
    expect(screen.queryByTestId('acal830-ajouter-plage')).toBeNull()
  })
})

describe('Raccordement — limitation de l’injection (ACAL1188)', () => {
  // Micro-onduleurs + plafond 0 kW : le sixième verdict, tel que le serveur le prononce
  // (libellés et phrases de services/raccordement.py::_verdict_limitation_injection).
  const verdictSix = (statut, detail) => CONTRAT.exemple.verdicts.map((v) => (
    v.code === 'limitation_injection' ? { ...v, statut, detail, source: 'saisie — dispositif_limitation_injection' } : v))
  const micro = (dispositif, statut, detail) => ({
    ...CONTRAT.exemple,
    saisie: { ...CONTRAT.exemple.saisie, plafond_injection_kw: 0, dispositif_limitation_injection: dispositif },
    verdicts: verdictSix(statut, detail),
  })
  const DETAIL_ALERTE = 'Des micro-onduleurs ne limitent pas l’injection d’eux-mêmes : déclarez le dispositif qui tient ce plafond.'

  it('le sixième verdict est rendu avec son intitulé, « À surveiller » et sa phrase', async () => {
    servir(micro(null, 'alerte', DETAIL_ALERTE))

    rendre()

    await screen.findByTestId('calx244-verdicts')
    expect(screen.getByTestId('calx244-verdict-limitation_injection')).toHaveTextContent('Limitation de l\'injection')
    expect(screen.getByTestId('calx244-statut-limitation_injection')).toHaveTextContent('À surveiller')
    expect(screen.getByTestId('calx244-detail-limitation_injection')).toHaveTextContent('déclarez le dispositif')
  })

  it('l’erreur du serveur s’affiche sous le champ dispositif', async () => {
    servir(micro(null, 'alerte', DETAIL_ALERTE))
    calepinageApi.calepinages.enregistrerRaccordement.mockRejectedValue({
      response: { status: 400, data: { 'raccordement.dispositif_limitation_injection': 'Dispositif non valide.' } },
    })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.click(screen.getByText(/Limites imposées par le distributeur/))
    await userEvent.type(document.getElementById('calx244-champ-dispositif_limitation_injection'), 'x')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    expect(await screen.findByTestId('calx244-erreur-dispositif_limitation_injection'))
      .toHaveTextContent('Dispositif non valide.')
  })

  it('taper un dispositif puis enregistrer passe le verdict à « Conforme »', async () => {
    servir(micro(null, 'alerte', DETAIL_ALERTE))
    calepinageApi.calepinages.enregistrerRaccordement.mockResolvedValue({
      data: micro('Passerelle de limitation', 'ok',
        'un plafond d’injection est saisi sur des micro-onduleurs ; dispositif déclaré : Passerelle de limitation.'),
    })

    rendre()
    await screen.findByTestId('calx244-formulaire')
    await userEvent.type(document.getElementById('calx244-champ-dispositif_limitation_injection'), 'Passerelle de limitation')
    await userEvent.click(screen.getByTestId('calx244-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerRaccordement).toHaveBeenCalledTimes(1))
    const [, corps] = calepinageApi.calepinages.enregistrerRaccordement.mock.calls[0]
    expect(corps.dispositif_limitation_injection).toBe('Passerelle de limitation')
    await waitFor(() => expect(screen.getByTestId('calx244-statut-limitation_injection')).toHaveTextContent('Conforme'))
  })
})
