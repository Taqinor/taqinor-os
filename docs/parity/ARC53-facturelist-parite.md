# ARC53 — Parité fonctionnelle : `FactureList.jsx` (chemin de l'argent 2/2)

But : migration prudente de `frontend/src/pages/ventes/FactureList.jsx` vers le
moteur `ui/datatable`, avec **parité fonctionnelle exhaustive prouvée**, **zéro
changement des flux PDF / statuts** (le **PDF facture legacy reste INTOUCHÉ** —
les factures gardent leur PDF séparé, règle #4), `prix_achat`/marge jamais exposés,
checklist committée AVANT, e2e verts avant fold. Isolé d'ARC49.

Écrit AVANT toute modification (méthode ARC53).

---

## 1. Appels API / réseau (doivent rester BYTE-IDENTIQUES)

| Déclencheur | Appel | Note |
|---|---|---|
| Montage | `dispatch(fetchFactures())` + `parametresApi.getProfile()` (flag `dgi_export_actif`) | Redux inchangé |
| Émettre | `dispatch(emettreFacture(id))` (via `doAction`) | statut serveur |
| Marquer payée | `dispatch(marquerPayeeFacture(id))` (confirm) | |
| Annuler | `dispatch(annulerFacture(id))` (confirm) | |
| Générer PDF | `dispatch(genererPdfFacture(id))` + polling `ventesApi.getFacture(id)` | **PDF facture LEGACY — inchangé** |
| Télécharger PDF | `ventesApi.telechargerPdfFacture(id)` | |
| Enregistrer paiement | `ventesApi.enregistrerPaiement(id, {montant,date_paiement,mode,reference?})` | |
| Arrondi caisse (espèces) | `ventesApi.arrondiCaisseFacture(id, 'especes')` | ZFAC11 |
| Historique (chatter) | `GET /ventes/factures/<id>/historique/` | |
| Créer avoir | `ventesApi.creerAvoir(id, {motif, lignes?})` + `ventesApi.getFacture(id)` (détail lignes) | total OU partiel |
| Éditer échéance inline | `ventesApi.patchFacture(id, {date_echeance})` | |
| WhatsApp | `ventesApi.whatsappFacture(id, {modele, langue})` → aperçu wa.me | L851/L852 |
| Aperçu UBL | `ventesApi.telechargerUbl(id)` | N38 |
| Payer en ligne | `ventesApi.lienPaiementFacture(id)` → clipboard | FG53/WR2b |
| Export DGI | `ventesApi.dgiExportFacture(id)` | gated `dgi_export_actif` |
| Conformité DGI | `ventesApi.dgiConformiteFacture(id)` | badge cliquable, aucun statut modifié |
| Audit numérotation | `ventesApi.auditNumerotation()` (admin) | N31 |
| Actions en masse | `ventesApi.bulkFactures(action, ids)` | FG43/WR2b — emettre/relancer/envoyer-email/generer-pdf |
| Export Excel liste | `importApi.exportList('factures', ids)` → `downloadXlsx` | |
| Journal comptable | `ventesApi.journalVentes({month|quarter})` | |
| Export comptable | `GET /ventes/export-comptable/` (xlsx + csv) | |

## 2. Filtres, recherche, tabs, vues, bascule Liste/Kanban

- **Tabs** (`TABS`) : Toutes / Brouillon / Émises / En retard / Partiellement payées /
  Payées / Annulées — avec compteurs `counts`. « En retard » (`overdue`) et
  « Partiellement payées » (`isPartiallyPaid`) sont des filtres DÉRIVÉS, pas des statuts.
- **Recherche** : `reference` OU `client_nom`.
- **Filtre type** (`TYPES_FACTURE`) : complète/acompte/intermédiaire/solde.
- **Vues enregistrées** (FG11) : `{activeTab, typeFilter}` (chips `.lp-saved-view-*`).
- **Bascule Liste/Kanban** (ZFAC9) : `role="group"` « Mode d'affichage », réutilise
  `filtered` (aucune donnée nouvelle). Kanban → `<FactureKanbanBoard>`.
- **Tri** : pas de tri de colonne (ordre serveur) — à préserver.

## 3. Colonnes (8) + statuts

Case sélection (`w-10`) · Référence · Client · Émission · Échéance (édit inline) ·
Total TTC (`ta-right`) · Statut · Actions. Table = classe **`data-table`**.
- `STATUT_DISPLAY` : brouillon/emise/payee/en_retard/annulee. `statutKey` bascule
  `emise`→`en_retard` si `isOverdue`. Ligne échue : `bg-destructive/5`.
- Badges : type_facture + %, lien Devis, mentions manquantes (Art.145),
  télédéclaration DGI (`TELEDECLARATION_DISPLAY/TONE`), conformité DGI (gated,
  cliquable), « À relancer » (next-best-action).

## 4. Actions par ligne (conditionnelles) — **visibles** + menu « Actions »

Boutons visibles à `loading` individuel : Éditer (brouillon), Émettre (brouillon,
variante `default` si NBA), Payée (emise/en_retard/overdue, success+confirm),
Enregistrer paiement (`montant_du>0 && !annulee`), Payer en ligne (idem), PDF
(télécharger si `fichier_pdf` sinon générer), Avoir (admin, emise/payee/en_retard).
Menu **`DropdownMenu` « Actions »** (queryable `getByRole('button',{name:'Actions'})`) :
WhatsApp (désactivé si numéro invalide), Aperçu UBL, Export DGI (gated), Annuler la
facture. Édition inline de l'échéance (Input date + OK/×).

## 5. PDF facture — LEGACY INTOUCHÉ (règle #4)

Contrairement au devis, la facture garde son **PDF legacy séparé** : `genererPdfFacture`
(thunk) + `telechargerPdfFacture`. **Aucune** option de format, **aucun** passage par le
moteur premium `/proposal`. La migration ne touche RIEN de ce flux — pas de dialog PDF
à porter, juste les deux boutons Générer/Télécharger conservés à l'identique.

## 6. Avoirs (note de crédit) — total ou partiel

Modale `avoirTarget` : motif + tableau des lignes (`data-table`) pour un avoir
**partiel** (quantités par ligne) ; boutons « Avoir partiel » / « Avoir total ».
Charge le détail via `getFacture`. Statuts/flux inchangés.

## 7. Paiement + chatter

Modale `payTarget` : montant/date/mode/référence, proposition d'arrondi caisse
(espèces, ZFAC11), historique des paiements encaissés + chatter (avoirs & paiements).

## 8. `prix_achat` / marge — vérification

`grep prix_achat|marge` dans `FactureList.jsx` = **AUCUNE occurrence**. Conservé.

## 9. Hors-scope (noté pour l'orchestrateur)

- Troncature 100 lignes (`fetchFactures`) : VX54/VX60, PAS ARC53. `ventesSlice` inchangé.

## 10. Contrat de test / DOM verrouillé (à PRÉSERVER)

Aucun spec e2e ne cible directement FactureList. Le contrat dur vient de
`src/pages/ventes/FactureList.test.jsx` (11 tests) + `FactureKanbanBoard.test.jsx` /
`factureKanban.test.mjs` :
- `screen.getByRole('table')` (Liste) ; `queryByRole('table')` null en Kanban
- `getByTestId('facture-kanban-board')`, `fkb-count-*`
- `cell.closest('tr')` + `within(row).…` sur chaque ligne
- Boutons ligne queryables : `/Payer en ligne/`, `getByRole('button',{name:'Actions'})`,
  `getByRole('menuitem',{name:/Export DGI/})`, badge `/Conformité DGI/`
- `getByRole('region',{name:'Actions factures en masse'})` + `getByRole('button',{name:'Émettre'})`
- `getByRole('checkbox',{name:/Sélectionner la facture …/})`, `{name:'Tout sélectionner'}`
- Bascule `getByRole('button',{name:/Kanban/})` / `{name:/^Liste/}`

## 11. Conclusion sur la forme de migration (décision d'ingénierie)

Même incompatibilité qu'ARC49 (§12 de ARC49-devislist-parite.md) : le moteur
`ui/datatable` rend `rowActions` en 2 icônes + kebab figé (`DropdownMenu` interne),
sans état `loading` par bouton, sans enfant JSX riche (édition inline d'échéance,
badges cliquables, la propre `DropdownMenu` « Actions » testée par rôle, la barre
de masse `role=region`), et émet `role="grid"` — pas `getByRole('table')` +
`table.data-table` attendus par les tests. Forcer FactureList dans ce modèle
casserait la parité (les 11 tests de page + les tests Kanban) — l'inverse de
« migration prudente / zéro changement ».

**Décision (phase 1) :** on a d'abord livré **« lignes divisées » avec parité
prouvée** en extrayant la ligne (`FactureRow`) et les deux modales lourdes en
composants internes, en gardant `getByRole('table')` + `table.data-table`, tous
les appels API, le PDF facture legacy, les statuts, les avoirs, la barre de masse,
la bascule Kanban et les hooks DOM **strictement identiques**. La bascule du CADRE
vers `DataTable` était alors marquée BLOCKED (incompatibilité prouvée).

## 12. RÉSOLU (ARC53 3/3) — extension du moteur + bascule sur le frame

Le blocage du §11 est LEVÉ (mêmes échappatoires additives du moteur qu'ARC49 §13 —
`renderRow`/`renderHeaderRow`/`tableClassName`/`tableRole`/`hideToolbar`/
`hidePagination`, 100 % opt-in, ~79 consommateurs intacts et prouvés).

**Bascule FactureList (ARC53 3/3).** Seul le bloc `<table className="data-table">`
a été remplacé par `<DataTable … renderRow={f => <FactureRow f={f} ctx={rowCtx} />}
renderHeaderRow={…} tableClassName="data-table" tableRole="table" hideToolbar
hidePagination manualSorting manualFiltering manualPagination>`. Points clés de
parité :

- **`tableRole="table"`** : le moteur rend par défaut `role="grid"` ; FactureList
  exige `getByRole('table')` → on force `role="table"`. En Kanban, aucune table
  n'est rendue → `queryByRole('table')` reste `null` (inchangé).
- `<FactureRow>` reste **verbatim** (boutons à état, menu « Actions » queryable
  par rôle, édition inline d'échéance, badges DGI/conformité, next-best-action).
- La **barre de masse** `role="region"` « Actions factures en masse » reste rendue
  PAR LA PAGE, hors de la table (le moteur n'héberge PAS cette barre — sa propre
  `BulkActionBar` porte un autre nom accessible ; on ne l'utilise donc pas ici).
  Sélection pilotée par l'état de page (`selectedIds`).
- La **bascule Liste/Kanban** et le **PDF facture legacy** sont **inchangés**
  (règle #4 — aucune option de format, aucun passage par `/proposal`).

Les **11 tests page + 4 tests Kanban passent inchangés** ; seule modification de
test : ajout du wrapper `<ThemeProvider>` au harnais (le moteur lit `useDensity()`,
présent en prod via `<Layout>`) — **aucune assertion modifiée**.
