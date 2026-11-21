## Réserve — cartes du backlog qui n'ont pas donné de tâche (vague 2)

### D1 — Site, toit, relevé
- CAP-D1-20 — Aide « hauteur d'un bâtiment voisin » (étages × hauteur d'étage) — preuve mince (1 fil, 2 lignes), effort S, score 3 (rang 20) ; la hauteur d'un voisin reste saisissable.
- CAP-D1-23 — Toit en sheds (dents de scie) — preuve mince (2 fils 2008-2009, inférence « halls marocains » non vérifiée), effort M, score 1,5 (rang 23).

### D2 — Pose, structure, plans
- CAP-D2-22 — Numéros de série posés rattachés au module et à la chaîne — une seule lane (avis d'applis), score 2 (rang 22) ; liste des modules posés et rattachement chantier non repris.

### D3 — Électrique
- CAP-D3-17 — Micro-onduleurs ≠ injection zéro, place et sens de la pince CT — aucune tâche finale ; raison non écrite dans les lots (score 6, rang 10) ; à confirmer.
- CAP-D3-23 — Réserver une entrée MPPT et des modules pour une extension — preuve mince (2 fils, 1 lane), score 2 (rang 27).

### D4 — Simulation, résultats, rapport
- CAP-D4-25 — Rapport éditable : variables de texte et export DOCX — jumelle de CAP-D6-18, écartée d'office pour D4 ; variables non reprises, DOCX = dépendance neuve (voir ligne fondateur Word).
- CAP-D4-29 — Ombre de cadre, de pinces ou de différence de hauteur de châssis — une seule lane (3 fils), score 2 (rang 29), avertissement sans chiffre ; écartée d'office pour D4.

### D5 — Consommation, stockage, pompage, réseau
- CAP-D5-19 — Énergie réactive (kVArh) et cos φ par mois — preuve de « notes de version » seule, aucun fil de forum ; attend la position écrite ONEE/SRM (CIQM4).
- CAP-D5-20 — Batterie hors de sa plage de température au site — preuve mince (1 fil), effort S, score 4,5 (rang 20).
- CAP-D5-21 — Gabarits de profils de consommation nommés, vides — score 4 (rang 21) ; aucune valeur livrée, profils société éditables existent déjà.
- CAP-D5-22 — Règles de batterie par saison (une stratégie par mois) — score 1 (rang 22), « à ne construire qu'à la demande » ; dépend de CAP-D5-01.

### D6 — Parcours, simplicité, explications
- CAP-D6-11 — Dossier par distributeur (pièces exigées, version du formulaire) — D-ACAL-42 : dossier générique d'abord ; seule la date « vérifié le » reprise (ACAL822, ACAL824) ; liste des distributeurs à fournir.
- CAP-D6-15 — File de demandes « calepinage à faire » commerciale → technicien — preuve d'éditeur seule, score 4 (rang 15) ; moitié bouton fiche lead (PLAN_AUDIT_LEAD) non reprise.
- CAP-D6-18 — Documents éditables (Word) et textes à variables du modèle société — variables non reprises ; DOCX gated fondateur (nouvelle dépendance), voir ligne fondateur Word ; jumelle de CAP-D4-25.
- CAP-D6-19 — Pouce haut / bas sur le remplissage automatique, avec un motif — un seul éditeur (OpenSolar), score 2 (rang 17).

### D7 — Constats du tour 1
- (aucune carte en réserve : CAP-D7-07 est portée par ACAL927, qui ne cite pas son id)

### D8 — Moteur partagé
- CAP-D8-01 t2 — Propriété `core/conception` dans `ownership.yml` — coupé : `core/conception` non créé, la lecture des pans posés va dans `core/calepinage` (critique d, B3).
- CAP-D8-01 t3 — Contrat import-linter `conception-est-un-noyau-pur` — coupé : même raison, pas de paquet `core/conception`.
- CAP-D8-01 t4 — Paquet `core/conception` et test de pureté — coupé : même raison, `pans_poses` vit dans `core/calepinage` (ACAL1002).
- CAP-D8-01 t5 — Section « Le moteur de conception » dans `docs/moteur-calepinage.md` — décrit adaptateur et interrupteurs non retenus ; aucune tâche finale ne la porte.
- CAP-D8-02 t3 — Garde économie année 1 : carte de l'atelier = économie du devis — ACAL982 ne garde que kWc, production et verdict ; aucune garde sur l'économie.
- CAP-D8-02 t5 — Garde du site public (`estimatorBrainV2`) bornée par le moteur — dépend de D8-07 t2 (coupé, B3) et de D8-12 (reporté, web stop-and-ask).
- CAP-D8-03 t2 — Règle de nuit `CAL_ECONOMIE_ATELIER_VS_DEVIS` — non reprise : seul `CAL_PRODUCTION_DEVIS_VS_CALEPINAGE` devient tâche (ACAL1011) ; pas de garde économie.
- CAP-D8-03 t3 — Règle de nuit `CAL_VERDICT_PUBLIABLE_SANS_MATERIEL` — non reprise ; « publiable à vide » partiellement voulu (D-ACAL-9), état « à compléter » servi par ACAL934.
- CAP-D8-04 t1 — Façade `concevoir()` / `chiffrer()` du calepinage — remplacée par la porte unique `chiffrer_conception` dans `ventes` (ACAL991, ACAL992) : l'argent ne sort pas de `ventes` (B3).
- CAP-D8-04 t3 — `design-context` du devis délègue à celui du calepinage lié — non reprise ; aucune tâche finale ne la porte.
- CAP-D8-04 t4 — `ecrire_etude_params` reçoit la `Conception` — non reprise ; la production de la pose réelle passe par le productible servi (ACAL996-ACAL999).
- CAP-D8-04 t5 — `contenance.py` (assistant) passe par la façade — sans objet : la façade n'est pas créée.
- CAP-D8-06 t1 — `kwc(pans, modules)` pur dans `core/conception` — coupé : paquet non créé ; la parité du kWc est tenue par ACAL982 et ACAL916.
- CAP-D8-07 t1 — Constat d'extraction de la production horaire — sans objet : la production reste dans `ventes` (B3).
- CAP-D8-07 t2 — Déplacement PUR de la production horaire vers `core` — coupé B3 : ≈ 10 000 lignes, I/O PVGIS, contrat import-linter, 8 `mock.patch` qui cesseraient d'agir.
- CAP-D8-07 (interrupteur) — `MOTEUR_CONCEPTION_PRODUCTION` — coupé B4 : un devis envoyé changerait de chiffre à la bascule ; un seul verrou, le niveau de règles.
- CAP-D8-08 t1 — Déplacement PUR de l'économie vers `core/conception/economie.py` — coupé B3 : l'argent reste dans `ventes`, propriétaire moteur.
- CAP-D8-08 (interrupteur) — `MOTEUR_CONCEPTION_ECONOMIE` — coupé B4 : aucun interrupteur d'environnement sur un chiffre client.
- CAP-D8-09 t2 — `electrical_service.py` délègue à la façade — non reprise ; B3/B6 : casserait les devis sans calepinage lié, façade non créée.
- CAP-D8-09 t3 — Remplacer `solar_design.string_design` par `core.electrique` — coupé B6 : peut changer onduleur, quantités et prix des nouveaux devis ; hors lot (goldens à nommer).
- CAP-D8-10 t1 — Remplisseur serveur unique `remplir` — GATED fondateur Q5 (étape 6) : lève l'interdit `USE_MOTEUR_CALEPINAGE`, décision après comparaison (B8).
- CAP-D8-10 t2 — Dry-run `comparer_compte_moteur_calepinage` étendu à tous les calepinages — étape 6 GATED Q5 ; non repris (ACAL1000 est un autre dry-run, niveaux de règles).
- CAP-D8-10 t3 — « Remplir le toit » de l'atelier appelle `remplir`, derrière `MOTEUR_CONCEPTION_POSE` — GATED Q5 (B8) ; plus aucun nouvel interrupteur d'environnement.
- CAP-D8-10 t4 — Dessins Éco / Recommandé / Max par `remplir(cible=N)` — GATED Q5 (B8), même raison.
- CAP-D8-11 t3 — `concevoir_rapide_pour_lead` (remplissage serveur) — coupé B7 : retirerait le feu vert, l'agricole et le second devis automatique, et publierait du deviné ; « rapide » = marquage (ACAL1004-ACAL1006).
- CAP-D8-11 t4 — `build_devis_auto` délègue à `concevoir_rapide_pour_lead` — coupé B7 ; plafond deviné non voulu (Q3, F2 retiré) ; le bouton reste sur `build_devis_auto`.
- CAP-D8-11 t5 — Fiche lead : kWc, production, économie servis du calepinage rapide et bouton « Affiner dans l'atelier » — non reprise ; dépend du chiffrage rapide coupé (t3).
- CAP-D8-12 t1 — Mention « estimation » sur les estimateurs du site public — reporté : touche `apps/web`, déployé seul par Cloudflare ; question web stop-and-ask pour Reda.
- CAP-D8-12 t2 — Le webhook lead n'accepte que de la géométrie du site — reporté : touche le flux de données du formulaire (stop-and-ask, CLAUDE.md).
- CAP-D8-13 t1 — Retirer l'aperçu navigateur du générateur (`computeROI`, `productibleForCity`) — non reprise : « après interrupteur levé 7 nuits », interrupteurs coupés ; brancher plutôt que retirer (D-ACAL-17..20).
- CAP-D8-13 t2 — Retirer `fallbackPerKwc` en mode ERP — non reprise ; ACAL994 le garde et le marque « estimation » ; interrupteur coupé.
- CAP-D8-13 t3 — Retirer `orientation_du_pan`, `pans_du_document` et jumeaux de `geometrie.py` — coupé B6 : les branches d'avant un niveau de règles servent à vie les devis envoyés.
- CAP-D8-13 t4 — Retirer `calepinage_options._Trame` et la prolongation de rangées — non reprise ; dépend de CAP-D8-10 t4 (GATED) et d'un interrupteur coupé.
- CAP-D8-13 t5 — Retirer l'adaptateur `electrical_service.py` et `string_design` — coupé B6 : devis sans calepinage et prix des nouveaux devis.
- CAP-D8-13 t6 — Retirer le remplissage navigateur de l'atelier en mode ERP — non reprise ; dépend de CAP-D8-10 (GATED Q5), le remplissage navigateur reste.
- CAP-D8-13 t7 — Retirer les interrupteurs `MOTEUR_CONCEPTION_*` de `settings/base.py` — coupé B4 : ces interrupteurs ne sont plus créés.

### Décisions fondateur du 21/11/2026
- Profils par distributeur marocain (pièces, limites, choix du gabarit par distributeur du lead) — D-ACAL-42 : un dossier générique d'abord ; ex-ACAL785, ACAL823, ACAL825, ACAL826, ACAL899.
- Export Word du rapport interne — preuve mince (deux fils de forum), dépendance gratuite : choix pris seul ; ex-ACAL900.

Total : 53 cartes ou sous-parties en réserve.

<!-- méthode : script Python (integ/_cov.py) — pour chaque carte `### CAP-D<n>-<nn>` de S\backlog\D1..D8, recherche de `CAP-D<n>-0*<nn>` dans les seules lignes de tâche (`- [ ] ACALnnn`) de tous les S\lots2\lot-D1..D8.md et lot-D1..D8-autres-plans.md ; cartes sans aucune citation : D1 (2), D2 (2), D3 (3), D4 (4), D5 (4), D6 (4), D7 (1), D8 (6 sur 13) ; recherche complémentaire « fiche NN » et mots-clés dans les lots : aucune couverture cachée trouvée. Quatre cartes jumelles non citées mais livrées sous un autre id, donc exclues : CAP-D2-19 (ACAL674, cite CAP-D3-20), CAP-D3-19 et CAP-D4-28 (ACAL885, cite CAP-D6-13), CAP-D4-26 (ACAL895, cite CAP-D6-09) ; CAP-D7-07 est portée par ACAL927 (REJEU-NEW-3, D-ACAL-38). Sous-parties D8 : découpe des tâches de chaque fiche confrontée aux tâches finales (ACAL991-ACAL1011, ACAL973) et à CRITIQUE-fable (b) B3-B8 et (d) « Coupé » ; D8-05, D8-06 t2, D8-08 t2-t3, D8-09 t1 jugées couvertes par ACAL1002/1003, les tâches D7 (ACAL916, 921, 924, 934-935) et ACAL994. Les raisons D1-D6 viennent des fiches (preuves, effort, score, rang) et de D4-contexte-partage.md ; D3-17 n'a aucune raison écrite. -->
