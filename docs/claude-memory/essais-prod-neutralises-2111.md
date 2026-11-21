---
name: essais-prod-neutralises-2111
description: 21/11/2026 — données d'essai neutralisées en production à la demande de Reda (fausses signatures, 4 factures d'essai, 53 leads d'essai en corbeille) ; ce qui reste ; piège de notification
metadata:
  type: project
---

# Données d'essai neutralisées en production (21/11/2026)

**Demande de Reda (21/11/2026)** : les signatures que l'ERP rattachait au site étaient des essais ; « erase this testing
data », puis « those test leads should be suppressed ». Chaque geste a été approuvé par lui (outil de question) et fait
avec les fonctions de l'ERP, après un essai à blanc.

## Ce qui a été fait (prod, 21/11 vers 17 h UTC, commit déployé 919b49b7d)
- **13 fausses acceptations défaites** par `ventes.services.annuler_acceptation` (devis d'essai de juin à août, leads
  24, 377, 370, 281, 40, 39, 38, 35, 1) : les devis sont revenus à « envoyé » (validité reportée au 21/12/2026) et leurs
  **11 chantiers d'essai annulés** par l'abonné (motif « dés-acceptation »).
- **2 factures d'essai annulées** par `annuler_facture` : FAC-202606-0002 et FAC-202606-0003 (31 068 MAD de fausses
  créances « en retard »). L'ERP a émis deux avoirs de contre-passation, **AVO-202611-0001 et AVO-202611-0002** : ces
  deux numéros légaux sont des essais, ils ne correspondent à aucune vente.
- **2 autres factures d'essai annulées le soir même**, sur le « Yes, cancel both » de Reda : FAC-202607-0001 (client
  « Reda kasri », sans devis, 17 000 MAD) et FAC-202606-0001 (client de démonstration « Tazi Omar », 33 139,44 MAD).
  Avoirs émis : **AVO-202611-0003 et AVO-202611-0004**, des essais eux aussi. Aucune notification, aucun mouvement de
  stock. Les 5 factures « en retard » qui restent sont celles de vrais clients d'octobre.
- **53 leads d'essai en corbeille** (`soft_delete`, restaurables) : noms « test… », noms tapés au hasard, fiches au
  téléphone de Reda. Pour ceux qui portaient des devis, la garde « archivez-le plutôt » de l'ERP a été contournée
  depuis le serveur, sur sa demande explicite.
- Vraies signatures dans l'ERP à cette date : **4, toutes en octobre 2026** (3 venues du formulaire Meta, 1 cliente de
  l'époque Odoo). Le site n'a amené aucune vraie signature.

## Ce qui reste, volontairement
- **DEV-202606-0068** (lead d'essai 35, en corbeille) reste « accepté » : son chantier d'essai **CHT-202606-0004** est à
  « Mise en service » avec 11 lignes de stock réellement sorties en juin (11 mouvements sous sa référence). La
  dés-acceptation est refusée par l'ERP tant que ce stock est sorti. Toute analyse des signatures doit l'exclure.
- **Les trois fiches de démonstration** (leads 1, 2, 3) restent, archivées : décision du 30/09
  ([[demo-accounts-prod-incident]]). Le chantier de démonstration CHT-202606-0001 reste « à planifier », non annulé.
- **Jamais touchés** : marouane essaid (356), marouane (353), Said Essaidi (1075) — vraies personnes dont le nom
  contient « essai ».
- Anciennes valeurs, sorties d'exécution et scripts : OneDrive de Reda,
  `TAQINOR\Marketing\Ad material\strategie-2026-11\travail\prod-essais\`.

## Pièges appris (à appliquer à toute opération de ce genre)
- **`Lead.delete()` est une suppression définitive en cascade** ; la corbeille, c'est `lead.soft_delete(user)`.
- **Mettre en corbeille un lead qui a des touches ouvertes envoie à tort « Nouveau lead assigné » à son responsable**
  (`ERR-NOTIF-LEAD-ASSIGNE-CORBEILLE` dans `docs/ERROR_PLAN.md`). Parade tant que ce n'est pas corrigé : appeler
  `arreter_cadence(lead, user=None, motif=…)` puis `annuler_rendez_vous_sur_arret(lead, None, cause=…)` AVANT
  `soft_delete`, et compter les notifications créées après.
- Annuler une facture numérotée émet un avoir au numéro définitif ; refuser un devis n'a pas de retour ; ré-accepter un
  devis envoie un e-mail de confirmation au client.
- Un « essai à blanc » dans une transaction annulée n'annule pas un e-mail ou une notification déjà partis : lire
  d'abord le code des abonnés, puis essayer sur UN enregistrement.
