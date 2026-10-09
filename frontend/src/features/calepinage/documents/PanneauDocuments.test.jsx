import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

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
import PanneauDocuments from './PanneauDocuments'

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
  it('le contrat committé porte bien les NEUF documents du lot 6', () => {
    const codes = exempleContrat(APP, NOM, 'exemple').documents.map((d) => d.code)
    expect(codes).toHaveLength(9)
    expect(codes).toEqual([
      'rapport_etude', 'rapport_ombrage', 'export_projet_json', 'plan_cablage',
      'manuel_proprietaire', 'document_asbuilt', 'dossier_fin_chantier',
      'diagramme_pertes', 'presentation_compacte',
    ])
  })

  it('9 documents servis ⇒ 9 lignes, rien de plus', async () => {
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

  it('sans conception (exemple_vide) : les NEUF boutons sont inactifs, motif ET manque lisibles', async () => {
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

    // Les NEUF sont indisponibles ici.
    for (const code of exempleContrat(APP, NOM, 'exemple_vide').documents.map((d) => d.code)) {
      expect(screen.getByTestId(`cal-doc-bouton-${code}`)).toBeDisabled()
    }
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
      .toHaveBeenCalledWith(documentDe('exemple', 'rapport_etude').endpoint, { langue: 'fr' })
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

  it('clic → renderImageHd(2) puis dépôt genre « ombrage », confirmation affichée', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderImageHd = vi.fn().mockResolvedValue({ blob, width: 800, height: 600, scale: 2 })
    calepinageApi.calepinages.deposerImageDocument.mockResolvedValue({
      data: { ok: true, genre: 'ombrage', attachment: 512, depose_le: '2026-09-23T10:00:00Z' },
    })
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderImageHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-images-confirmation'))
        .toHaveTextContent('2026-09-23T10:00:00Z')
    })
    expect(renderImageHd).toHaveBeenCalledWith(2)
    expect(calepinageApi.calepinages.deposerImageDocument).toHaveBeenCalledWith(
      1, { genre: 'ombrage', fichier: expect.stringContaining('data:') },
    )
  })

  it('un refus serveur (champ nommé) s’affiche SOUS la carte, jamais en tête de panneau', async () => {
    servirInventaire('exemple')
    const blob = new Blob(['png-simule'], { type: 'image/png' })
    const renderImageHd = vi.fn().mockResolvedValue({ blob, width: 800, height: 600, scale: 2 })
    calepinageApi.calepinages.deposerImageDocument.mockRejectedValue({
      response: { status: 400, data: { genre: 'Genre d’image inconnu : « ombrage ».' } },
    })
    const utilisateur = userEvent.setup()

    rendreAvecBuilder({ renderImageHd })
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-joindre-ombrage'))

    await waitFor(() => {
      expect(screen.getByTestId('cal-doc-images')).toHaveTextContent('Genre d’image inconnu')
    })
    expect(screen.queryByTestId('cal-doc-images-confirmation')).toBeNull()
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
      .toHaveBeenCalledWith(documentDe('exemple', 'rapport_etude').endpoint, { langue: 'en' }))
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
      .toHaveBeenCalledWith(doc.autres_formats[0].endpoint))
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
    render(<MemoryRouter><PanneauDocuments calepinageId={1} builderApi={{ renderImageHd }} /></MemoryRouter>)

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
      .toHaveBeenCalledWith(sortieDe('note_calcul_pdf').endpoint))
    expect(downloadBlob).toHaveBeenCalled()
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
    expect(calepinageApi.calepinages.composerPackTechnique).toHaveBeenCalledWith(1)
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
      .toHaveBeenCalledWith(sortieDe('planche_png').endpoint)
  })
})
