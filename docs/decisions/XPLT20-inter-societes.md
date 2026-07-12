# XPLT20 — DÉCISION : activation des miroirs inter-sociétés (vente A → achat B)

**Statut : PROPOSÉ — mécanisme livré mais INERTE (aucune `RegleInterSociete`
créée par défaut ; `actif=False` tant qu'elle n'est pas explicitement posée).
Activation d'une paire réelle réservée au fondateur, après lecture de ce
dossier.**

Type : DECISION (founder-gated). Standing consent couvre la LIVRAISON du
mécanisme OFF ; il ne couvre PAS la création d'une règle réelle avec un
compte de liaison.

---

## 1. Contexte

FG153 livre déjà l'élimination inter-sociétés + les états consolidés
(`EntiteConsolidation`), mais une vente réelle de la SARL à l'EI (ou
inversement) se saisit aujourd'hui DEUX FOIS à la main : une facture côté
vendeur, une facture fournisseur côté acheteur, avec un risque d'écart de
montant/oubli.

## 2. Ce qui est décidé ici

- **On NE crée AUCUNE règle maintenant.** On livre le MÉCANISME opt-in par
  paire de sociétés (`RegleInterSociete` : société A, société B, `actif`,
  `compte_liaison`), désactivé par défaut.
- Avec aucune règle (ou `actif=False`), le comportement est **byte-identique
  à aujourd'hui** — aucune facture ne génère quoi que ce soit.
- Créer une règle `actif=True` pour la paire réelle EI↔SARL (ou toute autre
  paire de sociétés du groupe) — et choisir le **compte de liaison CGNC**
  (ex. 4468 « autres comptes créditeurs/débiteurs — comptes de liaison ») —
  reste une décision explicite du fondateur.

## 3. Mécanisme livré (inerte tant qu'aucune règle n'est créée)

- **Modèles** (`apps/compta/models.py`) : `RegleInterSociete` (société A,
  société B, `actif` bool défaut `False`, `compte_liaison` CharField vide par
  défaut) + `EcritureLiaisonInterSociete` (trace lettrable + garde
  d'idempotence, une ligne par facture source déjà miroirée).
- **Déclencheur** : événement `facture_emise` existant (`core.events`),
  déjà émis par `ventes` à l'émission d'une facture — AUCUN nouvel événement
  ajouté. Un récepteur dédié (`apps/compta/receivers.py`,
  `_miroir_intersociete_pour_facture_emise`), indépendant du toggle
  `COMPTA_AUTO_ECRITURES` (qui ne gouverne que les ÉCRITURES GL, pas ce
  miroir documentaire).
- **Rapprochement** : le client de la facture de A doit matcher (ICE OU
  identifiant fiscal) le `parametres.CompanyProfile` de B ; A doit
  elle-même avoir un ICE/IF renseigné sur son propre `CompanyProfile` ; B
  doit déjà porter une fiche `stock.Fournisseur` pour A (matchée par le même
  ICE/IF, via le sélecteur existant `stock.selectors.fournisseurs_pour_
  controle_ice` — **jamais de création silencieuse d'un tiers hors du
  groupe**).
- **Génération** : réutilise la fabrique EXISTANTE
  `stock.services.creer_facture_fournisseur_depuis_ocr` (déjà conçue pour
  produire un BROUILLON, cf. XACC36) — aucune nouvelle route d'écriture
  fournisseur, aucun import direct de `apps.stock.models`/`apps.ventes.models`
  depuis `compta` (lecture des montants via les propriétés publiques
  `Facture.total_ht/total_tva/total_ttc`).
- **Jamais d'auto-validation** : le miroir reste une `FactureFournisseur` au
  statut `a_payer` (pas de `PaiementFournisseur` créé) — à valider par B.
- **Idempotence** : contrainte unique `(regle, facture_source_id)` sur
  `EcritureLiaisonInterSociete` — une même facture ne génère jamais deux
  miroirs, même si le signal est ré-émis.
- **Réversibilité** : repasser `actif` à `False` arrête toute génération
  future sans toucher aux miroirs déjà créés (aucune migration de données).

## 4. Ce qu'il reste à trancher avant d'activer une paire réelle

1. **Le compte de liaison CGNC** exact (`RegleInterSociete.compte_liaison`)
   pour la paire EI↔SARL — champ texte libre, laissé vide tant que non
   confirmé.
2. **Confirmation du flux** : la vente de la SARL à l'EI (ou l'inverse)
   doit-elle réellement transiter par ce miroir automatique, ou rester une
   saisie manuelle pilotée (le mécanisme n'est qu'une PROPOSITION de
   brouillon, jamais un document validé) ?
3. **Renseigner les `CompanyProfile.ice`/`identifiant_fiscal`** des deux
   sociétés réelles (prérequis technique du rapprochement) s'ils ne le sont
   pas déjà, et créer la fiche `Fournisseur` réciproque de chaque côté.

## 5. Traçabilité

- Mécanisme : `apps/compta/models.py` (`RegleInterSociete`,
  `EcritureLiaisonInterSociete`), `apps/compta/services.py`
  (`generer_facture_fournisseur_miroir_intersociete`),
  `apps/compta/receivers.py`.
- Migration : `apps/compta/migrations/0110_xplt20_regle_intersociete.py`
  (nouvelles tables, additive, aucune donnée existante affectée).
- Tests : `apps/compta/tests/test_xplt20_miroir_intersociete.py`.
