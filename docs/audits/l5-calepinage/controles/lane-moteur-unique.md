# Lane « moteur-unique » — vague C (contrôles d'après L5, 23/11/2026)

Demande du fondateur : « there should be one engine that should be the CRM one » ; cas : le calepinage d'un lead dont
le devis est déjà parti chez le client recalcule autrement que le devis (autre devis lié, autre nombre de panneaux,
autre onduleur, alertes contre des constantes qui ne sont pas celles du devis).

Règles de travail : `docs/audits/l5-calepinage/T2/brief-lanes.md` (à lire en entier ; ses §0 à §6 s'appliquent, y
compris le bloc d'ancrage). Enquête qui fonde ces tâches : `docs/audits/l5-calepinage/controles/C1-moteur-unique.md`
(§1 carte, §2 causes, §3 chemin, §4 « fini quand ») et `C3-mesures-prod.md`. Les textes ci-dessous PRIMENT sur C1 §4
quand ils diffèrent. Ces tâches ne sont pas encore des lignes du plan : `python scripts/audit_tache.py <ID>` ne les
connaît pas — fais toi-même, par grep, les clauses calculées (appelants côté front et serveur, assertions existantes
qui portent l'ancien comportement, jumeaux) et colle-les dans chaque message de commit.

## Garde-fous propres à cette lane (en plus du brief)

- Lecture d'un devis : UNIQUEMENT par `apps/ventes/selectors_calepinage.py` (ou `apps/ventes/selectors.py`). Jamais
  `apps.ventes.models` depuis `apps/calepinage` (import-linter). `core/` n'importe aucune app.
- Tu ne touches NI `apps/ventes/moteur_ci/`, NI `apps/ventes/domain/`, NI `apps/ventes/quote_engine/`, NI un PDF, NI un
  prix : aucun chiffre d'un devis ne change. Tu LIS le devis ; tu ne le recalcules pas et tu n'y écris rien.
- Aucun prix d'achat (`prix_achat`) ni marge dans une réponse.
- Une clé ajoutée à une réponse servie : son `contract_samples/*.json` dans le MÊME commit (contrat d'abord), et dis-le
  au rapport (l'orchestrateur régénère OpenAPI et `docs/api-contracts.md`).
- Tests : dans les modules de test EXISTANTS des fichiers touchés. Un test serveur qui a besoin d'un devis à deux
  options se construit avec les fabriques déjà utilisées par `apps/calepinage/tests/` (cherche-les) — jamais un devis
  écrit à la main sans onduleur.
- Avant ton rapport, en plus des contrôles du brief, joue une fois la suite ENTIÈRE du module :
  `bash "<…>/scratchpad/l5cal/tester.sh" "<ton worktree>" moteurunique apps.calepinage` (≈ 10 à 15 min, un seul appel) —
  le run de PR ne joue pas le backend : la file de fusion a refusé deux fois une vague pour un test que personne
  n'avait joué. Dis le résultat exact (nombre de tests, échecs).

## Décisions prises par l'orchestrateur (fondateur absent, à confirmer — ne les rediscute pas)

- D-ACAL-89 : quand le calepinage ouvert d'un lead est re-lié au devis ENVOYÉ, le brouillon quitté ne garde rien
  (aucune variante créée pour lui) ; le journal du calepinage dit d'où il vient et où il va.
- D-ACAL-90 : la simulation de production reste un GESTE (aucun appel PVGIS lancé seul à l'enregistrement) ; l'étape
  Résultats d'un calepinage lié à un devis envoyé ou accepté montre la production RETENUE PAR LE DEVIS tant que la
  simulation de la pose n'est pas faite.
- Pour un calepinage lié à un devis envoyé ou accepté, les contrôles qui contredisent le devis sont des
  INFORMATIONS (« écart avec le devis »), jamais des « à régler » bloquants : le client a déjà reçu ce devis.

## Tâches, dans l'ordre

1. **ACAL1950 — Le devis dit sa conception retenue (contrat d'abord).** `apps/ventes/selectors_calepinage.py` : une
   fonction (nom à toi, cohérent avec le fichier) qui rend, pour un devis : l'option retenue (`etude_params.
   recommended_option` quand le devis porte deux options, sinon l'unique), le module et sa quantité, les onduleurs et
   leur quantité, les chaînes (longueur, nombre) quand le devis les porte (`electrical_design` — lis sa forme réelle
   avant d'écrire), la production annuelle retenue par le devis (clé figée de l'étude ; lis `ventes/horaire/` et
   `moteur_ci/production.py` pour son nom exact) et le statut du devis. Échantillon :
   `apps/calepinage/contract_samples/` (nouveau fichier, dans ce commit). Fini quand : devis « les deux options »
   recommandé sans ⇒ option sans et ses quantités ; recommandé avec ⇒ l'option avec ; devis à option unique ⇒ elle ;
   clé absente ⇒ `null`, jamais un nombre supposé. Test rouge d'abord.
2. **ACAL1951 — La cible de l'atelier suit l'option retenue, et le dessin dit de quelle option il est.** La cible
   servie (`GET cible-…`, `design-context`) n'est plus l'option sans en dur : c'est l'option retenue d'ACAL1950.
   L'enregistrement du dessin mémorise l'option visée (clé du document côté serveur ; ne grossis pas un fichier mur
   du moteur de dessin). Un toit rempli au-delà de la cible dit l'écart à l'option retenue (« 48 posés, 35 au devis »)
   là où l'atelier dit déjà la cible. Fini quand : devis recommandé avec ⇒ cible = quantité de l'option avec ; devis
   recommandé sans, toit rempli à 48 ⇒ l'écart est dit ; un calepinage sans devis ⇒ comportement inchangé (cible des
   factures). Jumeaux : la puce de l'étape Toit et l'étape Panneaux (`atelier/coque/etapes/panneaux/sources.js`).
3. **ACAL1952 — Sans saisie, le matériel électrique est celui du devis, et il le dit.** `services/electrique.py::
   resoudre_materiel`, `_options_entree`, `services/equipements.py` : sans désignation saisie, onduleur, nombre
   d'onduleurs et longueur de chaîne viennent d'ACAL1950, avec la provenance « devis » servie et affichée ; une saisie
   contraire au devis reste permise et est montrée comme « écart avec le devis » (information). Fini quand : devis à
   1 onduleur X ⇒ l'entrée électrique sert X, 1, provenance devis ; saisie Y ⇒ Y servi + écart nommé ; aucun devis ⇒
   inchangé.
4. **ACAL1953 — Plus d'écart de longueur de chaîne contre le 16 des appels d'offres.** `services/electrique.py::
   _longueur_chaine_retenue` : pour un calepinage lié à un devis, la référence est la longueur du devis (ACAL1950) ;
   absente ⇒ aucun écart publié ; la constante `core/calepinage/electrique.py::MODULES_PAR_CHAINE` ne sert qu'aux
   dossiers d'appel d'offres. Fini quand : calcul 12, devis 12 ⇒ aucun écart ; calcul 12, devis 14 ⇒ écart « 12 contre
   14 au devis » ; sans devis ⇒ aucun « contre 16 ».
5. **ACAL1954 — Un onduleur hybride se juge à sa capacité publiée, pas à un ratio.** Règle du fondateur D-HYB-1 (lue
   dans `apps/ventes/moteur_ci/onduleurs.py::_capacite_kwc` — LIS-la, ne l'édite pas) : pour un hybride dont la fiche
   publie `dc_max_kwc`, la limite du champ est cette capacité. Écris la règle comme fonction PURE dans
   `core/electrique/` (aucun import d'app), applique-la dans `core/electrique/onduleurs.py::dimensionner_onduleurs`
   (l'alerte « au-dessus du seuil 1,50 ») et dans le jugement du ratio du calepinage (`services/electrique.py::
   _juger_ratio` / `_bloc_ratio_dc_ac`). Fini quand : hybride 20 kW publiant 40 kWc + 34,32 kWc de panneaux ⇒ ni
   alerte 1,50 ni « à régler », le contrôle dit « dans la capacité publiée de l'onduleur (40 kWc) » ; 41 kWc ⇒ alerte ;
   onduleur réseau ⇒ comportement inchangé ; fiche sans `dc_max_kwc` ⇒ comportement inchangé. La moitié « le moteur
   C&I importe la même fonction » est une tâche du plan transverse, PAS la tienne.
6. **ACAL1955 — Le calepinage suit le devis envoyé du lead.** `apps/calepinage/receivers.py` (abonné à l'événement
   d'envoi `core/events` — lis comment `crm` s'y abonne dans son `apps.py`), `services/liens.py`,
   `services/creation.py` : à l'envoi d'un devis S, le calepinage OUVERT du même lead qui est lié à un brouillon JAMAIS
   envoyé est re-lié à S (D-ACAL-89), avec une ligne au journal du calepinage ; si le lead a plusieurs calepinages
   ouverts ou si le lié est déjà un devis envoyé ou accepté ⇒ rien ne bouge. Plus une commande de gestion
   `relier_calepinages_devis_envoye` : SANS option elle LISTE seulement (identifiants : calepinage, devis lié, devis
   envoyé) ; `--appliquer` re-lie. Fini quand : deux devis automatiques v1 du même lead, calepinage sur le premier
   (brouillon), envoi du second ⇒ calepinage lié au second ; test de la commande en liste et en application ;
   isolation par société tenue.
7. **ACAL1956 — Résultats d'un devis envoyé jamais vide.** Réponse `GET resultat/` (et son échantillon de contrat) +
   étape Résultats de l'atelier : pour un calepinage lié à un devis envoyé ou accepté, sans simulation faite, l'étape
   montre « Production retenue par le devis : N kWh par an » (ACAL1950) avec le lien vers le devis, et le geste
   « Simuler la pose » ; quand la simulation existe, les deux chiffres sont côte à côte, chacun nommé. Fini quand :
   les trois états (sans devis ; devis envoyé sans simulation ; devis envoyé avec simulation) rendent ce qui est dit
   — test serveur + test de rendu React. Aucun chiffre du devis n'est recalculé.
8. **ALEA67 — « Prêt pour le devis automatique » dit tout ce que le moteur exige.** `apps/crm/devis_auto.py::
   champs_requis` (propriétaire : lead) : en résidentiel, le lead n'est « prêt » que si le moteur sait le situer
   (ville reconnue par `apps.parametres.pvgis_profils.productible_mensuel` ou GPS posé) — sinon « Manque : ville » ;
   en agricole, la phase (`raccordement`) est requise comme le moteur l'exige. Mesuré en production le 23/11 : 29 leads
   résidentiels « prêts » que le moteur refuse ensuite. Fini quand : un lead « prêt » ne reçoit plus
   `localisation_inconnue` ni un refus de phase du moteur ; le contrat `devis_auto_pret.json` et l'écran qui lit
   `devis_auto` restent cohérents (grep des lecteurs front de ces libellés avant de changer). Si la règle du moteur
   n'est pas atteignable depuis `crm` sans import interdit (import-linter), passe par un sélecteur de `ventes` /
   `parametres` et dis-le ; si c'est impossible proprement : sortie « impossible », avec la raison.

## Ton fichier d'événements

`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/l5b/T2-lane-moteurunique.jsonl`
(forme du brief §3, `"tour":3`).
