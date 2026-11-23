# Classes du tour 1 et du tour 2 encore violées — complément du lot C (production), 23/11/2026

Code lu sur la tête `f2f2348ec`. Une ligne par endroit neuf ; les fiches d'origine ne sont pas dupliquées.

## K-GRANDEUR-UNIQUE — la TABLE des lectures de la production (complète la matrice du tour 1)
Invariant rappelé : pour une conception, UNE production source ; tout autre chiffre est une LECTURE de celle-ci, ou nomme son
écart et sa raison. Source unique voulue (tranchée au § 3 de `lot-C.md`) : **le P50 servi par la simulation**
(`resultat.production.total.p50_kwh`) quand une simulation à jour existe ; avant simulation, l'estimation de l'atelier, dite
« estimation » ; le chiffre du devis (moteur du devis, `/proposal`) est une AUTRE méthode, toujours nommée comme telle.

| # | Écran / sortie | Chiffre lu (calepinage) | Source aujourd'hui | Source voulue | Écart nommé ? | Tâche |
|---|---|---|---|---|---|---|
| 1 | barre de résumé, avant simulation (étape Panneaux) | 4 542 kWh/an (1898) | estimation du navigateur | estimation, dite telle | oui (« estimation de la pose ») | — (tient) |
| 2 | barre de résumé, après simulation | 5 131 → 5 173 (1898) | P50 servi | P50 servi | — | — (tient) |
| 3 | colonne de l'atelier Expert, « TOTAL — TOUTES LES ZONES » + « Dans la durée » | 4 362 kWh/an, « ~0,5 %/an » inventé | navigateur (`affichageErp.ts::texteBande`) | estimation + P50 nommé ; dégradation de la fiche ou silence motivé | non | ACAL1612 |
| 4 | bloc de provenance Expert « Devis : … (imprimée au client) » | 4 362 | figure posée par le calepinage | — (ligne retirée quand le PDF ne l'imprime pas) | — | doublon ACAL1274 (plié) |
| 5 | « Le devis annonce » (Expert ; absent du Guidé) | 4 542 | `quote_engine/figures.py::production_imprimee` | même chiffre, aussi à l'étape Résultats guidée | oui (+ 13,9 %) | ACAL1638 |
| 6 | étape Résultats (P50 de tête) | 13 053 (1983), dont 4 panneaux non raccordés | simulation de TOUS les modules | P50 des modules raccordés, `hors_chaine` dit | non | ACAL1602 (S1) |
| 7 | écrêtage, ratio DC/AC (Verdict électrique) | 12,1 % sur 9,1 kWc ; ratio 1,26 sur 6,3 kWc | deux bases | une base : modules raccordés | non | ACAL1602 |
| 8 | carte Recommandation (Expert) ↔ onglet Économie | 11 611 ↔ 14 620 (1988) | atelier ↔ moteur du devis | P50 / estimation ; moteur du devis nommé | non | ACAL1611 (+ ACAL853 contredit) |
| 9 | rapport d'étude, synthèse | P50 au rendu (5 131,1) | P50 servi | P50 servi | — | — (tient) ; P50 « 8 198 » contre 5 571 cité par l'orchestrateur : non retrouvé dans les rapports du lot C, à rejouer |
| 10 | onglet Pertes, ligne d'arrivée | « 19,6 % (pertes totales) » | `100 − niveau` | énergie livrée + part | — | ACAL1658 |
| 11 | tuile « Écart avec PVGIS » | + 17,3 % | PVcalc à perte TOTALE (double compte) | PVcalc à pertes système | non | ACAL1606 |
| 12 | part de consommation : carte Panneaux ↔ Résultats ↔ PDF | 66 % ↔ (rien) ↔ 48 % | carte (facture) ↔ — ↔ moteur du devis | même fonction partout ; devis nommé | non | ACAL1613, ACAL1631, ACAL1608 |
| 13 | carte « Couvrir la facture » kWc ↔ barre | 4,97 ↔ 4,90 ; « plusieurs modèles » | ancien module ; zone vide comptée | modules posés | non | ACAL1663 |
| 14 | cible Expert ↔ bande | « 400 cible » ↔ 4 | sentinelle stockée | cible ou « le plus possible » | non | ACAL1665 |
| 15 | « Production visée » maximum ↔ « + » | 7 536 / 7 panneaux ↔ 10 panneaux | orientation courante | deux orientations | non | ACAL1618 |
| 16 | comptes « N pertes non comptées » ↔ lignes listées | 20 ↔ 7 ; 13 ↔ 3 | deux comptes | un compte | non | ACAL1619 (+ ACAL700 contredit) |
| 17 | rapport d'ombrage « Accès solaire moyen (%) » | 0,9 | fraction étiquetée % | % arrondi | — | ACAL1660 |
Garde : celle de la fiche du tour 1 (« une grandeur, une valeur » sur un golden) ; les lignes 3, 6, 8 et 12 y sont à ajouter par le
rédacteur des tests premiers.

## K-SAISIE-PERDUE — la consommation saisie n'atteint pas le calcul
| Endroit | Viole ? | Tâche |
|---|---|---|
| `services/courbe_charge.py::_courbe_de_base` (facture du lead ignorée par la simulation, `ORIGINES` sans elle) | oui, lue (CONSO-013 a) | ACAL1608 |
| `apps/web/src/scripts/roofPro11/consommationSerialisee.ts::construireConsommation` (`emptyCurve()` : 24 zéros écrits) | oui, lue (CONSO-013 b) | ACAL1609 |
| `apps/web/src/scripts/roofPro11/consommationMois.ts::monterGrilleFactures` (mois jamais écrits ni relus ; aucune clé au contrat) | oui, lue (CONSO-006) | ACAL1601 → ACAL1610 |
| `frontend/.../atelier/PanneauBatterie.jsx::DeclarationBatterie` (champs masqués encore postés : la saisie cachée agit) | probable (CONSO-009) | ACAL1666 |
| `backend/django_core/apps/stock/serializers_fiche_technique.py::FicheTechniqueSerializer` (dégradation, rendement d'optimiseur acceptés puis ignorés) | oui, lue (RESU-b-010, SIMU-b-002) | ACAL1600 |
Matrice ajoutée : facture du lead × simulation (casse), factures mensuelles × rechargement (casse), charge seule × base (casse),
stratégie changée × saisie masquée (casse), déclaration batterie × rechargement (tient, CONSO), carte Recommandation × facture (tient, ACAL777).

## K-COLONNE-ETROITE (lot B) — endroits du lot C
`frontend/src/features/calepinage/atelier/coque/CoqueAtelier.jsx::CoqueAtelier` force la carte en Expert : les onglets de
Résultats (Production, Pertes, Économie, Batterie) tombent dans la colonne de 270-300 px (RESU-011, CONSO-004, ACAL970, ACAL737)
→ ACAL1617 (racine) ; restent en colonne même après : barres de « Mes factures » (`consommationMois.ts::htmlBarres`, CONSO-005,
ACAL837) → ACAL1643 ; champs de la déclaration batterie (CONSO-008, ACAL788, ACAL792) → ACAL1644.

## K-RETOUR-FAUX, K-JARGON, K-HYDRATATION — endroits neufs du lot C
- K-RETOUR-FAUX : motif « document modifié » pour un réglage société (SIMU-a-002 → ACAL1647) ; rapport d'ombrage toujours
  indisponible, chemin `zones[]` (RESU-b-008 → ACAL1615) ; liste et rail qui ne nomment pas le blocage (RESU-003 → ACAL1650) ;
  simulation auto refusée en silence (RESU-004 → ACAL1651) ; bandeau non rafraîchi (RESU-009 → ACAL1653) ; jumeau de consigne
  ACAL732 (RESU-020 → ACAL1637) ; variante identique qui périme (RESU-026 → ACAL1659) ; job tué resté à 5 % (ORCH-001 → ACAL1622).
- K-JARGON : clés et codes servis (RESU-001, -014, -018, -021, CONSO-015) ; motifs d'étapes de développeur (RESU-010 → ACAL1655) ;
  fiche CLIENT « 5 postes » (RESU-023 → ACAL1616, S2) ; provenance du rapport (RESU-015 → ACAL1656).
- K-HYDRATATION (lot A) : accès solaire « aucune obstruction » à la réouverture (RESU-b-006 → ACAL1620, `@after` ACAL1501) ;
  « Modifications non enregistrées » sans geste (RESU-b-012 → ACAL1661).
