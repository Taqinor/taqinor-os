import { useSelector } from 'react-redux'

// NTI18N10 — fuseau horaire D'AFFICHAGE de la société courante
// (`CompanyProfile.fuseau_horaire`, IANA, défaut 'Africa/Casablanca' —
// comportement historique inchangé pour toute société qui n'a pas configuré
// ce champ). Le backend continue de stocker en UTC (aucun changement) ; ce
// hook lit la préférence déjà chargée par `Layout.jsx` au montage du shell
// authentifié (`fetchProfile`, `parametresSlice`) — jamais un appel réseau
// supplémentaire ici, et un no-op total tant que le profil n'est pas encore
// chargé (repli sur le défaut historique).
const DEFAUT = 'Africa/Casablanca'

export function useCompanyTimeZone() {
  return useSelector((s) => s.parametres?.profile?.fuseau_horaire) || DEFAUT
}

export default useCompanyTimeZone
