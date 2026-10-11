# Vérifie ATOT — contre-visite mi-parcours du groupe totaux (X2), 11/10/2026

Commande `vérifie ATOT` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**31 tâches cochées sur 34** constructibles (**91 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 13ᵉ et dernière de la boucle des groupes jamais vérifiés. Groupe ARGENT à forte densité P0/S1 — la méthode v3 avait
relevé que 2 régressions d'écran y avaient été mergées sous CI verte (ATOT2, ATOT9) ; contre-visite rigoureuse.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `751629bea` (re-fetch en début d'itération). Branche de claim : `verifie-atot`.
- **Registre.** X2 `totaux`, groupe ATOT, tâches réparties (facturation 17, transverse 5, devis 3…).
- **Inventaire (déterministe).** 34 tâches ATOT, 31 `[x]`.
- **Échantillon (graine = SHA `751629bea`).** Toutes les P0/S1 cochées (11) + 25 % du reste (5 sur 20). Total : **16 tâches**.

## 1. Vérificateurs (16 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **15** | ATOT2, 3, 5, 6, 10, 13, 15, 16, 18, 20, 22, 24, 26, 32, 34 |
| partiel | **1** | ATOT31 (S2) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1 : 0.** Pas de critique Fable (réservée aux écarts S1 restants).

Points saillants des tâches jugées ok (argent, double-facturation, parité) :

- **ATOT2 (aucune vente facturée deux fois).** `factures_du_devis` = Q(devis)|Q(bon_commande__devis)|Q(sources__devis) ;
  `exiger_devis_facturable` lève 400 FR sur les 4 portes (tranche/complète/BC/consolidée) ; test endpoints réels, 12 ordres,
  Σ `total_ttc` ≤ TTC du devis. **La garde S1 est tenue CÔTÉ SERVEUR** (c'est ce qui rend l'écart ATOT31 S2 et non S1).
- **ATOT3/ATOT6 (consolidée & ventilation d'avoir à taux mixtes).** La consolidée recopie le MÊME panier que la facture
  simple (option effective, taux par ligne) et refuse 400 si TTC ≠ Σ options ; avoir/note-débit ventilés au centime
  (`ventilation_tva`), jumeaux écran/PDF corrigés. Tests comportementaux sur montants stockés.
- **ATOT5/ATOT10 (tranche par clé, pro-forma = option effective).** La tranche suit la 1ʳᵉ clé non couverte (plus jamais
  `tranches[len]`) ; le pro-forma suit `option_effective` (plus de `_proforma_option`). Tests sur PDF rendu réel.

## 2. Tests nommés

- Les 15 tâches jugées ok ont un test nommé **présent et comportemental** (endpoints/PDF réels, montants stockés, Σ ≤ TTC).
  Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `751629bea`.

## 3. Sondes

Aucune sonde déposée : l'unique écart (ATOT31) est S2 (écran trompeur, pas de corruption d'argent — la garde S1 est tenue
serveur par ATOT2). Les clauses argent des tâches échantillonnées ont été jugées tenues par lecture du code de production.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| ATOT39 | C-ATOT-VER-001 | ATOT31 | S2 | `crm/serializers.get_devis` ne sert aucun bloc `solde` → l'onglet Devis du lead retombe sur 'libre' et offre « Facturer » après facture complète ; double-facturation refusée 400 serveur (ATOT2) donc écran trompeur, pas S1 | tâche v3 déposée (`PLAN_AUDIT_TRANSVERSE.md`, multi-propriétaires lead + facturation, @atomique) |

**Constats S1 : 0.** ATOT31 est S2 : la moitié ÉCRAN de C-ATOT-001 (onglet Devis du lead) n'est pas câblée côté serveur, mais
la double facturation reste impossible (ATOT2, garde serveur vérifiée). ATOT ne devient pas `vérifié` tant qu'ATOT39 n'est
pas construit.

## 5. Optionnel (non déposé)

- ATOT38 (open, frontend DevisTab) et ATOT37 (open, DevisRow) dépendent du bloc `solde` servi — ATOT39 est leur prérequis
  backend manquant, non couvert par AMET9 (qui sert `solde` côté ventes seulement).
- ATOT6/ATOT10 : notes de leçons (jumeaux) des vérificateurs sans divergence — verdict ok.

## 6. Couverture et non-couvert

- **Couvert.** 16 tâches sur 31 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code d'argent, gardes serveur.
- **Non couvert.** Les 15 autres tâches cochées ; aucun aller-retour en direct (lecture seule) — l'acceptation du groupe
  (ATOT17) est en dette gelée.
- **Statut du registre.** Après ce dépôt : 31/34 cochées (91 %), contre-visite mi-parcours avec **1 écart S2** déposé en
  tâche (0 écart S1). La clôture (≥ 95 %) et la sortie du cycle restent dues ; ATOT `vérifié` seulement après ATOT39.

## 7. Coût

- 16 vérificateurs opus (effort élevé) : **≈ 1,55 M de jetons**, 301 appels d'outil, ≈ 28 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 16 verdicts (focus régression d'écran), vérification que l'S1 est
  tenu serveur (ATOT2) et que la moitié écran manque au sérialiseur crm, rédaction.

<!-- verifie | groupe: ATOT | pct: 91 | ecarts_s1_s2: 1 -->
