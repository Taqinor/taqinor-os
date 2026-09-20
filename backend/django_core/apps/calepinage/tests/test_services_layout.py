"""CAL13 — enregistrer une conception : empreinte + instantané de version.

Ce qui est prouvé ici :

* deux enregistrements IDENTIQUES → UNE seule version et ``inchange: True``
  (un double-clic ne pollue pas l'historique) ;
* un layout MODIFIÉ → une version de plus, et le NOUVEAU hash est lisible sur
  le pivot ;
* l'empreinte est EXACTEMENT celle de ``apps.ventes.services.layout_hash`` —
  elle n'est pas recodée ici (deux empreintes pour une toiture = deux
  vérités) ;
* seul l'état de la géométrie compte : changer une clé d'interface (``pin``)
  ne crée pas de version ;
* aucun statut de devis n'est écrit (règle #4) ;
* un pivot non enregistré ou un document qui n'est pas un objet sont refusés
  en nommant le champ.

Run :
    python manage.py test apps.calepinage.tests.test_services_layout -v2
"""
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import LayoutRefuse, enregistrer_layout
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.services import layout_hash
from authentication.models import Company

LAYOUT = {'zones': [{'id': 'z1', 'panels': 12}], 'result': {'kwc': 6.9},
          'panelWatt': 575}
LAYOUT_MODIFIE = {'zones': [{'id': 'z1', 'panels': 14}],
                  'result': {'kwc': 8.05}, 'panelWatt': 575}


class BaseLayout(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Layout Co',
                                              slug='layout-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.pivot = Calepinage.objects.create(company=self.company,
                                               client=self.client_a)


class EnregistrementTest(BaseLayout):
    def test_premier_enregistrement_cree_une_version(self):
        rendu = enregistrer_layout(self.pivot, LAYOUT)
        self.assertFalse(rendu['inchange'])
        self.assertIsNotNone(rendu['version'])
        self.assertEqual(self.pivot.versions.count(), 1)

    def test_deux_enregistrements_identiques_une_seule_version(self):
        enregistrer_layout(self.pivot, LAYOUT)
        rendu = enregistrer_layout(self.pivot, LAYOUT)
        self.assertTrue(rendu['inchange'])
        self.assertIsNone(rendu['version'])
        self.assertEqual(self.pivot.versions.count(), 1)

    def test_layout_modifie_ajoute_une_version(self):
        enregistrer_layout(self.pivot, LAYOUT)
        rendu = enregistrer_layout(self.pivot, LAYOUT_MODIFIE)
        self.assertFalse(rendu['inchange'])
        self.assertEqual(self.pivot.versions.count(), 2)

    def test_nouveau_hash_lisible_sur_le_pivot(self):
        rendu = enregistrer_layout(self.pivot, LAYOUT_MODIFIE)
        relu = Calepinage.objects.get(pk=self.pivot.pk)
        self.assertEqual(relu.layout_hash, rendu['layout_hash'])
        self.assertEqual(relu.roof_layout, LAYOUT_MODIFIE)


class EmpreinteNonRecodeeTest(BaseLayout):
    def test_empreinte_identique_a_celle_des_ventes(self):
        rendu = enregistrer_layout(self.pivot, LAYOUT)
        self.assertEqual(rendu['layout_hash'], layout_hash(LAYOUT))

    def test_etat_d_interface_ne_cree_pas_de_version(self):
        """``pin`` est de l'état d'écran, pas de la géométrie."""
        enregistrer_layout(self.pivot, LAYOUT)
        avec_pin = dict(LAYOUT, pin={'lat': 33.57, 'lng': -7.58})
        rendu = enregistrer_layout(self.pivot, avec_pin)
        self.assertTrue(rendu['inchange'])
        self.assertEqual(self.pivot.versions.count(), 1)


class ChampsOptionnelsTest(BaseLayout):
    def test_resultat_et_moteur_mis_a_jour(self):
        enregistrer_layout(self.pivot, LAYOUT,
                           resultat={'kwc': 6.9}, version_moteur='v1',
                           roof_image='cle/minio.png')
        relu = Calepinage.objects.get(pk=self.pivot.pk)
        # Le résultat DÉPOSÉ est conservé tel quel…
        self.assertEqual(relu.resultat['kwc'], 6.9)
        # …et la seule clé que le chemin de layout puisse AJOUTER est le
        # verdict électrique rejoué (CAL128), qui peut ne pas être rendu
        # — jamais une autre clé inventée.
        self.assertLessEqual(set(relu.resultat) - {'kwc'},
                             {'verdict_electrique'})
        self.assertEqual(relu.version_moteur, 'v1')
        self.assertEqual(relu.roof_image, 'cle/minio.png')

    def test_none_laisse_la_valeur_en_place(self):
        enregistrer_layout(self.pivot, LAYOUT, version_moteur='v1')
        enregistrer_layout(self.pivot, LAYOUT_MODIFIE)
        relu = Calepinage.objects.get(pk=self.pivot.pk)
        self.assertEqual(relu.version_moteur, 'v1')

    def test_libelle_porte_par_la_version(self):
        rendu = enregistrer_layout(self.pivot, LAYOUT,
                                   libelle='Après visite')
        self.assertEqual(rendu['version'].libelle, 'Après visite')


class RegleQuatreTest(BaseLayout):
    def test_aucun_statut_de_devis_ecrit(self):
        devis = Devis.objects.create(company=self.company,
                                     client=self.client_a,
                                     reference='DEV-202609-0020')
        pivot = Calepinage.objects.create(company=self.company,
                                          client=self.client_a, devis=devis)
        avant = Devis.objects.get(pk=devis.pk).statut
        enregistrer_layout(pivot, LAYOUT)
        self.assertEqual(Devis.objects.get(pk=devis.pk).statut, avant)


class RefusTest(BaseLayout):
    def test_pivot_non_enregistre(self):
        with self.assertRaises(LayoutRefuse) as capture:
            enregistrer_layout(Calepinage(company=self.company, lead_id=1),
                               LAYOUT)
        self.assertEqual(capture.exception.champ, 'calepinage')

    def test_conception_qui_n_est_pas_un_objet(self):
        with self.assertRaises(LayoutRefuse) as capture:
            enregistrer_layout(self.pivot, ['zones'])
        self.assertEqual(capture.exception.champ, 'roof_layout')
