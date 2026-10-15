import crmApi from '../../api/crmApi'
import { searchCompanies, hitsToOptions } from './companyLookup'

/* Recherche d'entreprise existante (clients / fournisseurs / leads, données
   propres) : options du Combobox pour une requête saisie. */
export const rechercherEntreprises = (query) =>
  searchCompanies(query, { searcher: crmApi.searchClients }).then(hitsToOptions)

/* Recherche d'un CLIENT existant (les fournisseurs et leads sont écartés) :
   options { value, label } du Combobox pour une requête saisie. */
export const rechercherClients = async (query) => {
  const hits = await searchCompanies(query, { searcher: crmApi.searchClients })
  const clientHits = hits.filter((h) => h.source === 'client')
  return clientHits.map((h) => ({ value: String(h.id), label: h.nom }))
}
