import { useSelector } from 'react-redux'

// NTI18N9 — devise d'AFFICHAGE de la société courante
// (`CompanyProfile.devise_tenant`, ISO 4217). Lit le profil déjà chargé par
// `Layout.jsx` (`fetchProfile`, `parametresSlice`) : aucun appel réseau, repli
// sur 'MAD' (comportement historique) tant que le profil n'est pas chargé.
// À passer à `formatMontant(value, { devise })` (lib/format.js).
export function useDeviseTenant() {
  return useSelector((s) => s.parametres?.profile?.devise_tenant) || 'MAD'
}

export default useDeviseTenant
