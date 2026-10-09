# Fiche de relecture — texte français (YBW67)

> GÉNÉRÉE par `node scripts/review-sheet.mjs --captures` depuis les pages CONSTRUITES — ne pas éditer à la main.
> Chaque phrase publique, dans l’ordre de la page. Une phrase qui affirme un fait porte l’identifiant de son
> affirmation (`src/lib/claims.ts`), son statut et ses preuves ; les autres sont du texte d’interface
> (titres, navigation, appels). Question à Reda : YBWM13 — approuver ce texte avant toute traduction.

## État des gardes

- `check-claims` : OK
- `check-claims --stale` : vide

## Décisions ouvertes

- YBWM13 — approuver ce texte français avant toute traduction (YBW70).
- YBWM11 — coloration du slogan (A ou B) : le logo du pied de page reste en version actuelle.
- YBWM4 — numéro WhatsApp et e-mail de YanBow : tant qu’ils manquent, aucun bouton WhatsApp.
- YBWM5 / YBWM6 — sociétés à créer : tant que legal.ts est vide, aucune forme juridique n’est rendue (page Société, pages juridiques fermées).
- YBW41 — captures réelles du kit (société fictive locale) : en attendant, un cadre neutre « Capture d’écran en préparation » avec la légende « Données fictives ».

## YanBow — logiciels métier — `/`

