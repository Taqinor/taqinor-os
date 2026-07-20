# Blueprint — Cockpit de la page Leads (LB50-LB56)

Synthèse Fable (2026-07-20) d'après 5 études parallèles : Attio/Folk/Twenty
(source de Twenty lue sur GitHub), Linear/Notion/Airtable, HubSpot/Pipedrive/
Salesforce. Brief fondateur : « regarde ce que font les meilleurs du monde et
copie — je suis sûr qu'ils donnent une grande place à la table des leads. »

## Les invariants du marché (mesurés)

- **Twenty** (vérifié dans son source React) : 48px d'en-tête + 39px de ViewBar
  = **87px de chrome au repos** ; la rangée des chips filtres/tri (32px) rend
  `null` quand rien n'est actif ; lignes de table 32px ; agrégat par colonne
  kanban (40px d'en-tête) ; AUCUNE rangée KPI.
- **Attio/Folk** : vue = un DROPDOWN nom+compteur (jamais des onglets) ; le
  TYPE (table/kanban) est une propriété de la vue ; pas de recherche inline ;
  métriques sur des dashboards séparés.
- **Linear** : titre au poids d'un breadcrumb, jamais un H1 ; rangée de pills
  de filtres SEULEMENT quand des filtres sont actifs ; Filter et Display = deux
  popovers ; ~90px de chrome au repos.
- **Notion/Airtable** : onglets de vues (Notion) / sidebar de vues (Airtable) ;
  recherche = icône qui se déplie ; agrégats en pied de grille (Airtable) ;
  le grand titre Notion = l'anti-modèle.
- **HubSpot** : vues en onglets-pills (glisser en 1re position = défaut
  personnel) ; carte de métriques REPLIABLE ; Total+Weighted dans les en-têtes
  de colonnes ; ~300px de chrome = l'extrémité grasse du marché.
- **Pipedrive** : totaux d'étape au SURVOL seulement ; résumé derrière une
  icône info ; recherche = palette `/` ; quick-filters en pills repliables.
- **Salesforce** : UNE barre de contrôle (picker de vue + pin-défaut +
  recherche de liste + filtre + New + toggle de vue tout à droite) ; somme
  par colonne via Summarize By ; le kanban mobile n'existe pas.

## LA DÉCISION : PICKER, pas onglets

`[Pipeline · 143 ▾]` — le titre EST le sélecteur de vues (patron
Twenty/Attio/Folk). Nos `crm.SavedView` (name+rank+payload{filters,view},
rang 1 = défaut de connexion) sont déjà exactement le modèle Twenty. Le menu
du picker : vues du compte (★ rang 1, ▲▼, 🔗 copier le lien, ✕) +
« ⭐ Enregistrer la vue actuelle… ». Le ViewSwitcher 6 icônes RESTE un contrôle
séparé à droite (nos 6 types = des projections rapides du même jeu de
filtres ; le picker = des vues nommées).

## Anatomie desktop

**RANGÉE 1 (44px, l'unique au repos)** :
`[Picker] [🔍 200px] [Filtres ▾ ³] [Mes leads][☎ Rappels][Dû auj. 4][Retard 2][Chauds 6] — [1,2 M MAD] [⋯][+ Nouveau lead][|][switcher]`
- Chips rapides = fusion des tuiles KPI-toggles et des chips fréquentes : UN
  jeu homogène de chips comptées (badge seulement si > 0), facettes sur kpiPool.
- Pipeline MAD : texte discret, prévisionnel pondéré en infobulle, masqué
  < 1600px (reste dans le panneau Filtres + en-têtes kanban).
- ⋯ : Express/Doublons/Importer/Exporter (« Enregistrer la vue » → picker).

**RANGÉE 2 (32px, CONDITIONNELLE)** : facettes actives (chips ✕) + « Effacer
les filtres » — rend `null` à 0 facette (hors DOM, patron Twenty/Linear).

**Chrome total : ~52px au repos, ~88px filtré** (Twenty : 87/119 ; HubSpot :
~300). Repli en 2 lignes minces < 1450px.

## En-têtes kanban : ZÉRO churn
Compte + total MAD · Prév. + chevron restent (consensus Twenty/Folk/HubSpot ;
seul Pipedrive cache au survol — sa faiblesse).

## Mobile — UNE ligne 44px
`[Pipeline · 143 ▾] [🔍] [Filtres ³] [⋯]` + FAB. Le picker met les vues du
compte au pouce ; ⋯ garde Express/Doublons/Import/Export + les 6 types de
vue ; panneau Filtres : chips rapides + Pipeline MAD + facettes + selects.
Les 6 types restent au téléphone (kanban Odoo conservé) ; défaut = kanban ;
priorité URL > session > rang 1 > kanban inchangée.

## Patterns e2e changés (déclarés)
« Pipeline » : heading → `getByRole('button', {name: /Pipeline/})` (trigger du
picker). Tuiles KPI → chips `aria-pressed` (plus de `.lp-kpi-tile`). Radios
« Vue kanban »…, '+ Nouveau lead', bulk : inchangés.
