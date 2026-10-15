import adsengineApi from './adsengineApi'

/* Devise de la connexion Meta, chargée en tâche de fond par les écrans de la
   console (cockpit, campagnes, détail d'une ad) : `setCurrency` reçoit la devise
   de la connexion, « MAD » à défaut ; un échec ou une API sans `connection.get`
   laisse la devise courante inchangée. */
export function chargerDevise(setCurrency) {
  const connGet = adsengineApi.connection?.get
  if (connGet) {
    connGet()
      .then(r => setCurrency(r?.data?.currency || 'MAD'))
      .catch(() => {})
  }
}
