# Socle e-signature — décision (WIR138)

Décision d'architecture. Elle est la référence unique : le code qui la répète
(`backend/django_core/core/esign.py`, `apps/ventes/services.py`,
`apps/ged/services.py`) pointe ici.

## Le problème

Trois chemins « e-signature » coexistaient sans propriétaire désigné :

| Chemin | Ce qu'il fait | État avant WIR138 |
| --- | --- | --- |
| `core/esign.py` + `core.EsignRequest` | Demande de signature adossée à un prestataire externe (Yousign/DocuSign), cible attachée par contenttypes | Fondation intentionnelle, **0 appelant, 0 endpoint** |
| `apps/ventes` — `DevisSignature` | Preuve d'acceptation en ligne d'un devis (loi 53-05) | En production |
| `apps/ged` — `DemandeSignatureDocument` + `esign_provider` | Circuit de signature interne d'un document GED | En production, connecteur externe en stub gardé par `ESIGN_ENABLED` |

## La décision

1. **`core.esign` est le socle canonique** des demandes de signature adossées à
   un prestataire externe. Toute app qui devra un jour envoyer un document en
   signature chez un prestataire passe par `creer_demande()` / `envoyer()` —
   jamais par un connecteur local réinventé.

2. **Il est explicitement PARQUÉ (dormant).** L'envoi réel exige un compte
   Yousign/DocuSign et une clé d'API que seul le fondateur peut provisionner
   (`IntegrationConfig.secret_ref`). Le brancher aujourd'hui ne produirait que
   des `EsignRequest` en brouillon perpétuel : aucune valeur, une surface d'API
   de plus à maintenir. Aucun endpoint n'est exposé, et c'est volontaire.

3. **Les deux autres chemins ne sont pas des socles concurrents.**
   - `ventes.DevisSignature` est une **preuve** d'acceptation en ligne
     (consentement, IP, user-agent, hash du devis) — pas une demande envoyée à
     un tiers. Elle ne migrera jamais vers `core.esign`.
   - `ged.DemandeSignatureDocument` est un **circuit interne** (rôles
     signataires, ordre). C'est le seul des trois qui devra déléguer son envoi
     externe à `core.esign` le jour de l'activation.

## Ce qui est verrouillé par les tests

`backend/django_core/core/tests/test_wir138_esign_socle.py` :

- le socle parqué ne fait aucun appel réseau et n'écrit rien de plus qu'un
  brouillon quand aucun prestataire n'est configuré ;
- aucun endpoint n'expose `EsignRequest` (le parking est un invariant, pas un
  oubli) ;
- l'acceptation d'un devis ne crée pas d'`EsignRequest` (les chemins restent
  séparés tant que le socle est parqué).

## Activation (étape fondateur)

1. Créer un `IntegrationConfig` e-sign actif pour la société (provider +
   `secret_ref` pointant sur la clé d'API en variable d'environnement).
2. Router `ged.services.demander_signature` vers
   `core.esign.creer_demande()` / `envoyer()`.
3. Exposer l'endpoint de suivi de statut et retirer les assertions de parking
   du test ci-dessus.

Tant que ce n'est pas fait : **ne pas ajouter de quatrième chemin.**
