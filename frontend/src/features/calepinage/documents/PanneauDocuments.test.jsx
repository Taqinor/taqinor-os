import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { readFileSync } from 'node:fs'

/* ============================================================================
   CALX320 — le panneau « Documents » BASCULE sur l'inventaire `documents/`
   (CALX291/321/322), DISTINCT de `sorties/` (CALX19/20-24, retiré de CE
   panneau — voir l'en-tête de `PanneauDocuments.jsx`).
   ----------------------------------------------------------------------------
   PACT10/PACT13 — AUCUNE CHARGE UTILE RETAPÉE ICI : les payloads viennent du
   document committé `backend/django_core/apps/calepinage/contract_samples/
   calepinage_documents.json`, le MÊME que le test backend
   `apps/calepinage/tests/test_calx291_contrat_documents.py` affirme. Un mock
   écrit à la main serait une DEUXIÈME source de vérité (l'incident
   « AO — Tableau de bord » du 03/08/2026, exactement ce que ces helpers
   empêchent).
   ========================================================================== */

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      documents: vi.fn(),
      telechargerDocument: vi.fn(),
      exporterConception: vi.fn(),
      importerConception: vi.fn(),
      deposerImageDocument: vi.fn(), // CALX302
      remettreDocument: vi.fn(), // ACAL223
      sorties: vi.fn(), // ACAL228
      telechargerSortie: vi.fn(), // ACAL228
      composerPackTechnique: vi.fn(), // ACAL228
      declencherDocument: vi.fn(), // ACAL223
      apercuDocument: vi.fn(), // ACAL223
      pretAEnvoyer: vi.fn(), // ACAL1193
      explications: vi.fn(() => Promise.resolve({ data: { entrees: [] } })), // ACAL1193
      sldPdf: vi.fn(), // ACAL1723
    },
  },
}))
vi.mock('../../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
  // Reprend la RÈGLE du vrai helper (lire `Content-Disposition`, jamais un
  // nom inventé) — assez fidèle pour prouver que le nom AFFICHÉ est bien
  // celui posé par le serveur, jamais un nom écrit en dur côté écran.
  filenameFromResponse: vi.fn((res, repli) => {
    const cd = res?.headers?.['content-disposition'] || ''
    return /filename="([^"]+)"/.exec(cd)?.[1] || `${repli}.bin`
  }),
}))

import calepinageApi from '../../../api/calepinageApi'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import { ONGLETS } from '../atelier/onglets'
import { OPTIONS_TELECHARGEMENT } from './telechargement'
import PanneauDocuments from './PanneauDocuments'
import EtapeDocuments from './EtapeDocuments'
import PretAEnvoyer from '../commun/PretAEnvoyer'
import { cartesGuide } from './cartesGuide'

const APP = 'calepinage'
const NOM = 'calepinage_documents'

const documentDe = (variante, code) =>
  exempleContrat(APP, NOM, variante).documents.find((d) => d.code === code)

const servirInventaire = (variante = 'exemple') => {
  calepinageApi.calepinages.documents.mockResolvedValue(reponseContrat(APP, NOM, variante))
}

