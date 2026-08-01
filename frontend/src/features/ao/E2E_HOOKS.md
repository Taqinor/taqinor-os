# Contrat de hooks DOM `data-ao-*` (AOF8)

> **FIGÉ AVANT le premier écran.** Le dépôt a déjà payé la dérive de ses hooks
> e2e ailleurs (`ap-*`/`att-*`/`pp-*`) : un hook renommé casse des specs
> écrites des semaines plus tôt. Cette liste est normative et publiée AVANT
> qu'aucun écran AO n'existe — chaque écran ultérieur du Groupe AOF **consomme
> ces noms tels quels**, il n'en invente aucun nouveau. Ce fichier a **un seul
> propriétaire** dans tout le Groupe AOF (AOF8) : aucune autre tâche ne le
> déclare dans ses `Files:` — le modifier ailleurs unirait deux lanes par
> erreur (`plan_lanes.py` unionne les lanes qui partagent un `Files:`).
>
> Gardé vert par `e2eHooks.test.mjs` (même dossier) : la liste ci-dessous ne
> perd jamais un hook sans que le test le remarque, et aucun écran AO ne peut
> introduire un `data-ao-*` hors de cette liste sans que le test le remarque
> aussi.

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-canvas` | Le canvas géométrique partagé (toiture from-scratch AOF84, atelier de calepinage AOF92/`StudioShell` AOF73) | La surface de dessin/rendu SVG ou canvas elle-même — un seul repère par écran, jamais un par outil. |
| `data-ao-outil` | Barre d'outils de tracé/dessin (tracé toiture AOF84, outils obstacles AOF88) | Un bouton d'outil de dessin actif/inactif (tracé, rectangle, polygone, muret…). |
| `data-ao-verdict` | Barre de verdict permanente (AOF93) | Le bandeau TOUJOURS visible (compte de modules, kWc, marge signée, statut CONFIRMÉ/TENDU). |
| `data-ao-compte` | Compteur de provenance (AOF90 — « 28 obstacles — 26 mesurés… »), compte de modules (AOF93) | Un chiffre agrégé affiché en continu, jamais un chiffre recalculé côté front (AOF94). |
| `data-ao-tiroir` | Tiroirs de paramètres de l'atelier (Kits AOF95, Allées AOF96, Rives & dégagements AOF97, Orientation & segments AOF98, Contraintes électriques AOF99) | Un panneau de réglage ouvrable/fermable avec impact chiffré. |
| `data-ao-variante` | Sélecteur/carte de variante (atelier variantes — retenue/alternative/sensibilité) | Une variante d'étude individuelle (brouillon/calculé/publiable/périmé — voir `statusAo.js`, AOF10). |
| `data-ao-piece` | Écran « Dossier de soumission » (AOF174), prévisualisation de pièce (AOF175) | Une pièce produite du dossier (à produire/généré/à jour/PÉRIMÉ/fourni/signé/hors contrôle). |
| `data-ao-controle` | Panneau « Contrôles avant dépôt » (AOF176) | Un contrôle individuel de la porte de cohérence croisée (OK/avertissement/bloquant). |
| `data-ao-repere` | Inspecteur d'obstacles (AOF88 — repères lettrés A, B, C…) | Le repère lettré d'un obstacle/muret sur le canvas ET dans la liste latérale synchronisée. |
| `data-ao-provenance` | `ProvenanceBadge` (AOF9) | Le badge de provenance d'une valeur (mesuré / à confirmer / déduit / deviné). |
| `data-ao-etat` | Pastilles d'état (`statusAo.js`, AOF10) | La pastille d'état d'une affaire / pièce / variante / contrôle. |

## Règle de non-invention

Un écran AO qui a besoin d'un hook e2e stable choisit **un des 11 noms
ci-dessus** — jamais un nouveau `data-ao-*` ad hoc. Si un besoin réel ne
correspond à AUCUN des 11, la liste ci-dessus s'étend **ici d'abord**
(nouvelle ligne + mise à jour d'`ALL_HOOKS` dans `e2eHooks.test.mjs`), jamais
en douce dans un composant d'écran.
