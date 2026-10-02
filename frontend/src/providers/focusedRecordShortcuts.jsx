// VX248 — Registre des raccourcis d'ACTION sur le RECORD FOCALISÉ (la fiche
// ouverte à l'écran), à ne JAMAIS confondre avec la navigation
// (GOTO_SHORTCUTS/CREATE_SHORTCUTS, shortcuts.js) ou la palette ⌘K.
//
// @coord NTUX9/18 — la palette ⌘K est CHERCHER-PUIS-EXÉCUTER (n'importe quel
// enregistrement, depuis n'importe où) ; ce registre est TROUVER-UN-RACCOURCI
// CONNU sur l'enregistrement DÉJÀ OUVERT à l'écran — mécanismes disjoints,
// jamais fusionnés.
//
// Chaque écran de détail déclare ICI ses touches (`FOCUSED_RECORD_SHORTCUTS`),
// ce qui alimente À LA FOIS le câblage clavier réel (`useFocusedRecordShortcuts`)
// ET la cheatsheet « ? » de ShortcutsProvider.jsx (apprentissage passif,
// groupée par écran ACTIF via `ActiveScreenProvider`/`useActiveScreen` +
// filtrée par rôle — un filtre d'AFFICHAGE seulement, JAMAIS une désactivation
// fonctionnelle : les touches marchent pour tout le monde, peu importe le
// rôle affiché en tête).
//
// Portée de CETTE tâche (Files: LeadForm.jsx/DevisList.jsx/FactureList.jsx) :
// seuls ces 3 écrans sont câblés. Le Ticket SAV est un écran candidat FUTUR
// (aucun fichier `sav/*` touché ici) — délibérément ABSENT du registre pour
// ne jamais afficher un raccourci qui ne fait rien (exactement le défaut que
// cette tâche corrige par ailleurs : la cheatsheet promettait déjà des
// raccourcis identiques à tous les rôles sans jamais les adapter).
import { createContext, useContext, useEffect, useState } from 'react'
import { PIPELINE_STAGES, STAGE_LABELS } from '../features/crm/stages'
import { isTypingTarget } from './shortcuts'

// VX248 — 4 touches de stage = les transitions du QUOTIDIEN commercial
// (Nouveau → Contacté → Devis envoyé → Relance). SIGNED exige le dialogue
// d'acceptation (devis + option, jamais un PATCH direct — même garde que
// LeadForm.handleSubmit) ; COLD est un abandon délibéré. Ni l'un ni l'autre
// ne reçoit de raccourci à une touche. Labels dérivés de STAGE_LABELS —
// JAMAIS un libellé en dur (règle #2 — les clés viennent de STAGES.py).
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée, pas un composant
export const LEAD_STAGE_SHORTCUTS = PIPELINE_STAGES.slice(0, 4).map((stage, i) => ({
  key: String(i + 1),
  stage,
  label: `Étape : ${STAGE_LABELS[stage]}`,
}))

// VX248 — `roles` est un filtre d'AFFICHAGE de la cheatsheet (regroupement
// « Pour votre rôle » d'abord), calqué sur la même classification que
// Dashboard.jsx `cockpitProfile` (commercial/sav/directeur) SANS en dépendre
// (évite une dépendance providers→pages) — voir `roleProfile` dans
// ShortcutsProvider.jsx.
// eslint-disable-next-line react-refresh/only-export-components -- registre co-localisé, pas un composant
export const FOCUSED_RECORD_SHORTCUTS = {
  leadForm: {
    title: 'Fiche lead',
    roles: ['commercial'],
    // INCIDENT 02/10/2026 — plus de touche « a » pour archiver : un lead
    // vivant (« ouissam merbahi ») a disparu du pipeline sur UNE frappe tapée
    // dans le panneau devis ouvert par-dessus la fiche. Masquer un lead n'a
    // plus de raccourci à une touche : bouton ou ⌘K, toujours confirmés
    // (LeadWorkspace.doArchive).
    items: [
      { key: 'd', label: 'Aller au responsable (déléguer)' },
      // LW23 — nouveau : bascule le rail contexte sur l'onglet Historique et
      // focus le composer (événement `lw:open-note-composer`, cf.
      // features/crm/workspace/LeadWorkspace.jsx).
      { key: 'n', label: "Noter (bascule sur l'onglet Historique)" },
      ...LEAD_STAGE_SHORTCUTS,
    ],
  },
  devisDetail: {
    title: 'Devis (édition)',
    roles: ['commercial'],
    items: [
      { key: 'a', label: 'Générer le PDF' },
    ],
  },
  factureDetail: {
    title: 'Facture (édition)',
    roles: ['commercial'],
    items: [
      { key: 'a', label: 'Générer le PDF' },
    ],
  },
}