[375 px](review/accueil-fr-375.jpg) · [1440 px](review/accueil-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Aller au contenu _(en-tête)_ | — | interface |  |
| 2 | YanBow _(en-tête)_ | — | interface |  |
| 3 | SolarBow _(en-tête)_ | — | interface |  |
| 4 | MarketingBow _(en-tête)_ | — | interface |  |
| 5 | Sur mesure _(en-tête)_ | — | interface |  |
| 6 | Société _(en-tête)_ | — | interface |  |
| 7 | Prendre rendez-vous _(en-tête)_ | — | interface |  |
| 8 | Studio logiciel | — | interface |  |
| 9 | Nous construisons des logiciels métier pour les entreprises. | `YB-METIER` | construit | `docs/plans/PLAN_YANBOW_WEB.md:42`<br>`docs/plans/PLAN_YANBOW_WEB.md:54` |
| 10 | Prendre rendez-vous | — | interface |  |
| 11 | Deux produits construits, SolarBow pour les installateurs solaires et MarketingBow pour les campagnes publicitaires, et du sur mesure pour le reste. | `YB-POSITIONNEMENT` | construit | `docs/plans/PLAN_YANBOW_WEB.md:43`<br>`docs/plans/PLAN_YANBOW_WEB.md:44`<br>`docs/plans/PLAN_YANBOW_WEB.md:54` |
| 12 | Découvrir les produits | — | interface |  |
| 13 | Capture d’écran en préparation | — | interface |  |
| 14 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 15 | Données fictives | — | interface |  |
| 16 | Produits | — | interface |  |
| 17 | Deux produits construits | — | interface |  |
| 18 | Pour les installateurs solaires | — | interface |  |
| 19 | SolarBow | — | interface |  |
| 20 | Le logiciel des installateurs solaires, du premier contact à la proposition commerciale. | `SB-POUR-QUI` | construit | `backend/django_core/apps/crm/models.py:520`<br>`backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49`<br>`docs/plans/PLAN_YANBOW_WEB.md:60` |
| 21 | Un CRM pensé pour les installateurs solaires : fiches prospects complètes, pipeline et relances planifiées. | `SB-CRM` | construit | `backend/django_core/apps/crm/models.py:520`<br>`backend/django_core/apps/crm/models.py:1156` |
| 22 | Un calepinage de toiture en vue 3D et en plan 2D. | `SB-CALEPINAGE-3D` | construit | `frontend/src/features/calepinage/atelier/OutilsVue.jsx:46`<br>`backend/django_core/apps/calepinage/models.py:41` |
| 23 | Les dossiers déclaration préalable, Enedis et Consuel composés à partir des modèles de l’installateur. | `SB-PACKS-FR` | construit | `backend/django_core/apps/calepinage/services/reglementaire.py:866`<br>`backend/django_core/apps/calepinage/services/reglementaire.py:918` |
| 24 | Capture d’écran en préparation | — | interface |  |
| 25 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 26 | Données fictives | — | interface |  |
| 27 | Découvrir SolarBow | — | interface |  |
| 28 | Pour les campagnes publicitaires | — | interface |  |
| 29 | MarketingBow | — | interface |  |
| 30 | Un moteur de campagnes publicitaires Meta où une personne valide chaque changement. | `MB-POUR-QUI` | construit | `backend/django_core/apps/adsengine/meta_client.py:741`<br>`backend/django_core/apps/adsengine/services.py:1880` |
| 31 | Campagnes, ensembles et publicités sont toujours créés en pause ; une personne les active. | `MB-CREATION-EN-PAUSE` | construit | `backend/django_core/apps/adsengine/meta_client.py:32`<br>`backend/django_core/apps/adsengine/meta_client.py:741` |
| 32 | Chaque changement est d’abord proposé, puis approuvé par une personne, avant d’être appliqué. | `MB-PROPOSE-APPROUVE` | construit | `backend/django_core/apps/adsengine/services.py:228`<br>`backend/django_core/apps/adsengine/services.py:1880` |
| 33 | Des garde-fous et un coupe-circuit global qui met tout en pause. | `MB-COUPE-CIRCUIT` | construit | `backend/django_core/apps/adsengine/flightrunner.py:204` |
| 34 | Capture d’écran en préparation | — | interface |  |
| 35 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 36 | Données fictives | — | interface |  |
| 37 | Découvrir MarketingBow | — | interface |  |
| 38 | Sur mesure | — | interface |  |
| 39 | Et pour le reste, du sur mesure | — | interface |  |
| 40 | Au-delà de nos deux produits, nous construisons des logiciels sur mesure pour les entreprises. | `SM-OFFRE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:54`<br>`docs/plans/PLAN_YANBOW_WEB.md:42` |
| 41 | La démarche sur mesure | — | interface |  |
| 42 | Le besoin | — | interface |  |
| 43 | Le prototype | — | interface |  |
| 44 | La mise en service | — | interface |  |
| 45 | L’exploitation | — | interface |  |
| 46 | Société | — | interface |  |
| 47 | Pourquoi YanBow | — | interface |  |
| 48 | YanBow vient de ينبوع, la source. | `YB-NOM-SOURCE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:198` |
| 49 | Qui nous sommes | — | interface |  |
| 50 | Parlons de votre projet | — | interface |  |
| 51 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
| 52 | Prendre rendez-vous | — | interface |  |
| 53 | SolarBow _(pied)_ | — | interface |  |
| 54 | MarketingBow _(pied)_ | — | interface |  |
| 55 | Sur mesure _(pied)_ | — | interface |  |
| 56 | Société _(pied)_ | — | interface |  |
| 57 | Prendre rendez-vous _(pied)_ | — | interface |  |

## SolarBow — le logiciel des installateurs solaires — `/solarbow/`

[375 px](review/solarbow-fr-375.jpg) · [1440 px](review/solarbow-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Pour les installateurs solaires | — | interface |  |
| 2 | Le logiciel des installateurs solaires, du premier contact à la proposition commerciale. | `SB-POUR-QUI` | construit | `backend/django_core/apps/crm/models.py:520`<br>`backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49`<br>`docs/plans/PLAN_YANBOW_WEB.md:60` |
| 3 | L’interface est en français. | `SB-INTERFACE-FR` | construit | `docs/plans/PLAN_YANBOW_WEB.md:103` |
| 4 | Construit au sein d’une vraie entreprise d’installation. | `SB-ENTREPRISE-REELLE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:63` |
| 5 | Prendre rendez-vous | — | interface |  |
| 6 | Voir ce que fait SolarBow | — | interface |  |
| 7 | Capture d’écran en préparation | — | interface |  |
| 8 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 9 | Données fictives | — | interface |  |
| 10 | Ce que fait SolarBow | — | interface |  |
| 11 | Du premier contact à la proposition | — | interface |  |
| 12 | Prospects et relances | — | interface |  |
| 13 | Un CRM pensé pour les installateurs solaires : fiches prospects complètes, pipeline et relances planifiées. | `SB-CRM` | construit | `backend/django_core/apps/crm/models.py:520`<br>`backend/django_core/apps/crm/models.py:1156` |
| 14 | Une relance WhatsApp s’ouvre en un clic ; c’est l’installateur qui envoie le message. | `SB-WHATSAPP-LIEN` | construit | `frontend/src/features/crm/relances/PanneauProposerVisite.jsx:73` |
| 15 | Calepinage | — | interface |  |
| 16 | Un calepinage de toiture en vue 3D et en plan 2D. | `SB-CALEPINAGE-3D` | construit | `frontend/src/features/calepinage/atelier/OutilsVue.jsx:46`<br>`backend/django_core/apps/calepinage/models.py:41` |
| 17 | Pour une toiture en France, une suggestion de pente tirée des données altimétriques de l’IGN. | `SB-PENTE-IGN` | construit | `backend/django_core/apps/calepinage/services/lidar_ign.py:61`<br>`backend/django_core/apps/calepinage/services/lidar_ign.py:127` |
| 18 | Capture d’écran en préparation | — | interface |  |
| 19 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 20 | Données fictives | — | interface |  |
| 21 | Dossiers déclaration préalable, Enedis et Consuel | — | interface |  |
| 22 | Les dossiers déclaration préalable, Enedis et Consuel composés à partir des modèles de l’installateur. | `SB-PACKS-FR` | construit | `backend/django_core/apps/calepinage/services/reglementaire.py:866`<br>`backend/django_core/apps/calepinage/services/reglementaire.py:918` |
| 23 | Capture d’écran en préparation | — | interface |  |
| 24 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 25 | Données fictives | — | interface |  |
| 26 | Devis et proposition | — | interface |  |
| 27 | Des devis et une proposition commerciale en PDF générés depuis l’étude. | `SB-DEVIS-PDF` | construit | `backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py:49` |
| 28 | Capture d’écran en préparation | — | interface |  |
| 29 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 30 | Données fictives | — | interface |  |
| 31 | Voyons SolarBow sur vos projets | — | interface |  |
| 32 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
| 33 | Prendre rendez-vous | — | interface |  |

## MarketingBow — campagnes publicitaires validées par une personne — `/marketingbow/`

[375 px](review/marketingbow-fr-375.jpg) · [1440 px](review/marketingbow-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Pour les campagnes publicitaires | — | interface |  |
| 2 | Un moteur de campagnes publicitaires Meta où une personne valide chaque changement. | `MB-POUR-QUI` | construit | `backend/django_core/apps/adsengine/meta_client.py:741`<br>`backend/django_core/apps/adsengine/services.py:1880` |
| 3 | Proposé en option, après une démonstration. | `MB-OPTION` | construit | `docs/plans/PLAN_YANBOW_WEB.md:59` |
| 4 | Prendre rendez-vous | — | interface |  |
| 5 | Voir comment il fonctionne | — | interface |  |
| 6 | Capture d’écran en préparation | — | interface |  |
| 7 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 8 | Données fictives | — | interface |  |
| 9 | Comment il fonctionne | — | interface |  |
| 10 | Une personne décide, toujours | — | interface |  |
| 11 | Tout est créé en pause | — | interface |  |
| 12 | Campagnes, ensembles et publicités sont toujours créés en pause ; une personne les active. | `MB-CREATION-EN-PAUSE` | construit | `backend/django_core/apps/adsengine/meta_client.py:32`<br>`backend/django_core/apps/adsengine/meta_client.py:741` |
| 13 | Proposer, approuver, appliquer | — | interface |  |
| 14 | Chaque changement est d’abord proposé, puis approuvé par une personne, avant d’être appliqué. | `MB-PROPOSE-APPROUVE` | construit | `backend/django_core/apps/adsengine/services.py:228`<br>`backend/django_core/apps/adsengine/services.py:1880` |
| 15 | Consulter, préparer et approuver sont trois droits distincts. | `MB-PERMISSIONS` | construit | `backend/django_core/apps/adsengine/views.py:166`<br>`backend/django_core/apps/adsengine/views.py:269`<br>`backend/django_core/apps/adsengine/views.py:1779` |
| 16 | Capture d’écran en préparation | — | interface |  |
| 17 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 18 | Données fictives | — | interface |  |
| 19 | Garde-fous et coupe-circuit | — | interface |  |
| 20 | Des garde-fous et un coupe-circuit global qui met tout en pause. | `MB-COUPE-CIRCUIT` | construit | `backend/django_core/apps/adsengine/flightrunner.py:204` |
| 21 | Capture d’écran en préparation | — | interface |  |
| 22 | Vrai écran du logiciel, société fictive, recadré sur la zone utile. | — | interface |  |
| 23 | Données fictives | — | interface |  |
| 24 | Les chiffres des textes générés | — | interface |  |
| 25 | Un chiffre dans un texte généré doit correspondre à un fait que vous avez publié, sinon le texte est bloqué ; le texte attend ensuite une validation humaine. | `MB-CHIFFRES-CITES` | construit | `backend/django_core/apps/adsengine/claim_check.py:8`<br>`backend/django_core/apps/adsengine/groundedness.py:12` |
| 26 | Notre façon de travailler | — | interface |  |
| 27 | Votre compte reste le vôtre | — | interface |  |
| 28 | Vous gardez la propriété de votre Page et de votre compte publicitaire Meta : nous y travaillons avec un accès partenaire que vous nous accordez. | `MB-PROPRIETE` | construit | `docs/adsengine-tenant-onboarding.md:17`<br>`docs/adsengine-tenant-onboarding.md:20` |
| 29 | Voyons MarketingBow en démonstration | — | interface |  |
| 30 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
| 31 | Prendre rendez-vous | — | interface |  |

## Logiciel sur mesure — YanBow — `/sur-mesure/`

[375 px](review/surMesure-fr-375.jpg) · [1440 px](review/surMesure-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Sur mesure | — | interface |  |
| 2 | Le logiciel dont votre entreprise a besoin | — | interface |  |
| 3 | Au-delà de nos deux produits, nous construisons des logiciels sur mesure pour les entreprises. | `SM-OFFRE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:54`<br>`docs/plans/PLAN_YANBOW_WEB.md:42` |
| 4 | La démarche | — | interface |  |
| 5 | Quatre temps, dans cet ordre | — | interface |  |
| 6 | On part du besoin réel, on montre un prototype, puis on met le logiciel en service et on l’exploite avec vous. | `SM-DEMARCHE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:54` |
| 7 | Le besoin | — | interface |  |
| 8 | On part de votre façon de travailler et de ce qui coince aujourd’hui. | — | interface |  |
| 9 | Le prototype | — | interface |  |
| 10 | Un premier logiciel qui fonctionne, à essayer avant d’aller plus loin. | — | interface |  |
| 11 | La mise en service | — | interface |  |
| 12 | Le logiciel est installé et utilisé par vos équipes. | — | interface |  |
| 13 | L’exploitation | — | interface |  |
| 14 | On le maintient et on le fait évoluer avec vous. | — | interface |  |
| 15 | La preuve | — | interface |  |
| 16 | Deux produits construits | — | interface |  |
| 17 | Nos deux produits, SolarBow et MarketingBow, sont construits. | `YB-DEUX-PRODUITS` | construit | `docs/plans/PLAN_YANBOW_WEB.md:43`<br>`backend/django_core/apps/adsengine/meta_client.py:741`<br>`backend/django_core/apps/crm/models.py:520` |
| 18 | SolarBow | — | interface |  |
| 19 | Découvrir SolarBow | — | interface |  |
| 20 | MarketingBow | — | interface |  |
| 21 | Découvrir MarketingBow | — | interface |  |
| 22 | Parlons de votre besoin | — | interface |  |
| 23 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
| 24 | Prendre rendez-vous | — | interface |  |

## La société — YanBow — `/societe/`

[375 px](review/societe-fr-375.jpg) · [1440 px](review/societe-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Société | — | interface |  |
| 2 | Qui nous sommes | — | interface |  |
| 3 | Nous construisons des logiciels métier pour les entreprises. | `YB-METIER` | construit | `docs/plans/PLAN_YANBOW_WEB.md:42`<br>`docs/plans/PLAN_YANBOW_WEB.md:54` |
| 4 | Le nom | — | interface |  |
| 5 | Pourquoi YanBow | — | interface |  |
| 6 | YanBow vient de ينبوع, la source. | `YB-NOM-SOURCE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:198` |
| 7 | « Yan » signifie « un » en amazigh. | `YB-NOM-YAN` | construit | `docs/plans/PLAN_YANBOW_WEB.md:198` |
| 8 | Your Arrow Needs 1Bow | `YB-SLOGAN` | construit | `docs/plans/PLAN_YANBOW_WEB.md:72` |
| 9 | D’où vient SolarBow | — | interface |  |
| 10 | SolarBow | — | interface |  |
| 11 | Construit au sein d’une vraie entreprise d’installation. | `SB-ENTREPRISE-REELLE` | construit | `docs/plans/PLAN_YANBOW_WEB.md:63` |
| 12 | Ce que nous faisons | — | interface |  |
| 13 | Deux produits et du sur mesure | — | interface |  |
| 14 | SolarBow | — | interface |  |
| 15 | MarketingBow | — | interface |  |
| 16 | Sur mesure | — | interface |  |
| 17 | Parlons de votre projet | — | interface |  |
| 18 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
| 19 | Prendre rendez-vous | — | interface |  |

## Prendre rendez-vous — YanBow — `/rendez-vous/`

[375 px](review/rendezVous-fr-375.jpg) · [1440 px](review/rendezVous-fr-1440.jpg)

| # | Phrase | Affirmation | Statut | Preuves |
| --- | --- | --- | --- | --- |
| 1 | Rendez-vous | — | interface |  |
| 2 | Prendre rendez-vous | — | interface |  |
| 3 | Dites-nous qui vous êtes et ce dont vous avez besoin. | — | interface |  |
| 4 | Nom et prénom (obligatoire) | — | interface |  |
| 5 | Société (obligatoire) | — | interface |  |
| 6 | E-mail (obligatoire) | — | interface |  |
| 7 | Téléphone (facultatif) | — | interface |  |
| 8 | Sujet du rendez-vous (obligatoire) | — | interface |  |
| 9 | Choisir un sujet | — | interface |  |
| 10 | SolarBow | — | interface |  |
| 11 | MarketingBow | — | interface |  |
| 12 | Développement sur mesure | — | interface |  |
| 13 | Message (facultatif) | — | interface |  |
| 14 | N'indiquez aucune donnée sensible (santé, opinions, numéro d'identité…). | — | interface |  |
| 15 | J'accepte que ces informations soient utilisées pour répondre à ma demande de rendez-vous. | — | interface |  |
| 16 | Envoyer la demande | — | interface |  |
| 17 | Ce qui se passe ensuite | — | interface |  |
| 18 | Une personne de l’équipe lit votre demande et vous répond. | `YB-REPONSE-HUMAINE` | construit | `backend/django_core/apps/crm/webhooks.py:3354`<br>`docs/plans/PLAN_YANBOW_WEB.md:56` |
