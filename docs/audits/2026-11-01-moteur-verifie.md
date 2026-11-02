# Vérifie AMOT — seconde contre-visite de clôture du groupe moteur (D2), 01/11/2026

La commande `vérifie AMOT` (METHODE §C.4.2, skill audit §5) a été lancée pendant `loop audit`. Le
groupe compte 109 tâches cochées sur 113 (96 %, `audit_registre.py status` ; restent AMOT54, AMOT64, AMOT65 et AMOT78
`[BLOCKED]`), et toutes les tâches ÉCART de la contre-visite précédente (`docs/audits/2026-10-31-moteur-verifie.md`,
AMOT102-AMOT114) sont cochées. `audit_registre.py --du` ne la liste pas : sa règle ne recompte pas un groupe déjà passé à
≥ 95 %. Elle a donc été jouée sans attendre la règle.

Le moteur relève de la règle n° 4 (`/proposal` seul chemin des PDF de devis client) : les vérificateurs et le rédacteur ont
tourné en opus, effort élevé. Toute correction d'un chiffre ou d'un texte imprimé ne touche que les nouveaux rendus (règle
du fondateur « devis envoyés : nouveaux rendus seulement », niveaux `regles_calcul`).

Pour chaque tâche de l'échantillon, on rapproche le texte, les commits, le test nommé et le code de `main` avec les 7
critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés deviennent des tâches v3 dans le plan du
propriétaire des fichiers. La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `56d5b623a` (PR #1197) pour l'échantillon et les vérificateurs ; `0d4aa868d` (PR #1200) pour le
  rédacteur, sans changement sur les fichiers visés (`git diff --stat` vide). Le conteneur de sondes partagé
  `erp-agentique-django_core-1` monte le checkout principal.
- **Échantillon (graine = SHA `56d5b623a`, `random.Random(int(sha, 16)).sample`) : 43 tâches.**
  - Les tâches S1/P0 : AMOT8, 17, 19, 60, 79, 80, 86, 90, 102, 103.
  - Les 13 tâches ÉCART du 31/10 : AMOT102-AMOT114.
  - 25 % du reste (22 sur 88) : AMOT2, 7, 13, 14, 15, 23, 25, 27, 30, 40, 42, 45, 50, 55, 68, 69, 73, 77, 85, 95, 99, 100.
- **Incident de pile.** Pendant la contre-visite, le moteur Docker de la machine (partagé par trois sessions de
  contre-visite) est tombé sous la charge. Reda l'a redémarré. Les sondes ont été rejouées une par une ensuite (§2) ;
  C-AMOT-VER-030 avait d'abord été jouée sur l'hôte (fonctions pures), puis rejouée dans le conteneur.

## 1. Vérificateurs (5 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **40** | AMOT2, 7, 8, 13, 15, 17, 19, 23, 25, 27, 30, 40, 42, 45, 50, 55, 60, 68, 69, 73, 77, 79, 85, 86, 90, 99, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114 |
| partiel | **2** | AMOT14 (appelant oublié : l'envoi par e-mail), AMOT80 (test qui encode le défaut) |
| régression | **1** | AMOT95 (par `d60b9695e0`, CPDF3/CPDF5 du 27/10) |
| non-fait / faux / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, donc pas des régressions :
- CPDF5 (décision du 26/10, « aucune incertitude imprimée ») : la mention TVA de page 1 d'AMOT95 et la rangée « méthode
  d'autoconsommation » d'AMOT99 ne s'impriment plus ;
- décisions du 26/10 et du 30/10 : la rangée « Statut de l'étude : offre ferme » d'AMOT80 retirée, horizon C&I à 10 ans ;
- `9dcd86b438` : les devis aux règles d'origine gardent leur rendu (AMOT8, AMOT45) ;
- APAR49 / RGEN2 : repli `tva_standard(company)` (AMOT69) ; AMOT92 après AMOT90 ; niveau de règles 8 après AMOT103.

## 2. Sondes

Rejouées une par une par `scripts/sonde.py` (créneau partagé), en transaction annulée, base inchangée à chaque fois.

| Sonde | Tâche | Verdict | Observé (code de `main`) |
|---|---|---|---|
| `docs/audits/sondes/AMOT/C-AMOT-VER-030.py` | AMOT95 | REPRO | couverture C&I à deux options, base « deux » : cartes « Investissement TTC 640 000 MAD / Économie annuelle 98 931 MAD HT » et « 840 000 / 20 000 MAD HT », sans « soit … TTC » ; la tuile mono-option imprime « soit 118 717 MAD TTC » |
| `docs/audits/sondes/AMOT/C-AMOT-VER-040.py` | AMOT80 | REPRO | économie « omis » (contrat non déclaré), baseline source « factures » : la couverture demande quand même les 12 dernières factures |
| `docs/audits/sondes/AMOT/C-AMOT-VER-050.py` | AMOT14 | REPRO | dernier rendu mémorisé « onepage » ; `envoyer-email` sans `pdf_mode` → 200, pièce jointe rendue en « full » |
| `docs/audits/sondes/AMOT/C-AMOT-VER-010.py` | AMOT102, AMOT107 (rejeu) | non-régression | devis réel au niveau de règles 8 : `roi_a` attendu 16,8 = palier 16,8 = repli « avec » 16,8 → la cause des deux écarts a disparu |
| `docs/audits/sondes/AMOT/C-AMOT-VER-003.py` | AMOT103 (rejeu) | non concluant | la sonde du 31/10 appelle `_payback_publie_palier` et `_balayage_stockage_publique` avec leur ancienne signature (sans `devis`, sans `servi`) : elle rejoue le chemin d'avant AMOT102/103 ; remplacée par C-AMOT-VER-010 |

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-AMOT-VER-030 | AMOT115 | AMOT95 (régression) | C1 | **S2** | `backend/django_core/apps/ventes/quote_engine/ci/options_cote.py::lignes_sans` | cartes « Sans / Avec batterie » : investissement TTC face à une économie HT seule → l'économie TTC servie à côté de la HT, en base « deux », nouveaux rendus seulement |
| C-AMOT-VER-040 | AMOT116 | AMOT80 | C1 | S3 | `backend/django_core/apps/ventes/quote_engine/ci/synthese.py::_bloc_argent` | « vos 12 dernières factures » demandé même quand la consommation est connue → dire le vrai manque (contrat, horaires) ; crée le niveau de règles 9 lu par AMOT115 |
| C-AMOT-VER-050 | AMOT117 | AMOT14 (appelant oublié) | C8 | S3 | `backend/django_core/apps/ventes/views/devis_envoi.py::DevisEnvoiActionsMixin.envoyer_email` | sans `pdf_mode`, la pièce jointe part en « full » → suivre les options mémorisées comme « Télécharger » |

**Constats S1-S2 : 1** (0 S1, 1 S2), reproduit par sonde.

Routage (`check_ownership.py --owner-of`) :

| Propriétaire | Plan | Tâches |
|---|---|---|
| moteur | `PLAN_AUDIT_MOTEUR.md` | AMOT115 (`@after: AMOT116`) |
| moteur + devis | `PLAN_AUDIT_TRANSVERSE.md` `(@atomique: moteur, devis)` | AMOT116 |
| devis | `PLAN_AUDIT_DEVIS.md` | AMOT117 |

AMOT116 porte la moitié partagée (niveau `regles_calcul` 9, migration, drapeau du builder), sur le précédent AMOT102 →
AMOT103 ; `plan_lanes.py` refuse AMOT115 tant qu'AMOT116 n'est pas cochée. Les libellés des nouveaux motifs d'AMOT116
(« votre contrat d'électricité (tarif, puissance souscrite) », « vos horaires d'activité ») sont une proposition du
rédacteur, à relire au build. Aucune décision du fondateur n'est requise.

## 4. Seconde lentille et critique

Aucun constat S1 : pas de seconde lentille ni de critique Fable (METHODE §C.4.2, skill audit §5). Le rédacteur (opus, effort
élevé, contexte frais) a relu chaque mécanisme : la valeur TTC de l'option « avec » existe dans
`etude_ci.option_avec.economie_ci.economie_annee1.total_mad_ttc`, mais `ci/mentions.py::valeur_option_avec` ne sert que la HT.

## 5. Optionnel (non déposé)

- **Jumeau probable d'AMOT115.** `ci/blocs.py::bloc_option_avec` imprime l'économie « avec » en « … MAD » sans TTC (non
  sondé) ; avec l'option « avec » servie (CPDF1), l'offre de financement n'apparaît plus (bloc absent de
  `option_avec.economie_ci`) — à signaler au groupe CPDF si involontaire.
- **AMOT13.** `crm/public_views.py::_item_payload` (salle de vente publique, parquée D-ACRM-6) peut créer ou prolonger un
  lien de partage sur un GET public.
- **AMOT14.** La clé `__apercu` est commune à tous les rendus non persistés d'un devis (croisement possible).
- **AMOT100.** Aucun écran ne règle `facteur_co2_reseau_*` (API seule).
- **AMOT102 / AMOT103.** Écart de TVA de ligne possible entre `_payback_publie_palier` et `_cout_onduleur_ttc` si
  `Produit.tva` ≠ taux du devis (hypothétique) ; provision arrondie par `arrondi_affichage` hors position offerte.
- **AMOT108.** La remise de la provision diffère entre PDF (`remise_globale`) et carte (facteur moyen, remises de ligne
  comprises) — approximation antérieure, documentée.
- **Tests plus étroits que la tâche** : AMOT8 (clause client au niveau des données), AMOT17 (résidentiel hors module nommé),
  AMOT23 (pages HTML), AMOT25 (pas le texte du PDF d'étude), AMOT30 (pas de `TariffSettings` en base), AMOT40 (mentions
  codées en dur), AMOT42, AMOT45 (pas d'industriel), AMOT69 (persistance non assertée), AMOT85, AMOT104, AMOT106 (branchement
  du hook non testé), AMOT108 (espion au lieu du payback final).

## 6. Couverture et non-couvert

- **Couvert.** 43 des 109 tâches cochées : commits, tests nommés, code de `main`, décisions D-AMOT-*.
- **Non couvert.** Les 66 autres tâches cochées ; aucune lecture en production ; aucune suite de tests rejouée (les verdicts
  sur les tests viennent de leur lecture).

<!-- verifie | groupe: AMOT | pct: 96 | ecarts_s1_s2: 1 -->
