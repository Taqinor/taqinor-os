"""CIQ214 — retenue de garantie SEULEMENT à la demande du client, libérée à la
réception définitive ; pénalités de retard et caution déclarées et plafonnées,
jamais par défaut (D-CIQ-14).

Lecteurs de ``Facture.montant_du`` (grep joint au commit) :
  * relances → ``montant_exigible`` : ``recouvrement.variables_relance``,
    ``facture_relancable``, ``apercu_relance``, ``relances_list`` (montant et
    pénalité du niveau), ``lettre_relance_pdf`` ; ``scheduled.
    check_overdue_factures``, ``_check_promesses_expirees``,
    ``pre_echeance_reminders`` ; ``domain/recouvrement.
    _rouvrir_facture_apres_rejet`` ;
  * restent sur la CRÉANCE TOTALE (justifié) : ``recouvrement.balance_agee``
    et ``_releve_data`` (relevé de compte : la retenue est due, à terme),
    ``domain/recouvrement.abandonner_solde_facture`` (un abandon ne doit
    jamais effacer une retenue en silence), le grand livre / la balance /
    le portail (créance comptable), ``Facture.jours_retard`` (statut).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq214_retenue"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

RETENUE = {'taux_pct': 5, 'liberation': 'reception_definitive'}
#: Une première tranche déclarée en MONTANT : 100 000 MAD TTC pile.
ECHEANCIER = [
    {'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 100000},
    {'type': 'solde', 'pct_or_montant': 10},
]


class ReglesPuresTest(SimpleTestCase):
    def test_retenue_de_tranche_au_centime(self):
        from types import SimpleNamespace
        from apps.ventes.utils.echeancier import retenue_de_tranche
        devis = SimpleNamespace(retenue_garantie=RETENUE)
        retenue = retenue_de_tranche(devis, Decimal('100000.00'))
        self.assertEqual(retenue['montant'], Decimal('5000.00'))
        self.assertIn('sans effet sur la base taxable', retenue['phrase'])
        self.assertIsNone(retenue_de_tranche(
            SimpleNamespace(retenue_garantie=None), Decimal('100000')))

    def test_validateurs_entete(self):
        from rest_framework import serializers
        from apps.ventes.serializers import DevisWriteSerializer
        ser = DevisWriteSerializer()
        with self.assertRaises(serializers.ValidationError) as ctx:
            ser.validate_penalites_retard_livraison(
                {'taux_pct_par_semaine': 0.5})
        self.assertIn('penalites_retard_livraison.plafond_pct',
                      str(ctx.exception))
        normalise = ser.validate_retenue_garantie({'taux_pct': '5'})
        self.assertEqual(normalise, {'taux_pct': 5.0,
                                     'liberation': 'reception_definitive'})
        self.assertEqual(ser.validate_retenue_garantie(normalise), normalise)
        self.assertIsNone(ser.validate_caution(None))
        with self.assertRaises(serializers.ValidationError):
            ser.validate_caution({'montant_ou_pct': '5 %'})


class _Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq214-co', defaults={'nom': 'CIQ214 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', prenom='CIQ214',
            email='ciq214@example.com')
        self.user = User.objects.create_user(
            username='ciq214_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, ref, retenue=None, statut='accepte'):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20.00'),
            mode_installation='industriel', echeancier=ECHEANCIER,
            retenue_garantie=retenue)
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('100000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _premiere_facture(self, devis):
        from apps.ventes.models import Facture
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['id'])


class RetenueFactureTest(_Base):
    def test_retenue_5_pct_tva_inchangee_exigible_95000(self):
        temoin = self._premiere_facture(self._devis('DEV-CIQ214-0010'))
        facture = self._premiere_facture(
            self._devis('DEV-CIQ214-0020', retenue=RETENUE))
        self.assertEqual(facture.montant_ttc, Decimal('100000.00'))
        # Ni le HT ni la TVA ne baissent (assiette complète, AUD180).
        self.assertEqual(facture.montant_ht, temoin.montant_ht)
        self.assertEqual(facture.montant_tva, temoin.montant_tva)
        self.assertEqual(facture.retenue_garantie_mad, Decimal('5000.00'))
        self.assertIn('sans effet sur la base taxable',
                      facture.conditions_paiement)
        self.assertEqual(facture.montant_exigible, Decimal('95000.00'))
        self.assertEqual(facture.montant_du, Decimal('100000.00'))
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/liberer-retenue/',
            {'date': '2027-06-30'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(str(facture.retenue_liberee_le), '2027-06-30')
        self.assertEqual(facture.montant_exigible, Decimal('100000.00'))
        self.assertEqual(r.data['montant_exigible'], '100000.00')

    def test_relance_avant_liberation_ne_reclame_que_95000(self):
        from apps.ventes.recouvrement import (
            apercu_relance, facture_relancable, variables_relance)
        facture = self._premiere_facture(
            self._devis('DEV-CIQ214-0030', retenue=RETENUE))
        self.assertEqual(variables_relance(facture)['montant_du'],
                         '95000.00')
        self.assertEqual(apercu_relance(facture)['montant_du'], '95000.00')
        self.assertTrue(facture_relancable(facture)[0])

    def test_sans_retenue_facture_identique(self):
        facture = self._premiere_facture(self._devis('DEV-CIQ214-0040'))
        self.assertIsNone(facture.retenue_garantie_mad)
        self.assertNotIn('Retenue de garantie', facture.conditions_paiement)
        self.assertEqual(facture.montant_exigible, facture.montant_du)

    def test_liberer_sans_retenue_400(self):
        facture = self._premiere_facture(self._devis('DEV-CIQ214-0050'))
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/liberer-retenue/',
            {'date': '2027-06-30'}, format='json')
        self.assertEqual(r.status_code, 400)


class EnteteDevisTest(_Base):
    def _patch(self, devis, corps):
        return self.api.patch(f'/api/django/ventes/devis/{devis.id}/', corps,
                              format='json')

    def test_penalite_sans_plafond_400_nommant_le_champ(self):
        devis = self._devis('DEV-CIQ214-0060', statut='brouillon')
        r = self._patch(devis, {'penalites_retard_livraison': {
            'taux_pct_par_semaine': 0.5}})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('penalites_retard_livraison.plafond_pct', str(r.data))

    def test_enregistrer_rouvrir_enregistrer_entete_identique(self):
        devis = self._devis('DEV-CIQ214-0070', statut='brouillon')
        corps = {'retenue_garantie': {'taux_pct': '5'},
                 'penalites_retard_livraison': {'taux_pct_par_semaine': 0.5,
                                                'plafond_pct': 5},
                 'caution': {'nature': 'caution bancaire',
                             'montant_ou_pct': '5 %', 'plafond': '10 %'}}
        r1 = self._patch(devis, corps)
        self.assertEqual(r1.status_code, 200, r1.data)
        devis.refresh_from_db()
        premier = (devis.retenue_garantie, devis.penalites_retard_livraison,
                   devis.caution)
        r2 = self._patch(devis, {
            'retenue_garantie': devis.retenue_garantie,
            'penalites_retard_livraison': devis.penalites_retard_livraison,
            'caution': devis.caution})
        self.assertEqual(r2.status_code, 200, r2.data)
        devis.refresh_from_db()
        self.assertEqual((devis.retenue_garantie,
                          devis.penalites_retard_livraison, devis.caution),
                         premier)
        self.assertEqual(premier[0], {'taux_pct': 5.0,
                                      'liberation': 'reception_definitive'})

    def test_vides_par_defaut(self):
        devis = self._devis('DEV-CIQ214-0080', statut='brouillon')
        self.assertIsNone(devis.retenue_garantie)
        self.assertIsNone(devis.penalites_retard_livraison)
        self.assertIsNone(devis.caution)
