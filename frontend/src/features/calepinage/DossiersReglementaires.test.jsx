/* CAL196 — l'écran « Dossiers réglementaires » du calepinage.

   Ce qui est prouvé ici, sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/dossiers_reglementaires.json` (CAL247,
   PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main) :
   1. chaque pièce est listée avec son état et sa SOURCE ;
   2. AUCUN champ « à compléter » n'est prérempli quand le serveur sert
      `valeur: null` — le champ est rendu VIDE et le message du serveur
      s'affiche (le Done de la tâche) ;
   3. un dossier dont le gabarit n'est pas déposé reste VISIBLE et dit pourquoi ;
   4. société sans aucun gabarit ⇒ liste vide ET le message du serveur.

   CALX40 — la génération est SERVIE : le bouton n'est actif que si le serveur
   déclare `peut_generer`, et un refus 400 est rendu sous le champ nommé. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      dossiersReglementaires: vi.fn(),
      genererDossier: vi.fn(),
      enregistrerChampsDossier: vi.fn(),
      joindrePiece: vi.fn(),
    },
  },
}))

import calepinageApi from '../../api/calepinageApi'
import DossiersReglementaires from './DossiersReglementaires'

const servir = (variante) => {
  calepinageApi.calepinages.dossiersReglementaires
    .mockResolvedValue(reponseContrat('calepinage', 'dossiers_reglementaires', variante))
}

const echantillon = (variante) => reponseContrat(
  'calepinage', 'dossiers_reglementaires', variante,
).data

const rendre = () => render(
  <MemoryRouter><DossiersReglementaires calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DossiersReglementaires (ACAL309) - packs France', () => {
  it('affiche les trois packs France et le lien de dépôt', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('cal196-ecran')
    const packs = echantillon('exemple').packs_france
    expect(packs).toHaveLength(3)
    for (const pack of packs) {
      expect(screen.getByTestId(`acal309-pack-${pack.genre}`)).toHaveTextContent(pack.libelle)
      if (!pack.gabarit_depose) {
        expect(screen.getByTestId(`acal309-message-${pack.genre}`)).toHaveTextContent(pack.message)
        expect(screen.getByTestId(`acal309-depot-${pack.genre}`)).toHaveAttribute('href', '/calepinage/reglages')
      }
    }
    expect(screen.getByTestId('acal309-avancement-enedis')).toHaveTextContent('pièces fournies')
  })
})

describe('DossiersReglementaires (CAL196)', () => {
  it('liste les pièces de chaque dossier avec leur état et leur source', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const exemple = echantillon('exemple')
    const premier = exemple.dossiers[0]

    const bloc = screen.getByTestId(`cal196-dossier-${premier.id}`)
    expect(within(bloc).getByText(premier.intitule)).toBeInTheDocument()

    const pieces = within(bloc).getByTestId('cal196-pieces')
    premier.pieces.forEach((piece) => {
      expect(within(pieces).getByText(piece.intitule)).toBeInTheDocument()
    })
    // Chaque pièce de l'échantillon porte une source : aucune n'est « non déclarée ».
    expect(within(pieces).getAllByTestId('cal196-source'))
      .toHaveLength(premier.pieces.length)
    expect(within(pieces).queryByText('source non déclarée')).toBeNull()
  })

  it('aucun champ « à compléter » n’est prérempli quand le serveur sert null', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    premier.champs_a_completer.forEach((champ) => {
      const saisie = screen.getByTestId(`cal196-champ-${champ.code}`)
      // `valeur: null` dans le contrat ⇒ champ VIDE à l'écran.
      expect(champ.valeur).toBeNull()
      expect(saisie).toHaveValue('')
      expect(screen.getByTestId(`cal196-message-${champ.code}`))
        .toHaveTextContent(champ.message)
    })
  })

  it('la génération est refusée avec le motif SERVEUR, jamais un motif inventé', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    expect(premier.peut_generer).toBe(false)
    expect(screen.getByTestId(`cal196-generer-${premier.id}`)).toBeDisabled()
    expect(screen.getByTestId(`cal196-motif-${premier.id}`))
      .toHaveTextContent(premier.motif_non_generable)
  })

  it('gabarit non déposé : le dossier reste visible et dit pourquoi', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const second = echantillon('exemple').dossiers[1]

    expect(second.gabarit.present).toBe(false)
    const bloc = screen.getByTestId(`cal196-dossier-${second.id}`)
    expect(bloc).toBeInTheDocument()
    expect(screen.getByTestId(`cal196-gabarit-${second.id}`))
      .toHaveTextContent('Gabarit non déposé')
    expect(within(bloc).getByTestId('cal196-pieces-vide')).toBeInTheDocument()
  })

  it('société sans gabarit : aucun dossier fantôme, et le message du serveur', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const vide = echantillon('exemple_vide')

    expect(vide.dossiers).toHaveLength(0)
    expect(screen.getByTestId('cal196-aucun-gabarit'))
      .toHaveTextContent(vide.message_aucun_gabarit)
    expect(screen.queryByTestId('cal196-pieces')).toBeNull()
    expect(screen.getByTestId('cal196-entete')).toHaveTextContent('Pays de la société : MA')
  })

  it('erreur réseau : message français, aucune pièce inventée', async () => {
    calepinageApi.calepinages.dossiersReglementaires.mockRejectedValue(new Error('boum'))
    rendre()

    expect(await screen.findByTestId('cal196-erreur')).toHaveTextContent(
      'Dossiers réglementaires indisponibles.',
    )
  })
})

/* ── CALX40 — la génération, autorisée par le SERVEUR et par lui seul ──────
   L'échantillon committé ne porte que des dossiers `peut_generer: false`
   (c'est son propos : rien n'est générable sans gabarit ni champs). Pour le
   cas AUTORISÉ, on part de CE MÊME échantillon et on bascule la seule clé que
   le serveur publie pour l'autoriser — aucune charge utile écrite à la main,
   aucune autre clé inventée. */
