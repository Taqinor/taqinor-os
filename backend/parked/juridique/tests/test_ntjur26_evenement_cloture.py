"""NTJUR26 — événement ``dossier_juridique_clos`` sur le bus ``core.events``.

Critère d'acceptation : « fermer un dossier avec provision déclenche
l'apparition de la bannière de reprise sans action manuelle préalable, mais
aucune écriture comptable n'est postée sans confirmation ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.compta.models import Provision
from apps.juridique import services
from apps.juridique.models import DossierJuridique
from core import events

from ._base import auth, make_admin, make_company

URL = '/api/django/juridique/dossiers/'


class EvenementClotureTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-e26-co', 'Juridique E26')
        self.admin = make_admin(self.company, 'jur-e26-admin')
        self.api = auth(self.admin)
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Litige provisionné', date_ouverture=date(2026, 1, 5),
            montant_en_jeu=Decimal('450000'))

    def _provisionner(self):
        resp = self.api.post(f'{URL}{self.dossier.id}/proposer-provision/',
                             {'montant': '100000.00', 'confirme': True},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.dossier.refresh_from_db()

    def test_l_evenement_porte_le_resultat_et_le_montant_final(self):
        recus = []

        def _espion(sender, **kwargs):
            recus.append(kwargs)

        events.dossier_juridique_clos.connect(
            _espion, dispatch_uid='test-ntjur26-espion')
        try:
            services.clore_dossier(self.dossier, 'clos_transaction')
        finally:
            events.dossier_juridique_clos.disconnect(
                dispatch_uid='test-ntjur26-espion')
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0]['resultat'], 'clos_transaction')
        self.assertEqual(recus[0]['montant_final'], Decimal('450000.00'))
        self.assertEqual(recus[0]['company'], self.company)

    def test_la_banniere_apparait_sans_action_manuelle_prealable(self):
        self._provisionner()
        resp = self.api.post(f'{URL}{self.dossier.id}/clore/',
                             {'statut_final': 'clos_perdu'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # La réponse de la CLÔTURE elle-même porte déjà la bannière : aucun
        # second appel, aucune action manuelle.
        self.assertTrue(resp.data['reprise_provision_a_proposer'])

    def test_aucune_ecriture_n_est_postee_par_l_evenement(self):
        self._provisionner()
        provision = Provision.objects.get(company=self.company)
        self.api.post(f'{URL}{self.dossier.id}/clore/',
                      {'statut_final': 'clos_gagne'}, format='json')
        provision.refresh_from_db()
        # Dotation intacte, RIEN de repris : l'événement ne fait que proposer.
        self.assertEqual(provision.montant_repris, Decimal('0'))
        self.assertEqual(
            Provision.objects.filter(company=self.company).count(), 1)

    def test_un_dossier_sans_provision_ne_leve_aucune_banniere(self):
        resp = self.api.post(f'{URL}{self.dossier.id}/clore/',
                             {'statut_final': 'clos_desistement'},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['reprise_provision_a_proposer'])
        self.assertFalse(resp.data['reprise_provision_proposee'])

    def test_banniere_deja_traitee_n_est_jamais_relevee(self):
        self._provisionner()
        self.dossier.reprise_provision_traitee = True
        self.dossier.save(update_fields=['reprise_provision_traitee'])
        resp = self.api.post(f'{URL}{self.dossier.id}/clore/',
                             {'statut_final': 'clos_gagne'}, format='json')
        self.assertFalse(resp.data['reprise_provision_proposee'])
        self.assertFalse(resp.data['reprise_provision_a_proposer'])
