"""ACAL319 (C-ACAL-097, C-ACAL-096) — garde permanente : CHAQUE route
d'écriture du ``CalepinageViewSet`` est classée « sous verrou » (et répond
409 sur un devis ACCEPTÉ) ou « hors verrou » avec son motif.

Une nouvelle route d'écriture (``@action`` POST / PUT / PATCH / DELETE
rattachée au viewset, ou méthode CRUD) qui n'est dans AUCUNE des deux tables
fait échouer ``test_chaque_route_d_ecriture_est_classee`` en la NOMMANT
(classe de défaut : porte d'écriture qui contourne le verrou).

Les routes « sous verrou » sont SONDÉES en HTTP réel sur un calepinage lié à
un devis accepté : 409 + le motif ventes, rien d'écrit. Trois routes passent
par un formulaire lourd (schéma v2 strict, téléversement, cote de relevé)
AVANT d'atteindre l'écrivain unique ``services.layout.enregistrer_layout`` :
elles sont classées sous verrou en NOMMANT cet écrivain, dont le refus est
prouvé ici par ``POST layout/`` (même fonction, même refus).

Run :
    python manage.py test apps.calepinage.tests.test_acal_garde_routes_verrou -v2
"""
import copy

from django.core.files.uploadedfile import SimpleUploadedFile

import apps.calepinage.urls  # noqa: F401 — rattache les @action au viewset
from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.services.layout import (
    empreinte_document, enregistrer_layout,
)
from apps.calepinage.services.lidar_ign import CLE_SUGGESTION
from apps.calepinage.services.releve import enregistrer_releve
from apps.calepinage.views.calepinages import CalepinageViewSet
from apps.ventes.models import Devis

from .test_acal_layout_section import HORIZON
from .test_acal_verrou_couverture import MOTIF, PNG, _poste
from .test_api_liste import BaseApiCalepinage, url_detail
from .test_releve_terrain import CHAINE_FRDISI, HIER

ECRITURES = ('post', 'put', 'patch', 'delete')
VARIANTE = r'variantes/(?P<variante_id>[^/.]+)'
RELEVE = r'releve/(?P<releve_id>[^/.]+)'
PHOTO = r'photos/(?P<photo_id>[^/.]+)'

#: L'écrivain unique du document de conception : son refus (409) est sondé
#: par ``POST layout/`` ; les routes qui l'atteignent après un formulaire
#: lourd le NOMMENT au lieu d'une sonde.
PAR_ENREGISTRER_LAYOUT = ('services.layout.enregistrer_layout (refus prouvé '
                          'par POST layout/)')

#: Routes SOUS VERROU : (méthode, url_path) → nom de la sonde (méthode de
#: ``GardeRoutesVerrouTest``) ou l'écrivain nommé.
ROUTES_SOUS_VERROU = {
    ('POST', 'layout'): '_sonde_layout',
    ('POST', 'layout/section'): '_sonde_section',
    ('POST', 'import-layout'): PAR_ENREGISTRER_LAYOUT,
    ('POST', 'fond-plan'): PAR_ENREGISTRER_LAYOUT,
    ('POST', r'versions/(?P<version_id>[^/.]+)/restaurer'): '_sonde_restaurer',
    ('POST', 'recentrer-sur-lead'): '_sonde_recentrer',
    ('POST', 'garder-repere'): '_sonde_garder_repere',
    ('POST', 'suggestions-pente'): '_sonde_suggestion',
    ('POST', 'roof-image'): '_sonde_roof_image',
    ('POST', 'variantes'): '_sonde_creer_variante',
    ('PATCH', VARIANTE): '_sonde_modifier_variante',
    ('DELETE', VARIANTE): '_sonde_supprimer_variante',
    ('POST', VARIANTE + '/retenir'): '_sonde_retenir',
    ('POST', 'enregistrer-pertes'): '_sonde_pertes',
    ('POST', 'entree-electrique'): '_sonde_entree_electrique',
    ('POST', 'schema-unifilaire'): '_sonde_schema',
    ('POST', 'raccordement'): '_sonde_raccordement',
    ('POST', 'approbation'): '_sonde_approbation',
    ('PATCH', RELEVE): '_sonde_modifier_releve',
    ('DELETE', RELEVE): '_sonde_supprimer_releve',
    ('POST', RELEVE + '/appliquer-cote'): PAR_ENREGISTRER_LAYOUT,
}