const rendre = (calepinageId = 1) => render(
  <MemoryRouter><PanneauDocuments calepinageId={calepinageId} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauDocuments — bascule sur `documents/` (CALX320)', () => {
  it('le contrat committé porte bien les DIX documents du lot 6', () => {
    const codes = exempleContrat(APP, NOM, 'exemple').documents.map((d) => d.code)
    expect(codes).toHaveLength(10)
    expect(codes).toEqual([
      'rapport_etude', 'rapport_ombrage', 'export_projet_json', 'plan_cablage',
      'manuel_proprietaire', 'document_asbuilt', 'dossier_fin_chantier',
      'diagramme_pertes', 'presentation_compacte', 'pertes_en_postes',
    ])
  })

  it('10 documents servis ⇒ 10 lignes, rien de plus', async () => {
    servirInventaire('exemple')

    rendre()

    await screen.findByTestId('cal-doc-sortie-rapport_etude')
    for (const code of exempleContrat(APP, NOM, 'exemple').documents.map((d) => d.code)) {
      expect(screen.getByTestId(`cal-doc-sortie-${code}`)).toBeTruthy()
    }
    // Les anciens codes de `sorties/` (CALX19-24) n'ont plus AUCUNE carte ici.
    expect(screen.queryByTestId('cal-doc-sortie-planche_pdf')).toBeNull()
    expect(screen.queryByTestId('cal-doc-sortie-pack_technique')).toBeNull()
  })

  it('un seul onglet `documents` est inscrit au registre', () => {
    expect(ONGLETS.filter((o) => o.cle === 'documents')).toHaveLength(1)
  })

  it('un document DISPONIBLE : bouton actif, aucun motif ni manque affichés', async () => {
    servirInventaire('exemple') // rapport_etude disponible=true ici

    rendre()

    const bouton = await screen.findByTestId('cal-doc-bouton-rapport_etude')
    expect(bouton).toBeEnabled()
    expect(screen.queryByTestId('cal-doc-motif-rapport_etude')).toBeNull()
    expect(screen.queryByTestId('cal-doc-manque-rapport_etude')).toBeNull()
  })

  it('sans conception (exemple_vide) : les DIX boutons sont inactifs, motif ET manque lisibles', async () => {
    servirInventaire('exemple_vide')

    rendre(2) // exemple_vide::calepinage = 2

    const bouton = await screen.findByTestId('cal-doc-bouton-rapport_etude')
    expect(bouton).toBeDisabled()

    const attendu = documentDe('exemple_vide', 'rapport_etude')
    expect(screen.getByTestId('cal-doc-motif-rapport_etude'))
      .toHaveTextContent(attendu.motif_indisponible)
    expect(screen.getByTestId('cal-doc-manque-item-rapport_etude-roof_layout'))
      .toHaveTextContent(attendu.manque[0].libelle)
    expect(screen.getByTestId('cal-doc-manque-item-rapport_etude-roof_layout'))
      .toHaveTextContent(attendu.manque[0].ou_saisir)

    // Les DIX sont indisponibles ici.
    for (const code of exempleContrat(APP, NOM, 'exemple_vide').documents.map((d) => d.code)) {
      expect(screen.getByTestId(`cal-doc-bouton-${code}`)).toBeDisabled()
    }
  })

  it('ACAL942 — conception sans calcul (exemple_sans_calcul) : motif « il manque le calcul », geste nommé', async () => {
    servirInventaire('exemple_sans_calcul')

    rendre(2)

    const bouton = await screen.findByTestId('cal-doc-bouton-rapport_etude')
    expect(bouton).toBeDisabled()
    const attendu = documentDe('exemple_sans_calcul', 'rapport_etude')
    expect(screen.getByTestId('cal-doc-motif-rapport_etude'))
      .toHaveTextContent('Conception enregistrée — il manque le calcul')
    expect(screen.getByTestId('cal-doc-manque-item-rapport_etude-resultat'))
      .toHaveTextContent(attendu.manque[0].ou_saisir)
  })

  it('« ou_saisir » devient un LIEN vers l’onglet que NOMME le serveur (`manque[].onglet`, ACAL14)', async () => {
    servirInventaire('exemple') // dossier_fin_chantier : pieces → onglet « documents »

    rendre()

    const manque = documentDe('exemple', 'dossier_fin_chantier').manque
      .find((m) => m.champ === 'pieces')
    expect(manque.onglet).toBe('documents')
    const lien = await screen.findByTestId('cal-doc-manque-lien-dossier_fin_chantier-pieces')
    expect(lien).toHaveAttribute('href', `/calepinage/1?onglet=${manque.onglet}`)
    expect(lien).toHaveTextContent(manque.ou_saisir)
  })

  it('l’onglet du lien est CELUI du contrat, jamais retrouvé dans la phrase : plan_cablage → « affectation »', async () => {
    servirInventaire('exemple')

    rendre()

    const manque = documentDe('exemple', 'plan_cablage').manque
      .find((m) => m.champ === 'electrique.chainage')
    expect(manque.onglet).toBe('affectation')
    const lien = await screen.findByTestId('cal-doc-manque-lien-plan_cablage-electrique.chainage')
    expect(lien).toHaveAttribute('href', '/calepinage/1?onglet=affectation')
  })

  it('un « manque » dont `onglet` vaut null (geste dans l’atelier 3D / Réglages) reste un texte SIMPLE, jamais un lien', async () => {
    servirInventaire('exemple')

    rendre()

    await screen.findByTestId('cal-doc-sortie-rapport_ombrage')
    const manque = documentDe('exemple', 'rapport_ombrage').manque[0]
    expect(manque.onglet).toBeNull()
    expect(screen.queryByTestId(`cal-doc-manque-lien-rapport_ombrage-${manque.champ}`)).toBeNull()
    // Le texte NOMMÉ (celui du contrat, jamais retapé ici) reste lisible
    // malgré l'absence de lien.
    expect(screen.getByTestId(`cal-doc-manque-item-rapport_ombrage-${manque.champ}`))
      .toHaveTextContent(manque.ou_saisir)
  })

  it('l’empreinte de la conception (layout_hash) s’affiche en tête de panneau', async () => {
    servirInventaire('exemple')

    rendre()

    const empreinte = await screen.findByTestId('cal-doc-empreinte')
    const attendu = exempleContrat(APP, NOM, 'exemple').layout_hash.slice(0, 12)
    expect(empreinte).toHaveTextContent(attendu)
  })

  it('sans conception (exemple_vide) : aucune empreinte affichée (layout_hash null)', async () => {
    servirInventaire('exemple_vide')

    rendre(2)

    await screen.findByTestId('cal-doc-sortie-rapport_etude')
    expect(screen.queryByTestId('cal-doc-empreinte')).toBeNull()
  })

  it('clic sur « Télécharger » : télécharge via l’endpoint du serveur, nommé par le serveur', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerDocument.mockResolvedValue({
      data: new Blob(['%PDF-1.4']),
      headers: { 'content-disposition': 'attachment; filename="rapport-etude-1.pdf"' },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-rapport_etude'))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    // ACAL223 : une carte à deux langues transmet `{langue}` (défaut = data.langue).
    expect(calepinageApi.calepinages.telechargerDocument)
      .toHaveBeenCalledWith(documentDe('exemple', 'rapport_etude').endpoint, { langue: 'fr' },
        expect.objectContaining({ timeout: 120000 }))
    expect(filenameFromResponse).toHaveBeenCalled()
    expect(downloadBlob.mock.calls[0][1]).toBe('rapport-etude-1.pdf')
  })

  it('refus serveur au téléchargement : le motif s’affiche SOUS la carte concernée, jamais en tête', async () => {
    servirInventaire('exemple')
    const corpsErreur = { resultat: 'Aucun résultat de moteur enregistré.' }
    calepinageApi.calepinages.telechargerDocument.mockRejectedValue({
      response: {
        status: 400,
        data: new Blob([JSON.stringify(corpsErreur)], { type: 'application/json' }),
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-rapport_etude'))

    const carte = await screen.findByTestId('cal-doc-sortie-rapport_etude')
    await waitFor(() => {
      expect(carte.querySelector('[data-testid="cal-doc-erreurs"]'))
        .toHaveTextContent('Aucun résultat de moteur enregistré.')
    })
    expect(screen.queryByTestId('cal-doc-erreur')).toBeNull() // pas de bandeau de tête
    expect(downloadBlob).not.toHaveBeenCalled()
  })

  it('l’enveloppe `error` du handler global n’est jamais rendue (« [object Object] »)', async () => {
    servirInventaire('exemple')
    const motif = 'La conception vendue a changé : rien n’est rendu.'
    const corpsErreur = {
      calepinage: [motif],
      error: { code: 'conflict', message: motif, fields: {}, request_id: 'r-1' },
    }
    calepinageApi.calepinages.telechargerDocument.mockRejectedValue({
      response: {
        status: 409,
        data: new Blob([JSON.stringify(corpsErreur)], { type: 'application/json' }),
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-rapport_etude'))

    const carte = await screen.findByTestId('cal-doc-sortie-rapport_etude')
    await waitFor(() => {
      expect(carte.querySelector('[data-testid="cal-doc-erreurs"]')).toHaveTextContent(motif)
    })
    const erreurs = carte.querySelector('[data-testid="cal-doc-erreurs"]')
    expect(erreurs).not.toHaveTextContent('[object Object]')
    expect(erreurs.querySelectorAll('li')).toHaveLength(1)
  })
})

describe('PanneauDocuments — versions (CALX322/CALX320)', () => {
  it('un document à UNE version affiche « Dernière version » et son téléchargement', async () => {
    servirInventaire('exemple') // rapport_etude porte UNE version dans le contrat

    rendre()

    const version = documentDe('exemple', 'rapport_etude').versions[0]
    const ligne = await screen.findByTestId(`cal-doc-version-rapport_etude-${version.numero}`)
    expect(ligne).toHaveTextContent('Dernière version')
    expect(ligne).toHaveTextContent(`v${version.numero}`)
    expect(screen.getByTestId(`cal-doc-version-telecharger-rapport_etude-${version.numero}`))
      .toHaveAttribute('href', `/api/django/records/attachments/${version.attachment}/download/`)
  })

  it('un document à DEUX versions offre les DEUX téléchargements', async () => {
    // PACT10 : la charge de BASE vient du contrat committé (clonée) — SEULE
    // la cardinalité de `versions[]` est étendue ici, avec la MÊME forme que
    // la version 1 déjà publiée (même précédent que
    // `PanneauProduction.test.jsx` qui compose deux variantes du contrat).
    const exemple = JSON.parse(JSON.stringify(exempleContrat(APP, NOM, 'exemple')))
    const rapport = exemple.documents.find((d) => d.code === 'rapport_etude')
    const version1 = rapport.versions[0]
    rapport.versions = [
      { ...version1, numero: 2, produit_le: '2026-09-20T09:00:00Z', attachment: 777 },
      version1,
    ]
    calepinageApi.calepinages.documents.mockResolvedValue({ data: exemple })

    rendre()

    const derniere = await screen.findByTestId('cal-doc-version-rapport_etude-2')
    expect(derniere).toHaveTextContent('Dernière version')
    const anterieure = screen.getByTestId('cal-doc-version-rapport_etude-1')
    expect(anterieure).toHaveTextContent('Version antérieure')
    expect(screen.getByTestId('cal-doc-version-telecharger-rapport_etude-2'))
      .toHaveAttribute('href', '/api/django/records/attachments/777/download/')
    expect(screen.getByTestId('cal-doc-version-telecharger-rapport_etude-1'))
      .toHaveAttribute('href', `/api/django/records/attachments/${version1.attachment}/download/`)
  })

  it('aucune version produite : rien ne s’affiche sous la carte', async () => {
    servirInventaire('exemple_vide')

    rendre(2)

    await screen.findByTestId('cal-doc-sortie-rapport_etude')
    expect(screen.queryByTestId('cal-doc-versions-rapport_etude')).toBeNull()
  })
})

describe('PanneauDocuments — images jointes (CALX302/CALX320)', () => {
  it('les images DÉJÀ déposées (contrat `images[]`) sont visibles, avec leur téléchargement', async () => {
    servirInventaire('exemple') // exemple::images = [{genre: 'ombrage', attachment: 512, ...}]

    rendre()

    const image = exempleContrat(APP, NOM, 'exemple').images[0]
    const item = await screen.findByTestId(`cal-doc-image-${image.genre}-${image.attachment}`)
    expect(item).toHaveTextContent('chaleur')
    expect(item.querySelector('a')).toHaveAttribute(
      'href', `/api/django/records/attachments/${image.attachment}/download/`,
    )
  })

  it('aucune image déposée (exemple_vide) : rien ne s’affiche', async () => {
    servirInventaire('exemple_vide')

    rendre(2)

    await screen.findByTestId('cal-doc-sortie-rapport_etude')
    expect(screen.queryByTestId('cal-doc-images-jointes')).toBeNull()
  })
})

describe('PanneauDocuments — export/import du document de conception (CALX28)', () => {
  it('les deux boutons sont toujours visibles, HORS de l’inventaire (`disponible` ne les gouverne pas)', async () => {
    servirInventaire('exemple_vide') // tout le reste est indisponible ici

    rendre(2)

    expect(await screen.findByTestId('cal-doc-bouton-export-layout')).toBeEnabled()
    expect(screen.getByTestId('cal-doc-bouton-import-layout')).toBeEnabled()
  })

  it('exporter télécharge le document TEL QUEL en JSON', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.exporterConception.mockResolvedValue({
      data: { roof_layout: { version: 2, zones: [] }, layout_hash: 'abc123', schema_version: 2 },
    })
    const utilisateur = userEvent.setup()

    rendre(1)
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-export-layout'))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.exporterConception).toHaveBeenCalledWith(1)
    expect(downloadBlob.mock.calls[0][1]).toBe('conception-calepinage-1.json')
    const contenu = JSON.parse(await downloadBlob.mock.calls[0][0].text())
    expect(contenu.layout_hash).toBe('abc123')
  })

  it('importer un document valide confirme l’enregistrement', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.importerConception.mockResolvedValue({
      data: { calepinage: 1, layout_hash: 'nouveau-hash', inchange: false },
    })
    const utilisateur = userEvent.setup()

    rendre(1)
    const document = { version: 2, zones: [] }
    const fichier = new File([JSON.stringify(document)], 'conception.json', { type: 'application/json' })
    await utilisateur.upload(await screen.findByTestId('cal-doc-fichier-import-layout'), fichier)

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-conception-confirmation'))
        .toHaveTextContent('Conception importée et enregistrée.')
    })
    expect(calepinageApi.calepinages.importerConception).toHaveBeenCalledWith(1, document)
  })

  it('un document invalide affiche le CHEMIN JSON du premier défaut et n’écrase rien', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.importerConception.mockRejectedValue({
      response: {
        status: 400,
        data: { 'zones.0.vertices': 'Document refusé au champ « zones.0.vertices » : trop peu de sommets.' },
      },
    })
    const utilisateur = userEvent.setup()

    rendre(1)
    const fichier = new File([JSON.stringify({ version: 2, zones: [{}] })], 'conception.json',
      { type: 'application/json' })
    await utilisateur.upload(await screen.findByTestId('cal-doc-fichier-import-layout'), fichier)

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-conception')).toHaveTextContent('zones.0.vertices')
    })
    expect(screen.queryByTestId('cal-doc-conception-confirmation')).toBeNull()
    expect(downloadBlob).not.toHaveBeenCalled()
  })

  it('T4-X5-009 — un fichier sans toit n’écrase rien et ne remplace qu’après confirmation en mots', async () => {
    servirInventaire('exemple')
    const message = 'Ce fichier ne décrit aucun toit (ni contour ni pan) : l’importer effacerait le toit déjà '
      + 'dessiné. Rien n’a été enregistré.'
    calepinageApi.calepinages.importerConception
      .mockRejectedValueOnce({
        response: { status: 409, data: { roof_layout: message, confirmation_requise: true } },
      })
      .mockResolvedValueOnce({ data: { calepinage: 1, layout_hash: 'h2', inchange: false } })
    const utilisateur = userEvent.setup()

    rendre(1)
    const document = { version: 2, zones: [] }
    const fichier = new File([JSON.stringify(document)], 'conception.json', { type: 'application/json' })
    await utilisateur.upload(await screen.findByTestId('cal-doc-fichier-import-layout'), fichier)

    const avis = await screen.findByTestId('cal-doc-conception-remplacement')
    expect(avis).toHaveTextContent('Rien n’a été enregistré.')
    expect(avis).not.toHaveTextContent('confirmation_requise')
    expect(screen.queryByTestId('cal-doc-conception-confirmation')).toBeNull()

    await utilisateur.click(screen.getByTestId('cal-doc-bouton-remplacer-toit'))
    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-conception-confirmation'))
        .toHaveTextContent('Conception importée et enregistrée.')
    })
    expect(calepinageApi.calepinages.importerConception).toHaveBeenLastCalledWith(
      1, { roof_layout: document, remplacer_toit: true })
    expect(screen.queryByTestId('cal-doc-conception-remplacement')).toBeNull()
  })

  it('un JSON illisible est refusé AVANT tout appel serveur, même régime d’erreur', async () => {
    servirInventaire('exemple')
    const utilisateur = userEvent.setup()

    rendre(1)
    const fichier = new File(['{ceci n\'est pas du JSON'], 'conception.json', { type: 'application/json' })
    await utilisateur.upload(await screen.findByTestId('cal-doc-fichier-import-layout'), fichier)

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-conception')).toHaveTextContent('JSON valide')
    })
    expect(calepinageApi.calepinages.importerConception).not.toHaveBeenCalled()
  })
})

