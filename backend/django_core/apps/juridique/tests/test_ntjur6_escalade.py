"""NTJUR6 — escalade « ouvrir un dossier juridique » depuis une réclamation.

Critère d'acceptation : « cliquer deux fois sur "ouvrir dossier juridique" sur
la même réclamation ne crée qu'un seul dossier ».
"""
from decimal import Decimal

from django.test import TestCase

from apps.juridique import services as juridique_services
from apps.juridique.models import DossierJuridique
from apps.litiges.models import Reclamation

from ._base import auth, make_admin, make_company

RECLAMATIONS = '/api/django/litiges/reclamations/'


class EscaladeJuridiqueTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-e6-co', 'Juridique E6')
        self.autre = make_company('jur-e6-autre', 'Juridique E6 Autre')
        self.admin = make_admin(self.company, 'jur-e6-admin')
        self.api = auth(self.admin)
        self.reclamation = Reclamation.objects.create(
            company=self.company, objet='Retard de livraison majeur',
            description='Livraison en retard de 4 mois.',
            montant_conteste=Decimal('82000.00'),
            type_reclamation=Reclamation.TypeReclamation.FINANCIER)

    def test_escalade_cree_un_dossier_prerempli(self):
        resp = self.api.post(
            f'{RECLAMATIONS}{self.reclamation.id}/escalader-juridique/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['cree'])
        dossier = DossierJuridique.objects.get(
            pk=resp.data['dossier_juridique_id'])
        self.assertEqual(dossier.company_id, self.company.id)
        self.assertEqual(dossier.titre, 'Retard de livraison majeur')
        self.assertEqual(dossier.montant_en_jeu, Decimal('82000.00'))
        self.assertEqual(dossier.resume_faits,
                         'Livraison en retard de 4 mois.')
        self.reclamation.refresh_from_db()
        self.assertEqual(self.reclamation.dossier_juridique_id, dossier.id)

    def test_double_clic_ne_cree_qu_un_seul_dossier(self):
        premier = self.api.post(
            f'{RECLAMATIONS}{self.reclamation.id}/escalader-juridique/', {},
            format='json')
        second = self.api.post(
            f'{RECLAMATIONS}{self.reclamation.id}/escalader-juridique/', {},
            format='json')
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data['cree'])
        self.assertEqual(second.data['dossier_juridique_id'],
                         premier.data['dossier_juridique_id'])
        self.assertEqual(
            DossierJuridique.objects.filter(company=self.company).count(), 1)

    def test_reclamation_d_une_autre_societe_ne_cree_rien(self):
        etrangere = Reclamation.objects.create(
            company=self.autre, objet='Litige voisin')
        dossier, cree = (
            juridique_services.creer_dossier_depuis_reclamation(
                self.company, etrangere.pk))
        self.assertIsNone(dossier)
        self.assertFalse(cree)
        self.assertFalse(DossierJuridique.objects.exists())

    def test_le_lien_n_est_pas_posable_par_patch(self):
        resp = self.api.patch(
            f'{RECLAMATIONS}{self.reclamation.id}/',
            {'dossier_juridique_id': 4242}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.reclamation.refresh_from_db()
        self.assertIsNone(self.reclamation.dossier_juridique_id)

    def test_surcharge_partie_adverse_est_respectee(self):
        resp = self.api.post(
            f'{RECLAMATIONS}{self.reclamation.id}/escalader-juridique/',
            {'partie_adverse_nom': 'SARL Oméga'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        dossier = DossierJuridique.objects.get(
            pk=resp.data['dossier_juridique_id'])
        self.assertEqual(dossier.partie_adverse_nom, 'SARL Oméga')

    def test_escalade_journalise_une_note_au_chatter(self):
        self.api.post(
            f'{RECLAMATIONS}{self.reclamation.id}/escalader-juridique/', {},
            format='json')
        self.assertEqual(self.reclamation.activites.count(), 1)
