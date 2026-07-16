# ARC49 — Parité fonctionnelle : `DevisList.jsx` (chemin de l'argent 1/2)

But de la tâche : migration prudente de `frontend/src/pages/ventes/DevisList.jsx`
vers le moteur `ui/datatable`, avec **parité fonctionnelle exhaustive prouvée**,
**zéro changement des flux PDF / statuts** (règle #4), `prix_achat`/marge jamais
exposés, checklist committée AVANT la migration, e2e verts avant fold.

Ce document est écrit AVANT toute modification (méthode ARC49) : il inventorie
100 % du comportement observable de l'écran, la surface de test qui le verrouille,
puis conclut sur la forme de migration réellement compatible avec les critères
d'acceptation.

---

## 1. Appels API / réseau (doivent rester BYTE-IDENTIQUES)

| Déclencheur | Appel | Payload / params | Note règle |
|---|---|---|---|
| Montage | `dispatch(fetchDevis())` | — | Redux `ventesSlice` — comportement inchangé (voir §9 hors-scope) |
| Générer PDF (une pièce) | `dispatch(genererPdfDevis({ id, options }))` puis polling `ventesApi.getDevisById(id)` + `ventesApi.telechargerPdfDevis(id)` | `options = buildPdfOptions(d)` (voir §5) | **Règle #4** — corps `generer-pdf` inchangé |
| Générer PDF (lot) | idem, boucle sur `selectedIds`, `autoOpen:false` | même `buildPdfOptions` partagé | **Règle #4** |
| Aperçu PDF | `ventesApi.getProposalPdf(id, params)` | `params = proposalParams('full', industriel&&hasEtude)` | **Règle #4** — `/proposal` inchangé |
| Télécharger dernier PDF | `ventesApi.telechargerPdfDevis(id)` | — | |
| Envoyer (WhatsApp) | `ventesApi.whatsappDevis(id)` → modale wa.me | — | statut → « envoyé » côté serveur (idempotent) |
| Refuser | `ventesApi.refuserDevis(id, {motif?})` | `{motif}` si saisi | **WR1** — action dédiée, JAMAIS un PATCH statut direct |
| Accepter | `ventesApi.accepterDevis(id, {nom,date,option})` | `option` seulement si `nb_options===2` | |
| Convertir en BC | `dispatch(convertirDevisEnBC(id))` | — | |
| Générer facture | `ventesApi.genererFacture(id)` | — | |
| Réviser | `ventesApi.reviserDevis(id)` | — | |
| Approuver remise | `ventesApi.approuverRemise(id)` | — | admin + brouillon + remise>0 + !approuvée |
| Variante (modale) | `ventesApi.getVarianteConfig()` puis `ventesApi.dupliquerVariante(id, {variante_pct?})` | `{variante_pct: pct}` si 0<pct<100 | **QG10** |
| Copier lien proposition | `ventesApi.shareLinkDevis(id)` | — | **WR2** — reconstruit URL publique, clipboard |
| Envoyer par email | `ventesApi.envoyerEmailDevis(id, {to_email?})` | `{to_email}` si saisi | **QJ14** |
| Contacter supérieur | `ventesApi.contacterSuperieur(id)` | — | **QJ28** — notification, jamais auto |
| Créer chantier | `installationsApi.createFromDevis(id)` (ou navigate si existe) | — | |
| Créer projet | `gestionProjetApi.creerProjetDepuisDevis(id)` | — | **XPRJ21** |
| Export Excel liste | `importApi.exportList('devis', ids)` → `downloadXlsx` | ids de tous les devis chargés | |

Toutes ces signatures + corps sont **conservés à l'identique** ; aucune n'est
reroutée par la migration.

## 2. Filtres, recherche, tris, vues

- **Filtre statut** (`Segmented`) : `tous` + 5 statuts (`brouillon/envoye/accepte/refuse/expire`),
  libellés depuis `STATUT_FILTERS`. Applique `effStatutOf` (un devis dont la
  validité est dépassée s'affiche « Expiré » via `is_expired` — statut stocké
  inchangé).
- **Recherche** : `Input type=search` sur `reference` OU `client_nom` (insensible casse).
- **Bascule « versions remplacées »** (U7) : `is_active===false` masquées par défaut ;
  bouton `Voir les versions remplacées (N)` / `Masquer…` avec compteur `supersededCount`.
- **Vues enregistrées** (FG11) : `useSavedViews(DL_SAVED_VIEWS_KEY)` — enregistrer
  `{statutFilter, query}`, appliquer, supprimer (chips `.lp-saved-view-*`).
- **Tri** : l'écran actuel N'A PAS de tri de colonne (ordre = ordre serveur). À
  préserver : ne PAS introduire de tri qui réordonnerait (changerait le contrat).

## 3. Colonnes du tableau (8) + `data-label` mobiles

`w-8` (case sélection) · Référence · Client · Créé le · Validité (`m-hide`) ·
Total TTC (`ta-right`) · Statut · Actions.
- La table porte la classe CSS **`data-table`** (verrouillée par le test squelette).
- Cellules avec `data-label` pour le rendu carte mobile CSS.

### Contenu riche par cellule (tout préservé)
- **Référence** : `<strong>`, badge `v{version}`, badge « Remplacé » (is_active=false),
  lien « remplacé par <ref> », bouton « Voir/Masquer les versions », badge
  « Consulté ×N » (QJ1), résumé d'engagement par section (XSAL16), chips
  factures liées + BC (U5, cliquables → listes).
- **Client** : `client_nom`, chip lead lié (↗) → `/crm/leads?lead=<id>`.
- **Total TTC** : `total_affiche ?? total_ttc` via `formatMAD`, badge « 2 options »,
  ligne solde (Facturé/Payé/Restant).
- **Statut** : `StatusPill`, option acceptée, badge « Proposition signée » (QJ22),
  état BC + avertissement d'incohérence (U8).

## 4. Actions par ligne (conditionnelles au statut) — **directement visibles**

Ordre et conditions exacts (toutes en boutons VISIBLES dans la cellule Actions,
avec `loading` individuel, `title`, variantes success/destructive/outline) :

1. **Éditer** (toujours, désactivé si `statut!=='brouillon'`)
2. **Réviser** (`is_active && statut!=='brouillon'`)
3. **Variante** (`statut==='brouillon'`) → modale % (QG10)
4. **Approuver remise** (`admin && brouillon && remise_globale>0 && !remise_approuvee`)
5. **Supprimer** (`canDelete = role==='admin'`) — enveloppé dans un **`AlertDialog`** de confirmation
6. **Envoyer** (`brouillon`) → WhatsApp
7. **Contacter supérieur** (`brouillon||envoye`) — icône `UserCog`
8. **Email** (`brouillon||envoye`)
9. **Copier le lien** (`brouillon||envoye`) — WR2
10. **Design 3D** (`roof_layout`) + **Ouvrir fenêtre** (icône `ExternalLink`)
11. **Aperçu** (icône `Eye`, `loading`)
12. **PDF** (`title="Générer le PDF (choix du format)"`, `loading=isGenerating`)
13. **Télécharger** (`fichier_pdf`, variant success, icône `FileDown`)
14. **Accepter** (`envoye`) → modale
15. **Refuser** (`envoye`, destructive) — WR1
16. **BC** (`accepte`, success)
17. **Créer/Voir le chantier** (`accepte`)
18. **Créer projet** (`accepte`) — XPRJ21
19. **Générer facture** : TOUJOURS présent — désactivé + note d'aide VISIBLE si
    `!accepte` ; « Échéancier complet » désactivé si toutes tranches facturées ;
    sinon actif.

## 5. Dialog PDF de la LISTE — options → `clean_pdf_options` (RÈGLE #4, inchangé)

`buildPdfOptions(d)` construit EXACTEMENT :
```
{
  pdf_mode:       'full' | 'onepage',
  show_monthly:   bool,
  devis_final:    bool,
  payment_mode:   'standard' | 'custom',
  custom_acompte: (devisFinal && payment_mode==='custom' && customAcompte!=='')
                    ? parseFloat(customAcompte) : null,
  include_etude:  pdf_mode==='full' && includeEtude && hasEtudeParams(d),
}
```
Contrôles de la modale (partagée pièce/lot via `ResponsiveDialog`) :
- Format (RadioGroup `full`/`onepage`) — libellé « 4 pages » si agricole, « 3 pages » sinon.
- « Économies mensuelles » (`show_monthly`) — masqué si agricole.
- « Inclure l'étude » (`include_etude`) — désactivé sans `etude_params`, masqué en lot/agricole (T13/T14).
- « Devis Final » (`devis_final`) → sous-bloc paiement standard/custom + acompte.

Ces valeurs et ce mapping **ne changent pas d'un octet** — ce sont les mêmes clés
whitelistées par `clean_pdf_options` côté serveur. `proposalParams`/`pdfBlob`
pour l'aperçu `/proposal` : inchangés.

## 6. Statuts — libellés & couleurs

`STATUT_DISPLAY` : brouillon=Brouillon, envoye=Envoyé, accepte=Accepté,
refuse=Refusé, expire=Expiré. Rendus via `StatusPill status={effStatut}`.
Aucune valeur/label/couleur modifiée.

## 7. Panneaux dépliables (2 types indépendants, dans la table)

- **Historique des versions** (`versionsOpenId`) : ligne `colSpan=8`, `versionChain`
  triée par version. Deep-link `?variantes=<id>` l'ouvre au montage.
- **Design 3D** (`roofOpenId`) : ligne `colSpan=8`, `<RoofViewer layout=…>` en
  lecture seule + « Ouvrir dans une fenêtre ». Deep-link `?design3d=<id>`.

## 8. États chargement / erreur / vide + modales

- **Chargement** : `useDelayedLoading` → spinner discret puis **squelette**
  (`DevisTableSkeleton`, classe **`data-table`**, 8 colonnes, `.animate-pulse`) +
  bandeau résumé squelette. En-tête « Devis » TOUJOURS visible (pas de saut de layout).
- **Erreur** : `EmptyState` « Erreur de chargement ».
- **Vide** : `EmptyState` « Aucun devis » (action Nouveau devis).
- **Filtre sans résultat** : ligne « Aucun devis ne correspond à ces filtres. »
- Bandeaux résumé par statut (T6), répartition batterie (T16), rappel expirations ≤7j (T15).
- Modales : PDF, Acceptation, Email (QJ14), WhatsApp (QG8), Variante (QG10).

## 9. `prix_achat` / marge — vérification (§ acceptance)

`grep` de `prix_achat|marge|prix_revient` dans `DevisList.jsx` = **AUCUNE
occurrence**. L'écran n'affiche AUCUN coût d'achat ni marge. Conservé tel quel.

## 10. Hors-scope (à NE PAS corriger — noté pour l'orchestrateur)

- **Troncature 100 lignes** (`fetchDevis` charge une page serveur non paginée
  côté client) : responsabilité de **VX54/VX60**, PAS d'ARC49. Le comportement
  `ventesSlice` reste inchangé.

## 11. Contrat de test / DOM verrouillé (à PRÉSERVER)

Aucun hook e2e `ap-/att-/pp-*` sur cet écran ; `e2e/devis.spec.js` (E4) travaille
depuis le panneau lead, **ne touche pas DevisList.jsx**. Le contrat dur vient des
**tests page-level vitest** :
- `src/pages/ventes/DevisList.test.jsx` (20 tests)
- `src/pages/ventes/DevisListCreerProjet.test.jsx` (3 tests)

Sélecteurs qu'ils exigent (donc figés) :
- `screen.getByRole('heading', { name: 'Devis' })`
- `document.querySelector('table.data-table')` + `.animate-pulse` pour le squelette
- `cell.closest('tr')` + `within(row).…` sur CHAQUE ligne (structure `<tr>` par devis)
- Boutons **directement queryables par rôle** dans la ligne :
  `/Refuser/`, `/Variante/`, `/Copier le lien/`, `/Design 3D/`, `/Créer projet/`,
  `getByTitle('Générer le PDF (choix du format)')`, `/Ouvrir le design 3D … dans une fenêtre/`
- Panneau « Historique des versions » et `getByTestId('roofviewer-svg')` dépliés inline
- Champ modale `getByLabelText(/Pourcentage de variation/)` (readOnly selon rôle)

## 12. Conclusion sur la forme de migration (décision d'ingénierie)

Le moteur `ui/datatable` (`DataTable.jsx`) impose, pour les actions de ligne, le
modèle `rowActions = (row) => [{id,label,icon,onClick,destructive}]` **rendu en 2
icônes au survol + un menu kebab** (`RowActions`, DataTable.jsx L916). Il :
- ne supporte PAS d'état `loading` par action, ni des variantes visuelles
  success/destructive/outline par bouton ;
- ne supporte PAS un enfant JSX riche (delete enveloppé d'`AlertDialog`, bouton
  « Générer facture » désactivé avec note d'aide visible, branche « Échéancier
  complet ») ;
- expose un unique `renderExpanded` (chevron possédé par le moteur), incompatible
  avec les **deux** panneaux dépliables indépendants (versions + 3D) ;
- émet `<table role="grid" class="w-full border-collapse …">` et possède son
  propre état de chargement — **PAS** `table.data-table` + `useDelayedLoading`
  attendus par le test squelette.

Forcer DevisList dans ce modèle **casserait la parité** (chaque bouton de ligne
n'est plus queryable, le flux PDF change de surface, les 23 tests page tombent) —
soit exactement l'inverse de « migration prudente / zéro changement / parité
prouvée » exigé par ARC49. `renderExpanded` n'est utilisé par AUCUNE migration du
Groupe J en production (seulement la démo `/ui`), confirmant que les écrans à
actions riches n'ont pas été portés sur ce modèle.

**Décision (phase 1) :** on a d'abord livré **« lignes divisées » avec parité
prouvée** en extrayant la ligne (`DevisRow`) et la modale PDF (`DevisPdfDialog`)
en composants internes au fichier nommé, en gardant le tableau `data-table`, tous
les appels API, les options PDF, les statuts, les hooks DOM et les 23 tests
**strictement identiques**. La bascule du cadre vers `DataTable` était alors
marquée BLOCKED (incompatibilité de contrat prouvée ci-dessus).

## 13. RÉSOLU (ARC49 2/3) — extension du moteur + bascule sur le frame

Le blocage du §12 est LEVÉ. Le moteur `ui/datatable` a été **étendu de façon
strictement additive** (échappatoires opt-in, zéro changement des ~79 consommateurs
existants — prouvé : `DataTable.test.jsx` 29 tests d'origine intacts + 8 nouveaux,
et 3 suites de pages lourdes vertes) :

- **`renderRow(row, api)`** — rend une LIGNE ENTIÈRE personnalisée (remplace le
  pipeline de cellules + le `RowActions` kebab intégrés). Résout d'un coup les
  points a) actions riches (boutons à état `loading`, variantes, `AlertDialog`,
  « Générer facture » désactivé + note) et b) panneaux multiples : la ligne custom
  émet elle-même ses `<tr>` de panneaux. `api` expose sélection + panneaux nommés
  (`isPanelOpen`/`togglePanel`/`setPanel`) + `query`.
