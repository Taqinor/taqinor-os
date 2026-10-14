"""ACHT76 (C-ACHT-072) — unicité PAR SOCIÉTÉ validée dans les sérialiseurs des
six référentiels de chantier : 400 en français sous le champ au lieu d'un 500
(IntegrityError) ; la même clé dans une AUTRE société reste acceptée ; un
PATCH qui garde sa propre clé reste 200.

Rejoue COUT-7 : les 6 doublons répondaient `500 server_error`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht76_unicite_referentiels"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ChecklistEtapeModele, ChecklistTemplate, Equipe,
    FicheInterventionTemplate, SafetyChecklistSlot, ShotListSlot,
    StageModele,
)

User = get_user_model()
BASE = '/api/django/installations'


def _api(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class UniciteReferentielsTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACHT76', slug='acht76-co')
        self.autre = Company.objects.create(nom='ACHT76 B', slug='acht76-b')
        self.admin = User.objects.create_user(
            username='admin-acht76', password='x', company=self.co,
            role_legacy='admin')
        self.admin_b = User.objects.create_user(
            username='admin-b-acht76', password='x', company=self.autre,
            role_legacy='admin')
        self.api = _api(self.admin)
        StageModele.objects.create(
            company=self.co, cle='etude_site', libelle='Étude', ordre=1)
        ShotListSlot.objects.create(
            company=self.co, cle='toit_avant', libelle='Toit avant',
            phase='avant')
        SafetyChecklistSlot.objects.create(
            company=self.co, cle='epi', libelle='EPI')
        self.tpl = ChecklistTemplate.objects.create(
            company=self.co, nom='Défaut')
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.tpl, cle='etape1', libelle='E1')
        FicheInterventionTemplate.objects.create(
            company=self.co, nom='Pose', type_intervention='pose')
        Equipe.objects.create(company=self.co, nom='E1')

    def _cas(self, tpl_id):
        return [
            ('etapes-chantier', {'cle': 'etude_site', 'libelle': 'X',
                                 'ordre': 5}, 'cle'),
            ('shotlist-slots', {'cle': 'toit_avant', 'libelle': 'X',
                                'phase': 'avant'}, 'cle'),
            ('consignes-securite', {'cle': 'epi', 'libelle': 'X'}, 'cle'),
            ('checklist-etapes', {'template': tpl_id, 'cle': 'etape1',
                                  'libelle': 'X'}, 'cle'),
            ('fiche-intervention-templates', {
                'nom': 'Autre', 'type_intervention': 'pose'},
             'type_intervention'),
            ('equipes', {'nom': 'E1'}, 'nom'),
        ]

    def test_doublons_409_sous_le_champ(self):
        # ERR-ENF11-FUZZ-INSTALLATIONS — un doublon est un CONFLIT de données
        # (409 unique_conflict), plus un 400 « données invalides » : le corps
        # reste rangé sous le champ (écrans inchangés).
        for route, corps, champ in self._cas(self.tpl.id):
            r = self.api.post(f'{BASE}/{route}/', corps, format='json')
            self.assertEqual(r.status_code, 409, (route, r.data))
            self.assertIn(champ, r.data, route)
            self.assertEqual(r.data['error']['code'], 'unique_conflict', route)
        self.assertEqual(StageModele.objects.filter(company=self.co).count(), 1)
        self.assertEqual(Equipe.objects.filter(company=self.co).count(), 1)

    def test_cle_protegee_409_sous_le_champ(self):
        # ERR-ENF11-FUZZ-INSTALLATIONS — renommer la clé d'une étape PROTÉGÉE
        # est refusé par l'état de l'étape (409), corps sous `cle`.
        etape = ChecklistEtapeModele.objects.create(
            company=self.co, template=self.tpl, cle='systeme', libelle='S',
            protege=True)
        r = self.api.patch(f'{BASE}/checklist-etapes/{etape.id}/',
                           {'cle': 'autre'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('cle', r.data)
        etape.refresh_from_db()
        self.assertEqual(etape.cle, 'systeme')

    def test_autre_societe_accepte(self):
        api_b = _api(self.admin_b)
        tpl_b = ChecklistTemplate.objects.create(
            company=self.autre, nom='Défaut B')
        for route, corps, _champ in self._cas(tpl_b.id):
            r = api_b.post(f'{BASE}/{route}/', corps, format='json')
            self.assertEqual(r.status_code, 201, (route, r.data))

    def test_patch_garde_sa_cle(self):
        etape = StageModele.objects.get(company=self.co, cle='etude_site')
        r = self.api.patch(f'{BASE}/etapes-chantier/{etape.id}/',
                           {'cle': 'etude_site', 'libelle': 'Renommée'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        equipe = Equipe.objects.get(company=self.co, nom='E1')
        r = self.api.patch(f'{BASE}/equipes/{equipe.id}/',
                           {'nom': 'E1', 'description': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    # ERR-ENF11-FUZZ-INSTALLATIONS — texte et booléens des référentiels sont
    # STRICTS : ``0`` pour une chaîne ou un booléen = 400 nommant le champ (le
    # schéma les déclare ``string`` / ``boolean``, DRF les convertissait).
    def test_nombre_pour_texte_ou_booleen_400(self):
        for url, corps, champ in (
                ('equipes/', {'nom': 'E strict', 'description': 0},
                 'description'),
                ('shotlist-slots/',
                 {'cle': 'k-strict', 'libelle': 'L', 'actif': 0}, 'actif'),
                ('sous-traitants/',
                 {'raison_sociale': 'ST strict', 'note': 0}, 'note'),
                ('sous-traitants/',
                 {'raison_sociale': 'ST strict', 'actif': 1}, 'actif')):
            with self.subTest(url=url, champ=champ):
                r = self.api.post(f'{BASE}/{url}', corps, format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(champ, r.data)

    def test_motif_texte_publie_egale_refus_drf(self):
        # ERR-ENF11-FUZZ-INSTALLATIONS — `nom: " "` (rogné en vide puis
        # refusé) était conforme au schéma : la règle partagée de
        # core.champs_stricts publie, côté requête, un motif qui accepte
        # EXACTEMENT ce que DRF accepte (NUL refusé ; blanc rogné refusé quand
        # le champ est obligatoire non blanc).
        import re

        from rest_framework.exceptions import ValidationError

        from core.champs_stricts import (
            MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, ChaineStricte,
            _ChaineSansNul)
        for valeur in ('ok', ' x ', ' ', '  ', '', 'a\x00b', '\x00',
                       ' z', '\t\n'):
            for champ, motif in ((ChaineStricte(), MOTIF_NON_BLANC_SANS_NUL),
                                 (ChaineStricte(allow_blank=True),
                                  MOTIF_SANS_NUL)):
                try:
                    champ.run_validation(valeur)
                    accepte = True
                except ValidationError:
                    accepte = False
                with self.subTest(valeur=valeur, motif=motif):
                    self.assertEqual(bool(re.search(motif, valeur)), accepte)

        class _Schema:
            @staticmethod
            def _map_serializer_field(champ, direction, bypass_extensions):
                return {'type': 'string'}
        ext = _ChaineSansNul(ChaineStricte())
        self.assertEqual(
            ext.map_serializer_field(_Schema, 'request')['pattern'],
            MOTIF_NON_BLANC_SANS_NUL)
        self.assertNotIn(
            'pattern', ext.map_serializer_field(_Schema, 'response'))