/**
 * useFocusedRecordShortcuts — câble les touches déclarées pour `screenId`
 * (registre ci-dessus) tant que `enabled` est vrai. `handlers` = { [key]: fn }
 * — une touche du registre SANS handler fourni par l'appelant reste un no-op
 * (ex. une fiche en CRÉATION n'a pas encore de responsable à déléguer).
 * Jamais dans un champ de saisie (`isTypingTarget`, même garde que
 * ShortcutsProvider) ni avec un modificateur (réservé au système/⌘K).
 * Enregistre aussi `screenId` comme écran ACTIF (pour la cheatsheet) tant que
 * `enabled` est vrai, et le retire au démontage/désactivation.
 *
 * `scopeRef` (optionnel) — un élément DE l'écran qui déclare les touches.
 * Fourni, les touches se coupent dès qu'une boîte de dialogue qui ne contient
 * PAS cet écran est ouverte (panneau devis, confirmation, popover… posés
 * par-dessus) : une frappe destinée à l'écran du dessus n'agit jamais sur la
 * fiche du dessous (incident 02/10/2026 — voir `dialogueParDessus`).
 */
// eslint-disable-next-line react-refresh/only-export-components -- hook co-localisé, pas un composant
export function useFocusedRecordShortcuts(screenId, handlers, enabled = true, { scopeRef } = {}) {
  const { setActiveScreen } = useActiveScreen()

  useEffect(() => {
    if (!enabled || !FOCUSED_RECORD_SHORTCUTS[screenId]) return undefined
    setActiveScreen(screenId)
    return () => setActiveScreen((current) => (current === screenId ? null : current))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screenId, enabled])

  useEffect(() => {
    const entry = FOCUSED_RECORD_SHORTCUTS[screenId]
    if (!enabled || !entry) return undefined
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return
      if (dialogueParDessus(scopeRef?.current)) return
      // Menu/liste déroulante ouverts : la frappe est une recherche par
      // première lettre (type-ahead Radix — « a » choisit « Aucune »), jamais
      // un raccourci de la fiche (incident 02/10/2026).
      if (e.target?.closest?.('[role="listbox"], [role="menu"]')) return
      const def = entry.items.find((it) => it.key === e.key)
      if (!def) return
      const handler = handlers[def.key]
      if (!handler) return
      e.preventDefault()
      handler(def)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // `handlers` : le réabonnement ne doit se refaire QUE quand le registre
    // ou l'objet handlers change réellement — fini le re-bind à chaque rendu
    // (l'appelant doit fournir un `handlers` mémoïsé, cf. LeadWorkspace.jsx).
  }, [screenId, enabled, handlers, scopeRef])
}

/* INCIDENT 02/10/2026 — le panneau devis (une Sheet Radix en portail) s'ouvre
   PAR-DESSUS la fiche lead, qui reste montée avec son écouteur `window`. Une
   frappe hors champ texte dans ce panneau (après un clic sur un bouton, une
   case, un sélecteur) atteignait les raccourcis de la fiche : « a » archivait
   le lead, « 1 »-« 4 » changeaient son étape. Règle sûre par défaut : si une
   boîte de dialogue ouverte ne contient PAS l'écran, c'est qu'un autre écran
   est posé par-dessus — les touches de la fiche se taisent. (Une fiche
   elle-même ouverte au-dessus d'une autre boîte perd aussi ses raccourcis :
   c'est le sens sûr, jamais une action de trop.) Seules comptent les boîtes
   OUVERTES au sens Radix (`data-state="open"` — Dialog, Sheet, AlertDialog,
   Popover) : une bannière permanente non modale (`role="dialog"` de
   l'invite PWA) ne doit pas faire taire la fiche. Exporté pour J/K
   (LeadWorkspace) — même garde, même règle. */
// eslint-disable-next-line react-refresh/only-export-components -- garde co-localisée, pas un composant
export function dialogueParDessus(scopeEl) {
  if (!scopeEl || typeof document === 'undefined') return false
  const ouvertes = document.querySelectorAll(
    '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]',
  )
  for (const d of ouvertes) {
    if (!d.contains(scopeEl)) return true
  }
  return false
}

// VX248 — écran de détail ACTUELLEMENT monté (au plus un à la fois dans cet
// ERP — un seul formulaire/panneau de détail occupe l'écran) : la cheatsheet
// « ? » (ShortcutsProvider.jsx) l'utilise pour n'afficher QUE le groupe de
// raccourcis pertinent, jamais les 3 écrans mélangés.
const ActiveScreenContext = createContext({
  activeScreen: null,
  setActiveScreen: () => {},
})

export function ActiveScreenProvider({ children }) {
  const [activeScreen, setActiveScreen] = useState(null)
  return (
    <ActiveScreenContext.Provider value={{ activeScreen, setActiveScreen }}>
      {children}
    </ActiveScreenContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- hook co-localisé, pas un composant
export function useActiveScreen() {
  return useContext(ActiveScreenContext)
}
