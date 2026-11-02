# Vérifie ASAV — seconde contre-visite de clôture du groupe sav (J4), 01/11/2026

Commande `vérifie ASAV` (METHODE §C.4.2, skill audit §5), lancée par la session d'orchestration de `loop audit`. La
contre-visite précédente, du 24/10 (`docs/audits/2026-10-24-sav-verifie.md`), avait déposé 11 tâches (ASAV104 à ASAV114),
dont 4 S1-S2. Toutes sont cochées. `audit_registre.py --du` ne liste pas cette contre-visite, parce que sa règle ignore les
contre-visites dues après le drainage des écarts. Elle est jouée quand même.

Pour chaque tâche tirée, on rapproche le texte, les commits, le test nommé et le code de `main`, avec les 7 critères de
`docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde jouée en transaction annulée.
Les écarts confirmés deviennent des tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon tiré sur `origin/main` = `56d5b623a` (PR #1197). Branche `verifie-asav-cloture-2`.
- **Registre.** J4 `sav`, groupe ASAV, dossier `docs/audits/2026-10-08-sav.md`.
- **Inventaire.** 101 tâches ASAV : 100 `[x]` et ASAV72 `[BLOCKED: sans objet]`.
- **Échantillon (graine = SHA `56d5b623a`) : 38 tâches.**
  - **Les 11 écarts du 24/10**, tous : ASAV104 à 114.
  - **Les P0/S1 cochées** : ASAV2 à 7, plus ASAV105, qui est déjà parmi les écarts.
  - **25 % du reste**, soit 21 sur 83 : ASAV16, 18, 23, 25, 27, 28, 29, 31, 33, 34, 35, 36, 37, 40, 52, 55, 56, 62, 64,
    73, 91.
- **Tirage additionnel.** Trois vérificateurs (lots 4, 5 et 7) ont tiré de leur propre chef un second quart du reste, soit
  environ 60 tâches. Des sous-vérificateurs sonnet les ont vérifiées en lecture seule. Ces verdicts sont rapportés à part
  (§1) ; seuls ceux recoupés par l'orchestrateur ou par une sonde fondent une tâche.
- **Pile des sondes.** Pile locale partagée `erp-agentique-*`, conteneur `erp-agentique-django_core-1`, qui monte le checkout
  principal (au même SHA). Le moteur Docker était saturé, puis il a été redémarré par la session d'orchestration. Les sondes
  sont passées une par une par le verrou partagé `.claude/sonde-slot.sh`. Chacune a fini en transaction annulée : base
  inchangée, 0 mail, 0 tâche Celery.

## 1. Vérificateurs (7 agents frais, opus, effort élevé, lecture seule, même répertoire, 4 à 6 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **35** | ASAV2, 3, 4, 6, 7, 16, 18, 23, 25, 27, 28, 29, 31, 33, 34, 35, 37, 40, 52, 55, 56, 62, 64, 73, 91, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113 |
| partiel | **3** | ASAV5 (**S1**), ASAV36 (S3), ASAV114 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

- **Les écarts du 24/10 sont fermés.** Les quatre sondes C-ASAV-VER-001 à 004 ne reproduisent plus (§2). Pour ASAV104 à 113,
  les causes ont disparu, jumeaux compris :
  - ASAV105 : les trois sites passent par `est_actif` ;
  - ASAV109 : annulation unitaire, annulation en lot, fusion et réactivation closent la pause ;
  - ASAV113 : le sélecteur, son jumeau en lot et la liste des contrats facturables utilisent `est_actif`.
- **Textes vieillis, code juste** (sans tâche) : ASAV2, 12 et 40 (le 400 est devenu 409 depuis ENF11), ASAV6, et ASAV90-94
  (`sav-decisions-fondateur.md` n'a jamais existé ; les décisions vivent dans `decisions-audit-0810.md` et `decisions.yml`).
- **Vitest rejoués** (un fichier à la fois) :
  - TicketsPage.asav3 4/4, TicketsPage.asav45 8/8 ;
  - SavParametresPage.asav56 3/3 et SavParametresPage 10/10 ;
  - SavListesPaginees.asav52 5/5, ProblemesPage.asav55 2/2 ;
  - EquipementSignalerPage.asav29 3/3, TicketSuiviPage.asav31 4/4, WarrantyClaimsPage.asav36 2/2.

  Les tests Django à base de données n'ont pas été rejoués : la base de test partagée est réservée, et la CI de `main` les
  couvre.
- **Tirage additionnel.** Environ 60 tâches. Partiels relevés, tous S3 :
  - ASAV10 : `equipement_neuf` ne sert pas la fin de garantie ;
  - ASAV11 : la fiche ne dit pas « garantie à confirmer » ;
  - ASAV21 : le balayage SLA ignore l'échéance horaire ;
  - ASAV65 : `sans_reference` est servi mais jamais lu ;
  - ASAV101, 102 et 103 : aucune preuve en direct, et ces tâches ne sont pas dans la dette gelée.

  Tous les autres sont ok.

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-ASAV-VER-001.py` | ASAV104 | non reproduit | « is_responsable=True sans override=403 avec override=403 lignes=[] » |
| `C-ASAV-VER-002.py` | ASAV105 | non reproduit | « ouverture=2026-09-02 contrat.date_debut=2026-11-01 … facturer=201 couverture=facturable lignes=['5000.00'] » |
| `C-ASAV-VER-003.py` | ASAV106 | non reproduit | « 1er envoi (HEIC)=400 renvoi sans photo=201 … tickets de l'équipement=2 » |
| `C-ASAV-VER-004.py` | ASAV107 | non reproduit | « statut servi=expire_bientot clé date_fin_garantie_effective servie=True » |
| `C-ASAV-VER2-31.py` | ASAV5 | **REPRO** | « t0 ouvert 2026-10-02 (avant contrat 2026-10-12) … t1 couverture_calculee=facturable … 'deplacements_consommes': 1, 'deplacements_restants': 0 … facturer=201 couverture=facturable lignes=['5000.00'] (attendu contrat, 0) » |
| `C-ASAV-VER2-411.py` | ASAV21 | REPRO (partiel) | « sla_breach=False notifications=1 » : le drapeau n'est pas posé par le balayage, alors qu'une notification part |
| `C-ASAV-VER2-71.py` | ASAV11 | REPRO | « 'sous_garantie_effectif_display': 'À déterminer' … mention « à confirmer » servie=False facturer=409 » |