const servirGenerable = () => {
  const reponse = reponseContrat('calepinage', 'dossiers_reglementaires', 'exemple')
  calepinageApi.calepinages.dossiersReglementaires.mockResolvedValue({
    ...reponse,
    data: {
      ...reponse.data,
      dossiers: reponse.data.dossiers.map((dossier) => ({
        ...dossier, peut_generer: true, motif_non_generable: '',
      })),
    },
  })
}

describe('DossiersReglementaires — génération (CALX40)', () => {
  it('le bouton n’est actif que si le serveur déclare peut_generer', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    echantillon('exemple').dossiers.forEach((dossier) => {
      expect(dossier.peut_generer).toBe(false)
      expect(screen.getByTestId(`cal196-generer-${dossier.id}`)).toBeDisabled()
    })

    cleanup()
    servirGenerable()
    rendre()

    await screen.findByTestId('cal196-ecran')
    echantillon('exemple').dossiers.forEach((dossier) => {
      expect(screen.getByTestId(`cal196-generer-${dossier.id}`)).toBeEnabled()
    })
  })

  it('génère le dossier désigné et liste les pièces rendues par le serveur', async () => {
    servirGenerable()
    calepinageApi.calepinages.genererDossier.mockResolvedValue({
      data: {
        dossier: 1,
        document: 42,
        genere_le: '2026-09-21T10:00:00Z',
        pieces: [{ code: 'planche', libelle: 'Planche de calepinage' },
          { code: 'note_calcul', libelle: 'Note de calcul' }],
        signalements: [],
      },
    })
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]
    await userEvent.click(screen.getByTestId(`cal196-generer-${premier.id}`))

    await waitFor(() => {
      expect(calepinageApi.calepinages.genererDossier)
        .toHaveBeenCalledWith(1, { dossier: premier.id })
    })
    expect(await screen.findByTestId(`calx40-genere-${premier.id}`))
      .toHaveTextContent('Planche de calepinage, Note de calcul')
  })

  it('un refus 400 est rendu SOUS le champ que le serveur nomme', async () => {
    servirGenerable()
    const motif = 'Le gabarit « Dossier d’essai » n’a pas de fichier déposé.'
    calepinageApi.calepinages.genererDossier.mockRejectedValue({
      response: { data: { gabarit: [motif] } },
    })
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]
    await userEvent.click(screen.getByTestId(`cal196-generer-${premier.id}`))

    expect(await screen.findByTestId('calx40-erreur-gabarit'))
      .toHaveTextContent(motif)
    // Aucun message générique n'est fabriqué à côté du message serveur.
    expect(screen.queryByTestId(`calx40-genere-${premier.id}`)).toBeNull()
  })
})