- **`renderHeaderRow(api)`** — en-tête `<th>` personnalisé (l'écran garde ses 8
  colonnes + la case « tout sélectionner »).
- **`tableClassName`** (→ `data-table`) et **`tableRole`** (défaut `grid` inchangé).
- **`hideToolbar` / `hideMobileCards` / `hidePagination`** — masquent les chromes
  intégrés quand l'écran fournit les siens.

**Bascule DevisList (ARC49 2/3).** Seul le bloc `<table className="data-table">` a
été remplacé par `<DataTable … renderRow={d => <DevisRow d={d} ctx={rowCtx} />}
renderHeaderRow={…} tableClassName="data-table" hideToolbar hidePagination
manualSorting manualFiltering manualPagination>` (seams manuels → ordre serveur
préservé, aucun tri/pagination client). `<DevisRow>` et `<DevisPdfDialog>` restent
**verbatim** ; la sélection reste pilotée par l'état de page (`selectedIds`), les
deux panneaux (versions / 3D) restent pilotés par l'état de page + deep-links
(`?variantes=`, `?design3d=`), le flux PDF est **inchangé** (règle #4). Le cas
« filtre sans résultat » garde sa ligne pleine largeur (le moteur ne déroule
`renderRow` que pour ≥ 1 ligne). Les **23 tests page passent inchangés** ; seule
modification de test : ajout du wrapper `<ThemeProvider>` au harnais (le moteur lit
`useDensity()`, présent en prod via `<Layout>`) — **aucune assertion modifiée**.
