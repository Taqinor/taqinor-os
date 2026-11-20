<!-- verifie | groupe: AERR | pct: 99 | ecarts_s1_s2: 1 | faits: 167 -->
# Vérifie AERR — contre-visite des correctifs du parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran », 20/11/2026 (2e passe)

Commande `loop audit` (20/11, seconde passe du jour). La passe du matin (même fichier, version de `5a77c93d9^` ; rappel §6)
avait ouvert 2 écarts S2 et 6 tâches (AERR181 à 186) ; une autre session les a construites et cochées le jour même (PR
#1503, acceptation en direct 6/6 PASS). `audit_registre.py --du` redemande la contre-visite (167 tâches cochées sur 168,
« écarts S1-S2 du 2026-11-20 tous cochés »). Rien n'a été construit ni déployé ; aucune base, aucun conteneur, aucune
production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `5a77c93d9` (PR #1503). Branche de claim : `verifie-aerr-2011b`.
- **Registre.** PF12 `erreurs-ecran`, groupe AERR, 167 tâches cochées sur 168. Reste ouverte la tâche d'acceptation AERR131.
- **Échantillon : les 6 tâches d'écart du matin** (METHODE §C.4-6), S2 d'abord : AERR181, 182, 183, 184 ; S3 AERR185, 186.
- **Méthode.** Un vérificateur frais (opus / high, même répertoire) : commits, code servi, corps des tests nommés,
  spec et enregistrement d'acceptation (`frontend/e2e/acceptation/aerr15.spec.js`,
  `docs/audits/acceptation/AERR/2026-11-20-2be475ef6.md`, run 44665980498 ; son SHA d'essai n'est pas sur `main`, mais
  `git diff 2be475ef6 origin/main -- frontend/src` est vide). Recherche exhaustive des jumeaux : une sonde neuve balaie
  TOUS les composants qui enregistrent une garde de saisie. `frontend/node_modules` absent : aucun vitest lancé.

## 1. Verdicts

| Tâche | Verdict | Commit | Test nommé (casse si on revient en arrière) | L'acceptation affirme la clause |
|---|---|---|---|---|
| AERR181 | ok | `60101da92` | `InstallationDetail.appro.test.jsx`, 3 cas : après « Rester », `onClose` non appelé, « Horaires d'accès » gardé (oui) | oui : valeur gardée, aucune écriture, base inchangée |
| AERR182 | ok | `bade51046` | `EquipementsPage.test.jsx`, 2 cas (oui) | oui |
| AERR183 | ok | `4565ae64b` | `BonsCommandeFournisseur.test.jsx`, 2 cas (oui) | oui |
| AERR184 | ok | `13047c82d` | `TicketDetailSplitView.test.jsx` à `mockMatchMedia(false)` : note puis Échap ⇒ demande (oui ; la croix et le fond, même booléen, non testés) | oui : à 1 000 px, pas de vue scindée, « Rester » garde la note, « Quitter » n'écrit rien (réseau et base) |
| AERR185 | ok | `30357c078` | 4 cas : « Annuler » sans appel, « Confirmer » un appel, la confirmation nomme la cible (oui) — elle nomme le document : un `PartageGed` est un lien public sans destinataire | oui : base relue après chaque geste |
| AERR186 | ok | `9cf3a3e6c` | revenir en arrière remet à zéro à la fermeture et vide la note (oui) | oui : saisie gardée sur A, vide sur B, vide après journalisation, un seul appel en base |

**AERR186 ne rouvre pas le succès faux du 14/11 (VER2-200)** : après une relance ratée, `appelJournalise` est vrai, la
fermeture remet à zéro, l'appel suivant est journalisé ; la sonde VER2-200 rejoue `repro: false`.

**Les deux écarts S2 du matin, sur `origin/main` :**
- C-AERR-VER3-300 : **fermé pour ses trois sites** (sa sonde rend une liste vide). Le même défaut subsiste derrière des
  boutons « Annuler » que cette sonde ne cherchait pas (C-AERR-VER4-401).
- C-AERR-VER3-301 : **fermé.** `brouillonEnCours` nourrit `useDirtyGuard` et le `<Sheet>` ; le « Fermer » du pied lit
  `isAnyFormDirty()`, qui l'inclut.

## 2. Sondes

| Sonde | Verdict | Observé (hôte, `5a77c93d9`) |
|---|---|---|
| `C-AERR-VER3-300.py` (matin) | réfutée | `repro: false`, liste vide |
| `C-AERR-VER3-301.py` (matin) | réfutée, périmée | `repro: false` ; l'argument de la garde est désormais une variable nommée : la sonde ne prouve plus rien |
| `C-AERR-VER2-200.py` (14/11) | réfutée | `repro: false` |
| `C-AERR-VER4-400.py` (neuve) | **REPRO** | 11 composants à garde de saisie ; sorties nues : « Annuler » de `ProduitForm`, `NouvelleReception`, `FactureForm` ; aucun `onOpenChange` sans garde ; un booléen différent (`ToitureDesign.jsx::AtelierToiture`, `confirmLeaveIfDirty(modifiee)`, calcul frais au clic, ACAL85 : juste) ; témoin : les six sites corrigés sont rangés « gardés » |

