"""CAL223 — TESTS DE CONTRAT sur TOUTES les sorties du module.

POURQUOI CE FICHIER EXISTE À CÔTÉ DE ``scripts/check_api_shapes.py``
---------------------------------------------------------------------
La garde de dépôt fait beaucoup, mais elle s'ABSTIENT par construction : « un
doute ne rougit JAMAIS ». Une vue dont la forme n'est pas certaine
statiquement sort du contrat, et son échantillon n'est alors comparé à RIEN.
C'est exactement la porte par laquelle un échantillon dérive en silence.

Ce fichier ferme cette porte, avec trois contrôles qui ne demandent NI base de
données NI réseau :

1. **INVENTAIRE** — tout échantillon du dossier est complet (``endpoint``,
   ``pourquoi``, ``exemple``) et déclaré dans CE fichier : un échantillon neuf
   ne peut pas entrer sans qu'on décide s'il est comparable. C'est le contrôle
   qui empêche la liste de pourrir.
2. **CHEMIN DÉCLARÉ** — le chemin de chaque échantillon du module existe
   vraiment dans ``urls.py`` ou dans une ``@action`` (``url_path=``) des vues.
   Renommer une route côté serveur sans toucher l'échantillon échoue ICI, en
   nommant le chemin. Contrôle TEXTUEL et non ``resolve()`` : charger la
   configuration d'URL complète tire WeasyPrint, absent des postes Windows —
   un test qui ne peut pas tourner chez le développeur ne garde rien.
3. **CLÉS SERVIES** — pour chaque échantillon dont le producteur est
   appelable SANS base, on compare les clés RÉELLEMENT servies à celles de
   l'échantillon, et on ÉCHOUE EN NOMMANT la clé divergente.

Les échantillons dont le producteur exige la base (comparatif de variantes,
moteur, pompage…) sont listés dans ``SANS_PRODUCTEUR_PUR`` avec leur raison :
ils restent couverts par les contrôles 1 et 2 ici, et par
``check_api_shapes.py`` + leurs tests dédiés côté CI.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.selectors import (
    SECTIONS_LECTURE_SEULE,
    SECTIONS_PARAMETRES,
    parametres_de_societe,
)
from apps.calepinage.services import site
from apps.calepinage.services.equipements import equipements_du_calepinage
from apps.calepinage.services.lestage import masse_et_lestage
from apps.calepinage.services.parametres_cles import (
    REGISTRES,
    SOURCES_ADMISES,
)
from apps.calepinage.services.modules_stock import (
    modules_disponibles_du_calepinage,
)
from apps.calepinage.services.raccordement import bloc_raccordement
from apps.calepinage.services.reglementaire import _composer_dossiers

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLONS = RACINE / 'contract_samples'
VUES = RACINE / 'views'

#: Les échantillons du module qui ONT un producteur appelable sans base.
#: ``nom de fichier -> (clé de l'exemple, producteur)``.
#: Le producteur rend le dictionnaire RÉELLEMENT servi.
AVEC_PRODUCTEUR_PUR = ('calepinage_equipements.json',
                       'dossiers_reglementaires.json',
                       'parametres_calepinage.json',
                       'site_imagerie.json',
                       # CALX17 — masse posée + feuille de lestage : producteur
                       # PUR (aucune base) sur un calepinage nu.
                       'calepinage_masse_lestage.json',
                       # CALX244 — le point de raccordement : producteur PUR
                       # (``services/raccordement.py::bloc_raccordement``),
                       # servi par ``views/raccordement.py``.
                       'calepinage_raccordement.json',
                       # CALX109 — le catalogue de modules de la société :
                       # producteur PUR (``services/modules_stock.py``), la
                       # vue ne fait que lui passer le QuerySet du stock.
                       'calepinage_modules_disponibles.json',
                       # ACAL56 — l'entrée électrique servie : producteur
                       # PUR sur un calepinage nu
                       # (``services/electrique.py::entree_electrique_servie``).
                       'calepinage_entree_electrique.json')

#: Les autres, avec la RAISON — aucun n'est oublié, chacun est un choix.
SANS_PRODUCTEUR_PUR = {
    # ENF15 (routes_sous_contrat) — formes lues en base ou rendues par une vue :
    # chacune a sa route vérifiée par ``CheminDeclareTest``.
    'calepinage_apercu_document.json':
        'HTML du document, mis en page depuis le calepinage en base (CALX323)',
    'calepinage_export_kml.json':
        'KML de la géométrie du calepinage en base, celle de la planche (ACAL536)',
    'calepinage_export_csv.json':
        "vocabulaire des colonnes du service d'export, fichier CSV rendu "
        'par une vue (ACAL753, test_calx313)',
    'legende_acces_solaire.json':
        "rendu serveur du rapport d'ombrage, aucune route (ACAL727, "
        'test_calx317)',
    'calepinage_consommation_photo_facture.json':
        'lecture crm.services.lire_photo_facture (OCR du serveur IA), '
        "rien d'écrit (ACAL839, test_acal_consommation_proposee)",
    'calepinage_export_layout.json':
        'roof_layout du calepinage en base, exporté tel quel (CAL216)',
    'calepinage_modeles.json':
        'bibliothèque des calepinages modèles de la société en base (CAL199)',
    'calepinage_profils_types.json':
        'profils saisis par la société, lus en base (CAL149)',
    'calepinage_suggestion_pente.json':
        'disponibilité lue sur le réglage de la société en base (CAL237)',
    'calepinage_variante_detail.json':
        'sérialiseur DRF sur une variante en base (CAL21)',
    'calepinage_variantes_liste.json':
        'sérialiseur DRF sur les variantes en base (CAL21)',
    'calepinage_versions_liste.json':
        "historique des versions du calepinage en base (CAL20)",
    'calepinage_detail.json':
        'sérialiseur DRF sur une instance en base (test dédié CAL1)',
    'calepinage_design_context.json':
        'contexte lu sur le devis et la société en base (CAL231)',
    'calepinage_horizon.json':
        'profil PVGIS lu sur le calepinage en base (CAL92/93)',
    'calepinage_pompage.json':
        'dimensionnement qui lit le catalogue produits en base (CAL155-159) '
        'et range le dernier rendu dans resultat (ACAL831, test_agr125)',
    'calepinage_resultat.json':
        'résultat du moteur électrique, lu sur le calepinage en base (CAL244)',
    'calepinage_sorties.json':
        "inventaire qui interroge la géométrie et les documents du "
        "calepinage en base (CAL175)",
    'lead_layout_public.json':
        "endpoint d'une AUTRE app (apps.crm) — hors périmètre de ce module",
    'moteur_calculer.json':
        'appel du moteur pur, couvert par ses propres tests (CAL22)',
    'pose.json': 'appel du moteur de pose, tests dédiés (CAL78)',
    'variantes_comparer.json':
        'comparatif qui lit les variantes en base (CAL21)',
    'zones.json':
        'entrée du moteur (pas une réponse serveur) — couvert par CAL22',
    # CALX4 / CALX5 — le document écrit par la simulation dans
    # ``Calepinage.resultat``. Son producteur EXISTE désormais
    # (``services/simulation.py``), mais il lit le devis, le stock et les
    # réglages en base : la forme est affirmée sans base par
    # apps/calepinage/tests/test_calx5_simulation.py.
    'calepinage_simulation.json':
        'document écrit par services/simulation.py (CALX5) : son producteur '
        'lit le document, les fiches produit et les réglages société en base',
    # Copilote vague 2 (CALA2-CALA10) — routes minces de l'assistant
    # (``views/assistant.py``) ; chacune est comparée à son échantillon par
    # tests/test_api_liste.py (contrat de forme, sur base de test).
    'calepinage_assistant_resume.json':
        'résumé compact lu sur un calepinage et ses variantes en base '
        '(services/assistant.py::resume_compact) — comparé par test_api_liste.py',
    'calepinage_assistant_du_lead.json':
        "état du calepinage OUVERT d'un lead lu en base, visibilité de "
        "l'appelant comprise (etat_du_lead) — comparé par test_api_liste.py",
    'calepinage_assistant_a_traiter.json':
        "file « à traiter » lue en base par le sélecteur "
        'calepinages_a_traiter — comparée par test_api_liste.py',
    'calepinage_assistant_contenance.json':
        'estimation lue sur la visite validée, le catalogue panneaux et le '
        'lead en base (services/contenance.py) — comparée par test_api_liste.py',
    'calepinage_assistant_preparer.json':
        'ouvre ou retrouve le calepinage du lead en base (écriture) — '
        'comparé par test_api_liste.py',
    'calepinage_assistant_publier_apercu.json':
        'aperçu calculé par le service de devis dans une transaction annulée '
        '(devis et lignes en base) — comparé par test_api_liste.py',
    'calepinage_assistant_publier_devis.json':
        'publication au devis : écrit devis et lignes en base — comparée par '
        'test_api_liste.py',
    # CALX45
    'calepinage_du_devis.json':
        "endpoint d'une AUTRE app (apps.ventes, DevisSerializer) — couvert "
        'par apps/ventes/tests/test_calx46_calepinage_du_devis.py',
    # ACON6
    'calepinage_conception_du_devis.json':
        'sélecteur sur un calepinage et sa variante en base — couvert par '
        'tests/test_acal_reviser_relie.py (second devis actif du lead)',
    # ACAL1950
    'calepinage_conception_retenue.json':
        'sélecteur sur un devis et ses lignes en base — couvert par '
        'tests/test_acal_design_context_devis.py (ConceptionRetenueTest)',
    'calepinage_brouillon.json':  # ACAL400
        'brouillon de l\'appelant lu en base (champ du pivot) — comparé par '
        'tests/test_api_layout.py (BrouillonServeurTest)',
    # CALX25
    'calepinage_releve.json':
        'enveloppe (`releve_en_ligne`) lue sur un `ReleveTerrain` SAUVÉ en '
        'base (photos, auteur) — la géométrie PURE (`resoudre_chaines`) est '
        'affirmée sans base par tests/test_calx25_releve_contrat.py',

    # CALX39
    'calepinage_import_plan.json':
        "réponse d'une porte MULTIPART : son producteur exige un plan "
        'déposé (DXF/PDF réel) et un calepinage résolu — affirmé par '
        'apps/calepinage/tests/test_calx39_import_plan.py, qui appelle la '
        "porte sur un DXF fabriqué par ezdxf",

    # CALX35
    'calepinage_dupliquer.json':
        'la réponse décrit la COPIE enregistrée (identifiant, référence '
        'dérivée, variantes comptées) : son producteur exige la base — '
        'couvert par apps/calepinage/tests/test_calx35_dupliquer.py',

    # CALX141
    'calepinage_pertes_cascade.json':
        "détail du bloc `resultat['cascade']` servi par GET resultat/ "
        '(CALX70) : son producteur est services/chaine_pertes.py '
        '(CALX147), pas encore écrit — la forme est affirmée sans base par '
        'apps/calepinage/tests/test_calx141_contrat_cascade.py',

    # CALX143
    'calepinage_meteo.json':
        "détail du bloc `resultat['meteo']` servi par GET resultat/ "
        '(CALX70) : la provenance est aujourd’hui éparse (pvgis_serie, '
        'horizon, production) et son assembleur arrive avec CALX150 — la '
        'forme est affirmée sans base, depuis une réponse PVGIS rejouée, par '
        'apps/calepinage/tests/test_calx143_contrat_meteo.py',

    # CALX144
    'calepinage_incertitude.json':
        "détail du bloc `resultat['incertitude']` servi par GET resultat/ "
        '(CALX70) : son producteur est services/incertitude.py (CALX185, '
        'CALX186), pas encore écrit — la forme et les deux règles dures '
        '(aucun σ sans source, aucun P50 recopié en P90) sont affirmées sans '
        'base par '
        'apps/calepinage/tests/test_calx144_contrat_incertitude.py',

    # CALX142
    'calepinage_serie_horaire.json':
        "détail du bloc `resultat['serie_horaire']` PERSISTÉ : il n'est pas "
        'recopié par GET resultat/ (D-CALX 14, volume) et son seul lecteur '
        "est l'export CSV, qui rend un FICHIER — aucune forme JSON servie à "
        'comparer ; la série est écrite par CALX150 et la forme est affirmée '
        "sans base, par l'exporteur lui-même, dans "
        'apps/calepinage/tests/test_calx142_contrat_serie.py',

    # CALX201
    'electrique_equipements.json':
        "FRAGMENT du document `roof_layout` v2 (clé racine OPTIONNELLE "
        '`electrical.equipements[]`), pas une réponse serveur : la route '
        'GET layout/ rend `{roof_layout, layout_hash, schema_version}` et '
        "l'écrivain du fragment est l'atelier 3D (CALX219/CALX220) — la "
        'forme est affirmée sans base, contre le schéma et contre la porte '
        "d'import réelle, par "
        'apps/calepinage/tests/test_calx201_contrat_equipements.py',

    # CALX202
    'electrique_cheminements.json':
        'FRAGMENT du document `roof_layout` v2 (clé racine OPTIONNELLE '
        '`electrical.cheminements[]`), pas une réponse serveur : le tracé '
        "est écrit par l'atelier 3D (CALX223) et relu par "
        'services/troncons.py (CALX224) — la forme, les deux refus et la '
        'résolution des références sont affirmées sans base par '
        'apps/calepinage/tests/test_calx202_contrat_cheminements.py',

    # CALX203
    'calepinage_troncons.json':
        'métré et chute TRONÇON PAR TRONÇON : la route arrive avec la vague '
        'ÉLECTRIQUE PRO et son producteur est services/troncons.py '
        '(CALX224-226), pas encore écrit — la forme, les omissions nommées '
        'et la cohérence avec electrique_cheminements.json sont affirmées '
        'sans base par '
        'apps/calepinage/tests/test_calx203_contrat_troncons.py',

    # CALX204
    'calepinage_sld.json':
        "schéma unifilaire ÉDITABLE : GET est servi (views/schema.py) mais "
        'son producteur traverse la conception électrique et la porte '
        'cross-app apps.ventes.selectors.schema_unifilaire_svg, donc la '
        'base ; les deux clés neuves (`blocs`, `edition`) et la règle dure '
        "« `edition` n'est pas une seconde source de vérité du dessin » "
        'sont affirmées sans base par '
        'apps/calepinage/tests/test_calx204_contrat_sld.py',


    # CALX106
    'calepinage_empreinte_osm.json':
        "endpoint d'une AUTRE app (apps.crm, GET leads/<id>/roof-footprint/) "
        '— hors périmètre de ce module ; son producteur '
        '(apps/crm/roof_detect.py::_parse_geometry) est PUR et la forme est '
        'affirmée sans base, depuis des réponses Overpass FIXÉES, par '
        'apps/crm/tests/test_calx106_empreinte_osm.py, et le document lui-'
        'même par '
        'apps/calepinage/tests/test_calx106_contrat_empreinte_osm.py',

    # CALX62
    'calepinage_meteo_fichier.json':
        'réponse de la porte MULTIPART qui dépose une série météo de la '
        'société : son producteur crée une ligne records.Attachment et écrit '
        "dans le magasin d'objets, donc il exige la base — le bloc `meteo` et "
        'le résumé de série sont affirmés sans base, depuis un petit fichier '
        'synthétique, par '
        'apps/calepinage/tests/test_calx62_meteo_fichier.py',

    # CALX107
    'calepinage_plan_importe.json':
        "l'URL servie et la taille en pixels du plan de fond : son producteur "
        'résout une records.Attachment rattachée au calepinage et interroge '
        "le magasin d'objets, donc il exige la base — la lecture PURE des "
        'dimensions (en-tête PNG/JPEG) et les quatre refus nommés sont '
        'affirmés sans base par '
        'apps/calepinage/tests/test_calx107_plan_importe.py',

    # CALX292
    'rapport_etude.json':
        "DÉCLARATION des sections du rapport d'étude, lue par l'assembleur "
        '(CALX297) : la route déclarée sert un PDF, il n’y a donc aucune '
        'forme JSON servie à comparer — les chemins exigés sont résolus '
        'contre calepinage_resultat.json, sans base, par '
        'apps/calepinage/tests/test_calx292_contrat_rapport.py',

    # CALX291
    'calepinage_documents.json':
        "INVENTAIRE des documents du lot 6 (codes, versions, manques nommés) : "
        'sa route GET documents/ arrive avec CALX321 (panneau Documents, '
        'phase 2) et son producteur avec elle — la forme, les neuf codes et '
        "l'absence de tout mot de montant sont affirmés sans base par "
        'apps/calepinage/tests/test_calx291_contrat_documents.py',

    # CALX293
    'export_projet.json':
        "EXPORT JSON versionné du projet et de ses résultats, servi par "
        'GET export-projet.json/ (CALX312) : son producteur lit le devis, le '
        'CRM et le résultat du moteur en base — la forme servie (toutes clés, '
        'blocs imbriqués) est affirmée CONTRE l’exemple committé sans base '
        'par apps/calepinage/tests/test_calx312_export_projet.py, le contrat '
        'lui-même par test_calx293_contrat_export_projet.py',

    # CALX370
    'calepinage_projet_json.json':
        "l'IMPORT d'un projet exporté (POST calepinages/import-projet/) : "
        'son producteur écrit calepinage + variantes en base — la forme, les '
        'refus nommés et le tour complet export→import sont affirmés sans '
        'base par apps/calepinage/tests/test_calx370_projet_json.py',

    # CALX267
    'calepinage_batterie.json':
        'forme de services/batterie.py::simuler_groupes (plusieurs groupes '
        'de batteries, chacun avec son couplage) : producteur PUR mais que '
        'AUCUNE route ne sert encore (le bloc `batterie` de GET resultat/ '
        "l'adoptera avec la chaîne de simulation) — l'exemple est le "
        'résultat RÉEL du service sur son `entree_synthetique`, rejoué et '
        'affirmé égal sans base par '
        'apps/calepinage/tests/test_calx267_groupes_batteries.py',

    # CALX336
    'calepinage_releve_visite.json':
        'REPRISE d’une visite technique VALIDÉE dans le calepinage : la '
        'lecture vit dans une AUTRE app (apps.visites.selectors.'
        'releve_pour_calepinage, CALX363) et lit la visite et ses photos en '
        'base, et l’action (CALX364) crée un ReleveTerrain — le producteur '
        'exige la base ; la forme est affirmée contre l’exemple committé par '
        'apps/visites/tests/test_calx363_releve_pour_calepinage.py et '
        'apps/calepinage/tests/test_calx364_reprise_visite.py',
    # CALX331
    'calepinage_comparaison_projets.json':
        'comparaison de 1 à 5 calepinages DISTINCTS : son producteur '
        '(services/comparaison_projets.py, CALX341) lit les calepinages de '
        'la société en base — la ligne PURE (production lue, null jamais 0, '
        'motif) est affirmée contre l’exemple committé par '
        'apps/calepinage/tests/test_calx341_comparaison_projets.py',

    # CALX332
    'calepinage_etiquettes.json':
        'étiquettes libres d’un calepinage (records.Tag/TaggedItem) : son '
        'producteur (services/etiquettes.py, CALX343) lit le vocabulaire et '
        'les étiquettes posées en base — la forme, les refus nommés et '
        'l’exclusion du tag système sont affirmés contre l’exemple committé '
        'par apps/calepinage/tests/test_calx343_etiquettes.py',

    # CALX333
    'calepinage_versions_diff.json':
        'différentiel champ par champ entre deux versions : son producteur '
        '(services/diff_versions.py, CALX345) est PUR mais la porte lit les '
        'versions du calepinage en base — les écarts de l’exemple sont '
        'RECALCULÉS depuis deux documents v2 en mémoire par '
        'apps/calepinage/tests/test_calx345_diff_versions.py',

    # CALX334
    'calepinage_approbation.json':
        'décision d’approbation d’un calepinage : son producteur '
        '(services/approbation.py, CALX347) lit et écrit le champ dédié du '
        'calepinage et la permission `calepinage_approuver` en base — la '
        'forme est affirmée contre l’exemple committé par '
        'apps/calepinage/tests/test_calx347_approbation.py',

    # CALX337
    'calepinage_asbuilt_ecarts.json':
        'écarts de pose réelle : son producteur (services/asbuilt.py, '
        'CAL212/CALX366) lit les `PoseReelle` et la variante retenue en base '
        '— la forme est affirmée contre l’exemple committé par '
        'apps/calepinage/tests/test_calx366_pose_reelle.py',
    # ACAL846
    'calepinage_asbuilt_mesures.json':
        'consommation mesurée vs simulée : le cœur pur '
        '(services/asbuilt.py::_ecart_consommation) est rejoué contre '
        'l’exemple par apps/calepinage/tests/test_calx366_pose_reelle.py ; '
        'l’eau lit les relevés m³ du SAV en base',
    # ACAL886 / ACAL887
    'calepinage_production_mesuree.json':
        'douze kWh mensuels mesurés et leur écart au P50 servi : la route '
        '(views/production_mesuree.py) lit et écrit `ProductionMesuree` et le '
        'résultat servi en base — le cœur PUR (_composer_etat) est rejoué '
        'contre l’exemple par apps/calepinage/tests/test_production_mesuree.py',
    # CALX335
    'calepinage_fixation_bom.json':
        'nomenclature de fixation : son producteur (CALX359, '
        'services/fixation.py) lit le catalogue de systèmes de fixation de '
        'la société EN BASE (CALX358) — la forme (lignes non calculées à '
        '`quantite: null` + `manquant` nommé, aucune clé d’argent) est '
        'affirmée sans base par '
        'apps/calepinage/tests/test_calx335_contrat_fixation_bom.py, et le '
        'coeur PUR du producteur (_lignes_de_fixation) est rejoué contre '
        "l'exemple par apps/calepinage/tests/test_calx359_bom_fixation.py",
    # ACAL M0 (PACT10, 05/10/2026) — contrats posés SEULS avant leur moitié
    # serveur : chacun est affirmé par la tâche qui livre son producteur.
    'calepinage_layout_section.json':
        'écriture par section + jeton If-Match (ACAL1) : la porte lit et '
        'versionne le calepinage en base',
    'calepinage_publication.json':
        'réponse de generer-devis / sync-devis (ACAL3) : la publication '
        'écrit le devis et le calepinage en base',
    'calepinage_pertes.json':
        'pertes et dérogations du calepinage (ACAL8) : lues sur le '
        'calepinage et les réglages société en base',
    'calepinage_publication_electrique.json':
        'refus de publication électrique 409 + dérogation (ACAL9) : lit le '
        'verdict du calepinage en base',
    'calepinage_liste.json':
        'liste des calepinages (ACAL11) : queryset société en base',
    'calepinage_creation_conflit.json':
        'conflit de création 409 (ACAL12) : cherche le calepinage ouvert du '
        'lead en base',
    'calepinage_photos.json':
        'photos du site (ACAL13) : pièces jointes en base',
    'gabarits_dossier_reglementaire.json':
        'gabarits déposés par la société (ACAL15) : lus en base',
    'calepinage_consommation_proposee.json':
        'consommation proposée par le serveur (ACAL21) : lit les factures '
        'et le profil du lead en base',
    'calepinage_parcours_guide.json':
        'état du parcours guidé (ACAL386) calculé à chaque lecture sur le '
        'calepinage et ses réglages en base ; route livrée par ACAL392',
    'calepinage_profil_depart.json':
        'valeurs de départ sourcées proposées (ACAL387) : compilées depuis '
        'des pages citées, appliquées aux réglages société en base (ACAL403)',
    'calepinage_balayage.json':
        'balayage paramétrique (ACAL388) : le résultat vit dans un job lu '
        'en base par moteur/resultat/<job_id>/ ; route livrée par ACAL468',
    'calepinage_table_ombrage.json':
        'FRAGMENT du document roof_layout (zones[].geometry.shadeTable et '
        'skyViewFactor, ACAL389), pas une réponse serveur : écrit par '
        "l'atelier (ACAL459/460), lu par ACAL461",
    'calepinage_detection_toit.json':
        'détection du toit par IA (ACAL391) : appelle un fournisseur externe '
        'sur une image reçue ; route livrée par ACAL485',
    'calepinage_catalogue_materiel.json':  # ACAL960
        'GET : produits actifs de la société (modules, onduleurs) lus en '
        'base — affirmé par tests/test_acal_favoris_materiel.py',
    'calepinage_variantes_par_module.json':  # ACAL594
        'POST : une variante par module du stock ; écrit les variantes en '
        'base — affirmé par tests/test_api_variantes.py (VariantesParModule)',
    'calepinage_pente_terrain.json':
        'pente du relief du champ au sol (ACAL466) : lit le relief '
        'Copernicus GLO-30 sur le réseau (HTTP Range) ; route livrée par '
        'ACAL466',
    'calepinage_apercu_devis.json':  # lane E9 (T4-X5-010)
        'dry-run de « Générer le devis » : compose sur le catalogue de la société en base — la forme est '
        'affirmée contre l’exemple committé par apps/calepinage/tests/test_acal_resync_annonce.py',
    'calepinage_apercu_resync.json':  # ACAL1320 (D-ACAL-73)
        'dry-run de « Resynchroniser le devis » : joue la resynchronisation réelle sur le devis en base '
        'dans un point de sauvegarde annulé — forme affirmée contre l’exemple committé par '
        'apps/calepinage/tests/test_acal_resync_annonce.py',
    'calepinage_cible_factures.json':  # H3
        'taille tirée des factures : lit le lead et dimensionne par le moteur de devis '
        '(cible_depuis_lead) en base — la forme est affirmée contre l’exemple committé '
        'par apps/calepinage/tests/test_design_context.py (CibleFacturesTest)',
    'calepinage_pret_a_envoyer.json':  # ACAL856
        'contrôles « prêt à envoyer ? » (ACAL857-864) : lisent le lead, le '
        'devis lié, la simulation et les réglages société en base ; route '
        'livrée par ACAL860',
    'calepinage_explications.json':  # ACAL870
        'registre des explications (ACAL871) : ses valeurs sont lues dans le '
        'résultat servi du calepinage en base ; route livrée par ACAL871',
    'calepinage_productible_pose.json':  # ACAL996
        'rendement de la pose réelle lu sur le résultat servi du calepinage '
        'en base par selectors_devis.py (ACAL997) pour le devis (ACAL999)',
    'calepinage_evaluation_electrique.json':  # ACAL611
        'lit le verdict du calepinage en base (verdict_publiable)',
    'calepinage_configurations_onduleur.json':  # ACAL614
        'GET : onduleurs du catalogue de la société lus en base et évalués '
        'sur le calepinage en base ; route livrée par ACAL616',
    'calepinage_systemes_fixation.json':  # ACAL557
        'catalogue des systèmes de fixation de la société lu en base '
        '(SystemeFixation + ComposantFixation) ; route livrée par ACAL558',
    'calepinage_controle_chaine.json':  # ACAL626
        'POST : fiches module et onduleur lues dans le stock de la société '
        'en base ; route livrée par ACAL627',
    'calepinage_import_affectation.json':  # ACAL629
        'POST : verdict d’affectation sur le calepinage en base ; route '
        'livrée par ACAL630',
    'calepinage_soleil_legal.json':  # ACAL730
        'GET : fuseau lu au profil de la société en base (repli de '
        "l'imagerie) ; forme affirmée par test_forme_du_soleil_legal",
}

#: Contrats posés AVANT leur route (PACT10 : le contrat d'abord, seul, sur
#: `main`) — le contrôle 2 les ignore tant que la tâche nommée n'a pas livré
#: la porte ; retirer l'entrée dans la même tâche que la route.
#: CALX5 a livré ``POST simuler/`` : ``calepinage_simulation.json`` en est
#: SORTI, et le contrôle 2 vérifie désormais sa route comme celle des autres.
POSES_AVANT_LEUR_ROUTE = {
    # CALX228 a livré ``GET calepinages/<pk>/troncons/`` (``views/troncons.py``)
    # et CALX244 ``GET``/``POST calepinages/<pk>/raccordement/``
    # (``views/raccordement.py``) : ``calepinage_troncons.json`` et
    # ``calepinage_raccordement.json`` en sont SORTIS, et le contrôle 2
    # vérifie désormais leurs routes comme celles des autres.
    # CALX297 a livré ``GET calepinages/<pk>/rapport-etude.pdf/``
    # (``views/documents.py``) : ``rapport_etude.json`` en est SORTI.
    # CALX321 a livré ``GET calepinages/<pk>/documents/`` (``views/documents.py``,
    # action ``documents``) : ``calepinage_documents.json`` en est SORTI —
    # même retrait que CALX297 avant elle.
    # CALX312 a livré ``GET calepinages/<pk>/export-projet.json/``
    # (``views/documents.py``) : ``export_projet.json`` en est SORTI.
    # CALX364 a livré ``GET/POST calepinages/<pk>/releve-visite/``
    # (``views/reprise_visite.py``) : ``calepinage_releve_visite.json`` en est
    # SORTI.
    # CALX341 a livré ``POST calepinages/comparer-projets/``
    # (``views/comparaison_projets.py``) : ``calepinage_comparaison_projets.json``
    # en est SORTI.
    # CALX343 a livré ``GET/POST/DELETE calepinages/<pk>/etiquettes/``
    # (``views/etiquettes.py``) : ``calepinage_etiquettes.json`` en est SORTI.
    # CALX345 a livré ``GET calepinages/<pk>/versions/<id>/diff/``
    # (``views/versions_diff.py``) : ``calepinage_versions_diff.json`` en est
    # SORTI.
    # CALX347 a livré GET/POST approbation/ : calepinage_approbation.json en est SORTI.
    # CALX366 a livré ``GET/POST calepinages/<pk>/pose-reelle/``
    # (``views/asbuilt.py``) : ``calepinage_asbuilt_ecarts.json`` en est SORTI.
    # CALX359 a livré ``GET calepinages/<pk>/bom-fixation/``
    # (``views/fixation.py``) : ``calepinage_fixation_bom.json`` en est SORTI.
    # ACAL22 a livré POST layout/section/ (views/calepinages.py) :
    # calepinage_layout_section.json en est SORTI.
    # ACAL310 a livré ``POST calepinages/<pk>/consommation/proposer/``
    # (``views/consommation.py``) : calepinage_consommation_proposee.json en
    # est SORTI.
    # ACAL392 a livré ``GET calepinages/<pk>/parcours/``
    # (``views/parcours_guide.py``) : ``calepinage_parcours_guide.json`` en est
    # SORTI.
    # ACAL403 a livré ``GET``/``POST``/``DELETE calepinages/profil-depart/``
    # (``views/profil_depart.py``) : ``calepinage_profil_depart.json`` en est
    # SORTI.
    # ACAL468 a livré ``POST calepinages/<pk>/balayage/``
    # (``views/balayage.py``) : ``calepinage_balayage.json`` en est SORTI.
    # ACAL485 a livré ``GET``/``POST calepinages/<pk>/detection-toit/``
    # (``views/detection_toit.py``) : ``calepinage_detection_toit.json`` en est SORTI.
    # ACAL860 a livré ``GET calepinages/<pk>/pret-a-envoyer/``
    # (``views/pret_a_envoyer.py``) : ``calepinage_pret_a_envoyer.json`` en est SORTI.
    # ACAL871 a livré ``GET calepinages/explications/``
    # (``views/explications.py``) : ``calepinage_explications.json`` en est SORTI.
    # ACAL558 a livré ``GET``/``POST calepinages/systemes-fixation/``
    # (``views/systemes_fixation.py``) : ``calepinage_systemes_fixation.json``
    # en est SORTI.
    # ACAL1320 a livré ``GET calepinages/<pk>/apercu-resync/`` (``views/pret_a_envoyer.py``) :
    # ``calepinage_apercu_resync.json`` en est SORTI.
}

#: Clés promises par un contrat M0 (PACT10) AVANT que leur producteur pur ne
#: les serve : ``échantillon -> {clé: tâche qui la livre}``. La comparaison
#: les ignore tant que l'entrée existe ; la tâche nommée retire SA clé dans
#: le même commit que le producteur (le test rougit dès qu'une clé « en
#: attente » est réellement servie).
CLES_POSEES_AVANT_LEUR_PRODUCTEUR = {
    'dossiers_reglementaires.json': {'packs_france': 'ACAL238'},
    'site_imagerie.json': {'site_effectif': 'ACAL129'},
}


#: Les chemins qui ne sont PAS servis par ce module (aucun url_path à y
#: chercher) : ils appartiennent à une autre app.
HORS_MODULE = ('/api/django/crm/', '/api/django/ventes/')


def _echantillons():
    return sorted(chemin for chemin in ECHANTILLONS.glob('*.json')
                  if not chemin.name.endswith('.schema.json'))


def _charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


def _sources_de_routes():
    textes = [(RACINE / 'urls.py').read_text(encoding='utf-8')]
    textes += [chemin.read_text(encoding='utf-8')
               for chemin in sorted(VUES.glob('*.py'))]
    # ACAL229 — ``url_path=r'export\\.csv'`` (point échappé) déclare le
    # chemin servi ``export.csv`` : la source est lue comme le routeur la sert.
    return '\n'.join(textes).replace("url_path=r'", "url_path='").replace(
        '\\.', '.')


class Faux:
    """Un calepinage NU : aucun devis, aucun document — donc aucune base."""

    pk = 1
    devis_id = None
    roof_layout = None
    resultat = None
    company = None
    layout_hash = ''
    titre = 'Calepinage 1'

    def __str__(self):
        return self.titre


class InventaireDesEchantillonsTest(unittest.TestCase):
    """Aucun échantillon ne peut entrer sans être décidé."""

    def test_chaque_echantillon_est_complet(self):
        for chemin in _echantillons():
            donnees = _charger(chemin.name)
            for cle in ('endpoint', 'pourquoi', 'exemple'):
                self.assertIn(cle, donnees,
                              f"{chemin.name} : clé « {cle} » absente.")
            self.assertTrue(donnees['endpoint'].strip(), chemin.name)

    def test_chaque_echantillon_est_declare_ici(self):
        connus = set(AVEC_PRODUCTEUR_PUR) | set(SANS_PRODUCTEUR_PUR)
        trouves = {chemin.name for chemin in _echantillons()}
        self.assertEqual(
            sorted(trouves - connus), [],
            "Échantillon non déclaré dans test_cal223_contrats.py : ajoutez-le "
            "à AVEC_PRODUCTEUR_PUR (comparé) ou à SANS_PRODUCTEUR_PUR (avec "
            "sa raison) — un échantillon non décidé dérive en silence.")
        self.assertEqual(sorted(connus - trouves), [],
                         "Échantillon déclaré mais absent du dossier.")

    @staticmethod
    def _servies_sur_fiche_vide():
        """R3-09 — les sorties (ou refus) des services du lot R3-D sur une fiche VIDE, sans base."""
        from apps.calepinage.services import (
            architecture_onduleur, controle_chaine, production_mesuree, raccordement, troncons,
        )
        from apps.calepinage.services.etapes import onduleur

        def refus(appel):
            try:
                appel()
            except (controle_chaine.ControleInvalide, production_mesuree.MesureRefusee,
                    raccordement.RaccordementInvalide) as erreur:
                return str(erreur)
            return ''

        serie = {'colonne_energie': 'p_dc_kw', 'points': []}
        courbe = [{'charge_pct': 50, 'rendement_pct': 97.0}, {'charge_pct': 100, 'rendement_pct': 98.0}]
        sans_nominale = {'fiche_onduleur': {'rendement_par_charge': courbe}, 'electrique': {'onduleurs': [{}]}}
        return {
            'raccordement.bloc_raccordement': raccordement.bloc_raccordement(None, {}, [], {}),
            'raccordement.refus': refus(lambda: raccordement.bloc_raccordement(
                None, {'puissance_souscrite_kva': 'abc', 'cos_phi_impose': 9}, [], {})),
            'controle_chaine.verdict': controle_chaine._controler_chaine({}, {}, 10, -5, 70),
            'controle_chaine.refus': [refus(lambda: controle_chaine._temperatures(brut)) for brut in (
                {}, {'temperature_min_c': 40, 'temperature_max_c': 10})],
            'troncons.document': troncons._troncons_du_document({}),
            'architecture_onduleur.motifs': architecture_onduleur.motifs_de_l_architecture(None, {}, {}, {}),
            'production_mesuree.refus': [refus(lambda: production_mesuree._valider(brut)) for brut in (
                {}, {'annee': 1850, 'mesures': []}, {'annee': 9999, 'mesures': []},
                {'annee': 2026, 'mesures': [{'mois': 1}]}, {'annee': 2026, 'mesures': [{'mois': 13}]})],
            'etapes.onduleur': [onduleur.appliquer(serie, ctx)[1] for ctx in ({}, sans_nominale)],
        }

    def test_phrases_servies_sans_jargon(self):
        # ACAL990 (K-JARGON) — les phrases PRODUITES (jamais le source) d'une fiche vide : aucune clé,
        # chemin, code interne ni valeur brute. Services listés ci-dessous ; l'échec nomme le service.
        import re

        from apps.calepinage.services import lestage, norme, ombrage_chaines, profils_types, suppositions
        from apps.calepinage.tests.test_calx248_verdict_publiable import _Calepinage, _verdict

        interdit = re.compile(r'::|\.py\b|\[\]|\?\.|MODULES_PAR_CHAINE|degagements\.|CAL\d+|dépôt')
        # R3-09 — pour les services du lot R3-D, une PHRASE (texte à espaces) ne porte non plus aucune clé
        # technique (snake_case) ni index (``[0]``).
        cle_technique = re.compile(r'\b[a-z]+(?:_[a-z0-9]+)+\b|\[\d+\]')
        brutes = {'martin_ruiz', 'tmy'}
        servies = {
            'norme.norme_applicable': norme.norme_applicable(None),
            'electrique.verdict_publiable': _verdict(_Calepinage(layout={})),
            'ombrage_chaines.ombrage_des_chaines': ombrage_chaines.ombrage_des_chaines({}, {}),
            'lestage.feuille': lestage._feuille_de_lestage({}),
            'profils_types.replis': profils_types._profils_de_repli(),
            'suppositions.repli_longueur_dossier': suppositions.repli_longueur_dossier(16, 'dossier'),
        }
        strictes = self._servies_sur_fiche_vide()
        servies.update(strictes)

        def phrases(noeud):
            if isinstance(noeud, str):
                yield noeud
            elif isinstance(noeud, dict):
                for valeur in noeud.values():
                    yield from phrases(valeur)
            elif isinstance(noeud, (list, tuple)):
                for valeur in noeud:
                    yield from phrases(valeur)

        for service, sortie in servies.items():
            lues = list(phrases(sortie))
            self.assertTrue(lues, service)
            for phrase in lues:
                self.assertIsNone(interdit.search(phrase), f'{service} : « {phrase[:90]} » porte une clé ou un chemin')
                # « Champ manquant : « chemin » » est le CONTRAT relu par a_renseigner (R3-19 : le rendu le
                # traduit, la source ne change pas) : il n'est pas jugé ici.
                phrase_libre = re.sub('Champ manquant : « [^»]* »', '', phrase)
                if service in strictes and ' ' in phrase_libre:
                    self.assertIsNone(cle_technique.search(phrase_libre),
                                      f'{service} : « {phrase[:90]} » porte une clé technique')
                self.assertNotIn(phrase.strip(), brutes, f'{service} : valeur brute « {phrase} »')

    def test_etat_conception_du_detail(self):
        # ACAL1005 — `rapide` | `complet` ; `complet` sans motif, `rapide` motivé.
        donnees = _charger('calepinage_detail.json')
        for nom in ('exemple', 'exemple_vide', 'exemple_rapide'):
            self.assertIn(donnees[nom]['etat_conception'], {'rapide', 'complet'}, nom)
        for nom in ('exemple', 'exemple_vide'):
            self.assertEqual(donnees[nom]['etat_conception'], 'complet', nom)
            self.assertIsNone(donnees[nom]['etat_conception_motif'], nom)
        self.assertEqual(sorted(donnees['exemple_rapide']),
                         ['etat_conception', 'etat_conception_motif'])
        self.assertEqual(donnees['exemple_rapide']['etat_conception'], 'rapide')
        self.assertEqual(donnees['exemple_rapide']['etat_conception_motif'],
                         'ouvert depuis un devis automatique : à vérifier sur place')

    def test_manquants_portent_champ_et_cible_montee(self):
        # ACAL986 (K-IMPASSE) — chaque ligne `manquants[]` d'un échantillon ET
        # du producteur nomme son champ ; une cible « reglages » vise une clé
        # du registre servi (champ `calx69-<clé>` monté par les Réglages).
        from apps.calepinage.services.manquants_simulation import manquants_de_simulation
        from apps.calepinage.services.parametres_cles import REGISTRES

        cles = {cle for decl in REGISTRES.values() for cle, *_ in decl}

        def lignes(noeud, chemin):
            if isinstance(noeud, dict):
                for cle, valeur in noeud.items():
                    if cle == 'manquants' and isinstance(valeur, list):
                        # Les lignes « refus » (motif / cible) ; la masse a son vocabulaire (quoi, message).
                        yield from ((f'{chemin}.manquants[{i}]', m) for i, m in enumerate(valeur)
                                    if isinstance(m, dict) and ({'motif', 'cible'} & set(m)))
                    yield from lignes(valeur, f'{chemin}.{cle}')
            elif isinstance(noeud, list):
                for i, element in enumerate(noeud):
                    yield from lignes(element, f'{chemin}[{i}]')

        trouvees = [ligne for chemin in _echantillons()
                    for ligne in lignes(_charger(chemin.name), chemin.name)]
        trouvees += [(f'producteur[{i}]', m) for i, m in enumerate(manquants_de_simulation({}, {}))]
        self.assertGreater(len(trouvees), 4)
        for ou, ligne in trouvees:
            self.assertTrue(str(ligne.get('champ') or '').strip(), f'{ou} : `champ` absent')
            self.assertTrue(str(ligne.get('motif') or '').strip(), f'{ou} : `motif` absent')
            self.assertIn('cible', ligne, f'{ou} : `cible` absente (null si ce n’est pas un réglage)')
            cible = ligne.get('cible')
            if cible is None or cible.get('onglet') != 'reglages':
                continue
            champ = str(cible.get('champ') or '')
            self.assertTrue(champ.startswith('calx69-') and champ[len('calx69-'):] in cles,
                            f'{ou} : « {ligne["motif"][:60]}… » vise {champ!r}, aucun champ des Réglages')

    def test_etat_conception_marque_par_la_creation(self):
        # ACAL1006 — devis rapide ⇒ calepinage rapide ; dessiné ⇒ inchangé.
        from types import SimpleNamespace

        from apps.calepinage.services import creation
        from apps.calepinage.services.creation import ORIGINE_ADOPTE, ORIGINE_EXISTANT
        from apps.calepinage.models import Calepinage

        rapide = SimpleNamespace(etude_params={'origine_conception': 'rapide'})
        humain = SimpleNamespace(etude_params={'scenario': 'sans'})
        self.assertEqual(creation._etat_de_depart(rapide, None), 'rapide')
        self.assertEqual(creation._etat_de_depart(rapide, {'zones': [{}]}), 'complet')
        self.assertEqual(creation._etat_de_depart(humain, None), 'complet')
        self.assertEqual(creation._etat_de_depart(SimpleNamespace(), None), 'complet')
        self.assertEqual(Calepinage._meta.get_field('etat_conception').default, 'complet')
        self.assertEqual([c for c, _ in Calepinage.ETAT_CONCEPTION_CHOICES], ['rapide', 'complet'])

        class Pivot:  # sans ``objects`` : toute écriture en base lèverait
            def __init__(self, document):
                self.pk, self.roof_layout, self.etat_conception = 1, document, 'complet'

        for adopte in ((Pivot({'zones': [{}]}), ORIGINE_ADOPTE),
                       (Pivot(None), ORIGINE_EXISTANT)):
            creation._marquer_l_adopte(adopte, rapide)
            self.assertEqual(adopte[0].etat_conception, 'complet', adopte[1])

    def test_forme_des_systemes_de_fixation(self):
        # ACAL557 — chaque système et chaque composant aux clés du contrat,
        # vocabulaires lus sur les modèles, jamais `company`, aucun prix.
        from apps.calepinage.models import ComposantFixation, SystemeFixation

        donnees = _charger('calepinage_systemes_fixation.json')
        cles_systeme = {'id', 'code', 'libelle', 'fabricant', 'mode_pose',
                        'actif', 'provenance', 'composants',
                        'couvertures',  # couvertures : ACAL566
                        'controles_pose'}  # controles_pose : ACAL568
        cles_composant = {'id', 'role', 'libelle', 'unite', 'produit_id',
                          'regle', 'source', 'ordre'}
        cles_regle = {'base', 'facteur', 'diviseur', 'libelle_facteur',
                      'libelle_diviseur'}
        systemes = (donnees['exemple']['systemes']
                    + [donnees['exemple_creation']['reponse']['systeme']])
        for systeme in systemes:
            self.assertEqual(set(systeme), cles_systeme)
            self.assertIn(systeme['mode_pose'], SystemeFixation.ModePose.values)
            for composant in systeme['composants']:
                self.assertEqual(set(composant), cles_composant)
                self.assertIn(composant['role'], ComposantFixation.Role.values)
                self.assertEqual(set(composant['regle']), cles_regle)
        self.assertEqual(donnees['exemple_vide'], {'systemes': []})
        corps = donnees['exemple_creation']['corps']
        self.assertNotIn('company', corps)
        self.assertEqual(len(corps['composants']), 2)
        self.assertEqual(
            sorted(donnees['exemple_refus']['corps']),
            ['code', 'composants[0].regle', 'composants[1].source',
             'provenance'])
        self.assertNotIn('prix', json.dumps(systemes + [corps]))

    def test_forme_du_parcours_guide(self):
        # ACAL386 — le parcours guidé : cinq étapes ordonnées, « manque »
        # dédupliqué sur (code, cible), jamais une gravité inventée.
        donnees = _charger('calepinage_parcours_guide.json')
        cles = ['toit', 'panneaux', 'electrique', 'resultats', 'documents']
        etats = {'a_faire', 'en_cours', 'fait', 'bloque'}
        for nom in ('exemple', 'exemple_vide'):
            etapes = donnees[nom]['etapes']
            self.assertEqual([e['cle'] for e in etapes], cles, nom)
            self.assertTrue(all(e['etat'] in etats for e in etapes), nom)
            vus = set()
            for ligne in donnees[nom]['manque']:
                self.assertEqual(
                    sorted(ligne), ['cible', 'code', 'etape', 'gravite',
                                    'message', 'nombre'], nom)
                self.assertIn(ligne['etape'], cles)
                self.assertIn(ligne['gravite'],
                              ('bloquant', 'a_regler', 'info'))
                self.assertEqual(sorted(ligne['cible']), ['champ', 'onglet'])
                identite = (ligne['code'], ligne['cible']['onglet'],
                            ligne['cible']['champ'])
                self.assertNotIn(identite, vus, 'ligne en double')
                vus.add(identite)
        self.assertEqual(donnees['exemple_vide']['manque'], [])
        self.assertTrue(all(e['etat'] == 'a_faire'
                            for e in donnees['exemple_vide']['etapes']))

    def test_forme_du_profil_de_depart(self):
        # ACAL387 — chaque valeur de départ est SOURCÉE (jamais de mémoire).
        donnees = _charger('calepinage_profil_depart.json')
        prefixe = donnees['prefixe_reference']
        cles = ('cle', 'section', 'valeur', 'unite', 'source', 'reference',
                'url', 'date_lecture', 'etat')
        for ligne in donnees['exemple']['valeurs']:
            self.assertEqual(sorted(ligne), sorted(cles))
            self.assertIn(ligne['etat'], ('a_appliquer', 'posee_par_profil',
                                          'deja_saisie'))
            declarees = {c[0] for c in REGISTRES[ligne['section']]}
            self.assertIn(ligne['cle'], declarees)
            self.assertEqual(ligne['source'], 'texte')
            self.assertIn(ligne['source'], SOURCES_ADMISES)
            self.assertTrue(ligne['reference'].startswith(prefixe))
            self.assertTrue(ligne['url'].startswith('https://'))
            self.assertRegex(ligne['date_lecture'], r'^\d{4}-\d{2}-\d{2}$')
        valeurs = {(v['section'], v['cle'])
                   for v in donnees['exemple']['valeurs']}
        sans = {(v['section'], v['cle'])
                for v in donnees['exemple']['sans_source']}
        tout = {(sec, c[0]) for sec, lignes in REGISTRES.items()
                for c in lignes}
        self.assertEqual(valeurs & sans, set())
        self.assertEqual(valeurs | sans, tout)
        for ligne in donnees['exemple_application']['ignorees']:
            self.assertEqual(ligne['motif'], 'deja_saisie')

    def test_forme_du_balayage(self):
        # ACAL388 — même enveloppe que l'accusé de simulation, nature neuve.
        donnees = _charger('calepinage_balayage.json')
        axes = ('inclinaison_deg', 'azimut_deg', 'ratio_dc_ac')
        for axe in donnees['exemple_corps']['axes']:
            self.assertEqual(sorted(axe),
                             ['max', 'min', 'nom', 'pas'])
            self.assertIn(axe['nom'], axes)
        accuse = donnees['exemple']
        cles_simulation = set(
            _charger('calepinage_simulation.json')['exemple_accepte'])
        self.assertEqual(set(accuse), cles_simulation)
        self.assertEqual((accuse['kind'], accuse['nature']),
                         ('calepinage', 'balayage'))
        resultat = donnees['exemple_resultat']
        demandes = {a['nom'] for a in donnees['exemple_corps']['axes']}
        for ligne in resultat['grille'] + [resultat['optimum']]:
            self.assertTrue(demandes <= set(ligne))
            self.assertIn('p50_kwh', ligne)
            self.assertIn('rendement_specifique_kwh_kwc', ligne)
            self.assertEqual('ratio_dc_ac' in demandes,
                             'ecretage_pct' in ligne)
        for cle in ('appels_pvgis', 'complete', 'socle_manquant', 'etat'):
            self.assertIn(cle, resultat)

    def test_forme_de_la_table_d_ombrage(self):
        # ACAL389 — dimensions cohérentes, valeurs dans [0, 1].
        geometrie = _charger(
            'calepinage_table_ombrage.json')['exemple']['zones'][0]['geometry']
        table = geometrie['shadeTable']
        self.assertEqual(len(table['facteurs']), len(table['hauteursDeg']))
        for ligne in table['facteurs']:
            self.assertEqual(len(ligne), len(table['azimutsDeg']))
            self.assertTrue(all(0 <= v <= 1 for v in ligne))
        self.assertEqual(table['methode'], 'centres_de_modules')
        ciel = geometrie['skyViewFactor']
        self.assertTrue(0 <= ciel['facteur'] <= 1)
        self.assertEqual(sorted(ciel['methode']),
                         ['diffus', 'horizon', 'resolution'])
        self.assertEqual(ciel['methode']['diffus'], 'isotrope')
        self.assertIsInstance(ciel['methode']['horizon'], bool)
        for bloc in (table, ciel):
            self.assertTrue(bloc['signature'])

    def test_forme_de_la_detection_du_toit(self):
        # ACAL391 — une PROPOSITION : toujours « à confirmer », jamais écrite.
        donnees = _charger('calepinage_detection_toit.json')
        self.assertIn(donnees['exemple_corps']['origine'],
                      ('importee', 'carte'))
        dispo = donnees['exemple_disponibilite']
        self.assertEqual(sorted(dispo),
                         ['disponible', 'motif', 'origines_acceptees'])
        self.assertTrue(set(dispo['origines_acceptees'])
                        <= {'importee', 'carte'})
        propositions = donnees['exemple']['propositions']
        en_attente = set(CLES_POSEES_AVANT_LEUR_PRODUCTEUR.get(
            'calepinage_detection_toit.json', {}))
        self.assertEqual(sorted(set(propositions) - en_attente),
                         ['contour_lnglat', 'obstacles', 'pans'])
        self.assertEqual(donnees['exemple']['provenance'], 'ia')
        self.assertIs(donnees['exemple']['a_confirmer'], True)
        for pan in propositions['pans']:
            self.assertEqual(sorted(pan),
                             ['azimut_deg', 'confiance', 'contour_lnglat'])
            self.assertTrue(all(len(p) == 2 for p in pan['contour_lnglat']))
        self.assertTrue(donnees['exemple_indisponible_503']['detail'])

    def test_obstacles_proposes_servis_par_acal1049(self):
        # ACAL530 — types : la liste de l'atelier (ACAL498) du schéma du document ;
        # ACAL1049 sert la clé (plus « en attente »).
        self.assertNotIn('calepinage_detection_toit.json', CLES_POSEES_AVANT_LEUR_PRODUCTEUR)
        types = _charger('roof_layout_v2.schema.json')['$defs']['obstacle'][
            'properties']['type']['enum']
        obstacles = _charger('calepinage_detection_toit.json')['exemple'][
            'propositions']['obstacles']
        self.assertEqual(len(obstacles), 2)
        for obstacle in obstacles:
            self.assertEqual(sorted(obstacle), ['confiance', 'contour_lnglat', 'type'])
            self.assertIn(obstacle['type'], types)
            self.assertGreaterEqual(len(obstacle['contour_lnglat']), 3)
            self.assertTrue(0 <= obstacle['confiance'] <= 1)

    def test_forme_de_la_pente_terrain(self):
        # ACAL466 — lecture pure ; relief illisible = null + motif, jamais
        # une altitude de repli.
        donnees = _charger('calepinage_pente_terrain.json')
        cles = ['ancrage', 'attribution', 'azimut_pente_deg', 'lu_le', 'motif',
                'pente_deg', 'points', 'source', 'source_url', 'surface']
        self.assertEqual(sorted(donnees['exemple']), cles)
        self.assertEqual(sorted(donnees['exemple_sans_pente']), cles)
        lu = donnees['exemple']
        self.assertGreaterEqual(len(lu['points']), 3)
        self.assertEqual(lu['motif'], '')
        sans = donnees['exemple_sans_pente']
        self.assertIsNone(sans['pente_deg'])
        self.assertIsNone(sans['azimut_pente_deg'])
        self.assertEqual(sans['points'], [])
        self.assertTrue(sans['motif'])
        for charge in (lu, sans):
            self.assertNotIn('DATE', charge['attribution'])

    def test_forme_du_productible_pose(self):
        # ACAL996 — un résultat incomplet n'est jamais servi comme production.
        donnees = _charger('calepinage_productible_pose.json')
        cles = sorted([
            'perime', 'motif', 'source', 'calcule_le', 'kwc_simule',
            'kwc_document', 'p50_kwh', 'kwh_kwc_annuel', 'kwh_kwc_mensuel',
            'complete', 'etapes_omises', 'pertes_et_ombrage_inclus',
            'couvre_toutes_les_surfaces', 'pans'])
        for nom in ('exemple', 'exemple_perime', 'exemple_incomplet'):
            charge = donnees[nom]
            self.assertEqual(sorted(charge), cles, nom)
            self.assertEqual(charge['pertes_et_ombrage_inclus'],
                             charge['complete'], nom)
            if charge['kwh_kwc_annuel'] is not None:
                self.assertEqual(len(charge['kwh_kwc_mensuel']), 12, nom)
                self.assertAlmostEqual(sum(charge['kwh_kwc_mensuel']),
                                       charge['kwh_kwc_annuel'], delta=0.5)
            for pan in charge['pans']:
                self.assertEqual(sorted(pan), [
                    'azimut_deg', 'inclinaison_deg', 'kwc', 'pan',
                    'specific_yield_kwh_kwc'], nom)
        self.assertTrue(donnees['exemple_incomplet']['etapes_omises'])
        self.assertIn('180 = Sud', donnees['pourquoi'])

    def test_forme_de_la_publication_electrique(self):
        # ACAL611 — `etat` dit ce que `publiable` tait (D-ACAL-9 inchangé) ;
        # `points` = motifs d'abstention ; titre et phrase servis.
        from apps.calepinage.services.synthese_publication import (
            synthese_de_publication,
        )

        donnees = _charger('calepinage_evaluation_electrique.json')
        self.assertIn('exemple de forme', donnees['pourquoi'].lower())
        entree = donnees['exemple_corps_a_chaud']['entree_electrique']
        self.assertEqual(sorted(entree), ['module_produit', 'onduleur_produit',
                                          'optimiseur_produit'])
        self.assertNotIn('materiel', entree)
        abstentions = ('non_verifiable', 'omis', 'sans_source')
        attendus = {'exemple': (True, 'pret'),
                    'exemple_a_completer': (True, 'a_completer'),
                    'exemple_bloque': (False, 'bloquant')}
        for nom, (publiable, etat) in attendus.items():
            pub = donnees[nom]['publication']
            self.assertEqual(sorted(pub), ['etat', 'motifs', 'phrase',
                                           'points', 'publiable', 'titre'])
            self.assertEqual((pub['publiable'], pub['etat']),
                             (publiable, etat), nom)
            for motif in pub['motifs']:
                self.assertEqual(sorted(motif),
                                 ['code', 'libelle', 'source', 'statut'])
            # ACAL934 : un état bloquant compte ses motifs bloquants.
            comptes = ('bloquant',) if etat == 'bloquant' else abstentions
            self.assertEqual(pub['points'], sum(
                m['statut'] in comptes for m in pub['motifs']), nom)
            # ACAL612 : titre et phrase = ceux que le serveur compose.
            self.assertEqual(synthese_de_publication(
                {**pub, 'titre': None, 'phrase': None}), pub, nom)
        self.assertGreater(
            donnees['exemple_a_completer']['publication']['points'], 0)
        self.assertIsNone(donnees['exemple_a_chaud']['publication'])

    def test_forme_des_tensions_par_chaine(self):
        # ACAL620 — une ligne par chaîne ; null jamais 0, cause nommée.
        donnees = _charger('calepinage_evaluation_electrique.json')
        cles = sorted([
            'chaine', 'pan', 'mppt', 'nombre_modules', 'source',
            'voc_froid_v', 'voc_froid_limite_v', 'voc_froid_conforme',
            'temperature_froide_c', 'vmp_chaud_v', 'temperature_chaude_c',
            'demarrage_v', 'demarrage_source', 'vmp_chaud_conforme', 'isc_a',
            'temperature_source', 'indetermine'])
        lignes = []
        for nom in ('exemple', 'exemple_a_completer', 'exemple_bloque',
                    'exemple_a_chaud', 'exemple_vide', 'exemple_indetermine'):
            self.assertIn('chaines', donnees[nom], nom)
            lignes += donnees[nom]['chaines']
        self.assertEqual(donnees['exemple_vide']['chaines'], [])
        for ligne in lignes:
            self.assertEqual(sorted(ligne), cles)
            self.assertIn(ligne['demarrage_source'],
                          ('fiche', 'bas_de_plage_mppt', None))
            self.assertIn(ligne['temperature_source'], ('saisie', 'tmy', None))
            for cle in ('voc_froid_v', 'vmp_chaud_v', 'isc_a', 'demarrage_v'):
                self.assertNotEqual(ligne[cle], 0, cle)
                if ligne[cle] is None:
                    self.assertTrue(ligne['indetermine'], cle)
        sans_chaine = [ligne for ligne in
                       donnees['exemple_indetermine']['chaines']
                       if ligne['chaine'] is None]
        self.assertTrue(sans_chaine and sans_chaine[0]['pan'])

    def test_forme_du_controle_de_chaine(self):
        # ACAL626 — chaque contrôle NOMME sa borne ; jamais un faux vert.
        donnees = _charger('calepinage_controle_chaine.json')
        for corps in ('exemple_corps', 'exemple_corps_rouge'):
            self.assertEqual(sorted(donnees[corps]), [
                'module_produit', 'nombre_modules', 'onduleur_produit',
                'temperature_max_c', 'temperature_min_c'])
        for nom in ('exemple', 'exemple_rouge', 'exemple_indetermine'):
            charge = donnees[nom]
            self.assertEqual(sorted(charge), ['controles', 'longueur_max',
                                              'longueur_min', 'manquantes',
                                              'verdict'], nom)
            for controle in charge['controles']:
                self.assertEqual(sorted(controle), [
                    'bloquant', 'borne', 'code', 'conforme', 'libelle',
                    'source', 'valeur'], nom)
                self.assertTrue(controle['borne'], nom)
        rouge = [c for c in donnees['exemple_rouge']['controles']
                 if c['conforme'] is False and c['bloquant']]
        self.assertIn("tension maximale absolue de l'onduleur",
                      rouge[0]['borne'])
        self.assertEqual(donnees['exemple_rouge']['verdict'], 'bloquant')
        indetermine = donnees['exemple_indetermine']
        self.assertEqual(indetermine['verdict'], 'indetermine')
        self.assertTrue(indetermine['manquantes'])

    def test_forme_de_l_import_d_affectation(self):
        # ACAL629 — chaque refus nomme SA ligne de fichier ; jamais appliqué.
        donnees = _charger('calepinage_import_affectation.json')
        self.assertTrue(donnees['exemple_corps']['csv'].startswith(
            'module;chaine;mppt;onduleur\n'))
        for nom in ('exemple', 'exemple_refus', 'exemple_entete_absent'):
            charge = donnees[nom]
            self.assertEqual(sorted(charge), ['applique', 'bloquants',
                                              'lignes', 'refus'], nom)
            self.assertIs(charge['applique'], False, nom)
            for ligne in charge['lignes']:
                self.assertEqual(sorted(ligne),
                                 ['chaine', 'module', 'mppt', 'onduleur'])
            for refus in charge['refus']:
                self.assertEqual(sorted(refus),
                                 ['colonne', 'ligne', 'message'])
                self.assertIsInstance(refus['ligne'], int)
        self.assertEqual(
            {k: v for k, v in donnees['exemple_refus']['refus'][0].items()
             if k != 'message'}, {'ligne': 4, 'colonne': 'chaine'})
        self.assertEqual(
            donnees['exemple_entete_absent']['refus'][0]['ligne'], 1)

    def test_forme_du_soleil_legal(self):
        # ACAL730 — les clés servies par ``correspondance_du_jour`` (double
        # sans base, fuseau des réglages d'imagerie) sont celles du contrat.
        import datetime
        from types import SimpleNamespace

        from apps.calepinage.services.soleil_legal import (
            MOTIF_SANS_FUSEAU, correspondance_du_jour)

        donnees = _charger('calepinage_soleil_legal.json')
        servi = correspondance_du_jour(
            SimpleNamespace(roof_layout={'pin': {'lat': 33.57, 'lng': -7.59}},
                            company=None),
            datetime.date(2026, 2, 11),
            reglages={'imagerie': {'fuseau': 'Africa/Casablanca'}})
        self.assertEqual(sorted(servi), sorted(donnees['exemple']))
        for cle in ('decalage_utc_min', 'equation_du_temps_min',
                    'ecart_legal_moins_solaire_min', 'midi_solaire_legal_h'):
            self.assertEqual(servi[cle], donnees['exemple'][cle], cle)
        self.assertEqual(donnees['exemple_sans_fuseau'],
                         {'site.fuseau': [MOTIF_SANS_FUSEAU]})

    def test_forme_des_configurations_d_onduleur(self):
        # ACAL614 — 1 à 3 lignes comparables, null jamais 0, AUCUN prix.
        donnees = _charger('calepinage_configurations_onduleur.json')
        cles = sorted([
            'produit_id', 'libelle', 'marque', 'role', 'nombre_onduleurs',
            'puissance_ac_totale_kw', 'puissance_dc_kwc', 'ratio_dc_ac',
            'mppt_utilises', 'mppt_disponibles', 'verdict', 'bloquants',
            'alertes', 'manquantes'])
        for nom in ('exemple', 'exemple_vide', 'exemple_indetermine'):
            charge = donnees[nom]
            self.assertEqual(sorted(charge), ['configurations',
                                              'fiches_incompletes',
                                              'motif_vide', 'retenue'], nom)
            self.assertLessEqual(len(charge['configurations']), 3, nom)
            self.assertNotRegex(json.dumps(charge), r'"(prix|cout|marge)_')
            for ligne in charge['configurations']:
                self.assertEqual(sorted(ligne), cles, nom)
                self.assertIn(ligne['role'], ('retenue', 'plus_puissant',
                                              'moins_puissant'))
                self.assertIn(ligne['verdict'], ('conforme', 'alerte',
                                                 'bloquant', 'indetermine'))
                if ligne['ratio_dc_ac'] is None:
                    self.assertTrue(ligne['manquantes'], nom)
                else:
                    self.assertEqual(ligne['ratio_dc_ac'], round(
                        ligne['puissance_dc_kwc']
                        / ligne['puissance_ac_totale_kw'], 2), nom)
            for fiche in charge['fiches_incompletes']:
                self.assertEqual(sorted(fiche), ['champs_manquants', 'libelle',
                                                 'produit_id'])
        vide = donnees['exemple_vide']
        self.assertEqual((vide['retenue'], vide['configurations']),
                         (None, []))
        self.assertTrue(vide['motif_vide'])
        self.assertEqual(
            donnees['exemple_indetermine']['configurations'][0]['verdict'],
            'indetermine')


class CheminDeclareTest(unittest.TestCase):
    """Renommer une route sans toucher l'échantillon échoue ICI."""

    def test_chaque_chemin_du_module_existe_dans_les_sources(self):
        sources = _sources_de_routes()
        for chemin in _echantillons():
            donnees = _charger(chemin.name)
            _verbe, _, route = donnees['endpoint'].partition(' ')
            if route.startswith(HORS_MODULE):
                continue
            if chemin.name in POSES_AVANT_LEUR_ROUTE:
                continue
            segment = route.rstrip('/').rsplit('/', 1)[-1]
            if segment.startswith('<'):        # ``calepinages/<int:pk>/``
                continue
            # CALX345 — ``or f"/{segment}'"`` : une sous-route à paramètre
            # (``url_path=r'versions/(?P<version_id>[^/.]+)/diff'``) se
            # termine par son segment, sans ``/`` final.
            self.assertTrue(
                f"url_path='{segment}'" in sources
                or f"'{segment}/'" in sources
                or f"{segment}/'" in sources
                or f"/{segment}'" in sources
                # ACAL12 — la collection elle-même (``POST calepinages/``) est
                # déclarée par le routeur DRF.
                or f"register(r'{segment}'" in sources,
                f"{chemin.name} : le chemin « {route} » n'est déclaré nulle "
                f"part dans urls.py ni dans une @action du module "
                f"(segment cherché : « {segment} »).")


