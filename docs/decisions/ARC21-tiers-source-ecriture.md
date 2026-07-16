# ARC21 — DÉCISION : `Tiers` comme source d'écriture de l'identité

**Statut : PROPOSÉ — mécanisme livré mais DÉSACTIVÉ (flag `TIERS_SOURCE_ECRITURE=0`
par défaut). Bascule ON réservée au fondateur, après lecture de ce dossier.**

Type : DECISION (founder-gated). Standing consent couvre la LIVRAISON du
mécanisme OFF ; il ne couvre PAS son activation.

---

## 1. Contexte

ARC17 a créé le répertoire unifié `tiers.Tiers` (le `res.partner` de TAQINOR).
ARC18/19/56 ont posé des PONTS additifs : chaque modèle historique porteur
d'une identité (`crm.Client`, `stock.Fournisseur`, `compta.Partenaire`,
`rh.DossierEmploye`, `crm.Lead`) reçoit un FK nullable `tiers` et un MIROIR
one-way (à la sauvegarde, l'identité est recopiée VERS `Tiers` ; dédup
email/ICE company-scopée).

Aujourd'hui l'identité (nom / raison sociale / ICE / IF / RC / email /
téléphone / adresse) reste **saisie et maître dans chaque modèle historique** ;
`Tiers` n'en est qu'un reflet. ARC21 pose la question de la **bascule
write-path** : faire de `Tiers` la SOURCE d'écriture unique (saisie une seule
fois, style DC15), les champs identité des modèles historiques devenant des
MIROIRS lecture depuis `Tiers`.

## 2. Ce qui est décidé ici

- **On NE bascule PAS maintenant.** On livre le MÉCANISME de bascule,
  flag-gaté, **OFF par défaut**, réversible, avec double-écriture pendant la
  transition et rollback documenté.
- Avec le flag OFF, le comportement est **byte-identique à aujourd'hui** (prouvé
  par des tests des deux modes).
- La bascule ON reste une décision explicite du fondateur, à prendre au vu des
  volumes et risques ci-dessous.

## 3. Volumes & surface impactée (chiffré, mesuré depuis le code)

> Comptages `grep`/`Grep` sur le dépôt au moment d'ARC21 — ordre de grandeur,
> pas un audit ligne-à-ligne.

| Surface | Mesure | Note |
|---|---|---|
| Modèles historiques portant l'identité | 5 | Client, Fournisseur, Partenaire, DossierEmploye, Lead |
| Usages code des champs identité `Client` (ventes+crm) | ~56 fichiers | lecture `.nom/.ice/.email/…` |
| Usages `Fournisseur.nom/.ice/.identifiant_fiscal` | ~27 fichiers | AP, comptes auxiliaires, portail |
| Références identité client dans le moteur de devis | 8 lignes | `apps/ventes/quote_engine/*` |
| Templates PDF / moteur référençant `client` | ~26 fichiers | **risque PDF — voir §5** |
| Sérialiseurs identité (crm/stock/compta) | 3 modules | API |
| Écrans frontend touchant `ice/raison_sociale/identifiant_fiscal` | ~301 fichiers | large surface de saisie |

**Lecture** : la bascule touche une surface LARGE (identité lue partout :
devis, factures, PDF, portails, exports, ~300 fichiers front). C'est
précisément pourquoi elle est livrée OFF et gardée par un flag.

## 4. Mécanisme livré (OFF par défaut)

- **Flag** : `settings.TIERS_SOURCE_ECRITURE` (défaut `False`, lu de l'env
  `TIERS_SOURCE_ECRITURE`). OFF → aucun changement de comportement.
- **Double-écriture (mode transition, flag ON)** : une écriture d'identité
  passe par `apps.tiers.services` qui met à jour `Tiers` (source) PUIS recopie
  vers le modèle historique (miroir lecture) — les deux restent cohérents, donc
  un rollback est toujours sûr.
- **Sens du miroir selon le flag** :
  - OFF (aujourd'hui) : historique = maître → `Tiers` (miroir), ponts ARC18/19/56.
  - ON (futur) : `Tiers` = maître → historique (miroir lecture), saisie unique.
- **Réversibilité** : les DEUX copies restent peuplées en permanence ; repasser
  le flag à OFF restaure l'état antérieur sans migration de données.

## 5. Risques (dont PDF/exports)

1. **PDF client-facing (règle #4)** — le moteur `quote_engine` et les gabarits
   facture lisent l'identité client. Un décalage `Tiers`↔historique produirait
   un PDF avec une mauvaise raison sociale/ICE. **Mitigation** : la
   double-écriture garantit l'égalité ; jamais de bascule qui ne peuple pas les
   deux ; `prix_achat`/marge jamais concernés (hors identité).
2. **Exports & API** — 3 sérialiseurs + exports lisent l'identité historique.
   OFF = inchangés ; ON = ils continuent de lire le miroir historique (peuplé),
   donc pas de rupture de contrat.
3. **Dédup / collisions** — un même acteur client+fournisseur peut avoir
   aujourd'hui DEUX identités divergentes ; la bascule doit choisir une source.
   **Mitigation** : ARC20 fournit déjà le rapport de doublons inter-référentiels
   (lecture seule) pour les résoudre AVANT toute bascule.
4. **Multi-tenant** — la source d'écriture reste strictement company-scopée
   (aucune fusion inter-société). La dédup `Tiers` l'est déjà.
5. **RIB de paie (RH)** — la fusion RIB est explicitement HORS périmètre (ARC25) ;
   le pont DossierEmploye ne miroite jamais le RIB.

## 6. Recommandation

Livrer le mécanisme OFF (fait). NE PAS activer tant que :
(a) le rapport ARC20 des doublons inter-référentiels est vidé pour les sociétés
pilotes, et (b) une passe de non-régression PDF/exports est faite avec le flag
ON en préproduction. Activation = décision fondateur explicite.

## 7. Traçabilité

- Mécanisme : `apps/tiers/services.py` (`identite_source_est_tiers()`,
  `ecrire_identite`), `apps/crm/services.py`, `apps/stock/services.py`.
- Tests des deux modes : `apps/tiers/tests/test_arc21_source_ecriture.py`.
- Flag : `TIERS_SOURCE_ECRITURE` (défaut OFF).
