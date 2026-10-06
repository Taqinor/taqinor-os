"""CIQ212 — échéancier C&I à N jalons (D-CIQ-13) : commercial 40/50/10,
industriel 30/40/20/10, éditables par société et par devis, avec délai de
règlement et semaines indicatives par jalon.

Lecteurs de ``payment_terms_for`` / ``PAYMENT_TERMS_BY_MODE`` /
``data['payment_terms']`` (grep joint au commit) :
  * ``utils/echeancier.tranches_normalisees`` — lit la LISTE de jalons ;
  * ``utils/echeancier.termes_paiement_devis`` (builder, page publique) —
    rabat les jalons sur les trois créneaux {acompte, materiel, solde}
    (somme par créneau) : résidentiel / agricole identiques à l'octet ;
  * ``quote_engine/builder.py`` (``data['payment_terms']`` = ce rabattu ;
    ``data['jalons_paiement']`` C&I = ``jalons_paiement_devis``) ;
  * ``quote_engine/industriel/trust.py``, ``ci/synthese.py``,
    ``generate_devis_premium.py`` (marqueurs CGV {acompte}/{materiel}/
    {solde}), ``agricole/pages.py``, ``public/payload_conditions.py`` —
    lisent le rabattu à trois créneaux, inchangés (D3 imprimera les jalons).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq212_echeancier_jalons"
"""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.quote_engine.builder import PAYMENT_TERMS_BY_MODE
from apps.ventes.utils.company_settings import (
    creneaux_depuis_jalons, jalons_depuis_termes, payment_terms_for)
from apps.ventes.utils.echeancier import (
    EcheancierInvalide, normaliser_tranche, termes_paiement_devis,
    tranches_normalisees)


def _devis_sans_base(mode, echeancier=None):
    return SimpleNamespace(echeancier=echeancier, mode_installation=mode,
                           company=None)


class JalonsDefautTest(SimpleTestCase):
    def test_industriel_30_40_20_10(self):
        tranches = tranches_normalisees(_devis_sans_base('industriel'))
        self.assertEqual(
            [(t['key'], t['valeur']) for t in tranches],
            [('commande', 30), ('livraison_materiel', 40),
             ('mise_en_service', 20), ('reception_definitive', 10)])
        self.assertEqual(tranches[-1]['libelle'], 'Réception définitive')

    def test_commercial_40_50_10(self):
        tranches = tranches_normalisees(_devis_sans_base('commercial'))
        self.assertEqual([t['valeur'] for t in tranches], [40, 50, 10])

    def test_residentiel_identique_a_l_octet(self):
        self.assertEqual(
            tranches_normalisees(_devis_sans_base('residentiel')),
            [{'key': 'acompte', 'libelle': 'Acompte', 'valeur': 30,
              'unite': 'pct'},
             {'key': 'materiel', 'libelle': 'Livraison du matériel',
              'valeur': 60, 'unite': 'pct'},
             {'key': 'solde', 'libelle': 'Solde', 'valeur': 10,
              'unite': 'pct'}])
        self.assertEqual(
            termes_paiement_devis(None, payment_terms_for(None,
                                                          'residentiel')),
            {'acompte': 30, 'materiel': 60, 'solde': 10})
        self.assertEqual(
            termes_paiement_devis(None, payment_terms_for(None, 'agricole')),
            {'acompte': 30, 'materiel': 60, 'solde': 10})

    def test_ancienne_forme_toujours_lue(self):
        jalons = jalons_depuis_termes({'acompte': 40, 'materiel': 50,
                                       'solde': 10})
        self.assertEqual([(j['jalon'], j['pct']) for j in jalons],
                         [('acompte', 40), ('materiel', 50), ('solde', 10)])
        self.assertEqual(creneaux_depuis_jalons(jalons),
                         {'acompte': 40, 'materiel': 50, 'solde': 10})

    def test_rabattu_industriel_sur_trois_creneaux(self):
        self.assertEqual(
            creneaux_depuis_jalons(payment_terms_for(None, 'industriel')),
            {'acompte': 30, 'materiel': 40, 'solde': 30})

    def test_tranche_porte_ses_champs_de_jalon(self):
        t = normaliser_tranche({'type': 'solde', 'pct_or_montant': 10,
                                'jalon': 'reception_definitive',
                                'delai_reglement_jours': 45,
                                'semaines_indicatives': None,
                                'payeur': 'client'}, 3)
        self.assertEqual(t['jalon'], 'reception_definitive')
        self.assertEqual(t['delai_reglement_jours'], 45)
        self.assertNotIn('semaines_indicatives', t)
        self.assertEqual(t['payeur'], 'client')
        # Sans les nouveaux champs : forme d'hier, octet pour octet.
        self.assertEqual(
            normaliser_tranche({'type': 'solde', 'pct_or_montant': 10}, 2),
            {'key': 'solde', 'libelle': 'Solde', 'valeur': 10.0,
             'unite': 'pct'})

    def test_jalon_inconnu_refuse_en_nommant_le_champ(self):
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche({'pct_or_montant': 10, 'jalon': 'livraison'}, 1)
        self.assertIn('echeancier[1].jalon', str(ctx.exception))
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche({'pct_or_montant': 10,
                                'delai_reglement_jours': -3}, 0)
        self.assertIn('echeancier[0].delai_reglement_jours',
                      str(ctx.exception))