## 3. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-AERR-VER4-401 | AERR181 à 183 (jumeaux) | **S2** | « Annuler » ferme sans demande un formulaire modifié dont Échap et le fond demandent : `frontend/src/pages/stock/ProduitForm.jsx::ProduitForm`, `frontend/src/pages/stock/ReceptionsFournisseur.jsx::NouvelleReception`, `frontend/src/pages/ventes/FactureForm.jsx::FactureForm` ; le contrat de `frontend/src/ui/useDirtyGuard.js::confirmLeaveIfDirty` range « Annuler » parmi les sorties qui demandent | `C-AERR-VER4-400.py` (REPRO) | AERR187 (stock), AERR188 (facturation) |
| C-AERR-VER4-402 | AERR186 (appelant oublié) | S3 | La liste des leads démonte la fenêtre de planification de relance au premier `onOpenChange(false)` : un clic extérieur perd la date et l'objet ; la garde d'AERR186 ne peut pas s'y appliquer ; défaut antérieur à AERR156 (`frontend/src/pages/crm/leads/LeadsPage.jsx::LeadsPage`) | STATIQUE | AERR189 (lead) |

**Pourquoi ces gravités.**
- **VER4-401 (S2).** Même grille que VER2-202 à 204 et VER3-300 : perte de saisie réelle, sans avertissement, sur un geste
  ordinaire, contre le contrat écrit de la garde. Si le fondateur tient « Annuler » pour un abandon voulu, l'écart tombe
  en S3 (aucune décision ouverte : le contrat et le formulaire client vont déjà dans ce sens).
- **VER4-402 (S3).** Perte légère (une date, un objet), refaite en quelques secondes ; pas une régression.
- **Pas de S1.**

**Routage.** `check_ownership.py --owner-of` : stock AERR187 (deux formulaires) ; facturation AERR188 ; lead AERR189.

## 4. Optionnel (non déposé)

- Révocation d'un lien public d'un clic hors de la GED, même geste qu'AERR185 : `frontend/src/pages/reporting/DashboardSharePage.jsx`
  (`revoquer`) et `frontend/src/features/adsengine/ConsentScreen.jsx` (`revoke`) ; réversibilité non vérifiée.
- Sondes VER3-301 et VER2-200 fragiles ; VER4-400 remplace VER3-300.
- Test d'AERR184 : Échap seulement (la croix et le fond partagent le booléen).

## 5. Couverture et sortie de cycle

- **Couvert.** Les 6 tâches d'écart du matin : commits, code servi, tests nommés, spec et enregistrement d'acceptation ;
  balayage de tous les composants à garde de saisie (sonde VER4-400) ; sondes du matin et du 14/11 rejouées.
- **Non couvert.** Aucun vitest, aucun rejeu navigateur ; les crochets de brouillon (`useLeadDraft`, `useBrouillonEcran`)
  ne sont pas balayés par la sonde ; l'acceptation AERR131 reste ouverte.
- **Sortie de cycle.** Les deux S2 du matin sont fermés ; un S2 nouveau (VER4-401, AERR187-188). Le groupe reste
  « construit » ; compteur des `vérifie` consécutifs à zéro S1-S2 : **0**. Contre-visite d'AERR187 et AERR188 une fois cochées.

## 6. Rappel de la passe du matin

La passe du matin (SHA `a923179a4`, 14 tâches d'écart du 14/11) : 12 ok, AERR159 et AERR160 partielles ; quatre S2 du
14/11 fermés, un partiellement ; écarts retenus :

| Constat du matin | Grav. | Tâches | État ce soir |
|---|---|---|---|
| C-AERR-VER3-300 : « Fermer » sans demande sur trois fiches | S2 | AERR181, 182, 183 | **fermé** (jumeaux « Annuler » : VER4-401) |
| C-AERR-VER3-301 : panneau étroit de la fiche ticket | S2 | AERR184 | **fermé** |
| C-AERR-VER3-302 : révoquer un partage, retirer un droit GED d'un clic | S3 | AERR185 | fermé |
| C-AERR-VER3-303 : fenêtre d'appel vidée à une fermeture accidentelle | S3 | AERR186 | fermé (appelant oublié : VER4-402) |

## 7. Coût

H0 S0 O2 F0 · jetons sous-agents ≈ 0,45 M sur la journée (deux vérificateurs opus, un par passe). Aucun appel Fable : aucun S1.
