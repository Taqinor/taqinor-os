"""NTJUR15 — reprise de provision à la clôture du dossier.

Critère d'acceptation : « clore un dossier sans provision ne déclenche aucune
proposition ; clore un dossier avec provision affiche la bannière une seule
fois (pas à chaque reload si déjà traitée) ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.compta.models import Provision
from apps.juridique.models import DossierJuridique

from ._base import auth, make_admin, make_company

URL = '/api/django/juridique/dossiers/'


class RepriseProvisionTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-r15-co', 'Juridique R15')
        self.admin = make_admin(self.company, 'jur-r15-admin')
        self.api = auth(self.admin)

    def _dossier(self, reference='JUR-2026-0001'):
        return DossierJuridique.objects.create(
            company=self.company, reference=reference,
            titre='Litige provisionné', date_ouverture=date(2026, 6, 1),
            montant_en_jeu=Decimal('500000'))

    def _provisionner(self, dossier, montant='200000.00'):
        resp = self.api.post(
            f'{URL}{dossier.id}/proposer-provision/',
            {'montant': montant, 'confirme': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        dossier.refresh_from_db()
        return Provision.objects.get(pk=dossier.provision_comptable_id)

    def test_clore_sans_provision_ne_propose_rien(self):
        dossier = self._dossier()
        resp = self.api.post(f'{URL}{dossier.id}/clore/',
                             {'statut_final': 'clos_gagne'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['reprise_provision_a_proposer'])
        self.assertEqual(resp.data['statut'], 'clos_gagne')

    def test_clore_avec_provision_leve_la_banniere_une_seule_fois(self):
        dossier = self._dossier()
        self._provisionner(dossier)
        clos = self.api.post(f'{URL}{dossier.id}/clore/',
                             {'statut_final': 'clos_transaction'},
                             format='json')
        self.assertEqual(clos.status_code, 200, clos.data)
        self.assertTrue(clos.data['reprise_provision_a_proposer'])

        # Reprise CONFIRMÉE → écriture inverse + bannière éteinte.
        reprise = self.api.post(f'{URL}{dossier.id}/reprendre-provision/',
                                {'confirme': True}, format='json')
        self.assertEqual(reprise.status_code, 200, reprise.data)
        self.assertTrue(reprise.data['provision_reprise'])

        # Rechargement : la bannière ne revient pas.
        relu = self.api.get(f'{URL}{dossier.id}/')
        self.assertFalse(relu.data['reprise_provision_a_proposer'])
        self.assertTrue(relu.data['reprise_provision_traitee'])

    def test_sans_confirmation_aucune_reprise_n_est_postee(self):
        dossier = self._dossier()
        provision = self._provisionner(dossier)
        self.api.post(f'{URL}{dossier.id}/clore/',
                      {'statut_final': 'clos_perdu'}, format='json')
        resp = self.api.post(f'{URL}{dossier.id}/reprendre-provision/', {},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        provision.refresh_from_db()
        self.assertEqual(provision.montant_repris, Decimal('0'))
        dossier.refresh_from_db()
        self.assertTrue(dossier.reprise_provision_a_proposer)

    def test_abandon_explicite_eteint_la_banniere_sans_ecriture(self):
        dossier = self._dossier()
        provision = self._provisionner(dossier)
        self.api.post(f'{URL}{dossier.id}/clore/',
                      {'statut_final': 'clos_gagne'}, format='json')
        resp = self.api.post(f'{URL}{dossier.id}/reprendre-provision/',
                             {'abandonner': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['provision_reprise'])
        provision.refresh_from_db()
        self.assertEqual(provision.montant_repris, Decimal('0'))
        dossier.refresh_from_db()
        self.assertFalse(dossier.reprise_provision_a_proposer)

    def test_double_reprise_refusee(self):
        dossier = self._dossier()
        self._provisionner(dossier)
        self.api.post(f'{URL}{dossier.id}/clore/',
                      {'statut_final': 'clos_gagne'}, format='json')
        self.api.post(f'{URL}{dossier.id}/reprendre-provision/',
                      {'confirme': True}, format='json')
        second = self.api.post(f'{URL}{dossier.id}/reprendre-provision/',
                               {'confirme': True}, format='json')
        self.assertEqual(second.status_code, 400, second.data)

    def test_transition_illegale_laisse_le_dossier_inchange(self):
        dossier = self._dossier()
        resp = self.api.post(f'{URL}{dossier.id}/changer-statut/',
                             {'statut': 'jugement_rendu'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        dossier.refresh_from_db()
        self.assertEqual(dossier.statut, DossierJuridique.Statut.OUVERT)

    def test_statut_de_cloture_invalide_refuse(self):
        dossier = self._dossier()
        resp = self.api.post(f'{URL}{dossier.id}/clore/',
                             {'statut_final': 'instruction'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        dossier.refresh_from_db()
        self.assertEqual(dossier.statut, DossierJuridique.Statut.OUVERT)