describe('PanneauDocuments — joindre la carte de chaleur (CALX302)', () => {
  const rendreAvecBuilder = (builderApi, calepinageId = 1) => render(
    <MemoryRouter><PanneauDocuments calepinageId={calepinageId} builderApi={builderApi} /></MemoryRouter>,
  )

  it('sans builderApi, le bouton est désactivé et le dit', async () => {
    servirInventaire('exemple')

    rendreAvecBuilder(null)

    expect(await screen.findByTestId('cal-doc-bouton-joindre-ombrage')).toBeDisabled()
    expect(screen.getByTestId('cal-doc-images-outil-absent')).toBeInTheDocument()
  })

  it('clic → renderCarteAccesHd(2) puis dépôt genre « ombrage », confirmation affichée', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderCarteAccesHd = vi.fn().mockResolvedValue({ blob, width: 800, height: 600, scale: 2 })
    calepinageApi.calepinages.deposerImageDocument.mockResolvedValue({
      data: { ok: true, genre: 'ombrage', attachment: 512, depose_le: '2026-09-23T10:00:00Z' },
    })
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderCarteAccesHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-images-confirmation'))
        .toHaveTextContent('2026-09-23T10:00:00Z')
    })
    expect(renderCarteAccesHd).toHaveBeenCalledWith(2)
    expect(calepinageApi.calepinages.deposerImageDocument).toHaveBeenCalledWith(
      1, { genre: 'ombrage', fichier: expect.stringContaining('data:') },
    )
  })

  it('un refus serveur (champ nommé) s’affiche SOUS la carte, jamais en tête de panneau', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderCarteAccesHd = vi.fn().mockResolvedValue({ blob, width: 800, height: 600, scale: 2 })
    calepinageApi.calepinages.deposerImageDocument.mockRejectedValue({
      response: { status: 400, data: { genre: 'Genre d’image inconnu : « ombrage ».' } },
    })
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderCarteAccesHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-images')).toHaveTextContent('Genre d’image inconnu')
    })
    expect(screen.queryByTestId('cal-doc-images-confirmation')).toBeNull()
  })

  it('ACAL726 — sans ombre saisie : le motif est servi et rien n’est déposé', async () => {
    servirInventaire('exemple')
    const renderCarteAccesHd = vi.fn().mockResolvedValue(null)
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderCarteAccesHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-images')).toHaveTextContent('Rien à teinter : saisissez une ombre ou un obstacle avec sa hauteur, et posez les panneaux.')
    })
    expect(calepinageApi.calepinages.deposerImageDocument).not.toHaveBeenCalled()
  })

  it('ACAL1621 — jamais la vue 3D ordinaire sous le nom de carte de chaleur : sans rendu teinté, rien n’est déposé', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderImageHd = vi.fn().mockResolvedValue({ blob, width: 800, height: 600, scale: 2 })
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderImageHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    expect(await screen.findByTestId('cal-doc-images')).toHaveTextContent('Outil non prêt')
    expect(renderImageHd).not.toHaveBeenCalled()
    expect(calepinageApi.calepinages.deposerImageDocument).not.toHaveBeenCalled()
  })
})

