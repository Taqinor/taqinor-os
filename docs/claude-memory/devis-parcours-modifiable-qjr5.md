---
name: devis-parcours-modifiable-qjr5
description: Décisions fondateur du 30/09/2026 sur la correction des devis (envoyé corrigé sur place, accepté → Réviser V2, fusion au recalcul…) — groupe QJR5 de docs/PLAN2.md
metadata:
  type: project
---

Audit L3 du 30/09/2026 du parcours devis → groupe **QJR5** (QJR500-QJR670) dans `docs/PLAN2.md`. Décisions de Reda, à ne jamais re-demander (texte complet dans l'en-tête du groupe) :

- **Envoyé** avec erreur → corrigé SUR PLACE (même référence, même lien public, historique + chatter « corrigé après envoi », statut reste envoyé). Le 3D et « appliquer une taille » aussi.
- **Accepté** → verrouillé ; « Réviser » en V2 pour tout rôle qui écrit (IsResponsableOrAdmin, jamais IsAnyRole), aussi depuis la fiche lead ; aval V1 (BC/factures) rattaché à la V2 + complément/avoir.
- Copier le lien = envoi (inchangé).
- Recomposer FUSIONNE (prix tapés et lignes manuelles gardés).
- « Notes » = texte client imprimé ; historique des versions visible + « Revenir à cette version » ; échéancier éditable.
- Registre des surcharges réservé aux admins, aucune saisie ignorée ; résidentiel sans repli JS (erreur + Réessayer).
- Taille explicite jamais arrondie au palier 5 kWc ; GPS corrigé prime sur l'épingle du site ; PDF industriel premium = 4 pages ; pro « kWh seulement » dimensionné depuis les kWh.

**Why:** Reda ne pouvait pas corriger un devis déjà envoyé (« let me correct errors ») et voulait un parcours modifiable à chaque étape, une seule fonction par geste.

**How to apply:** toute tâche touchant l'édition, l'envoi ou la révision d'un devis suit ces règles ; 11 questions restent GATED dans le groupe (QJR659-QJR669).

## Décisions D-ADEV (audit devis, groupe ADEV de docs/plans/PLAN_AUDIT_DEVIS.md) — 09/10/2026

Option (a) recommandée retenue à chaque fois, choisi par Reda via la question interactive du 09/10/2026 (ne jamais re-demander) :

- **D-ADEV-1 = (a)** : la V1 reste la vente « signée en vigueur » (comptée une fois) jusqu'à la signature de la V2 ; supprimer / archiver / refuser / laisser expirer la V2 RÉACTIVE la V1 dans la même transaction (chatter « révision abandonnée »). Recopiée dans ADEV16 et ADEV46.
- **D-ADEV-2 = (a)** : accepter un brouillon exécute d'abord les mêmes gels que l'envoi (approbation de remise exigée, CGV gelées, marge figée, `date_envoi` = date d'acceptation) et refuse (400 nommé) si la remise n'est pas approuvée. Recopiée dans ADEV12.
- **D-ADEV-4 = (a)** : la tuile « kWc conçus / signés » (et la pastille de la fiche lead) compte le kWc du PROJET (×N villas). Recopiée dans ADEV40.
