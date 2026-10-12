// VNT45 — ouverture du PDF d'une facture (extrait de FacturerDevisDialog).
// Le PDF est généré en tâche de fond (202) : on le (re)génère — il doit porter
// les paiements consignés — puis on attend le fichier (sondage borné).
import ventesApi from '../../../api/ventesApi'
import { openPdfBlob } from '../../../utils/pdfBlob'

const ESSAIS = 10
const DELAI_MS = 1500
const attendre = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * Génère puis ouvre le PDF de la facture `factureId`.
 * @returns {Promise<'ouvert'|'attente'|'indisponible'>}
 */
export async function ouvrirPdfFacture(factureId, reference, { essais = ESSAIS, delaiMs = DELAI_MS } = {}) {
  try {
    await ventesApi.genererPdfFacture(factureId)
  } catch {
    return 'indisponible'
  }
  for (let i = 0; i < essais; i += 1) {
    await attendre(delaiMs)
    try {
      const res = await ventesApi.telechargerPdfFacture(factureId)
      openPdfBlob(res.data, `${reference}.pdf`)
      return 'ouvert'
    } catch (err) {
      console.warn('ouvrirPdfFacture : pas encore prêt', err)
    }
  }
  return 'attente'
}