class ClesServiesTest(unittest.TestCase):
    """La comparaison qui ÉCHOUE EN NOMMANT la clé divergente."""

    def _comparer(self, nom, servi, cle_exemple='exemple'):
        attendu = set(_charger(nom)[cle_exemple])
        obtenu = set(servi)
        en_attente = set(CLES_POSEES_AVANT_LEUR_PRODUCTEUR.get(nom, {}))
        self.assertEqual(
            sorted(en_attente & obtenu), [],
            f"{nom} : le producteur sert désormais "
            f"{sorted(en_attente & obtenu)} — retirer ces clés de "
            "CLES_POSEES_AVANT_LEUR_PRODUCTEUR.")
        attendu -= en_attente
        self.assertEqual(
            sorted(attendu - obtenu), [],
            f"{nom} : le serveur ne sert PAS la ou les clés "
            f"{sorted(attendu - obtenu)} que l'échantillon promet.")
        self.assertEqual(
            sorted(obtenu - attendu), [],
            f"{nom} : le serveur sert la ou les clés "
            f"{sorted(obtenu - attendu)} que l'échantillon ignore.")

    def test_equipements(self):
        self._comparer('calepinage_equipements.json',
                       equipements_du_calepinage(Faux()))
        self._comparer('calepinage_equipements.json',
                       equipements_du_calepinage(Faux()), 'exemple_vide')

    def test_gabarit_publie(self):
        # ACAL238 — la porte gabarits-dossiers/ publie chaque gabarit par
        # ``gabarit_publie`` (couple vue <-> échantillon) : mêmes clés que
        # ``detail.exemple``, et que chaque élément de ``exemple.gabarits``.
        from apps.calepinage.models import GabaritDossierReglementaire
        from apps.calepinage.services.reglementaire import gabarit_publie

        servi = set(gabarit_publie(GabaritDossierReglementaire(
            pays='ma', code='raccordement_bt', intitule='Dossier')))
        echantillon = _charger('gabarits_dossier_reglementaire.json')
        self.assertEqual(sorted(servi),
                         sorted(echantillon['detail']['exemple']))
        self.assertEqual(sorted(servi),
                         sorted(echantillon['exemple']['gabarits'][0]))
        self.assertEqual(sorted(servi),
                         sorted(echantillon['exemple_post_201']['gabarit']))

    def test_dossiers_reglementaires(self):
        servi = _composer_dossiers(calepinage_id=1, pays='ma', entrees=[],
                                   infos={})
        self._comparer('dossiers_reglementaires.json', servi)
        self._comparer('dossiers_reglementaires.json', servi, 'exemple_vide')

    def test_profil_de_depart(self):
        # ACAL403 — le GET rend le fichier ``data/profil_depart.json``, chaque
        # valeur avec son ``etat`` : mêmes clés que l'échantillon d'ACAL387,
        # chaque ligne de valeur aussi.
        from apps.calepinage.services.profil_depart import charger_profil
        from apps.calepinage.views.profil_depart import _avec_etats

        servi = _avec_etats(charger_profil(), None)
        self._comparer('calepinage_profil_depart.json', servi)
        attendu = _charger('calepinage_profil_depart.json')['exemple']
        for liste in ('valeurs', 'sans_source'):
            for ligne in servi[liste]:
                self.assertEqual(sorted(ligne), sorted(attendu[liste][0]))

    def test_parametres_de_societe(self):
        # ``kits`` est une clé DÉRIVÉE (CAL246), publiée par la vue et jamais
        # stockée : le sélecteur ne la rend pas, le contrat la porte.
        servi = dict(parametres_de_societe(None))
        for lecture_seule in SECTIONS_LECTURE_SEULE:
            servi[lecture_seule] = []
        self._comparer('parametres_calepinage.json', servi)
        self._comparer('parametres_calepinage.json', servi, 'exemple_vide')
        self.assertEqual(sorted(parametres_de_societe(None)),
                         sorted(SECTIONS_PARAMETRES))

    def test_raccordement(self):
        # CALX244 — ``bloc_raccordement`` est PUR : une conception absente,
        # aucun tronçon, aucun réglage, et les trois blocs sortent quand
        # même (les cinq verdicts omis en nommant ce qui manque).
        servi = bloc_raccordement(None, {}, [], {})
        self._comparer('calepinage_raccordement.json', servi)
        self._comparer('calepinage_raccordement.json', servi, 'exemple_vide')

    def test_masse_lestage(self):
        # CALX17 — ``masse_et_lestage`` sur un calepinage NU ne touche
        # aucune base : ni devis, ni document, ni produit désigné.
        servi = masse_et_lestage(Faux())
        self._comparer('calepinage_masse_lestage.json', servi)
        self._comparer('calepinage_masse_lestage.json', servi,
                       'exemple_vide')

    def test_modules_disponibles(self):
        # CALX109 — le service est PUR : la vue lui passe le QuerySet des
        # produits MODULE de la société, il n'en requête aucun lui-même.
        servi = modules_disponibles_du_calepinage(Faux(), [])
        self._comparer('calepinage_modules_disponibles.json', servi)
        self._comparer('calepinage_modules_disponibles.json', servi,
                       'exemple_vide')

    def test_entree_electrique(self):
        # ACAL56 — calepinage nu : aucune société, aucun devis, aucune base.
        from apps.calepinage.services.electrique import (
            entree_electrique_servie,
        )

        servi = entree_electrique_servie(Faux(), {})
        self._comparer('calepinage_entree_electrique.json', servi)
        self._comparer('calepinage_entree_electrique.json', servi,
                       'exemple_vide')

    def test_site_imagerie(self):
        # Cet échantillon décrit la SECTION « imagerie » (CAL46) à l'intérieur
        # de la réponse des réglages : ses sections sont donc un SOUS-ENSEMBLE
        # des sections servies, et ses ``cles`` sont celles du service.
        donnees = _charger('site_imagerie.json')
        for etat in ('exemple', 'exemple_vide',
                     'exemple_section_declaree_sans_valeur'):
            absentes = set(donnees[etat]) - set(SECTIONS_PARAMETRES)
            self.assertEqual(
                sorted(absentes), [],
                f"site_imagerie.json ({etat}) : section(s) {sorted(absentes)} "
                "que le serveur ne sert pas.")
        self.assertEqual(list(donnees['cles']), list(site.CLES))
        self.assertEqual(sorted(site.section_vide()), sorted(donnees['cles']))
        # ``site_effectif`` est une clé de la section ``imagerie`` posée par
        # ACAL8 avant son producteur (CLES_POSEES_AVANT_LEUR_PRODUCTEUR).
        en_attente = set(CLES_POSEES_AVANT_LEUR_PRODUCTEUR['site_imagerie.json'])
        self.assertEqual(sorted(en_attente & set(site.CLES)), [],
                         'site.CLES sert désormais la clé en attente : '
                         'retirer son entrée.')
        self.assertEqual(
            sorted(set(donnees['exemple_section_declaree_sans_valeur']
                       ['imagerie']) - en_attente),
            sorted(site.CLES))


