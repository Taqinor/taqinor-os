# Fabrique documentaire AO — contrat, invariants, visibilité, gates

> Groupe AOF (`docs/PLAN.md`). Ce document est le compagnon de
> `docs/moteur-calepinage.md` : celui-là décrit le MOTEUR (ce qui calcule),
> celui-ci décrit la FABRIQUE (ce qui rend un dossier remettable).

---

## 1. Le rituel de gates HÔTE — à faire AVANT tout push (AOF193)

**Pourquoi ce rituel existe.** Les gardes plateforme de ce dépôt sont
partiellement keyés par `fichier:ligne`. Un agent qui travaille en *worktree*
n'a ni `node_modules` ni base de données : il ne voit donc PAS qu'une migration
a décalé des lignes et rougi `backend-lint`. C'est une classe de bug déjà
mesurée ici (« réalignement massif des allowlists `file:line` `on_delete` »,
DONE LOG du 2026-07-19). Le remède est mécanique, pas de la vigilance.

**Règle 1 — réaligner DANS LE MÊME COMMIT.** Toute migration qui décale les
lignes d'un fichier de modèles réaligne `scripts/on_delete_allowlist.txt` dans
le commit qui la porte. Jamais « au fold », jamais « plus tard ».

**Règle 2 — les six scripts, sur l'HÔTE, avant tout push.** Depuis
`backend/django_core/` pour les cinq premiers, depuis la racine pour le
dernier :

```
python ../../scripts/check_platform.py
python ../../scripts/check_on_delete.py
python ../../scripts/check_build_order.py
python ../../scripts/check_modules.py
python ../../scripts/check_stages.py
PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --check
```

Sous Windows, `PYTHONIOENCODING=utf-8` n'est pas décoratif : sans lui, la
sortie accentuée de `codemap_fingerprint.py` casse sur la console.

**Règle 3 — aucun nouveau `FileField`.** Le garde ARC26
(`apps/records/platform_guards.py`) gèle `apps/ao/models.py` à
`{"fichier": 1}` — l'unique `PieceSoumission.fichier` historique. Ce garde est
keyé par **chemin ET nom de champ**, donc faire grossir `models.py` ne le
décale PAS : seule l'apparition d'un `FileField` le fait rougir. Tout nouvel
artefact passe par `records.Attachment` ou `ged.Document`.

