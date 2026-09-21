"""CAL12 — rattacher après coup un calepinage à un devis.

SOLMVP15 — ce module couvrait AUSSI le rattachement à une affaire d'appel
d'offres. C'était un PONT vers une app qui sort du produit : il est retiré,
et ses tests avec lui. Le rattachement au DEVIS — la voie du produit — est
couvert ici exactement comme avant.

Ce qui est prouvé ici :

* un calepinage né sans devis (porte autonome) se rattache plus tard, et il
  hérite alors du client/lead du devis s'il n'en avait pas ;
* le DOUBLE rattachement est refusé avec un message qui NOMME le calepinage
  déjà lié — sans son nom, l'utilisateur ne peut rien faire du refus ;
* un devis d'une AUTRE société est INTROUVABLE (on ne confirme jamais
  l'existence de la donnée d'autrui) ;
* rattacher au MÊME devis est NEUTRE (ré-envoyer la demande n'est pas une
  erreur) ;
* `Devis.statut` est strictement inchangé avant/après (règle #4).

Run :
    python manage.py test apps.calepinage.tests.test_services_liens -v2
"""
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.liens import LiaisonRefusee, lier_devis
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company


class BaseLiens(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Liens Co', slug='liens-co')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-12')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.client_b = Client.objects.create(company=self.autre,
                                              nom='Bâtiment Rif')
        self.lead_a = Lead.objects.create(company=self.company,
                                          nom='Toiture Anfa')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead_a,
            reference='DEV-202609-0010')
        self.devis_etranger = Devis.objects.create(
            company=self.autre, client=self.client_b,
            reference='DEV-202609-0011')
        self.autonome = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_a.pk,
            titre='Toiture Anfa')


class LierDevisTest(BaseLiens):
    def test_rattachement_tardif(self):
        lier_devis(self.autonome, self.devis.pk)
        self.autonome.refresh_from_db()
        self.assertEqual(self.autonome.devis_id, self.devis.pk)

    def test_herite_du_client_du_devis(self):
        self.assertIsNone(self.autonome.client_id)
        lier_devis(self.autonome, self.devis.pk)
        self.autonome.refresh_from_db()
        self.assertEqual(self.autonome.client_id, self.client_a.pk)

    def test_rattacher_au_meme_devis_est_neutre(self):
        lier_devis(self.autonome, self.devis.pk)
        lier_devis(self.autonome, self.devis.pk)
        self.autonome.refresh_from_db()
        self.assertEqual(self.autonome.devis_id, self.devis.pk)

    def test_double_rattachement_refuse_en_nommant_le_calepinage(self):
        premier = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Première conception', devis=self.devis)
        with self.assertRaises(LiaisonRefusee) as capture:
            lier_devis(self.autonome, self.devis.pk)
        message = str(capture.exception)
        self.assertEqual(capture.exception.champ, 'devis')
        self.assertIn('Première conception', message)
        self.assertIn(str(premier.pk), message)

    def test_double_rattachement_n_ecrit_rien(self):
        Calepinage.objects.create(company=self.company, client=self.client_a,
                                  titre='Première', devis=self.devis)
        with self.assertRaises(LiaisonRefusee):
            lier_devis(self.autonome, self.devis.pk)
        self.autonome.refresh_from_db()
        self.assertIsNone(self.autonome.devis_id)

    def test_devis_d_une_autre_societe_introuvable(self):
        with self.assertRaises(LiaisonRefusee) as capture:
            lier_devis(self.autonome, self.devis_etranger.pk)
        self.assertEqual(capture.exception.champ, 'devis')
        self.assertIn('introuvable', str(capture.exception))

    def test_statut_du_devis_inchange(self):
        avant = Devis.objects.get(pk=self.devis.pk).statut
        lier_devis(self.autonome, self.devis.pk)
        self.assertEqual(Devis.objects.get(pk=self.devis.pk).statut, avant)

    def test_devis_absent_refuse(self):
        with self.assertRaises(LiaisonRefusee) as capture:
            lier_devis(self.autonome, None)
        self.assertEqual(capture.exception.champ, 'devis')


class CalepinageNonEnregistreTest(BaseLiens):
    def test_refus_explicite(self):
        vierge = Calepinage(company=self.company, lead_id=1)
        with self.assertRaises(LiaisonRefusee) as capture:
            lier_devis(vierge, self.devis.pk)
        self.assertEqual(capture.exception.champ, 'calepinage')
