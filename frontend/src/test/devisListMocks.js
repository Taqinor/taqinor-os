import { vi } from 'vitest'

/* ACAL345 — doubles de module PARTAGÉS des tests de la liste des devis.

   Les goldens SPL191/SPL192 recopiaient mot pour mot les fabriques `vi.mock`
   de DevisList.test.jsx (ventesSlice, ventesApi, crmApi, uxviewsApi). Ils les
   importent désormais d'ici, depuis la fabrique (hissée) :

     vi.mock('../../api/uxviewsApi', async () =>
       (await import('../../test/devisListMocks.js')).uxviewsApiMock())

   Mêmes valeurs que les copies d'origine : aucun réseau, réponses stables. */

// Thunks neutralisés : fetchDevis no-op, genererPdfDevis chaînable en .unwrap().
// `onGenererPdf(args)` permet à un test de journaliser l'appel.
export async function ventesSliceMock(importOriginal, { onGenererPdf } = {}) {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: vi.fn(() => ({ type: 'ventes/fetchDevis/noop' })),
    genererPdfDevis: (...args) => {
      if (onGenererPdf) onGenererPdf(args)
      const action = { type: 'ventes/genererPdfDevis/noop' }
      action.unwrap = () => Promise.resolve()
      return action
    },
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
}

// ventesApi : réponses de DevisList.test.jsx ; `extra` ajoute/remplace des méthodes.
export async function ventesApiMock(importOriginal, extra = {}) {
  const actual = await importOriginal()
  const pdfBlob = () => new Blob(['%PDF-1.4'], { type: 'application/pdf' })
  return {
    ...actual,
    default: {
      ...actual.default,
      refuserDevis: vi.fn(() => Promise.resolve({ data: { statut: 'refuse' } })),
      getDevisById: vi.fn(() => Promise.resolve({ data: { fichier_pdf: '/media/devis/DEV-PDF-AUTO.pdf' } })),
      etatPdfDevis: vi.fn(() => Promise.resolve({
        data: { devis: 99, statut: 'pret', fichier_pdf: true, erreur: null, date: null },
      })),
      getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
      historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
      noterDevis: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      accepterDevis: vi.fn(() => Promise.resolve({ data: {} })),
      telechargerPdfDevis: vi.fn(() => Promise.resolve({ data: pdfBlob(), headers: {} })),
      getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '25.00' } })),
      dupliquerVariante: vi.fn(() => Promise.resolve({ data: [] })),
      dupliquerVarianteGamme: vi.fn(() => Promise.resolve({ data: { source: {}, gamme: {}, gammes: [] } })),
      shareLinkDevis: vi.fn(() => Promise.resolve({ data: { token: 'tok123', path: '/proposition/tok123' } })),
      whatsappPreviewDevis: vi.fn(() => Promise.resolve({ data: { wa_url: 'https://wa.me/212600000000', message: 'Bonjour' } })),
      whatsappDevis: vi.fn(() => Promise.resolve({ data: { statut: 'envoye' } })),
      partagePdfDevis: vi.fn(() => Promise.resolve({ data: { devis_statut: 'envoye' } })),
      reviserDevis: vi.fn(() => Promise.resolve({ data: {} })),
      patchDevis: vi.fn(() => Promise.resolve({ data: {} })),
      ...extra,
    },
  }
}

// crmApi : taxonomie des motifs de perte (QX26).
export async function crmApiMotifsMock(importOriginal) {
  const actual = await importOriginal()
  const motifs = [{ id: 5, nom: 'Trop cher' }, { id: 6, nom: 'Choisi un concurrent' }]
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: motifs })) },
  }
}

// uxviewsApi : vues sauvegardées serveur (WIR21), liste vide.
export function uxviewsApiMock() {
  return {
    default: {
      listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      createSavedView: vi.fn(() => Promise.resolve({ data: { id: 1, ecran: 'ventes.devis' } })),
      updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
      deleteSavedView: vi.fn(() => Promise.resolve({})),
    },
  }
}