/* ── CALX41 — les champs sont CONTRÔLÉS, ENREGISTRÉS, et relus ─────────────
   `apresSaisie` dérive MÉCANIQUEMENT l'état d'après-enregistrement de
   l'échantillon committé : le champ enregistré quitte `champs_a_completer` et
   rejoint `champs_saisis` avec sa valeur — ce que `composer_dossier` fait
   côté serveur. Aucune charge utile écrite à la main. */
const apresSaisie = (code, valeur) => {
  const reponse = reponseContrat('calepinage', 'dossiers_reglementaires', 'exemple')
  const dossiers = reponse.data.dossiers.map((dossier, rang) => {
    if (rang !== 0) return dossier
    const champ = dossier.champs_a_completer.find((c) => c.code === code)
    return {
      ...dossier,
      champs_a_completer: dossier.champs_a_completer.filter((c) => c.code !== code),
      champs_saisis: [...dossier.champs_saisis, { ...champ, valeur, message: '' }],
    }
  })
  return { ...reponse, data: { ...reponse.data, dossiers } }
}

describe('DossiersReglementaires — champs du dossier (CALX41)', () => {
  it('restitue les champs DÉJÀ enregistrés, avec la valeur du serveur', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    expect(premier.champs_saisis.length).toBeGreaterThan(0)
    premier.champs_saisis.forEach((champ) => {
      expect(screen.getByTestId(`cal196-champ-${champ.code}`))
        .toHaveValue(String(champ.valeur))
    })
  })

  it('n’enregistre rien tant que rien n’est saisi', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    expect(screen.getByTestId(`calx41-enregistrer-${premier.id}`)).toBeDisabled()
    expect(calepinageApi.calepinages.enregistrerChampsDossier)
      .not.toHaveBeenCalled()
  })

  it('quitter puis rouvrir restitue la saisie enregistrée', async () => {
    servir('exemple')
    const apres = apresSaisie('reference_dossier', 'DP-2026-01')
    calepinageApi.calepinages.enregistrerChampsDossier.mockResolvedValue(apres)
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    await userEvent.type(screen.getByTestId('cal196-champ-reference_dossier'), 'DP-2026-01')
    await userEvent.click(screen.getByTestId(`calx41-enregistrer-${premier.id}`))

    await waitFor(() => {
      expect(calepinageApi.calepinages.enregistrerChampsDossier)
        .toHaveBeenCalledWith(1, {
          dossier: premier.id, champs: { reference_dossier: 'DP-2026-01' },
        })
    })
    expect(await screen.findByTestId(`calx41-enregistre-${premier.id}`))
      .toHaveTextContent('Champs enregistrés.')

    // QUITTER puis ROUVRIR : le serveur sert désormais la saisie, et l'écran
    // la RESTITUE (elle n'est plus « à compléter », elle est enregistrée).
    cleanup()
    calepinageApi.calepinages.dossiersReglementaires.mockResolvedValue(apres)
    rendre()

    await screen.findByTestId('cal196-ecran')
    expect(screen.getByTestId('cal196-champ-reference_dossier'))
      .toHaveValue('DP-2026-01')
  })

  it('un champ refusé par le serveur est rendu SOUS ce champ', async () => {
    servir('exemple')
    const motif = 'Le champ « Référence du dossier » attend une valeur simple.'
    calepinageApi.calepinages.enregistrerChampsDossier.mockRejectedValue({
      response: { data: { reference_dossier: [motif] } },
    })
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    await userEvent.type(screen.getByTestId('cal196-champ-reference_dossier'), 'X')
    await userEvent.click(screen.getByTestId(`calx41-enregistrer-${premier.id}`))

    expect(await screen.findByTestId('calx41-erreur-reference_dossier'))
      .toHaveTextContent(motif)
    expect(screen.queryByTestId(`calx41-enregistre-${premier.id}`)).toBeNull()
  })
})

