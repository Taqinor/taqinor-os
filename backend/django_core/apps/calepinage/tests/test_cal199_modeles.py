"""CAL199 — marquer un calepinage comme MODÈLE réutilisable.

Ce qui est prouvé ici :

* le drapeau se pose, se lit et se retire — réversible, journalisé (CAL26) ;
* ``creer_depuis_modele`` appelle ``dupliquer`` (CAL14, service unique) puis
  détache tout ce qui est commercial : le nouveau projet ne porte NI le
  client, NI le lead, NI le devis, NI l'image, NI l'historique du modèle ;
* sans nouveau lead/client fourni, la création depuis un modèle est refusée
  en nommant le champ (un calepinage exige toujours au moins l'un des deux) ;
* un calepinage non marqué « modèle » refuse d'en servir un.

Run :
    python manage.py test apps.calepinage.tests.test_cal199_modeles -v2
"""
from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.modeles import (
    ModeleInvalide, calepinages_modeles, creer_depuis_modele, demarquer_modele,
    est_modele, marquer_modele,
)
from apps.crm.models import Client, Lead
from authentication.models import Company


class DrapeauModeleTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Modeles Co',
                                              slug='modeles-co-199')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=42, titre='Villa type')

    def test_pas_modele_par_defaut(self):
        self.assertFalse(est_modele(self.calepinage))

    def test_marquer_puis_lire(self):
        marquer_modele(self.calepinage)
        self.assertTrue(est_modele(self.calepinage))

    def test_marquer_est_idempotent(self):
        marquer_modele(self.calepinage)
        marquer_modele(self.calepinage)
        self.assertTrue(est_modele(self.calepinage))

    def test_demarquer_retire_le_drapeau(self):
        marquer_modele(self.calepinage)
        demarquer_modele(self.calepinage)
        self.assertFalse(est_modele(self.calepinage))

    def test_calepinages_modeles_liste_uniquement_les_marques(self):
        autre = Calepinage.objects.create(
            company=self.company, lead_id=43, titre='Non modèle')
        marquer_modele(self.calepinage)
        ids = set(calepinages_modeles(self.company).values_list('pk', flat=True))
        self.assertIn(self.calepinage.pk, ids)
        self.assertNotIn(autre.pk, ids)

    def test_isolation_multi_societe(self):
        autre_company = Company.objects.create(nom='Autre Co',
                                               slug='autre-co-199')
        marquer_modele(self.calepinage)
        self.assertEqual(calepinages_modeles(autre_company).count(), 0)


class CreerDepuisModeleTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Depuis Modele Co',
                                              slug='depuis-modele-co-199')
        self.lead_modele = Lead.objects.create(company=self.company,
                                               nom='Lead du modèle')
        self.modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_modele.pk,
            titre='Villa type', roof_layout={'foo': 'bar'},
            layout_hash='a' * 64)
        CalepinageVersion.objects.create(
            company=self.company, calepinage=self.modele,
            roof_layout={'foo': 'bar'}, layout_hash='a' * 64)
        self.lead_client = Lead.objects.create(company=self.company,
                                               nom='Nouveau lead')

    def test_refuse_si_pas_marque_modele(self):
        with self.assertRaises(ModeleInvalide) as ctx:
            creer_depuis_modele(self.modele, lead_id=self.lead_client.pk)
        self.assertEqual(ctx.exception.champ, 'modele')

    def test_refuse_sans_nouveau_rattachement(self):
        marquer_modele(self.modele)
        with self.assertRaises(ModeleInvalide) as ctx:
            creer_depuis_modele(self.modele)
        self.assertEqual(ctx.exception.champ, 'client')

    def test_cree_sans_copier_le_commercial_du_modele(self):
        marquer_modele(self.modele)
        client_a = Client.objects.create(company=self.company, nom='Client A')
        copie = creer_depuis_modele(self.modele, client_id=client_a.pk)

        self.assertEqual(copie.client_id, client_a.pk)
        self.assertIsNone(copie.lead_id)
        self.assertIsNone(copie.devis_id)
        self.assertEqual(copie.roof_image, '')
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=copie).count(), 0)
        # La géométrie, elle, EST recopiée (c'est le point d'un modèle).
        self.assertEqual(copie.roof_layout, {'foo': 'bar'})

    def test_nouveau_lead_remplace_celui_du_modele(self):
        marquer_modele(self.modele)
        copie = creer_depuis_modele(self.modele, lead_id=self.lead_client.pk)
        self.assertEqual(copie.lead_id, self.lead_client.pk)
        self.assertIsNone(copie.client_id)
