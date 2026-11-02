"""
ZFAC4 — Note de débit (majoration d'une facture émise) — pendant de l'avoir.

Une note de débit émise sur une facture augmente son reste à payer du
montant TTC, la référence suit ``ND-`` sans collision, PDF rendu, scoping
cross-company, tests (reste à payer, numérotation, isolation).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac4_note_debit -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, NoteDebit

User = get_user_model()


def make_company(slug='nd-co', nom='ND Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestNoteDebit(TestCase):
    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ALL_PERMISSIONS
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='nd_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ND',
            telephone='+212600000002')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PVND1',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('20.00'))
        # Facture émise : 10 × 1000 HT (TVA 20 %) = 10000 HT, TVA 2000,
        # TTC 12000.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-ND-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_facture_baseline_due(self):
        self.assertEqual(self.facture.total_ttc, Decimal('12000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('12000.00'))

    def test_note_debit_increases_montant_du(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Complément non prévu',
             'lignes': [{'produit': self.panneau.id, 'designation': 'Frais complémentaires',
                         'quantite': '1', 'prix_unitaire': '1000',
                         'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(id=resp.data['id'])
        self.assertEqual(note.total_ttc, Decimal('1200.00'))
        self.assertTrue(note.reference.startswith('ND-'))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('13200.00'))

    def test_reference_no_collision_across_two_notes(self):
        api = self._api(self.admin)
        r1 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Première majoration', 'montant': '1000'}, format='json')
        r2 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Deuxième majoration', 'montant': '500'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_nd_sur_facture_payee_a_sa_propre_echeance(self):
        """AARG53 (C-AARG-060) — une ND d'aujourd'hui sur une facture payée (échue
        depuis 90 j) n'est pas « en retard de 90 jours » : à J+31 de la ND,
        en retard d'1 jour ; une retenue libérée suit la même règle."""
        import datetime
        from decimal import Decimal as D

        from apps.ventes.domain.encaissements import recalculer_statut_paiement
        from apps.ventes.models import FollowupLevel, Paiement
        from apps.ventes.recouvrement import _current_level, _levels
        from apps.ventes.scheduled import check_overdue_factures
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Ferme', delai_jours=1,
            taux_interet_annuel=D('12'), frais_fixes=D('100'))
        jour = datetime.date.today()

        def facture_payee(ref, retenue=None):
            facture = Facture.objects.create(
                company=self.company, reference=ref, client=self.client_obj,
                statut=Facture.Statut.EMISE, taux_tva=D('20.00'),
                date_emission=jour - datetime.timedelta(days=120),
                date_echeance=jour - datetime.timedelta(days=90),
                retenue_garantie_mad=retenue)
            LigneFacture.objects.create(
                facture=facture, produit=self.panneau, designation='Panneau PV',
                quantite=D('1'), prix_unitaire=D('1000'), taux_tva=D('20.00'))
            Paiement.objects.create(
                company=self.company, facture=facture,
                montant=D('1200') - (retenue or 0),
                date_paiement=jour - datetime.timedelta(days=85),
                mode='virement', created_by=self.admin)
            recalculer_statut_paiement(facture)
            return facture

        def etat(facture):
            relue = Facture.objects.get(pk=facture.pk)
            return relue.statut, relue.jours_retard, _current_level(
                relue.jours_retard, _levels(self.company),
                montant_du=relue.montant_exigible)

        facture = facture_payee('FAC-ND-0002')
        self.assertEqual(etat(facture)[0], Facture.Statut.PAYEE)
        r = self._api(self.admin).post(
            f'/api/django/ventes/factures/{facture.id}/creer-note-debit/',
            {'motif': 'Complément', 'montant': '500.00', 'taux_tva': '20'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(etat(facture), (Facture.Statut.EMISE, 0, None))
        check_overdue_factures()
        self.assertEqual(etat(facture), (Facture.Statut.EMISE, 0, None))
        # J+31 de la ND (délai de la facture : 30 j).
        NoteDebit.objects.filter(pk=r.data['id']).update(
            date_emission=jour - datetime.timedelta(days=31))
        check_overdue_factures()
        statut, jours, niveau = etat(facture)
        self.assertEqual((statut, jours), (Facture.Statut.EN_RETARD, 1))
        self.assertIsNotNone(niveau)
        # Une facture encore due : sa part à elle reste la plus ancienne.
        ouverte = facture_payee('FAC-ND-0003')
        Paiement.objects.filter(facture=ouverte).update(montant=D('1000'))
        self._api(self.admin).post(
            f'/api/django/ventes/factures/{ouverte.id}/creer-note-debit/',
            {'motif': 'Complément', 'montant': '500.00', 'taux_tva': '20'},
            format='json')
        self.assertEqual(Facture.objects.get(pk=ouverte.pk).jours_retard, 90)

        # Retenue de garantie libérée à la date saisie.
        retenue = facture_payee('FAC-ND-0004', retenue=D('120'))
        self.assertEqual(Facture.objects.get(pk=retenue.pk).montant_exigible, 0)
        r = self._api(self.admin).post(
            f'/api/django/ventes/factures/{retenue.id}/liberer-retenue/',
            {'date': jour.isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Facture.objects.get(pk=retenue.pk).montant_exigible,
                         D('120'))
        check_overdue_factures()
        self.assertEqual(etat(retenue)[:2], (Facture.Statut.EMISE, 0))
        Facture.objects.filter(pk=retenue.pk).update(
            retenue_liberee_le=jour - datetime.timedelta(days=31))
        check_overdue_factures()
        self.assertEqual(etat(retenue)[:2], (Facture.Statut.EN_RETARD, 1))

    def test_note_debit_pdf_renders(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Complément', 'montant': '1000'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(id=resp.data['id'])
        self.assertTrue(note.fichier_pdf)

    def test_note_debit_scoping_cross_company_404(self):
        other_company = make_company(slug='nd-other', nom='Other Co')
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ALL_PERMISSIONS
        other_role = Role.objects.create(
            company=other_company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        other_admin = User.objects.create_user(
            username='nd_other_admin', password='x', role=other_role,
            role_legacy='admin', company=other_company)
        api = self._api(other_admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Tentative cross-company'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_lignes_dont_le_total_deborde_409_et_produit_inconnu_404(self):
        # CI #997 fuzz (24/10) : chaque ligne est dans ses bornes (< 10^8) mais
        # leur produit déborde les 10 chiffres entiers des montants : refus
        # d'état 409 (500 « numeric field overflow » avant), rien d'écrit ; un
        # produit bien formé mais absent du catalogue = 404.
        api = self._api(self.admin)
        url = f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/'
        avant = NoteDebit.objects.count()
        resp = api.post(url, {'motif': 'x', 'lignes': [{
            'produit': self.panneau.id, 'designation': 'Gros',
            'quantite': '99999999', 'prix_unitaire': '99999999'}]},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        resp = api.post(url, {'motif': 'x', 'lignes': [{
            'produit': 987654321, 'designation': 'Inconnu',
            'quantite': '1', 'prix_unitaire': '10'}]}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(NoteDebit.objects.count(), avant)