/* ACAL242 — joindre une pièce, ouvrir le document GED, utiliser la valeur du
   calepinage, bandeau « conception périmée » — rendu réel sur l'échantillon
   COMMITTÉ `dossiers_reglementaires.json`, seules les variations d'état
   (pièce fournie, écart, périmé) sont posées sur une COPIE de l'échantillon. */
describe('DossiersReglementaires — ACAL242', () => {
  const copie = () => structuredClone(reponseContrat('calepinage', 'dossiers_reglementaires', 'exemple'))

  it('joindre une piece la passe a fournie', async () => {
    const avant = copie()
    const apres = copie()
    const premier = avant.data.dossiers[0]
    const piece = premier.pieces.find((p) => p.etat !== 'fournie')
    apres.data.dossiers[0].pieces = apres.data.dossiers[0].pieces.map((p) => (
      p.code === piece.code ? { ...p, etat: 'fournie', message: '' } : p))
    calepinageApi.calepinages.dossiersReglementaires
      .mockResolvedValueOnce(avant).mockResolvedValueOnce(apres)
    calepinageApi.calepinages.joindrePiece.mockResolvedValue({
      data: { piece: piece.code, etat: 'fournie', attachment: 9, depose_le: '2026-10-07T10:00:00Z' },
    })
    rendre()
    await screen.findByTestId('cal196-ecran')

    const fichier = new File(['%PDF-1.4'], 'piece.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByTestId(`acal242-fichier-${piece.code}`), fichier)
    await userEvent.click(screen.getByTestId(`acal242-joindre-${piece.code}`))

    await waitFor(() => expect(calepinageApi.calepinages.joindrePiece).toHaveBeenCalled())
    const [id, corps] = calepinageApi.calepinages.joindrePiece.mock.calls[0]
    expect(id).toBe(1)
    expect(corps.get('dossier')).toBe(String(premier.id))
    expect(corps.get('piece')).toBe(piece.code)
    expect(corps.get('fichier')).toBeInstanceOf(File)
    // La relecture sert la pièce « fournie » : le bouton Joindre disparaît.
    await waitFor(() => expect(screen.queryByTestId(`acal242-joindre-${piece.code}`)).toBeNull())
  })

  it('lien vers le document GED', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('cal196-ecran')
    const [genere, jamais] = echantillon('exemple').dossiers
    expect(screen.getByTestId(`acal242-document-${genere.id}`))
      .toHaveAttribute('href', `/ged?document=${genere.document}`)
    expect(screen.queryByTestId(`acal242-document-${jamais.id}`)).toBeNull()
  })

  it('utiliser la valeur du calepinage', async () => {
    const reponse = copie()
    const champ = reponse.data.dossiers[0].champs_saisis[0]
    champ.valeur_calepinage = 'Valeur du calepinage d essai'
    champ.ecart_saisie = true
    calepinageApi.calepinages.dossiersReglementaires.mockResolvedValue(reponse)
    rendre()
    await screen.findByTestId('cal196-ecran')

    expect(screen.getByTestId(`acal242-ecart-${champ.code}`))
      .toHaveTextContent('Valeur du calepinage d essai')
    // Rien n'est écrit tant que l'utilisateur ne la choisit pas.
    expect(screen.getByTestId(`cal196-champ-${champ.code}`)).toHaveValue(champ.valeur)
    await userEvent.click(screen.getByTestId(`acal242-utiliser-${champ.code}`))
    expect(screen.getByTestId(`cal196-champ-${champ.code}`))
      .toHaveValue('Valeur du calepinage d essai')
    expect(calepinageApi.calepinages.enregistrerChampsDossier).not.toHaveBeenCalled()
  })

  it('bandeau conception perimee', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]
    // L'échantillon sert « à jour » : aucun bandeau.
    expect(screen.queryByTestId(`acal242-perime-${premier.id}`)).toBeNull()

    cleanup()
    const perime = copie()
    perime.data.dossiers[0].genere_sur_conception_perimee = true
    calepinageApi.calepinages.dossiersReglementaires.mockResolvedValue(perime)
    rendre()
    await screen.findByTestId('cal196-ecran')
    expect(screen.getByTestId(`acal242-perime-${premier.id}`))
      .toHaveTextContent('Généré sur une conception périmée')
  })
})
