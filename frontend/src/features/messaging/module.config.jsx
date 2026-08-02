import { MessageSquare } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   ODY22 — Config du module « Messages » (messagerie interne / Discuss).
   ----------------------------------------------------------------------------
   `features/messaging/` (Composer, ConversationList, MessageThread…) ne
   portait AUCUN module.config.jsx : l'écran /messages (ChatPage, dans
   `pages/messaging/ChatPage.jsx`) est enregistré en dur dans
   `router/index.jsx:340` (authLoader, tout rôle) et son lien de nav vivait
   UNIQUEMENT dans la section « tête » codée en dur de `Sidebar.jsx:150-156`
   (« Dashboard / Ma file / Messages » — sans `key` de module, donc jamais
   masquée par un toggle). Ce fichier COMPLÈTE la nav de l'app « Messages »
   (registre `moduleNavSections`) pour qu'ODY4 (extraction des sections en dur
   de la Sidebar) ait un module.config prêt à consommer — même patron que la
   complétion de /ged dans `features/ged/module.config.jsx`.

   La clé de module « chat » (ci-dessous) reprend TEL QUEL celle du manifest
   backend `apps.chat` (`apps/chat/apps.py` — label « Messagerie ») : aucun
   nouveau manifest côté Django, `scripts/check_modules.py` (CI ODX21) exige
   que toute clé frontend corresponde à une clé backend, et « chat »/
   « messaging » désignent le MÊME module (juste des noms de dossier
   différents entre back et front).

   La route `/messages` reste enregistrée dans `router/index.jsx` (ChatPage
   n'est pas importé ici) : `routes` est donc VOLONTAIREMENT vide — dupliquer
   l'entrée de route créerait un chemin `/messages` déclaré deux fois dans
   l'arbre du routeur. `nav`/`titles`/`sectionLabels` suffisent : ils ne font
   que POINTER vers la route déjà vivante ailleurs.
   ========================================================================== */

const config = {
  key: 'chat',
  order: 15,
  nav: {
    label: 'MESSAGES',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(MessageSquare),
    accent: 'azur', // VX8 — communication/info = accent azur (dérivé)
    items: [
      {
        to: '/messages',
        label: 'Messages',
        icon: <MessageSquare size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
    ],
  },
  titles: [['/messages', 'Messages']],
  sectionLabels: { messages: 'Messages' },
  // ODY22 — /messages (ChatPage) déjà routée dans router/index.jsx : aucune
  // entrée `routes` ici (voir note d'en-tête).
  routes: [],
}

export default config
