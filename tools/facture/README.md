# Facture premium TAQINOR (modèle réutilisable)

Générateur autonome de factures une-page au design du devis premium (navy/or,
DM Sans/DM Serif, pied de page légal identique). Il réutilise **en lecture
seule** le design system de `apps/ventes/quote_engine/` — c'est un chemin de
code séparé du devis (règle #4 de CLAUDE.md) ; le moteur de devis n'est jamais
modifié. La facture legacy de l'ERP n'est pas touchée non plus.

## Générer une facture

1. Dupliquer un JSON client (ex. `facture_lahlou_858.json`) et adapter :
   numéro, dates, client, lignes (**prix saisis en TTC**, `tva_pct` 10 pour les
   panneaux PV / 20 pour le reste), `acompte_regle` (0 si aucun acompte).
2. Rendre DANS l'image docker prod (Python 3.11 + WeasyPrint — jamais en
   Python local) :

   ```powershell
   docker run --rm -v "<racine du repo>:/repo" erp-agentique-django_core:latest `
     python /repo/tools/facture/generate_facture.py `
     /repo/tools/facture/<client>.json /repo/tools/facture/out/<nom>.pdf
   ```

Le HT, la TVA ventilée par taux, le TTC, la déduction d'acompte, le reste à
payer et les montants en toutes lettres sont tous recalculés automatiquement.

## Numérotation

Format ERP : `FAC-AAAAMM-NNNN` (série continue exigée par l'art. 145 CGI — un
trou dans la série est un risque fiscal). Avant d'envoyer une facture,
confirmer le prochain numéro réel dans l'ERP (la série vit dans la base de
production).

## Mentions légales — à compléter

Le pied de page porte : raison sociale, RC, ICE, capital, siège (identiques au
devis). L'art. 145 CGI exige AUSSI l'**IF** (identifiant fiscal) et le n° de
**Taxe Professionnelle** ; le champ `entreprise` du JSON les ajoute au pied de
page dès qu'ils sont renseignés (`if_fiscal`, `taxe_professionnelle`,
`cnss`). À renseigner dès que le fondateur fournit les numéros.

## Intégration ERP future

Quand le « facture part » du nouveau moteur sera construit (session future),
ce générateur est le modèle : même HTML, alimenté par le modèle `Facture` +
`parametres.selectors.company_identity` (multi-tenant), numéro via
`apps/ventes/utils/references.py`.
