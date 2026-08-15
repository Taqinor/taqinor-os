# `contract_samples/` — PACT10 : le contrat part EN PREMIER, et il est PARTAGÉ

Même règle et même format que `apps/ao/contract_samples/README.md` (lire ce
fichier-là pour le « pourquoi » complet : incident du 03/08/2026).

Le backend AFFIRME l'exemple committé ici ; le test frontend l'IMPORTE via
`frontend/src/test/fixtures/contractSamples.js` au lieu d'écrire un mock à la
main (un mock manuel est une DEUXIÈME source de vérité — c'est elle qui a fait
planter l'écran AO).

## Ce que ce dossier couvre (WIR263)

`relance_loyer` — l'historique des relances d'impayé d'une échéance de loyer
(NTPRO8). L'escalade niveau 1 → 2 → 3 a une portée JURIDIQUE : l'écran doit
montrer le niveau déjà atteint AVANT un nouveau clic, sinon on envoie une mise
en demeure sans le savoir.
