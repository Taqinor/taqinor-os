import { lazy, Suspense } from 'react'
import PwaPrompts from '../features/pwa/PwaPrompts'
// VX156 — moment d'accueil de marque, one-shot à la première connexion.
import WelcomeMoment from './WelcomeMoment'
import { Toaster } from '../ui/Toaster'
// Fête « affaire signée » : hôte global, hors de tout dialogue (au-dessus des modales).
import DealSignedCelebrationHost from '../ui/DealSignedCelebrationHost'
// NTI18N3 — langue d'interface persistée serveur (retrouvée d'un autre poste).
// Composant sans rendu, séparé pour ne pas coupler I18nProvider à Redux.
import ServerLocaleSync from '../i18n/ServerLocaleSync'

/* ADOC146 — SHELL GLOBAL : les composants montés HORS du RouterProvider
   (donc rendus pour TOUT compte connecté, y compris un compte PORTAIL
   client/fournisseur/partenaire). Ils vivaient en vrac dans main.jsx ; ADOC120
   a montré qu'un composant interne oublié ici (MessageAccueilModal : 403 +
   toast à chaque chargement ; WelcomeMoment : « Bienvenue chez Taqinor » à un
   client) casse l'expérience d'un compte externe sans qu'aucune garde ne le
   voie. La liste est ICI, une seule fois : `ShellGlobal.portail.test.jsx` rend
   ce composant pour chaque portée portail et échoue si un enfant appelle un
   endpoint hors /auth/ et /portail/ (sauf lecture silencieuse listée) ou affiche
   un toast ou une modale — tout composant ajouté plus tard entre
   AUTOMATIQUEMENT dans ce balayage.

   MSGACC1 — MessageAccueilModal est LAZY (budget bundle : sa modale ne
   conditionne pas le premier rendu) et monté EN PREMIER des deux accueils
   (message opérationnel posé par un responsable, avant l'accueil de marque). */
const MessageAccueilModal = lazy(() => import('./MessageAccueilModal'))

export default function ShellGlobal() {
  return (
    <>
      <ServerLocaleSync />
      <Toaster />
      <DealSignedCelebrationHost />
      <PwaPrompts />
      <Suspense fallback={null}><MessageAccueilModal /></Suspense>
      <WelcomeMoment />
    </>
  )
}
