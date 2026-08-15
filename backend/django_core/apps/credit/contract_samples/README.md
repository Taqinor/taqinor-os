# `contract_samples/` — PACT10 : le contrat part EN PREMIER, et il est PARTAGÉ

Même règle et même format que `apps/ao/contract_samples/README.md` (lire ce
fichier-là pour le « pourquoi » complet : incident du 03/08/2026, l'écran AO
Tableau de bord, zéro clé sur six concordante).

En bref : dès qu'une fonctionnalité a une moitié front et une moitié back, le
contrat atterrit **seul et en premier** sur `main`. Ce dossier EST le porteur.

## Ce que ce dossier couvre (WIR187 / WIR188)

`credit_warning` — l'objet d'avertissement crédit posé sur la réponse d'une
action sensible (aujourd'hui : l'acceptation d'un devis). La moitié frontend
(WIR188, `CreditWarningBanner`) lit exactement ces trois clés ; elle ne doit
en inventer aucune, et son test importe cet exemple au lieu d'écrire un mock
à la main.

**Ce que `credit_warning` n'est PAS** : ce n'est pas le blocage. Le blocage dur
reste le moteur FG41/XFAC28 (`ventes.services.verifier_credit_hold`), qui
répond en 403 AVANT l'acceptation. `credit_warning` accompagne une acceptation
RÉUSSIE : il rend visible ce que la société a paramétré.