## 3. Seconde lentille et critique de complétude

- **Seconde lentille sur ASAV122** (opus, effort élevé, contexte frais) : **S1 confirmé.**
  - Le scénario est réaliste. Un contrat né d'un devis prend `date_debut` = date d'acceptation, donc en cours d'année.
  - Le cas courant : une panne fait vendre un contrat sur un chantier existant.
  - `droits_restants` ne lit jamais `date_debut`, ce qui contredit ASAV5 (« tickets éligibles ») et D-ASAV-6.
  - Sur le chemin par défaut, `couverture` vaut `A_DETERMINER`, puis la couverture calculée donne « facturable », et
    `facturer` facture la pièce au prix de vente.
- **Critique de complétude (1 appel Fable, effort élevé).**
  - **ASAV122 : un jumeau manquait.** `serializers.py::TicketListSerializer._precharger_droits` refait la même requête de
    quota pour la liste SAV ; corrigée seule, `droits_restants` laisserait la liste dire « facturable » là où la fiche dit
    « contrat ». Le fichier est ajouté aux Files, et la parité liste/fiche a désormais un cas à contrat signé en cours
    d'année.
  - **Tickets sans `date_ouverture`.** Les tickets préventifs (`creer_ticket_preventif`) et quatre autres chemins de
    création ne posent pas `date_ouverture` : ils ne consomment jamais le quota. La date de référence de la tâche les
    compte.
  - **Spot-check des « ok » argent** (ASAV104, 105, 2, 113) : aucune divergence.
  - **Trous.** `creer_devis` est clos (`client_base_qs(company)`, une autre société reçoit 404). Une `date_ouverture`
    antidatée est un usage autorisé (D-ASAV-6) : c'est optionnel. Aucun autre S1-S2.
  - **Tâches.** Toutes les ancres des tâches ASAV115 à 121 sont exactes. La seule erreur était la clause Jumeaux d'ASAV122,
    corrigée.
- **Décisions** (Reda, 02/11/2026, questions interactives, inscrites dans `docs/audits/decisions.yml` et dans les tâches) :
  - **D-ASAV-VER2-1, « Couverts par le contrat seuls ».** Ne consomment le quota que les tickets que le contrat couvre :
    ouverts à partir de `date_debut`, sur un équipement de son registre, et pas déjà couverts par la garantie constructeur.
  - **D-ASAV-VER2-2, « Année civile ».** La fenêtre du quota reste l'année civile, bornée par `date_debut` l'année de départ.
  - **D-ASAV-VER2-3, « Oui, regel unique ».** La dette d'acceptation révélée par ASAV120 (environ 134 ids, 25 groupes) est
    regelée une seule fois, puis ne fait que rétrécir.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Gravité | Cause | Preuve | Plan |