#: Routes HORS VERROU, chacune avec son MOTIF (jamais vide).
ROUTES_HORS_VERROU = {
    ('POST', '<liste>'): 'création : porte unique creation.py, aucun devis '
                         'figé à protéger',
    ('PATCH', '<detail>'): 'fiche (titre, contraintes de site) et '
                           'rattachement — brouillon seulement (ACAL180) ; '
                           'non couverte par le verrou de conception',
    ('PUT', '<detail>'): '405 : remplacement complet non servi (ACAL120)',
    ('DELETE', '<detail>'): '405 : archiver est l\'unique geste (ACAL120)',
    ('POST', 'archiver'): 'archivage : son propre prédicat (devis non '
                          'brouillon refusé, ACAL118)',
    ('POST', 'restaurer-corbeille'): 'restauration depuis la corbeille',
    ('POST', 'simuler'): 'simulation : calcul, jamais une écriture de '
                         'conception (ACAL43)',
    ('POST', 'meteo-fichier'): 'simulation : entrée météo du calcul',
    ('DELETE', 'meteo-fichier'): 'simulation : entrée météo du calcul',
    ('POST', 'evaluer-electrique'): 'évaluation électrique à la demande '
                                    '(lecture calculée)',
    ('POST', 'pose-reelle'): 'pose réelle : preuve du chantier (ACAL43)',
    ('POST', 'photos'): 'photos de site',
    ('PATCH', PHOTO): 'photos de site',
    ('DELETE', PHOTO): 'photos de site',
    ('PATCH', PHOTO + '/calage'): 'photos de site (calage)',
    ('POST', 'releve'): 'relevé terrain : saisie de visite, pas la '
                        'conception',
    ('POST', 'releve-visite'): 'relevé terrain : reprise de la visite',
    ('POST', 'image-document'): 'documents : images des livrables',
    ('POST', 'dossier-fin-chantier'): 'documents : dossier de fin de chantier',
    ('POST', 'generer-dossier'): 'documents réglementaires',
    ('POST', 'champs-dossier'): 'documents réglementaires',
    ('POST', 'joindre-piece'): 'documents réglementaires',
    ('POST', 'remettre-document'): 'documents : remise d\'une pièce',
    ('POST', 'pack-technique'): 'documents : pack technique',
    ('POST', 'generer-devis'): 'chiffrage : portes ventes (modifiabilité du '
                               'devis) et approbation (ACAL116)',
    ('POST', 'sync-devis'): 'chiffrage : la règle ventes sync-layout fait foi '
                            '(409 du devis)',
    ('POST', 'chatter/noter'): 'journal : une note n\'écrit pas la conception',
    ('POST', 'etiquettes'): 'étiquettes (records.Tag), hors conception',
    ('DELETE', 'etiquettes'): 'étiquettes (records.Tag), hors conception',
    ('POST', 'marquer-modele'): 'bibliothèque : étiquette « modèle »',
    ('POST', 'demarquer-modele'): 'bibliothèque : étiquette « modèle »',
    ('POST', 'dupliquer'): 'crée une COPIE, la source n\'est pas écrite',
    ('POST', 'creer-depuis-modele'): 'création depuis un modèle',
    ('POST', 'depuis-modele'): 'création depuis un modèle',
    ('POST', 'depuis-lead'): 'création / ouverture depuis un lead',
    ('POST', 'import-projet'): 'création par import de projet',
    ('POST', 'comparer-projets'): 'lecture : le POST ne porte que des ids',
    ('POST', 'importer-plan'): 'analyse d\'un plan déposé (calques rendus, '
                               'rien d\'écrit)',
    ('POST', 'consommation/proposer'): 'proposition de consommation '
                                       '(lecture calculée)',
    ('POST', 'pompage'): 'proposition de pompage (lecture calculée)',
    ('POST', 'fixation'): 'choix du système de fixation (ACAL81) — non '
                          'couvert par le verrou (ACAL43) : à trancher',
}


def routes_d_ecriture():
    """Les (MÉTHODE, url_path) d'écriture servies par le viewset — CRUD
    compris (``<liste>`` / ``<detail>``)."""
    routes = {('POST', '<liste>'), ('PATCH', '<detail>'),
              ('PUT', '<detail>'), ('DELETE', '<detail>')}
    for action in CalepinageViewSet.get_extra_actions():
        for methode in action.mapping:
            if methode in ECRITURES:
                routes.add((methode.upper(), action.url_path))
    return routes


def _document(modules=4):
    return {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
            'zones': [{'id': 'z1', 'label': 'Pan Sud',
                       'geometry': {'count': modules, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0},
                       CLE_SUGGESTION: {'status': 'suggeree',
                                        'pitchDeg': 20.0}}]}


class GardeRoutesVerrouTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.lead.gps_lat = 33.60
        self.lead.gps_lng = -7.62
        self.lead.save(update_fields=['gps_lat', 'gps_lng'])
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL319-1', statut=Devis.Statut.BROUILLON)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            titre='ACAL319')
        enregistrer_layout(self.calepinage, _document(4), user=self.user)
        enregistrer_layout(self.calepinage, _document(6), user=self.user)
        self.version = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).order_by('id').first()
        self.a = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout=_document(4))
        self.b = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B',
            roof_layout=_document(6))
        self.releve = enregistrer_releve(
            self.calepinage, {'releve_le': HIER.isoformat(),
                              'chaines': [CHAINE_FRDISI]}, user=self.user)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            devis=self.devis)
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ACCEPTE)
        self.calepinage.refresh_from_db()
        self.base = url_detail(self.calepinage.pk)

    # ── les sondes : un corps VALIDE, le refus attendu est le verrou ──────
    def _post(self, suffixe, corps):
        return self.api.post(f'{self.base}{suffixe}', corps, format='json')

    def _jeton(self):
        return empreinte_document(Calepinage.objects.get(
            pk=self.calepinage.pk).roof_layout)

    def _sonde_layout(self):
        return self._post('layout/', {'roof_layout': _document(9)})

    def _sonde_section(self):
        return self._post('layout/section/', {
            'cle': 'horizonProfile', 'valeur': copy.deepcopy(HORIZON),
            'base_empreinte': self._jeton()})

    def _sonde_restaurer(self):
        return self._post(f'versions/{self.version.pk}/restaurer/', {})

    def _sonde_recentrer(self):
        return self._post('recentrer-sur-lead/', {})

    def _sonde_garder_repere(self):
        return self._post('garder-repere/', {})

    def _sonde_suggestion(self):
        return self._post('suggestions-pente/', {
            'operation': 'refuser', 'zone_id': 'z1',
            'base_empreinte': self._jeton()})

    def _sonde_roof_image(self):
        return self.api.post(
            f'{self.base}roof-image/',
            {'image': SimpleUploadedFile('rendu.png', PNG,
                                         content_type='image/png')},
            format='multipart')

    def _sonde_creer_variante(self):
        return self._post('variantes/', {'nom': 'C'})

    def _sonde_modifier_variante(self):
        return self.api.patch(f'{self.base}variantes/{self.b.pk}/',
                              {'nom': 'B2'}, format='json')

    def _sonde_supprimer_variante(self):
        return self.api.delete(f'{self.base}variantes/{self.b.pk}/')

    def _sonde_retenir(self):
        return self._post(f'variantes/{self.b.pk}/retenir/', {})

    def _sonde_pertes(self):
        return self._post('enregistrer-pertes/',
                          {'postes': [_poste('iam', 12)]})

    def _sonde_entree_electrique(self):
        return self._post('entree-electrique/', {'dc_m': 55})

    def _sonde_schema(self):
        return self._post('schema-unifilaire/', {'textes': {}})

    def _sonde_raccordement(self):
        return self._post('raccordement/', {})

    def _sonde_approbation(self):
        return self._post('approbation/', {'decision': 'approuve'})

    def _sonde_modifier_releve(self):
        return self.api.patch(f'{self.base}releve/{self.releve.pk}/',
                              {'notes': 'après'}, format='json')

    def _sonde_supprimer_releve(self):
        return self.api.delete(f'{self.base}releve/{self.releve.pk}/')

    # ── la garde ────────────────────────────────────────────────────────────
    def test_chaque_route_d_ecriture_est_classee(self):
        servies = routes_d_ecriture()
        classees = set(ROUTES_SOUS_VERROU) | set(ROUTES_HORS_VERROU)
        non_classees = sorted(servies - classees)
        self.assertEqual(
            non_classees, [],
            'route(s) d\'écriture NON classée(s) — ajoutez-la(les) à '
            'ROUTES_SOUS_VERROU (avec sa sonde 409) ou à ROUTES_HORS_VERROU '
            f'(avec son motif) : {non_classees}')
        self.assertEqual(sorted(classees - servies), [],
                         'route(s) classée(s) qui n\'existe(nt) plus')
        self.assertEqual(
            sorted(set(ROUTES_SOUS_VERROU) & set(ROUTES_HORS_VERROU)), [])
        for route, motif in ROUTES_HORS_VERROU.items():
            self.assertTrue(str(motif).strip(), f'{route} : motif vide')

    def test_routes_sous_verrou_repondent_409_sur_accepte(self):
        avant = Calepinage.objects.get(pk=self.calepinage.pk)
        variantes = sorted(CalepinageVariante.objects
                           .filter(calepinage=self.calepinage)
                           .values_list('pk', 'nom', 'retenue'))
        for route, sonde in ROUTES_SOUS_VERROU.items():
            if sonde == PAR_ENREGISTRER_LAYOUT:
                continue
            with self.subTest(route=route):
                reponse = getattr(self, sonde)()
                self.assertEqual(reponse.status_code, 409,
                                 (route, getattr(reponse, 'data', None)))
                self.assertIn(MOTIF, str(reponse.data))
        apres = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertEqual(apres.roof_layout, avant.roof_layout)
        self.assertEqual(apres.pertes, avant.pertes)
        self.assertEqual(apres.approbation, avant.approbation)
        self.assertEqual(apres.roof_image, avant.roof_image)
        self.assertEqual(sorted(CalepinageVariante.objects
                                .filter(calepinage=self.calepinage)
                                .values_list('pk', 'nom', 'retenue')),
                         variantes)