**État constaté au 2026-08-01 (lane intégrations + gouvernance).** Les cinq
premiers scripts sont VERTS sur l'hôte. `codemap_fingerprint.py --check`
signale une empreinte de STRUCTURE périmée : c'est attendu et normal — le
groupe ajoute des modules, et la régénération de `docs/CODEMAP.md` §3/§4/§10
puis `codemap_fingerprint.py --write` appartient à l'orchestrateur, dans le
commit de fold (aucune lane n'écrit dans `CODEMAP.md`, sinon chaque fold
produit un conflit d'empreinte). `scripts/on_delete_allowlist.txt` ne porte
**plus aucune** entrée `apps/ao/models.py:<ligne>` : les 15 anciennes ont été
remplacées par des commentaires inline `# on_delete: <raison>` dans le modèle,
ce qui immunise la baseline aux décalages de lignes de la lane AO. C'est un
RÉTRÉCISSEMENT de la baseline, jamais un élargissement.

---

## 2. Contrat du contexte de dossier

`construire_contexte(dossier)` rend **un** dict gelé et versionné qui alimente
les 9+ pièces du dossier. Deux règles en découlent :

- **Aucun gabarit ne contient de chiffre littéral.** Un chiffre écrit dans un
  gabarit est un chiffre qui divergera du calcul au premier ajustement, sans
  que personne ne s'en aperçoive avant le maître d'ouvrage.
- **Les montants en lettres sont RECALCULÉS, jamais recopiés ni stockés**
  (`core.nombre_lettres`, style administratif d'AOF109). Un montant en lettres
  stocké est un montant en lettres qui ment dès la première révision de prix.

---

## 3. Invariants de cohérence — une PORTE, pas un rapport

Le contrôleur croisé refuse le passage ; il ne se contente pas de signaler.
Les invariants portent notamment sur :

- quantités du bordereau **=** engagements portés sur les planches ;
- somme des engagements par bâtiment **=** engagement global du projet ;
- `Σ quantité × prix unitaire` **=** total annoncé, au centime ;
- capacité **démontrée** (variantes retenues) vs capacité **engagée** — l'écart
  est publié, jamais masqué ;
- aucune variante `publiable` dont le total retenu est inférieur au total
  optimal, dont une marge passe sous son seuil, ou dont la toiture porte encore
  un obstacle NON MESURÉ actif (`VarianteCalepinage.raisons_de_non_publiabilite`).

**État au 2026-08-01 :** la forme DISPONIBLE de ce contrôle est
`GET /api/django/ao/appels-offres/{id}/points-a-lever/` (AOF24) — cotes « à
confirmer » + obstacles actifs non engageables, DÉRIVÉS de la donnée. C'est
aussi la seule forme que l'agent conversationnel peut déclencher (AOF167) : on
ne déclare jamais un contrôle plus large que ce qui est câblé.

---

## 4. Matrice de visibilité des pièces

| Pièce / surface | Client (maître d'ouvrage) | Interne | Directeur |
|---|---|---|---|
| Planches de calepinage, note de calcul, bordereau, acte d'engagement | oui | oui | oui |
| Simulation de rentabilité 25 ans (pièce CLIENT, **sans aucun coût**) | oui | oui | oui |
| Points à lever, provenance des obstacles, marges de robustesse | non | oui | oui |
| Tableau de bord des marchés (`/ao/tableau-marches/`, AOF166) | non | oui (`ao_voir`) | oui |
| `EconomieAO`, `LigneCoutRevient`, Excel de rentabilité, `prix_achat`, marge, bénéfice | **jamais** | **jamais** | oui (`ao_rentabilite_voir`) |

**La règle qui tient tout le reste :** `prix_achat`, coût de revient, marge et
bénéfice ne sortent JAMAIS dans un rendu remis au maître d'ouvrage. La
permission `ao_rentabilite_voir` vit dans `ELEVATED_PERMISSIONS` — non
octroyable par un non-administrateur, mappée sur aucun rôle
Responsable/Commercial/Technicien/Viewer.

**Piège nommé :** la « simulation de rentabilité 25 ans » remise au client et
l'économie directeur ne sont PAS la même chose. Les fusionner « parce que ça
parle de rentabilité » est le chemin le plus court vers la fuite de marge.

---

## 5. Composition du gabarit de pack

Le pack est un ASSEMBLAGE ordonné, pas un dossier de fichiers : son gabarit
déclare quelles pièces entrent, dans quel ordre, et dans quel profil de
visibilité. Les neuf familles de pièces :

1. page de garde + sommaire (paginés, dérivés — jamais tapés) ;
2. acte d'engagement ;
3. bordereau des prix unitaires / DQE, avec sa clause de réserve ;
4. montants en lettres (recalculés à chaque rendu) ;
5. mémoire technique ;
6. note de calcul (productible : source UNIQUE, partagée avec la simulation) ;
7. planches de calepinage A3 (profil « dépôt » ou « interne », `rendu/`) ;
8. simulation de rentabilité 25 ans — **pièce CLIENT, sans aucun coût** ;
9. pièces administratives (attestations, RC, déclaration sur l'honneur…).

Trois règles d'assemblage :

- **Aucun gabarit ne contient de chiffre littéral** — tout vient du contexte
  de dossier unique (§2).
- **La fusion PDF passe par `apps.ged.services.fusionner_pdf`**, et le rendu
  HTML→PDF par `core.pdf.render_pdf` (ARC11). Jamais un import direct de
  WeasyPrint, jamais un assembleur maison.
- **La règle #4 tient sans exception** : `/proposal` reste le seul chemin PDF
  du devis CLIENT ; la fabrique AO est un domaine NEUF, sans aucun couplage à
  `apps/ventes/quote_engine` — pas même en lecture de ses jetons visuels.

---

## 6. Règles de sanitisation

La sanitisation est **bloquante avant tout rendu client** : aucune pièce ne se
génère si elle échoue. Elle vérifie qu'aucune clé de coût, de marge, de
bénéfice ou de `prix_achat` n'a atteint le contexte de rendu — le contrôle est
fait sur les CLÉS, pas sur les libellés, parce qu'un libellé se renomme et une
clé se teste (cf. `apps/ao/kpis.CLES_INTERDITES`, même principe appliqué au
tableau de bord).

---

## 7. Non-objectif v1 acté : **pas de signature électronique**

Le dépôt marocain visé est **papier, en deux exemplaires, avec paraphe
manuscrit**. `PieceDossierAO.signee` est donc un booléen de POINTAGE HUMAIN,
pas un état cryptographique. Ce n'est pas un oubli : c'est la forme réelle du
dépôt. Le jour où la signature devient un besoin, elle se branchera sur
`ged.ChampSignature` (déjà en production) et sur AUCUN mécanisme local.

---

## 8. Rétention et DSR des artefacts (AOF168)

- **Trois politiques, toutes OFF par défaut** (`AO_PHOTOS_RELEVE_PURGE_DAYS`,
  `AO_IMAGES_QUESTIONS_PURGE_DAYS`, `AO_PLANS_SOURCE_PURGE_DAYS`, défaut `0`).
  Une purge qui s'activerait toute seule à une mise à jour serait la pire
  régression possible de ce module.
- **Seuls les AO `perdu` / `abandonne`** sont éligibles. Un marché `gagne` est
  en exécution : purger ses pièces, ce serait détruire les pièces d'un chantier
  en cours.
- **Aucune ligne métier ne part** : le relevé garde sa date et son caractère
  contradictoire, la question garde son impact et sa décision, le plan source
  garde son calibrage et son empreinte. Seuls les FICHIERS partent.
- **DSR = anonymisation, jamais suppression.** Les identités
  (`ReleveAO.participants`, `SerieQuestions.destinataire`) sont vidées ; les
  FAITS opposables restent. Le lead CRM appartient au fournisseur DSR `crm` et
  n'est pas dupliqué ici — deux effacements concurrents pour la même personne
  seraient un bug.

---

## 9. Amont du tunnel : les avis de marchés (AOF169)

`services.creer_appel_offre_depuis_avis(company, avis)` est le **point de
contact UNIQUE** de l'amont : l'import de fichier (`imports.importer_avis`), la
saisie manuelle (`imports.saisir_avis`) et — le jour où il existera — le sas de
veille (`apps/veille_ao`, Groupe VAO) passent tous par lui. Déduplication par
`reference_acheteur`, dans la société.

**Aucun appel réseau vers un portail public n'existe dans `apps/ao`**, et un
test de grep l'impose sur tout le paquet (règle #5 du dépôt). La collecte
AUTOMATIQUE vit dans une app séparée, sous gate intégral : fichier `tos_risk/`
décrivant cible, risque et mitigation, **plus** l'accord explicite du fondateur
avant la première exécution.

---

## 10. `docs/CODEMAP.md` — qui l'écrit, et pourquoi pas les lanes

AOF194 demande la mise à jour de `docs/CODEMAP.md` §3/§4 + §10 et le re-stamp
`codemap_fingerprint.py --write`. **Aucune lane de ce groupe n'écrit dans
`CODEMAP.md` :** l'empreinte de structure est un hash global, donc deux lanes
qui la re-stampent chacune de leur côté produisent un conflit à CHAQUE fold —
c'est mécanique, pas de la malchance. La régénération et le re-stamp
appartiennent donc à l'orchestrateur, **dans le commit de fold**, une fois
toutes les lanes intégrées. La commande, depuis la racine :

```
PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --write
PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --check
```

Nouveaux modules à refléter en §4 pour la lane intégrations + gouvernance :
`apps/ao/kpis.py`, `apps/ao/agent_actions.py`, `apps/ao/dsr.py`,
`apps/ao/retention.py`, `apps/ao/management/commands/seed_ao_demo.py`, et la
route `GET /api/django/ao/tableau-marches/`.