describe('PanneauDocuments — contrat documents v2 (ACAL223)', () => {
  it('envoie la langue choisie en params au telechargement et a la remise', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerDocument.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    calepinageApi.calepinages.remettreDocument.mockResolvedValue({ data: { numero: 3 } })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.selectOptions(await screen.findByTestId('cal-doc-langue-rapport_etude'), 'en')
    await utilisateur.click(screen.getByTestId('cal-doc-bouton-rapport_etude'))
    await waitFor(() => expect(calepinageApi.calepinages.telechargerDocument)
      .toHaveBeenCalledWith(documentDe('exemple', 'rapport_etude').endpoint, { langue: 'en' },
        expect.objectContaining({ timeout: 120000 })))
    await utilisateur.click(await screen.findByTestId('cal-doc-remettre-rapport_etude'))
    await waitFor(() => expect(calepinageApi.calepinages.remettreDocument)
      .toHaveBeenCalledWith(1, { code: 'rapport_etude', langue: 'en' }))
  })

  it('appelle POST pour une carte methode POST et affiche les signalements', async () => {
    servirInventaire('exemple')
    const doc = documentDe('exemple', 'dossier_fin_chantier')
    // Le contrat sert ce document indisponible : on le rend disponible en
    // gardant TOUTE sa forme (methode, endpoint) — jamais un payload à la main.
    calepinageApi.calepinages.documents.mockResolvedValue({
      data: {
        ...exempleContrat(APP, NOM, 'exemple'),
        documents: [{ ...doc, disponible: true, manque: [], motif_indisponible: null }],
      },
    })
    calepinageApi.calepinages.declencherDocument.mockResolvedValue({
      data: {
        document: 9, nom: 'Dossier de fin de chantier',
        pieces: [{ code: 'plan_pose', libelle: 'Plan de pose', pages: 2 }],
        pages_attendues: 2, signalements: ['Recette IEC 62446-1 : à fournir par le chantier.'],
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-dossier_fin_chantier'))

    expect(await screen.findByTestId('cal-doc-post-signalements'))
      .toHaveTextContent('Recette IEC 62446-1')
    expect(calepinageApi.calepinages.declencherDocument).toHaveBeenCalledWith(doc.endpoint)
    expect(calepinageApi.calepinages.telechargerDocument).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-doc-post-lien-ged')).toHaveAttribute('href', '/ged')
  })

  it('Remettre appelle remettreDocument puis recharge les versions', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.remettreDocument.mockResolvedValue({ data: { numero: 3 } })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-remettre-rapport_etude'))

    await waitFor(() => expect(calepinageApi.calepinages.documents).toHaveBeenCalledTimes(2))
    expect(calepinageApi.calepinages.remettreDocument)
      .toHaveBeenCalledWith(1, { code: 'rapport_etude', langue: 'fr' })
  })

  it('lien d’onglet par clé manque[].onglet, texte simple quand null', async () => {
    servirInventaire('exemple')
    rendre()
    const lien = await screen.findByTestId('cal-doc-manque-lien-plan_cablage-electrique.chainage')
    expect(lien.getAttribute('href')).toContain('affectation')
    expect(screen.queryByTestId('cal-doc-manque-lien-rapport_ombrage-roof_layout.zones[].geometry.solarAccess.values'))
      .toBeNull()
  })

  it('carte francais seulement affiche la mention, sans selecteur', async () => {
    servirInventaire('exemple')
    rendre()
    expect(await screen.findByTestId('cal-doc-langue-fr-seul-manuel_proprietaire'))
      .toHaveTextContent('Ce document n’existe qu’en français')
    expect(screen.queryByTestId('cal-doc-langue-manuel_proprietaire')).toBeNull()
    expect(screen.getByTestId('cal-doc-langue-rapport_etude')).toBeInTheDocument()
  })

  it('Apercu appelle apercu-document avec code et langue', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.apercuDocument.mockResolvedValue({ data: '<html></html>' })
    const creer = vi.fn(() => 'blob:apercu')
    const ouvrir = vi.fn()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: creer }))
    const fenetre = vi.spyOn(window, 'open').mockImplementation(ouvrir)
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-apercu-rapport_etude'))

    await waitFor(() => expect(ouvrir).toHaveBeenCalled())
    expect(calepinageApi.calepinages.apercuDocument)
      .toHaveBeenCalledWith(1, 'rapport_etude', { langue: 'fr' })
    fenetre.mockRestore()
    vi.unstubAllGlobals()
  })

  it('la carte plan_cablage propose le DXF', async () => {
    servirInventaire('exemple')
    const doc = documentDe('exemple', 'plan_cablage')
    calepinageApi.calepinages.documents.mockResolvedValue({
      data: {
        ...exempleContrat(APP, NOM, 'exemple'),
        documents: [{ ...doc, disponible: true, manque: [], motif_indisponible: null }],
      },
    })
    calepinageApi.calepinages.telechargerDocument.mockResolvedValue({ data: new Blob(['0']), headers: {} })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-autre-format-plan_cablage-dxf'))

    await waitFor(() => expect(calepinageApi.calepinages.telechargerDocument)
      .toHaveBeenCalledWith(doc.autres_formats[0].endpoint, undefined,
        expect.objectContaining({ timeout: 120000 })))
  })

  it("ACAL769 : un dépassement de délai dit quoi faire sur la carte, sans toast ; l'attente est annoncée", async () => {
    servirInventaire('exemple')
    let rejeter
    calepinageApi.calepinages.telechargerDocument.mockReturnValue(
      new Promise((_ok, ko) => { rejeter = ko }))
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-rapport_etude'))
    expect(await screen.findByTestId('acal769-attente')).toHaveTextContent("jusqu'à 2 minutes")
    expect(calepinageApi.calepinages.telechargerDocument.mock.calls[0][2])
      .toEqual({ timeout: 120000, suppressErrorToast: true })
    rejeter({ code: 'ECONNABORTED' })

    const carte = await screen.findByTestId('cal-doc-sortie-rapport_etude')
    await waitFor(() => {
      expect(within(carte).getByTestId('cal-doc-erreurs'))
        .toHaveTextContent("Le serveur n'a pas fini de préparer ce document en 2 minutes")
    })
    expect(within(carte).getByTestId('cal-doc-erreurs')).not.toHaveTextContent('injoignable')
  })

  it('une version perimee est signalee, une version a jour aussi', async () => {
    servirInventaire('exemple')
    rendre()
    expect(await screen.findByTestId('cal-doc-version-rapport_etude-1')).toHaveTextContent('périmée')
    expect(screen.getByTestId('cal-doc-version-rapport_etude-2')).toHaveTextContent('à jour')
  })
})