class ReglageSocieteTest(SimpleTestCase):
    def _valider(self, valeur):
        from apps.parametres.serializers_company import (
            CompanyProfileSerializer)
        return CompanyProfileSerializer().validate_payment_terms(valeur)

    def test_liste_de_jalons_acceptee(self):
        valeur = {'industriel': PAYMENT_TERMS_BY_MODE['industriel']}
        self.assertEqual(self._valider(valeur), valeur)

    def test_somme_differente_de_100_refusee(self):
        from rest_framework import serializers
        with self.assertRaises(serializers.ValidationError):
            self._valider({'commercial': [{'jalon': 'commande', 'pct': 40},
                                          {'jalon': 'mise_en_service',
                                           'pct': 50}]})

    def test_jalon_inconnu_refuse(self):
        from rest_framework import serializers
        with self.assertRaises(serializers.ValidationError):
            self._valider({'commercial': [{'jalon': 'livraison', 'pct': 100}]})

    def test_ancienne_forme_toujours_acceptee(self):
        valeur = {'residentiel': {'acompte': 30, 'materiel': 60, 'solde': 10}}
        self.assertEqual(self._valider(valeur), valeur)


# ── Base de données : factures de tranche et profil société ─────────────────

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq212-co', defaults={'nom': 'CIQ212 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', prenom='CIQ212',
            email='ciq212@example.com', delai_paiement_jours=15)
        self.user = User.objects.create_user(
            username='ciq212_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, mode, ref, echeancier=None):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            mode_installation=mode, echeancier=echeancier)
        # 10 000,01 HT × 1,20 : un total qui ne se divise pas au centime.
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000.01'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _facturer_tout(self, devis):
        reponses = []
        while True:
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/')
            if r.status_code != 201:
                break
            reponses.append(r.data)
        return reponses


class FacturesDeTrancheTest(_Base):
    def test_industriel_quatre_tranches_reste_au_centime(self):
        from apps.ventes.utils.options import option_totaux
        devis = self._devis('industriel', 'DEV-CIQ212-0010')
        factures = self._facturer_tout(devis)
        self.assertEqual([Decimal(f['pourcentage']) for f in factures[:3]],
                         [Decimal('30'), Decimal('40'), Decimal('20')])
        self.assertEqual(len(factures), 4)
        total = Decimal(str(option_totaux(devis)['ttc']))
        self.assertEqual(sum(Decimal(f['total_ttc']) for f in factures),
                         total)
        self.assertEqual(factures[-1]['type_facture'], 'solde')

    def test_commercial_40_50_10(self):
        devis = self._devis('commercial', 'DEV-CIQ212-0020')
        factures = self._facturer_tout(devis)
        self.assertEqual(len(factures), 3)
        self.assertEqual([Decimal(f['pourcentage']) for f in factures[:2]],
                         [Decimal('40'), Decimal('50')])

    def test_delai_declare_60_jours_prime_sur_le_client(self):
        from apps.ventes.models import Facture
        devis = self._devis('industriel', 'DEV-CIQ212-0030', echeancier=[
            {'type': 'acompte', 'pct_or_montant': 30, 'jalon': 'commande',
             'delai_reglement_jours': 60},
            {'type': 'solde', 'pct_or_montant': 70,
             'jalon': 'reception_definitive'}])
        factures = self._facturer_tout(devis)
        premiere = Facture.objects.get(pk=factures[0]['id'])
        self.assertEqual(premiere.date_echeance,
                         premiere.date_emission + timedelta(days=60))
        # Sans délai déclaré : le repli XFAC23 (délai du client, 15 j).
        seconde = Facture.objects.get(pk=factures[1]['id'])
        self.assertEqual(seconde.date_echeance,
                         seconde.date_emission + timedelta(days=15))

    def test_jalons_paiement_devis(self):
        from apps.ventes.utils.echeancier import jalons_paiement_devis
        from apps.ventes.utils.options import option_totaux
        devis = self._devis('industriel', 'DEV-CIQ212-0040')
        jalons = jalons_paiement_devis(devis)
        self.assertEqual([j['jalon'] for j in jalons],
                         ['commande', 'livraison_materiel', 'mise_en_service',
                          'reception_definitive'])
        self.assertEqual(sum(j['montant_ttc'] for j in jalons),
                         Decimal(str(option_totaux(devis)['ttc'])))
        self.assertIsNone(jalons[0]['delai_reglement_jours'])


class ProfilSocieteTest(_Base):
    def test_payment_terms_effectifs_sans_reglage(self):
        from apps.parametres.models import CompanyProfile
        from apps.parametres.serializers_company import (
            CompanyProfileSerializer)
        profil = CompanyProfile.get(company=self.company)
        sortie = CompanyProfileSerializer(profil).data
        effectifs = sortie['payment_terms_effectifs']
        self.assertEqual([j['pct'] for j in effectifs['industriel']],
                         [30, 40, 20, 10])
        self.assertEqual([j['pct'] for j in effectifs['commercial']],
                         [40, 50, 10])
        self.assertEqual([j['jalon'] for j in effectifs['residentiel']],
                         ['acompte', 'materiel', 'solde'])