class RegistreLestageTest(unittest.TestCase):
    """ACAL572 — ``registre.lestage`` : les lignes de l'écran « Lestage »,
    dérivées des dictionnaires du service, jamais d'une liste figée."""

    def test_lignes_derivees_hors_constantes_physiques(self):
        from apps.calepinage.selectors import registre_des_reglages
        from apps.calepinage.services.lestage import (
            CONSTANTES_PHYSIQUES, PARAMETRES,
        )
        from apps.calepinage.services.lestage_zones import (
            PARAMETRES_ZONES_DE_POSE,
        )

        lignes = registre_des_reglages()['lestage']
        cles = [ligne['cle'] for ligne in lignes]
        self.assertEqual(
            len(lignes),
            len(PARAMETRES) - len(CONSTANTES_PHYSIQUES)
            + len(PARAMETRES_ZONES_DE_POSE))
        self.assertFalse(set(cles) & set(CONSTANTES_PHYSIQUES))
        self.assertEqual(len(set(cles)), len(cles))
        for ligne in lignes:
            self.assertEqual(
                set(ligne), {'cle', 'libelle', 'unite', 'texte', 'bloc'})
            self.assertIn(ligne['bloc'], ('global', 'zones_de_pose'))
        self.assertEqual(
            [ligne['cle'] for ligne in lignes
             if ligne['bloc'] == 'zones_de_pose'],
            list(PARAMETRES_ZONES_DE_POSE))
        self.assertEqual(
            [ligne['cle'] for ligne in lignes if ligne['texte']],
            ['categorie_terrain'])

    def test_le_contrat_publie_la_meme_liste_dans_les_deux_etats(self):
        from apps.calepinage.selectors import registre_des_reglages

        contrat = _charger('parametres_calepinage.json')
        attendu = registre_des_reglages()['lestage']
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(contrat[etat]['registre']['lestage'], attendu)