describe('PanneauDocuments — section Images (ACAL225)', () => {
  it('ne propose plus le diagramme de pertes', async () => {
    servirInventaire('exemple')
    rendre()
    await screen.findByTestId('cal-doc-bouton-joindre-ombrage')
    expect(screen.queryByTestId('cal-doc-bouton-joindre-pertes')).toBeNull()
    expect(screen.queryByText(/Joindre le diagramme de pertes/)).toBeNull()
  })

  it('affiche le badge Perimee d’une image perimee, avec la consigne', async () => {
    servirInventaire('exemple')
    const image = exempleContrat(APP, NOM, 'exemple').images[0]
    calepinageApi.calepinages.documents.mockResolvedValue({
      data: {
        ...exempleContrat(APP, NOM, 'exemple'),
        images: [{ ...image, perimee: true }],
      },
    })
    rendre()
    const badge = await screen.findByTestId(`cal-doc-image-perimee-${image.genre}-${image.attachment}`)
    expect(badge).toHaveTextContent('Périmée')
    expect(screen.getByTestId(`cal-doc-image-${image.genre}-${image.attachment}`))
      .toHaveTextContent('Rejoindre depuis l’atelier')
  })

  it('une image a jour n’a aucun badge Perimee', async () => {
    servirInventaire('exemple') // images[0].perimee = false dans le contrat
    const image = exempleContrat(APP, NOM, 'exemple').images[0]
    rendre()
    await screen.findByTestId(`cal-doc-image-${image.genre}-${image.attachment}`)
    expect(screen.queryByTestId(`cal-doc-image-perimee-${image.genre}-${image.attachment}`)).toBeNull()
  })

  it('apres Joindre l’inventaire est recharge', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderImageHd = vi.fn().mockResolvedValue({ blob, width: 8, height: 6, scale: 2 })
    calepinageApi.calepinages.deposerImageDocument.mockResolvedValue({
      data: { ok: true, genre: 'ombrage', attachment: 512, depose_le: '2026-09-23T10:00:00Z' },
    })
    const utilisateur = userEvent.setup()
    render(<MemoryRouter><PanneauDocuments calepinageId={1} builderApi={{ renderCarteAccesHd: renderImageHd }} /></MemoryRouter>)

    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => expect(calepinageApi.calepinages.documents).toHaveBeenCalledTimes(2))
  })
})

describe('PanneauDocuments — section Plans et exports (ACAL228)', () => {
  const sortieDe = (code) =>
    exempleContrat(APP, 'calepinage_sorties', 'exemple').sorties.find((x) => x.code === code)

  const servirSorties = () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.sorties.mockResolvedValue(
      reponseContrat(APP, 'calepinage_sorties', 'exemple'))
  }

  it('affiche une carte par code de sorties/ avec son bouton', async () => {
    servirSorties()
    rendre()
    for (const code of ['planche_pdf', 'plan_pose_pdf', 'note_calcul_pdf', 'dxf', 'tableur_csv', 'pack_technique']) {
      expect(await screen.findByTestId(`cal-doc-bouton-${code}`)).toBeInTheDocument()
    }
    // sortie indisponible : motif servi, bouton inactif
    expect(screen.getByTestId('cal-doc-bouton-plan_masse_pdf')).toBeDisabled()
    expect(screen.getByTestId('cal-doc-sorties-motif-plan_masse_pdf'))
      .toHaveTextContent(sortieDe('plan_masse_pdf').motif_indisponible)
  })

  it('telecharge l’endpoint servi tel quel', async () => {
    servirSorties()
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    const utilisateur = userEvent.setup()
    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-note_calcul_pdf'))
    await waitFor(() => expect(calepinageApi.calepinages.telechargerSortie)
      .toHaveBeenCalledWith(sortieDe('note_calcul_pdf').endpoint, undefined,
        { timeout: 120000, suppressErrorToast: true }))
    expect(downloadBlob).toHaveBeenCalled()
  })

  it('ACAL1534 — la pièce plan_lestage_pdf porte Aperçu et Télécharger, et l’aperçu ouvre le même PDF dans un onglet', async () => {
    servirInventaire('exemple')
    const sorties = reponseContrat(APP, 'calepinage_sorties', 'exemple')
    sorties.data.sorties = sorties.data.sorties.map((x) => (
      x.code === 'plan_lestage_pdf' ? { ...x, disponible: true, motif_indisponible: null } : x))
    calepinageApi.calepinages.sorties.mockResolvedValue(sorties)
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    const ouvrir = vi.spyOn(window, 'open').mockImplementation(() => null)
    const creer = vi.fn(() => 'blob:lestage')
    URL.createObjectURL = creer
    const utilisateur = userEvent.setup()
    rendre()
    expect(await screen.findByTestId('cal-doc-bouton-plan_lestage_pdf')).toBeEnabled()
    await utilisateur.click(await screen.findByTestId('cal-doc-sorties-apercu-plan_lestage_pdf'))
    await waitFor(() => expect(ouvrir).toHaveBeenCalledWith('blob:lestage', '_blank', 'noopener'))
    expect(calepinageApi.calepinages.telechargerSortie)
      .toHaveBeenCalledWith(sortieDe('plan_lestage_pdf').endpoint, undefined,
        { timeout: 120000, suppressErrorToast: true })
    // une pièce qui n'est pas un PDF n'a pas d'Aperçu
    expect(screen.queryByTestId('cal-doc-sorties-apercu-dxf')).toBeNull()
    ouvrir.mockRestore()
  })

  it('pack technique appelle composerPackTechnique et affiche les signalements', async () => {
    servirSorties()
    calepinageApi.calepinages.composerPackTechnique.mockResolvedValue({
      data: {
        document: 4, nom: 'Dossier technique',
        pieces: [{ code: 'planche', libelle: 'Planche', pages: 1 }],
        pages_attendues: 1, signalements: ['Recette IEC 62446-1 produite par le chantier.'],
      },
    })
    const utilisateur = userEvent.setup()
    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-pack_technique'))
    expect(await screen.findByTestId('cal-doc-post-signalements'))
      .toHaveTextContent('Recette IEC 62446-1')
    expect(calepinageApi.calepinages.composerPackTechnique)
      .toHaveBeenCalledWith(1, { timeout: 120000, suppressErrorToast: true })
  })

  it('un bouton Remettre est propose pour les PDF du registre seulement', async () => {
    servirSorties()
    calepinageApi.calepinages.remettreDocument.mockResolvedValue({ data: {} })
    const utilisateur = userEvent.setup()
    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-remettre-planche_pdf'))
    await waitFor(() => expect(calepinageApi.calepinages.remettreDocument)
      .toHaveBeenCalledWith(1, { code: 'planche_pdf' }))
    expect(screen.queryByTestId('cal-doc-remettre-dxf')).toBeNull()
  })

  it('planche_png rasterise planche.svg', async () => {
    servirSorties()
    const png = new Blob(['png'], { type: 'image/png' })
    class FauxImage { set src(_v) { this.width = 3; this.height = 2; queueMicrotask(() => this.onload?.()) } }
    globalThis.Image = FauxImage
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:svg')
    globalThis.URL.revokeObjectURL = vi.fn()
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() }))
    HTMLCanvasElement.prototype.toBlob = vi.fn((cb) => cb(png))
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({
      data: new Blob(['<svg xmlns="http://www.w3.org/2000/svg"/>'], { type: 'image/svg+xml' }),
    })
    const utilisateur = userEvent.setup()
    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-planche_png'))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith(png, 'planche-calepinage-1.png'))
    expect(calepinageApi.calepinages.telechargerSortie)
      .toHaveBeenCalledWith(sortieDe('planche_png').endpoint, undefined,
        { timeout: 120000, suppressErrorToast: true })
  })

  it('R3-20 : un dépassement de délai sur une sortie dit quoi faire, en français', async () => {
    servirSorties()
    calepinageApi.calepinages.telechargerSortie.mockRejectedValue(
      Object.assign(new Error('timeout of 20000ms exceeded'), { code: 'ECONNABORTED' }))
    const utilisateur = userEvent.setup()
    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-note_calcul_pdf'))
    const texte = await screen.findByText(/n'a pas fini de préparer ce document en 2 minutes/)
    expect(texte).toBeInTheDocument()
    expect(screen.queryByText(/timeout of/)).toBeNull()
  })
})