|---|---|---|---|---|---|---|
| ASAV122 | C-ASAV-VER2-31 | ASAV5 | **S1** | clause-manquante (« tickets éligibles » : un ticket antérieur au contrat consomme le déplacement inclus) | sonde REPRO | SAV |
| ASAV115 | C-ASAV-VER2-411 | ASAV21 | S3 | clause-manquante (balayage SLA sur la date seule) | sonde | SAV |
| ASAV116 | — | ASAV65 | S3 | L4-appelant (`sans_reference` sans lecteur) | lecture | SAV |
| ASAV117 | C-ASAV-VER2-71 | ASAV11 | S3 | clause-manquante (mention « garantie à confirmer », D-ASAV-2 a) | sonde | SAV |
| ASAV118 | — | ASAV36 | S3 | clause-manquante (fournisseur non prérempli) | lecture | SAV |
| ASAV119 | — | ASAV10 | S3 | clause-manquante (fin de garantie non servie) | lecture | SAV |
| ASAV120 | — | ASAV100-103, APDF101-109 | S3 | L7 (la garde d'acceptation ignore une preuve sans numéro d'étape) | garde exécutée | DEPLOY |
| ASAV121 | — | ASAV114 | S3 | L7 (oracle 10 jamais tracé ; DONE LOG vers l'enregistrement FAIL) | lecture | SAV |

**1 écart S1-S2** (ASAV122, argent) et 7 S3. Les tâches sont au format v3, sous `### ASAV — ÉCARTS vérifie 2026-11-01 ·
format v3`.

**Chiffre client.** ASAV122 change la facturation d'un ticket SAV couvert par un contrat signé en cours d'année. Seules les
nouvelles facturations sont touchées ; aucune facture émise n'est réécrite.

## 5. Optionnel (non déposé)

- **ASAV106 et 28.** Une photo valide est stockée avant le contrôle de rejeu, donc un rejeu laisse un objet orphelin dans
  MinIO. De plus, `store_attachment(photo)` est appelé sans `company=`.
- **ASAV23.** Le contrôle « vérifier puis créer » n'est pas atomique : un double clic simultané peut créer deux tickets.
- **ASAV55.** Le champ « N° du ticket à lier » attend l'identifiant interne, alors que l'écran n'affiche que les références.
- **ASAV108.** `test_creation_ticket_anterieur_au_contrat_sans_note` passerait aussi avec l'ancien code. Un quota 0
  discriminerait.
- **ASAV113.** Avec `est_actif`, un contrat à début futur refuse désormais la proposition d'entretien et le segment
  « sans contrat ». C'est voulu (ASAV105).
- **ASAV102.** Un `client_id` d'une autre société reçoit 409 au lieu de 404.
- **`creer_devis`.** La vue lit `client_id` dans le corps de la requête. Le recadrage par société n'a pas été vérifié.
- **Garde d'acceptation.** `check_acceptation.py --groupe ASAV` donne « 71 cochée(s) à preuve, 1 couverte(s) ». ASAV114 porte
  une étiquette `@acceptation` nue que la garde ne compte pas. Ce point est porté par ASAV120.

## 6. Couverture et non-couvert

- **Couvert.**
  - 38 tâches sur 100 : les 11 écarts du 24/10, ASAV2 à 7 et 25 % du reste.
  - Environ 60 tâches de plus en tirage additionnel.
  - Commits, tests nommés et code de `main`.
  - 7 sondes rejouées : les 4 anciennes et 3 nouvelles.
- **Non couvert.**
  - Les tâches restantes.
  - Les tests Django à base de données (laissés à la CI).
  - Aucun aller-retour à l'écran, aucune lecture en production : on ne sait pas combien de tickets réels l'écart ASAV122
    touche.
- **Statut du registre.** Après ce dépôt : 100 tâches cochées sur 108 constructibles (93 %), ASAV115 à 122 ajoutées. Cette
  contre-visite de clôture porte **1 écart S1-S2** : le cycle n'est pas sorti, il faut deux contre-visites consécutives à
  zéro S1-S2.

## 7. Coût

- 7 vérificateurs opus (effort élevé) : environ 1,3 M de jetons, plus les sous-vérificateurs sonnet du tirage additionnel.
- 1 seconde lentille, 1 critique Fable, 1 rédacteur opus (8 tâches v3).
- Orchestrateur : échantillon, triage, et 7 sondes jouées par le verrou.
- H0 S3 O9 F1 · jetons sous-agents environ 2 M

<!-- verifie | groupe: ASAV | pct: 93 | ecarts_s1_s2: 1 -->
