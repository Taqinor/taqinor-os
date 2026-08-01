// ODY30 — kill-switch build-time de la BASCULE de coquille « ERP-Apps ».
// ----------------------------------------------------------------------------
// Module volontairement minuscule et SANS AUCUN import : le flag a deux
// lecteurs (`components/layout/Layout.jsx`, contrat ODY30, et
// `lib/apps/ActiveAppContext.jsx`, qui décide réellement de la bascule) et
// Layout importe Sidebar qui importe ActiveAppContext — le définir dans l'un
// des deux créerait un cycle d'import. UNE définition, deux ré-exports, aucune
// dépendance tirée au passage.
//
// Défaut ON PARTOUT. Le flag ne gate QUE le paradigme de coquille (Menu
// d'accueil + immersion), JAMAIS une différence de fonctionnalité. Flag
// BUILD-TIME (Vite l'inline au bundle à la compilation) : changer sa valeur
// exige un rebuild d'image frontend (`docker compose up -d --build frontend`),
// jamais un simple redémarrage ni un `.env` rechargé à chaud. Le chemin OFF est
// un SMOKE D'URGENCE uniquement (repli legacy), non couvert par les tests
// unitaires — assumé et documenté par ODY30 ; son retrait est queued (ODY33).
export const APPS_SHELL_ENABLED = import.meta.env.VITE_APPS_SHELL !== '0'

export default APPS_SHELL_ENABLED
