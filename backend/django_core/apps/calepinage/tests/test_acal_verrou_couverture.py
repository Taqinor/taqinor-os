"""ACAL43 (C-ACAL-097) — le verrou unique couvre TOUTES les écritures de
conception, jamais la simulation ni la pose réelle.

Ce qui est prouvé ici, par HTTP réel :

* devis lié ACCEPTÉ : variantes (créer, modifier, supprimer, retenir),
  pertes, entrée électrique, édition du schéma unifilaire, raccordement,
  approbation et rendu répondent 409 ``{<champ>: [motif ventes]}`` et rien
  n'est écrit ;
* la simulation et la pose réelle restent permises (jamais 409) ;
* devis ENVOYÉ (corrigeable, D-QJR5-5) : enregistrer des pertes → 200 et
  une ligne de journal « Postes de pertes modifiés : iam 3 → 12 ».

Run :
    python manage.py test apps.calepinage.tests.test_acal_verrou_couverture -v2
"""
import copy

from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00'
       b'\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc'
       b'\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
MOTIF = 'Devis accepté : révisez-le'


def _poste(poste, pct):
    return {'poste': poste, 'libelle': poste, 'pct': pct,
            'source': None, 'mensuel': None}


class VerrouCouvertureTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL43-1', statut=Devis.Statut.BROUILLON)
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis,
            titre='ACAL43', roof_layout={'panels': 4})
        self.a = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A',
            roof_layout={'panels': 4})
        self.b = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B',
            roof_layout={'panels': 6})

    def _statut(self, statut):
        Devis.objects.filter(pk=self.devis.pk).update(statut=statut)

    def _etat(self):
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        variantes = sorted(CalepinageVariante.objects
                           .filter(calepinage=cal)
                           .values_list('pk', 'nom', 'retenue'))
        return (copy.deepcopy(cal.pertes), copy.deepcopy(cal.resultat),
                copy.deepcopy(cal.approbation), cal.roof_image, variantes)

    def _routes(self):
        base = url_detail(self.calepinage.pk)
        return [
            ('variantes POST', 'post', f'{base}variantes/', {'nom': 'C'},
             'variante'),
            ('variante PATCH', 'patch', f'{base}variantes/{self.b.pk}/',
             {'nom': 'B2'}, 'variante'),
            ('variante DELETE', 'delete', f'{base}variantes/{self.b.pk}/',
             None, 'variante'),
            ('retenir', 'post', f'{base}variantes/{self.b.pk}/retenir/', {},
             'variante'),
            ('pertes', 'post', f'{base}enregistrer-pertes/',
             {'postes': [_poste('iam', 12)]}, 'pertes'),
            ('entree electrique', 'post', f'{base}entree-electrique/',
             {'dc_m': 55}, 'entree_electrique'),
            ('schema unifilaire', 'post', f'{base}schema-unifilaire/',
             {'textes': {}}, 'sld_edition'),
            ('raccordement', 'post', f'{base}raccordement/', {},
             'raccordement'),
            ('approbation', 'post', f'{base}approbation/',
             {'decision': 'approuve'}, 'approbation'),
        ]

    def test_accepte_refuse_chaque_ecriture(self):
        self._statut(Devis.Statut.ACCEPTE)
        avant = self._etat()
        for nom, methode, url, corps, champ in self._routes():
            with self.subTest(route=nom):
                appel = getattr(self.api, methode)
                reponse = (appel(url, corps, format='json')
                           if corps is not None else appel(url))
                self.assertEqual(reponse.status_code, 409,
                                 (nom, reponse.status_code,
                                  getattr(reponse, 'data', None)))
                self.assertIn(champ, reponse.data)
                self.assertIn(MOTIF, str(reponse.data[champ]))
                self.assertEqual(self._etat(), avant)
        with self.subTest(route='roof-image'):
            reponse = self.api.post(
                f'{url_detail(self.calepinage.pk)}roof-image/',
                {'image': SimpleUploadedFile('rendu.png', PNG,
                                             content_type='image/png')},
                format='multipart')
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertIn('image', reponse.data)
            self.assertEqual(self._etat(), avant)

    def test_simulation_et_pose_reelle_restent_permises(self):
        self._statut(Devis.Statut.ACCEPTE)
        base = url_detail(self.calepinage.pk)
        reponse = self.api.post(f'{base}simuler/', {}, format='json')
        self.assertNotEqual(reponse.status_code, 409, reponse.data)
        reponse = self.api.get(f'{base}pose-reelle/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        reponse = self.api.post(f'{base}pose-reelle/',
                                {'creer_version': True}, format='json')
        self.assertNotEqual(reponse.status_code, 409, reponse.data)

    def test_envoye_pertes_journalisees(self):
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            pertes=[_poste('iam', 3)])
        self._statut(Devis.Statut.ENVOYE)
        ct = ContentType.objects.get_for_model(Calepinage)
        avant = Activity.objects.filter(
            content_type=ct, object_id=self.calepinage.pk).count()
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}enregistrer-pertes/',
            {'postes': [_poste('iam', 12)]}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = Activity.objects.filter(
            content_type=ct, object_id=self.calepinage.pk)
        self.assertEqual(lignes.count(), avant + 1)
        derniere = lignes.order_by('-id').first()
        self.assertIn('Postes de pertes modifiés : iam 3 → 12',
                      derniere.body)
        self.assertEqual(derniere.created_by_id, self.user.pk)
