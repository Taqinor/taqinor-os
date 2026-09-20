"""CAL26 — le chatter passe par la primitive plateforme, jamais par un maison.

Ce qui est prouvé ici :

* AUCUNE classe ``…Activity`` n'existe dans ``apps/calepinage`` (la garde
  ``apps/records/platform_guards.py`` fait rougir toute nouvelle) ;
* chacun des gestes journalisés produit EXACTEMENT une entrée
  ``records.Activity``, avec son auteur posé côté serveur et le format
  ancien → nouveau ;
* un enregistrement à l'identique ne journalise RIEN (il ne s'est rien passé) ;
* les NOTES manuelles passent par le même journal, et la lecture se fait par
  ``records`` (mixin de chatter du viewset), pas par une seconde API.

Run :
    python manage.py test apps.calepinage.tests.test_chatter -v2
"""
import pathlib
import re

from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.creation import creer_pour_lead
from apps.calepinage.services.journal import noter
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.variantes import retenir_variante
from apps.calepinage.services.versions import restaurer_version
from apps.crm.models import Client
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

V1 = {'result': {'panels': 10}}
V2 = {'result': {'panels': 12}}


class ChatterTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _entrees(self, calepinage=None):
        cible = calepinage or self.calepinage
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=cible.pk)

    def test_aucune_classe_activity_maison(self):
        motif = re.compile(r'^class\s+\w*Activity\s*\(', re.MULTILINE)
        for fichier in RACINE_APP.rglob('*.py'):
            if 'tests' in fichier.parts:
                continue
            self.assertIsNone(
                motif.search(fichier.read_text(encoding='utf-8')),
                f'{fichier.name} : une classe …Activity maison (ARC8 interdit '
                'tout chatter maison — passez par records.log_activity).')

    def test_creation_journalisee(self):
        calepinage = creer_pour_lead(self.lead.pk, self.company,
                                     user=self.user)
        entrees = self._entrees(calepinage)
        self.assertEqual(entrees.count(), 1)
        entree = entrees.first()
        self.assertEqual(entree.kind, Activity.Kind.CREATION)
        self.assertEqual(entree.created_by_id, self.user.pk)
        self.assertEqual(entree.company_id, self.company.pk)

    def test_layout_journalise_ancien_et_nouveau_nombre_de_modules(self):
        enregistrer_layout(self.calepinage, V1, user=self.user)
        enregistrer_layout(self.calepinage, V2, user=self.user)
        entrees = list(self._entrees().filter(field='roof_layout')
                       .order_by('id'))
        self.assertEqual(len(entrees), 2)
        self.assertEqual((entrees[0].old_value, entrees[0].new_value),
                         ('', '10'))
        self.assertEqual((entrees[1].old_value, entrees[1].new_value),
                         ('10', '12'))

    def test_enregistrement_a_l_identique_ne_journalise_rien(self):
        enregistrer_layout(self.calepinage, V1, user=self.user)
        avant = self._entrees().count()
        enregistrer_layout(self.calepinage, V1, user=self.user)
        self.assertEqual(self._entrees().count(), avant)

    def test_rattachement_devis_journalise(self):
        client = Client.objects.create(company=self.company, nom='Atlas 26')
        devis = Devis.objects.create(company=self.company, client=client,
                                     reference='DEV-202609-2626')
        lier_devis(self.calepinage, devis.pk, user=self.user)
        entree = self._entrees().filter(field='devis').first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, str(devis.pk))

    def test_bascule_de_variante_journalisee_par_les_noms(self):
        a = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='A')
        b = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='B')
        retenir_variante(a)
        retenir_variante(b)
        entrees = list(self._entrees().filter(field='variante')
                       .order_by('id'))
        self.assertEqual(len(entrees), 2)
        self.assertEqual((entrees[1].old_value, entrees[1].new_value),
                         ('A', 'B'))

    def test_restauration_journalisee(self):
        enregistrer_layout(self.calepinage, V1, user=self.user)
        premiere = self.calepinage.versions.order_by('id').first()
        enregistrer_layout(self.calepinage, V2, user=self.user)
        restaurer_version(premiere, user=self.user)
        entree = self._entrees().filter(field='version').first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, str(premiere.pk))

    def test_note_manuelle_et_note_vide(self):
        self.assertIsNone(noter(self.calepinage, '   ', user=self.user))
        noter(self.calepinage, 'Toiture à revoir côté ouest.', user=self.user)
        notes = self._entrees().filter(kind=Activity.Kind.NOTE)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.first().created_by_id, self.user.pk)

    def test_lecture_par_records_et_pas_une_seconde_api(self):
        noter(self.calepinage, 'Une note.', user=self.user)
        reponse = self.api.get(
            f'{url_detail(self.calepinage.pk)}chatter/historique/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(any(e.get('body') == 'Une note.'
                            for e in reponse.data))