describe('EtapeDocuments — l’écran guidé de la maquette (ACAL1193)', () => {
  const pret = exempleContrat(APP, 'calepinage_pret_a_envoyer', 'exemple')
  // Dix contrôles, comme la maquette : le contrat porte un modèle de ligne par état, décliné par code.
  const CODES = ['visite_validee', 'pentes_confirmees', 'kwc_coherent', 'taille_sans_facture', 'ombrage_chiffre',
    'tension_froid', 'ratio_dc_ac', 'chutes_tension', 'ecart_pvgis', 'simulation_fraiche']
  const [, modeleARegler, , modeleOk] = pret.controles
  const dixControles = () => CODES.map((code, i) => ({
    ...(i === 1 ? modeleARegler : modeleOk),
    code,
    libelle: `Contrôle ${code}`,
    valeur_texte: `Valeur ${i}`,
    ...(i === 1 ? { cible: { etape: 'toit', onglet: 'releve', champ: '' } } : {}),
  }))
  const servir = (controles = dixControles()) => {
    servirInventaire('exemple')
    calepinageApi.calepinages.sorties.mockResolvedValue(reponseContrat(APP, 'calepinage_sorties', 'exemple'))
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue({
      data: {
        ...pret,
        controles,
        nombre_bloquants: controles.filter((c) => c.etat === 'bloquant').length,
        nombre_a_regler: controles.filter((c) => c.etat === 'a_regler').length,
        pret: false,
      },
    })
  }
  const monter = (props = {}) => render(
    <MemoryRouter>
      <EtapeDocuments calepinageId={1} actionDevis={<button type="button">Générer le devis</button>} {...props} />
    </MemoryRouter>,
  )
  const controlesVisibles = (racine) => [...racine.querySelectorAll('button, a[href], input, select, textarea, summary')]
    .filter((e) => !e.disabled && !e.hidden)

  it('deux colonnes : « Prêt à envoyer ? » rangé par étape à gauche, les documents à droite', async () => {
    servir()
    monter()
    const gauche = await screen.findByTestId('cal-docs-controles')
    expect(await within(gauche).findByRole('heading', { name: 'Prêt à envoyer ?' })).toBeTruthy()
    expect(screen.getByTestId('cal-documents-synthese')).toHaveTextContent('9 contrôles sur 10 sont bons.')
    expect(within(gauche).getAllByRole('heading', { level: 3 }).map((h) => h.textContent))
      .toEqual(['Toit', 'Panneaux — 3 bons', 'Électrique — 3 bons', 'Résultats — 2 bons']) // ACAL1725 : sans point ⇒ replié
    expect(gauche).toHaveTextContent('1 point à régler')
    expect(within(screen.getByTestId('cal-pret-ligne-pentes_confirmees'))
      .getByRole('button', { name: 'Régler dans Toit' })).toBeTruthy()
    expect(within(gauche).getByRole('group', { name: 'Légende' })).toHaveTextContent('BonÀ réglerBloque le devis')
    expect(within(screen.getByTestId('cal-etape-documents-devis'))
      .getByRole('button', { name: 'Générer le devis' })).toBeTruthy()
    expect(gauche).toHaveTextContent('Le point à régler n’empêche pas le devis')
    const droite = await screen.findByTestId('cal-docs-liste')
    expect(within(droite).getByRole('heading', { level: 2 })).toHaveTextContent('Documents du projet')
    const cartes = within(droite).getAllByTestId('cal-docs-carte')
    expect(cartes.map((c) => c.dataset.document))
      .toEqual(['plan_pose', 'schema', 'note_calcul', 'rapport_etude', 'dxf'])
    for (const carte of cartes) {
      expect(carte.querySelector('svg[aria-hidden="true"]')).toBeTruthy() // la vignette
      expect(within(carte).getByRole('button', { name: /Télécharger/ })).toBeTruthy()
    }
    // ACAL1726 — « Aperçu » et « Télécharger » du document choisi vivent dans la colonne d'aperçu, plus sur la carte
    expect(within(cartes[0]).queryByRole('button', { name: 'Aperçu' })).toBeNull()
    const apercu = within(droite).getByTestId('cal-docs-colonne-apercu')
    expect(within(apercu).getByRole('button', { name: 'Aperçu' })).toBeTruthy()
    expect(droite).toHaveTextContent('Le devis remis au client ne se fait pas ici')
    expect(droite.querySelectorAll('[data-vignette]')).toHaveLength(6) // cinq cartes + la feuille de l'aperçu
  })

  it('ACAL1931 : inventaire des plans illisible — les cinq cartes restent, les pièces de sorties grisées avec leur motif', async () => {
    servir()
    calepinageApi.calepinages.sorties.mockRejectedValue(new Error('500'))
    monter()
    const droite = await screen.findByTestId('cal-docs-liste')
    await waitFor(() => expect(within(droite).getAllByTestId('cal-docs-carte')).toHaveLength(5))
    const cartes = within(droite).getAllByTestId('cal-docs-carte')
    expect(cartes.map((c) => c.dataset.document)).toEqual(['plan_pose', 'schema', 'note_calcul', 'rapport_etude', 'dxf'])
    for (const cle of ['plan_pose', 'note_calcul', 'dxf']) {
      expect(screen.getByTestId(`cal-docs-telecharger-${cle}`)).toBeDisabled()
      expect(screen.getByTestId(`cal-docs-motif-${cle}`)).toHaveTextContent('n’a pas pu être lue')
    }
  })

  it('ACAL1931 : un nouvel enregistrement relit l’inventaire des plans', async () => {
    servir()
    const { rerender } = monter({ enregistreLe: '2026-11-23T11:18:00Z' })
    await screen.findByTestId('cal-docs-liste')
    const avant = calepinageApi.calepinages.sorties.mock.calls.length
    rerender(
      <MemoryRouter>
        <EtapeDocuments calepinageId={1} enregistreLe="2026-11-23T12:40:00Z" actionDevis={<button type="button">Générer le devis</button>} />
      </MemoryRouter>,
    )
    await waitFor(() => expect(calepinageApi.calepinages.sorties.mock.calls.length).toBeGreaterThan(avant))
  })

  it('ACAL1726 : la colonne d’aperçu montre le document choisi ; un clic sur une carte le change, la note bleue est dans la colonne', async () => {
    servir()
    const utilisateur = userEvent.setup()
    monter()
    const colonne = await screen.findByTestId('cal-docs-colonne-apercu')
    expect(colonne).toHaveAttribute('data-document', 'plan_pose')
    expect(within(colonne).getByText('Plan de pose pour l’équipe')).toBeTruthy()
    expect(within(colonne).getByTestId('cal-docs-info-devis')).toBeTruthy()
    expect(screen.getAllByTestId('cal-docs-carte').filter((c) => c.dataset.choisie === 'oui').map((c) => c.dataset.document))
      .toEqual(['plan_pose'])
    await utilisateur.click(screen.getByRole('button', { name: 'Schéma électrique' }))
    expect(screen.getByTestId('cal-docs-colonne-apercu')).toHaveAttribute('data-document', 'schema')
    expect(screen.getByRole('button', { name: 'Schéma électrique' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Plan de pose pour l’équipe' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('ACAL1726 : chaque carte porte sa pastille « Prêt · PDF » ou « Il manque : … » (le libellé servi)', async () => {
    servir()
    monter()
    await screen.findByTestId('cal-docs-liste')
    expect(screen.getByTestId('cal-docs-pastille-plan_pose')).toHaveTextContent('Prêt · PDF')
    expect(screen.getByTestId('cal-docs-pastille-rapport_etude')).toHaveTextContent('Prêt · PDF')
    // `plan_cablage` n'est pas prêt dans l'exemple du contrat : son manque est celui du serveur, mot pour mot
    expect(screen.getByTestId('cal-docs-pastille-schema')).toHaveTextContent('Il manque : Schéma unifilaire (chaînage électrique)')
    expect(documentDe('exemple', 'plan_cablage').manque[0].libelle).toBe('Schéma unifilaire (chaînage électrique)')
  })

  it('ACAL1726 : une pièce à aperçu HTML montre sa première page réelle (cadre isolé) ; sinon le modèle de page, dit comme tel', async () => {
    servir()
    calepinageApi.calepinages.apercuDocument.mockResolvedValue({ data: '<html><body><h1>Rapport servi</h1></body></html>' })
    const utilisateur = userEvent.setup()
    monter()
    const colonne = await screen.findByTestId('cal-docs-colonne-apercu')
    expect(within(colonne).getByTestId('cal-docs-colonne-legende')).toHaveTextContent('Modèle de page de ce document')
    expect(within(colonne).queryByTestId('cal-docs-colonne-feuille-reelle')).toBeNull() // PDF de `sorties/` : pas d'aperçu HTML
    await utilisateur.click(screen.getByRole('button', { name: 'Rapport d’étude' }))
    const reelle = await screen.findByTestId('cal-docs-colonne-feuille-reelle')
    const cadre = reelle.querySelector('iframe')
    expect(cadre.getAttribute('srcdoc')).toContain('Rapport servi')
    expect(cadre.getAttribute('sandbox')).toBe('') // aucun script du document servi ne s'exécute
    expect(screen.getByTestId('cal-docs-colonne-legende')).toHaveTextContent('Aperçu de la première page')
    expect(calepinageApi.calepinages.apercuDocument).toHaveBeenCalledWith(1, 'rapport_etude', { langue: expect.any(String) })
  })

  it('ACAL1726 : aperçu HTML refusé par le serveur — le modèle de page reste, jamais une feuille vide', async () => {
    servir()
    calepinageApi.calepinages.apercuDocument.mockRejectedValue(new Error('500'))
    const utilisateur = userEvent.setup()
    monter()
    await utilisateur.click(await screen.findByRole('button', { name: 'Rapport d’étude' }))
    await waitFor(() => expect(calepinageApi.calepinages.apercuDocument).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-docs-colonne-feuille-reelle')).toBeNull()
    expect(screen.getByTestId('cal-docs-colonne-legende')).toHaveTextContent('Modèle de page de ce document')
  })

  it('ACAL1726 : une pièce indisponible choisie dit son motif servi en entier dans la colonne, boutons inactifs', async () => {
    servir()
    const utilisateur = userEvent.setup()
    monter()
    await utilisateur.click(await screen.findByRole('button', { name: 'Schéma électrique' }))
    const colonne = screen.getByTestId('cal-docs-colonne-apercu')
    expect(within(colonne).getByTestId('cal-docs-colonne-motif')).toHaveTextContent(screen.getByTestId('cal-docs-motif-schema').textContent)
    expect(within(colonne).getByTestId('cal-docs-colonne-telecharger-schema')).toBeDisabled()
    expect(within(colonne).getByTestId('cal-docs-apercu-schema')).toBeDisabled()
  })

  it('ACAL1834 : l’anneau de progression dit la part de contrôles bons ; la carte ouverte porte l’état « choisie »', async () => {
    servir()
    monter()
    const anneau = await screen.findByTestId('cal-docs-anneau')
    expect(anneau).toHaveAttribute('aria-label', '9 contrôles bons sur 10')
    expect(screen.getAllByTestId('cal-docs-carte').filter((c) => c.dataset.choisie === 'oui')).toHaveLength(1)
  })

  it('aucune empreinte en guidé ; « Faits à partir de … » seulement si l’heure est relayée', async () => {
    servir()
    const { unmount } = monter()
    await screen.findByTestId('cal-docs-liste')
    expect(screen.queryByTestId('cal-doc-empreinte')).toBeNull()
    expect(screen.queryByText(/Faits à partir de la version enregistrée/)).toBeNull()
    unmount()
    monter({ enregistreLe: '2026-11-22T14:41:00' })
    expect(await screen.findByText(/Faits à partir de la version enregistrée à 14:41\./)).toBeTruthy()
  })

  it('télécharger passe par les helpers existants, mêmes options et mêmes textes d’erreur', async () => {
    servir()
    calepinageApi.calepinages.telechargerDocument.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    const utilisateur = userEvent.setup()
    monter()
    await utilisateur.click(await screen.findByTestId('cal-docs-telecharger-rapport_etude'))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
    expect(calepinageApi.calepinages.telechargerDocument.mock.calls[0][2])
      .toEqual({ timeout: 120000, suppressErrorToast: true })
    calepinageApi.calepinages.telechargerSortie.mockRejectedValue(
      Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))
    await utilisateur.click(screen.getByTestId('cal-docs-telecharger-note_calcul'))
    expect(await screen.findByText(/n'a pas fini de préparer ce document en 2 minutes/)).toBeTruthy()
  })

  it('une pièce indisponible est grisée avec son motif servi, jamais un bouton mort', async () => {
    servir()
    const sorties = reponseContrat(APP, 'calepinage_sorties', 'exemple')
    sorties.data.sorties = sorties.data.sorties.map((x) => (x.code === 'dxf'
      ? { ...x, disponible: false, motif_indisponible: 'Aucune conception enregistrée.' } : x))
    calepinageApi.calepinages.sorties.mockResolvedValue(sorties)
    monter()
    expect(await screen.findByTestId('cal-docs-telecharger-dxf')).toBeDisabled()
    expect(screen.getByTestId('cal-docs-motif-dxf')).toHaveTextContent('Aucune conception enregistrée.')
    expect(screen.queryByTestId('cal-docs-apercu-dxf')).toBeNull() // le DXF n’a pas d’aperçu
  })

  // Suite des écrans v2 (24/11) — à 1440 × 900, trois pièces indisponibles faisaient défiler la colonne des cartes
  // (769 px dans 746, la carte DXF coupée) : le motif tient sur une ligne dans la carte, la colonne prend toute la hauteur.
  it('colonne des cartes : la section remplit sa colonne ; le motif d’une carte sur UNE ligne, en entier dans l’aperçu', async () => {
    const style = document.createElement('style')
    style.textContent = readFileSync('src/styles/calepinage/55-etape-documents.css', 'utf8')
    document.head.appendChild(style)
    try {
      servir()
      const sorties = reponseContrat(APP, 'calepinage_sorties', 'exemple')
      const long = 'Conception enregistrée — il manque le calcul : lancez la simulation à l’étape Résultats, puis revenez ici.'
      sorties.data.sorties = sorties.data.sorties.map((x) => ({ ...x, disponible: false, motif_indisponible: long }))
      calepinageApi.calepinages.sorties.mockResolvedValue(sorties)
      monter()
      const motif = await screen.findByTestId('cal-docs-motif-dxf')
      const c = getComputedStyle(motif)
      expect([c.whiteSpace, c.overflow, c.textOverflow]).toEqual(['nowrap', 'hidden', 'ellipsis'])
      expect(getComputedStyle(screen.getByTestId('cal-docs-liste')).flexGrow).toBe('1')
      fireEvent.click(within(motif.closest('[data-testid="cal-docs-carte"]')).getByRole('button', { pressed: false }))
      expect(await screen.findByTestId('cal-docs-colonne-motif')).toHaveTextContent(long) // le motif servi, en entier
    } finally {
      style.remove()
    }
  })

  // T4-X7-009 — tablette (1180 × 820 et 820 × 1180) : la liste des cartes mesurait 4 px (flex-basis 0 dans une colonne de
  // hauteur automatique) — le rapport d'étude ne s'atteignait pas. Sous 1 300 px, les cartes prennent leur hauteur.
  it('T4-X7-009 — sous 1 300 px, la liste des cartes prend la hauteur de ses cartes (jamais une boîte de 4 px)', async () => {
    const brut = document.createElement('style')
    brut.textContent = readFileSync('src/styles/calepinage/55-etape-documents.css', 'utf8')
    document.head.appendChild(brut)
    const regles = [...brut.sheet.cssRules]
    const style = document.createElement('style')
    style.textContent = regles.filter((r) => r.type !== 4).map((r) => r.cssText)
      .concat(regles.filter((r) => r.type === 4 && /max-width: 1300px/.test(r.conditionText))
        .flatMap((m) => [...m.cssRules].map((r) => r.cssText))).join(' ')
    brut.remove()
    document.head.appendChild(style)
    try {
      servir()
      monter()
      await screen.findByTestId('cal-docs-liste')
      const c = getComputedStyle(document.querySelector('.cdoc-cartes'))
      expect([c.flexGrow, c.flexShrink, c.flexBasis]).toEqual(['0', '0', 'auto'])
      expect(c.overflowY).toBe('visible')
      expect(screen.getAllByTestId('cal-docs-carte')).toHaveLength(5)
    } finally {
      style.remove()
    }
  })

  it('ACAL1193 — contrôles visibles de l’écran guidé : au plus 26 (la maquette v2 en dessine 24 ; + les trois lignes de groupe repliées, ACAL1725)', async () => {
    servir()
    const { container } = monter()
    await screen.findByTestId('cal-docs-liste')
    await screen.findByTestId('cal-pret-ligne-visite_validee')
    const n = controlesVisibles(container).length
    // dix « ? », « Régler dans Toit », trois lignes de groupe repliées, « Générer le devis », « Aperçu » + « Télécharger » de la colonne, cinq titres de carte, cinq icônes de téléchargement
    console.info(`ACAL1193 contrôles visibles (écran guidé, 10 contrôles) : ${n} :: ${controlesVisibles(container).map((e) => e.getAttribute('aria-label') || e.textContent.trim()).join(' | ')}`)
    expect(n).toBeLessThanOrEqual(26)
  })
  it('F4 — gabarit de la maquette : aucune marge propre à l’écran, les contrôles défilent DANS leur carte, vignettes à plat', async () => {
    const css = readFileSync('src/styles/calepinage/55-etape-documents.css', 'utf8')
      .split(String.fromCharCode(13)).join('')
    const bloc = (sel) => {
      const debut = css.lastIndexOf(`${sel} {`)
      return debut < 0 ? '' : css.slice(debut, css.indexOf('}', debut))
    }
    expect(bloc('.cdoc-ecran')).not.toMatch(/padding/) // le centre de l'atelier donne déjà 24 / 28 px
    expect(bloc('.cdoc-groupes')).toMatch(/overflow-y: auto/)
    expect(bloc('.cdoc-groupes')).toMatch(/min-height: 0/)
    expect(bloc('.cdoc-pied')).toMatch(/flex: none/) // la légende et « Générer le devis » ne défilent pas
    servir()
    monter()
    await screen.findByTestId('cal-docs-liste')
    expect(document.querySelectorAll('[data-vignette]')).toHaveLength(6) // cinq cartes + la feuille de l'aperçu
  })
  it('PretAEnvoyer `filtre` : seule l’étape demandée, compte compris ; sans `groupes` la présentation d’origine', async () => {
    servir()
    render(<MemoryRouter><PretAEnvoyer calepinageId={1} testIdCompte="compte" filtre="electrique" /></MemoryRouter>)
    // tension_froid, ratio_dc_ac, chutes_tension (tous ok) : « Prêt à envoyer », aucun autre contrôle
    expect(await screen.findByTestId('compte')).toHaveTextContent('Prêt à envoyer')
    expect(screen.queryByTestId('cal-pret-ligne-visite_validee')).toBeNull()
    expect(screen.queryByTestId('cal-pret-groupe-electrique')).toBeNull() // pas `groupes` : présentation d'origine
    expect(screen.getByTestId('cal-pret-reussis')).toHaveTextContent('Voir les 3 contrôles réussis')
  })
})


describe('EtapeDocuments — la carte « Schéma électrique » livre le schéma dessiné (ACAL1723)', () => {
  const pret = exempleContrat(APP, 'calepinage_pret_a_envoyer', 'exemple')
  const servirPieceCablagePrete = () => {
    const inventaire = structuredClone(reponseContrat(APP, NOM, 'exemple'))
    const cablage = inventaire.data.documents.find((d) => d.code === 'plan_cablage')
    cablage.disponible = true
    cablage.manque = []
    cablage.motif_indisponible = ''
    calepinageApi.calepinages.documents.mockResolvedValue(inventaire)
    calepinageApi.calepinages.sorties.mockResolvedValue(reponseContrat(APP, 'calepinage_sorties', 'exemple'))
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue({ data: { ...pret } })
  }
  const monter = () => render(
    <MemoryRouter>
      <EtapeDocuments calepinageId={1} actionDevis={<button type="button">Générer le devis</button>} />
    </MemoryRouter>,
  )

  it('« Télécharger » de la carte appelle le PDF du schéma unifilaire, jamais le plan de câblage', async () => {
    servirPieceCablagePrete()
    calepinageApi.calepinages.sldPdf.mockResolvedValue({
      data: new Blob(['%PDF']), headers: { 'content-disposition': 'attachment; filename="calepinage-1-schema.pdf"' } })
    const utilisateur = userEvent.setup()
    monter()
    const bouton = await screen.findByTestId('cal-docs-telecharger-schema')
    await waitFor(() => expect(bouton).not.toBeDisabled())
    await utilisateur.click(bouton)
    await waitFor(() => expect(calepinageApi.calepinages.sldPdf).toHaveBeenCalledWith(1, OPTIONS_TELECHARGEMENT))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'calepinage-1-schema.pdf'))
    expect(calepinageApi.calepinages.telechargerDocument).not.toHaveBeenCalled()
  })

  it('« Aperçu » de la colonne ouvre l’onglet AVANT la réponse, y pose le PDF puis révoque l’URL ; un refus ferme l’onglet et est dit sous la carte', async () => {
    servirPieceCablagePrete()
    const onglet = { location: { href: '' }, close: vi.fn(), opener: 'x' }
    const ouvrir = vi.spyOn(window, 'open').mockImplementation(() => onglet)
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:schema')
    globalThis.URL.revokeObjectURL = vi.fn()
    const minuteurs = vi.spyOn(globalThis, 'setTimeout')
    let rendre
    calepinageApi.calepinages.sldPdf
      .mockImplementationOnce(() => new Promise((resoudre) => { rendre = () => resoudre({ data: new Blob(['%PDF']) }) }))
      .mockRejectedValueOnce({ response: { status: 409, data: { onduleur: 'Le schéma unifilaire n’est pas exportable.' } } })
    const utilisateur = userEvent.setup()
    monter()
    await utilisateur.click(await screen.findByRole('button', { name: 'Schéma électrique' }))
    await waitFor(() => expect(screen.getByTestId('cal-docs-apercu-schema')).not.toBeDisabled())
    await utilisateur.click(screen.getByTestId('cal-docs-apercu-schema'))
    // L'onglet est déjà ouvert alors que le serveur n'a pas encore répondu (le geste du clic n'est pas perdu).
    expect(ouvrir).toHaveBeenCalledWith('', '_blank')
    expect(onglet.opener).toBeNull()
    expect(onglet.location.href).toBe('')
    rendre()
    await waitFor(() => expect(onglet.location.href).toBe('blob:schema'))
    expect(globalThis.URL.revokeObjectURL).not.toHaveBeenCalled()
    const revoquer = minuteurs.mock.calls.find(([, delai]) => delai === 60000)
    expect(revoquer).toBeTruthy()
    revoquer[0]()
    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith('blob:schema')
    await waitFor(() => expect(screen.getByTestId('cal-docs-apercu-schema')).not.toBeDisabled())
    await utilisateur.click(screen.getByTestId('cal-docs-apercu-schema'))
    expect(await screen.findByText(/n’est pas exportable/)).toBeTruthy()
    expect(onglet.close).toHaveBeenCalledTimes(1)
    ouvrir.mockRestore()
    minuteurs.mockRestore()
  })
})

describe('cartesGuide — la carte DXF ne promet pas une chaîne absente (ACAL1721)', () => {
  const sorties = [{ code: 'dxf', disponible: true, format: 'dxf' }]
  const carteDxf = (documents) => cartesGuide(documents, sorties).find((c) => c.cle === 'dxf')

  it('avec un câblage publié, la carte promet le pan ET la chaîne', () => {
    const { description } = carteDxf([{ code: 'plan_cablage', disponible: true }])
    expect(description.includes('son pan et sa chaîne')).toBe(true)
  })

  it('sans câblage publié, la carte promet le numéro et le pan, jamais la chaîne', () => {
    const { description } = carteDxf([{ code: 'plan_cablage', disponible: false }])
    expect(description.includes('chaîne')).toBe(false)
    expect(description.includes('avec son pan')).toBe(true)
  })
})
