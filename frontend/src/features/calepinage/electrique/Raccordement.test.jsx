/* CALX244 — le panneau « Raccordement réseau » de l'atelier.

   Ce qui est prouvé ici :
     1. les SEPT champs de la saisie sont demandés, et remplis avec ce que le
        serveur publie (exemple COMMITTÉ `calepinage_raccordement.json`,
        CALX205, relu par `node:fs` — jamais recopié à la main) ;
     2. les CINQ verdicts sont rendus PAR LEUR CODE, jamais par leur position,
        et un verdict `omis` affiche le MOTIF du serveur — jamais une pastille
        « Conforme », jamais un chiffre à la place du motif ;
     3. une valeur `null` du bloc `calcul` rend un TIRET, jamais un `0` ;
     4. l'enregistrement poste les sept clés (un champ vidé vaut `null`) et
        AFFICHE la réponse : aucun second appel de lecture n'est enchaîné ;
     5. un refus 400 pose le message SOUS le champ que le serveur NOMME, et le
        bandeau le nomme aussi (règle fondateur du 08/09/2026). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const ICI = dirname(fileURLToPath(import.meta.url))

function racineDepot() {
  let dossier = resolve(ICI)
  for (let i = 0; i < 10; i += 1) {
    try {
      readFileSync(join(dossier, 'backend', 'django_core', 'manage.py'))
      return dossier
    } catch { dossier = dirname(dossier) }
  }
  throw new Error(`Racine du depot introuvable depuis ${ICI}`)
}

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'calepinage_raccordement.json'), 'utf8'))

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { raccordement: vi.fn(), enregistrerRaccordement: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import Raccordement, {
  CHAMPS, corpsDeSaisie, erreursParChamp, libelleStatut,
} from './Raccordement'

const servir = (data) => {
  calepinageApi.calepinages.raccordement.mockResolvedValue({ data })
}

const rendre = () => render(
  <MemoryRouter><Raccordement calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Raccordement (CALX244)', () => {
  it('demande les SEPT champs du contrat, et rien de plus', async () => {
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

  it('rend les CINQ verdicts, lus par leur CODE', async () => {
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

  it('état vide : aucune grandeur n’est rendue `0`, cinq verdicts omis', async () => {
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

  it('poste les sept clés et affiche la réponse, sans seconde lecture', async () => {
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
