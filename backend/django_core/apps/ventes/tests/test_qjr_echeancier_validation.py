"""QJR21 — l'échéancier refuse un montant interprété comme un pourcentage.

``Devis.echeancier`` est un JSONField dont ``pct_or_montant`` était TOUJOURS lu
comme un pourcentage, alors que le nom du champ et son ``help_text``
autorisent un montant : une tranche saisie en dirhams produisait une facture de
plusieurs centaines de fois le total du devis.

Ce module prouve les trois cas exigés :

  1. POURCENTAGE VALIDE — une tranche ≤ 100 (déclarée ou non) reste un
     pourcentage, mot pour mot comme hier (rétro-compatibilité).
  2. MONTANT DÉCLARÉ — une tranche qui déclare ``montant`` vaut ce montant TTC
     et non un pourcentage ; son poids est DÉRIVÉ du total.
  3. AMBIGU REFUSÉ — au-delà de 100 sans unité déclarée, l'API refuse avec
     un message en français : 409 ``ConflitEtat`` depuis CI #997 (4) (règle
     inter-clés que le schéma publié ne sait pas dire), une tranche HORS
     FORME publiée (``pct_or_montant`` absent…) restant un 400.

ATTENTION FIXTURES (R4-B3) : les montants de test restent SOUS 1000 MAD —
``Facture.pourcentage`` est un ``numeric(5, 2)`` et un test qui le ferait
déborder échouerait pour la mauvaise raison.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr_echeancier_validation"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.echeancier import (
    EcheancierIncoherent, EcheancierInvalide, UNITE_MONTANT, UNITE_PCT,
    next_tranche, normaliser_tranche, schedule_for_devis,
    schema_echeancier, tranches_normalisees, unite_declaree,
    valider_echeancier,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA RÈGLE, SANS BASE — le validateur pur
# ═══════════════════════════════════════════════════════════════════════════
class RegleUniteTranche(SimpleTestCase):
    """``normaliser_tranche`` : la seule source de la règle et des messages."""

    def test_sans_declaration_et_sous_100_reste_un_pourcentage(self):
        """Rétro-compatibilité : toutes les données d'hier sont inchangées."""
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40})
        self.assertEqual(tranche['unite'], UNITE_PCT)
        self.assertEqual(tranche['valeur'], 40.0)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['libelle'], 'Acompte')

    def test_pourcentage_declare_explicitement(self):
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte',
             'unite': 'pct', 'pct_or_montant': 30})
        self.assertEqual(tranche['unite'], UNITE_PCT)
        self.assertEqual(tranche['key'], 'acompte')

    def test_montant_declare_par_la_cle_unite(self):
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte',
             'unite': 'montant', 'pct_or_montant': 500})
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['valeur'], 500.0)
        # La NATURE de la tranche reste 'acompte' : ``unite`` ne l'écrase pas.
        self.assertEqual(tranche['key'], 'acompte')

    def test_montant_declare_par_la_cle_type(self):
        """``type`` : 'montant' déclare l'unité et n'est alors PAS une nature."""
        tranche = normaliser_tranche(
            {'libelle': 'Premier versement', 'type': 'montant',
             'pct_or_montant': 750}, index=0)
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['key'], 'tranche_0')

    def test_valeur_ambigue_au_dela_de_100_est_refusee(self):
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche(
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 500})
        message = str(ctx.exception)
        self.assertIn('ambigu', message)
        self.assertIn('montant', message)

    def test_pourcentage_declare_au_dela_de_100_est_refuse(self):
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche({'unite': 'pct', 'pct_or_montant': 120})
        self.assertIn('100', str(ctx.exception))

    def test_montant_declare_au_dela_de_100_est_accepte(self):
        """C'est TOUTE la différence : déclaré, un montant n'est plus ambigu."""
        tranche = normaliser_tranche(
            {'unite': 'montant', 'pct_or_montant': 900})
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['valeur'], 900.0)

    def test_valeur_negative_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche({'unite': 'pct', 'pct_or_montant': -5})

    def test_valeur_non_numerique_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche({'pct_or_montant': 'quarante'})

    def test_tranche_non_objet_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche('acompte', index=1)

    def test_unite_declaree_lit_unite_puis_type(self):
        self.assertEqual(unite_declaree({'unite': 'MONTANT'}), UNITE_MONTANT)
        self.assertEqual(unite_declaree({'type': 'Pct'}), UNITE_PCT)
        # Une NATURE de tranche ne déclare aucune unité.
        self.assertIsNone(unite_declaree({'type': 'acompte'}))
        self.assertIsNone(unite_declaree({}))

    def test_valider_echeancier_refuse_une_non_liste(self):
        with self.assertRaises(EcheancierInvalide):
            valider_echeancier('pas-une-liste')

    def test_valider_echeancier_vide_ne_leve_pas(self):
        self.assertEqual(valider_echeancier(None), [])
        self.assertEqual(valider_echeancier([]), [])

    def test_ci997_4_regles_inter_cles_incoherentes_forme_invalide(self):
        """CI #997 (4) — somme ≠ 100 % et valeur > 100 selon l'unité
        déclarée : ``EcheancierIncoherent`` (409 à l'API) ; un refus de FORME
        de la même tranche (jalon inconnu) prime et reste un 400."""
        for brut in ([{'pct_or_montant': 60}],
                     [{'pct_or_montant': 150}],
                     [{'unite': 'pct', 'pct_or_montant': 120}]):
            with self.assertRaises(EcheancierIncoherent, msg=repr(brut)):
                valider_echeancier(brut)
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche({'pct_or_montant': 150, 'jalon': 'xx'})
        self.assertNotIsInstance(ctx.exception, EcheancierIncoherent)

    def test_ci997_4_schema_publie_exige_pct_or_montant(self):
        """Cas kZprmM (``PUT devis``, ``echeancier: [{}]``) : la tranche
        vide n'est plus conforme au schéma publié."""
        liste = schema_echeancier()['anyOf'][0]
        self.assertEqual(liste['items']['required'], ['pct_or_montant'])


class MixinEcheancierCi997(SimpleTestCase):
    """CI #997 (4) — ``EcheancierValidationMixin`` : 400 hors forme publiée,
    409 ``ConflitEtat`` (même message, sous ``echeancier``) sur une règle
    d'ensemble, seulement quand le reste du corps est valide."""

    def _juger(self, echeancier):
        from rest_framework import serializers
        from apps.ventes.serializers import EcheancierValidationMixin
        from core.conflit_etat import ConflitEtat

        class _Base:
            def validate(self, attrs):
                return attrs

        class _Ser(EcheancierValidationMixin, _Base):
            pass

        ser = _Ser()
        try:
            ser.validate_echeancier(echeancier)
        except serializers.ValidationError as exc:
            return 400, str(exc.detail)
        try:
            ser.validate({})
        except ConflitEtat as exc:
            return 409, str(exc.detail['echeancier'])
        return 200, ''

    def test_tranches_hors_forme_400(self):
        for brut, attendu in (
                ([{}], '« pct_or_montant » est obligatoire'),
                ([{'pct_or_montant': None}], 'la tranche est vide'),
                ([{'pct_or_montant': '1e2'}], 'pct_or_montant'),
                ([{'pct_or_montant': 100, 'libelle': 0}], 'libelle'),
                ([{'pct_or_montant': 100, 'libelle': 'a\x00'}], 'libelle'),
                ([{'pct_or_montant': 100, 'date_prevue': ' 2026-01-01'}],
                 'date_prevue'),
                ([{'pct_or_montant': 100,
                   'delai_reglement_jours': 10 ** 400}],
                 'delai_reglement_jours')):
            statut, message = self._juger(brut)
            self.assertEqual(statut, 400, brut)
            self.assertIn(attendu, message, brut)

    def test_regles_d_ensemble_409_meme_message(self):
        statut, message = self._juger([{'pct_or_montant': 0}])
        self.assertEqual(statut, 409)
        self.assertIn('Total des tranches : 0 % — il doit faire 100 %.',
                      message)
        statut, message = self._juger([{'pct_or_montant': 150}])
        self.assertEqual((statut, 'ambigu' in message), (409, True))

    def test_formes_valides_acceptees(self):
        for brut in ([{'pct_or_montant': 100}], [{'pct_or_montant': '100'}],
                     [{'unite': 'montant', 'pct_or_montant': 750},
                      {'pct_or_montant': 100}],
                     [{'pct_or_montant': 100, 'date_prevue': '2026-02-28',
                       'jalon': 'commande', 'payeur': 'tiers',
                       'delai_reglement_jours': 30,
                       'semaines_indicatives': '2,5'}]):
            self.assertEqual(self._juger(brut), (200, ''), brut)


# ═══════════════════════════════════════════════════════════════════════════
# 2. L'ÉCHÉANCIER D'UN DEVIS — lecture tolérante, calcul juste
# ═══════════════════════════════════════════════════════════════════════════
def _company():
    company, _ = Company.objects.get_or_create(
        slug='qjr21-co', defaults={'nom': 'QJR21 Co'})
    return company


def _user(company):
    return User.objects.create_user(
        username='qjr21_resp', password='x', role_legacy='responsable',
        company=company)


def _client_obj(company):
    return Client.objects.create(
        company=company, nom='QJR21', prenom='Client',
        email='qjr21@example.invalid', telephone='+212600000021')


def _devis(company, client_obj, ref, echeancier=None,
           statut=Devis.Statut.ACCEPTE):
    """Devis à 17 000 TTC : 15 000 HT + 2 000 TVA (split 10/20)."""
    devis = Devis.objects.create(
        company=company, reference=ref, client=client_obj, statut=statut,
        taux_tva=Decimal('20.00'), mode_installation='residentiel',
        echeancier=echeancier)
    panneau = Produit.objects.create(
        company=company, nom=f'Panneau {ref}', sku=f'PV-{ref}',
        prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'))
    onduleur = Produit.objects.create(
        company=company, nom=f'Onduleur {ref}', sku=f'OND-{ref}',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
    LigneDevis.objects.create(
        devis=devis, produit=panneau, designation='Panneau PV 450W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('10.00'))
    LigneDevis.objects.create(
        devis=devis, produit=onduleur, designation='Onduleur 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'))
    return devis


class EcheancierDUnDevis(TestCase):

    def setUp(self):
        self.company = _company()
        self.client_obj = _client_obj(self.company)

    def test_pourcentage_valide_facture_le_pourcentage(self):
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21A',
            echeancier=[
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 40},
                {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 60},
            ])
        self.assertEqual(schedule_for_devis(devis),
                         [('acompte', 40.0), ('solde', 60.0)])
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['pourcentage'], Decimal('40.0'))
        # 40 % de 17 000 TTC.
        self.assertEqual(tranche['ttc'], Decimal('6800.00'))

    def test_montant_declare_vaut_ce_montant_et_non_un_pourcentage(self):
        """Fixture SOUS 1000 MAD (R4-B3) : 500 MAD d'acompte sur 17 000 TTC."""
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21B',
            echeancier=[
                {'libelle': 'Acompte fixe', 'type': 'acompte',
                 'unite': 'montant', 'pct_or_montant': 500},
                {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
            ])
        tranches = tranches_normalisees(devis)
        self.assertEqual(tranches[0]['unite'], UNITE_MONTANT)

        tranche = next_tranche(devis)
        # AVANT QJR21 : 500 était lu « 500 % » → 85 000 MAD de TTC facturé.
        self.assertEqual(tranche['ttc'], Decimal('500.00'))
        self.assertEqual(tranche['ht'] + tranche['tva'], Decimal('500.00'))
        # Le pourcentage publié est DÉRIVÉ (500 / 17 000), jamais la valeur
        # brute — c'est aussi ce qui garde ``Facture.pourcentage`` dans son
        # numeric(5, 2).
        self.assertEqual(tranche['pourcentage'], Decimal('2.94'))
        self.assertLess(tranche['pourcentage'], Decimal('100'))

    def test_echeancier_ambigu_deja_stocke_retombe_sur_le_defaut(self):
        """Lecture TOLÉRANTE : une donnée héritée ambiguë ne facture pas
        500 % du devis — elle retombe sur l'échéancier par défaut."""
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21C',
            echeancier=[
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 500},
            ])
        self.assertEqual(len(tranches_normalisees(devis)), 3)
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['ttc'], Decimal('5100.00'))  # 30 % de 17 000

    def test_echeancier_malforme_retombe_sur_le_defaut(self):
        devis = _devis(self.company, self.client_obj, f'DEV-{MONTH}-Q21D',
                       echeancier='pas-une-liste')
        self.assertEqual(len(schedule_for_devis(devis)), 3)


# ═══════════════════════════════════════════════════════════════════════════
# 3. L'API REFUSE EN 400 — la garde à l'écriture
# ═══════════════════════════════════════════════════════════════════════════
class ApiEcheancier(TestCase):

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = _devis(self.company, self.client_obj,
                            f'DEV-{MONTH}-Q21E',
                            statut=Devis.Statut.BROUILLON)

    def _patch(self, echeancier):
        return self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'echeancier': echeancier}, format='json')

    def test_pourcentage_valide_accepte(self):
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
            {'libelle': 'Matériel', 'type': 'intermediaire',
             'pct_or_montant': 60},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
        ])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(len(self.devis.echeancier), 3)

    def test_montant_declare_accepte(self):
        """Fixture SOUS 1000 MAD (R4-B3)."""
        reponse = self._patch([
            {'libelle': 'Acompte fixe', 'type': 'acompte',
             'unite': 'montant', 'pct_or_montant': 750},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
        ])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.echeancier[0]['unite'], 'montant')

    def test_valeur_ambigue_refusee_en_409_en_francais(self):
        # CI #997 (4) — règle inter-clés (unité déclarée) : 409, même message.
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 750},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
        ])
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('echeancier', reponse.data)
        message = str(reponse.data['echeancier'])
        self.assertIn('ambigu', message)
        self.assertIn('montant', message)
        # Rien n'a été écrit.
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.echeancier)

    def test_liste_attendue(self):
        reponse = self._patch({'acompte': 30})
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_ci997_4_tranche_vide_400_somme_409(self):
        """Cas kZprmM : ``[{}]`` est hors forme publiée (400) ; une tranche
        bien formée dont la somme ≠ 100 % est un 409 ; rien n'est écrit."""
        reponse = self._patch([{}])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('pct_or_montant', str(reponse.data['echeancier']))
        reponse = self._patch([{'pct_or_montant': 60}])
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('Total des tranches : 60 % — il doit faire 100 %.',
                      str(reponse.data['echeancier']))
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.echeancier)

    def test_echeancier_vide_reste_accepte(self):
        reponse = self._patch(None)
        self.assertEqual(reponse.status_code, 200, reponse.data)


# ═══════════════════════════════════════════════════════════════════════════
# 4. VNT25 — LE GESTE ÉCHÉANCIER (brouillon / envoyé / ACCEPTÉ)
# ═══════════════════════════════════════════════════════════════════════════
ECHEANCIER_30_60_10 = [
    {'type': 'acompte', 'libelle': 'Acompte', 'unite': 'pct',
     'pct_or_montant': 30},
    {'type': 'materiel', 'libelle': 'Livraison du matériel', 'unite': 'pct',
     'pct_or_montant': 60},
    {'type': 'solde', 'libelle': 'Solde', 'unite': 'pct',
     'pct_or_montant': 10}]
#: Forme stockée : 15 000 MAD, 60 %, 10 % (dernière = reste).
ECHEANCIER_LIBRE_VNT = [
    {'type': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
     'pct_or_montant': 15000},
    {'type': 'materiel', 'libelle': 'Livraison du matériel',
     'pct_or_montant': 60},
    {'type': 'solde', 'libelle': 'Solde', 'unite': 'pct',
     'pct_or_montant': 10}]
#: La forme du contrat ``devis_echeancier.json`` : 15 000 MAD, 60 %, reste.
ACOMPTE_LIBRE_15000 = [
    {'cle': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
     'valeur': '15000.00'},
    {'cle': 'materiel', 'libelle': 'Livraison du matériel', 'unite': 'pct',
     'valeur': '60.00'},
    {'cle': 'solde', 'libelle': 'Solde', 'unite': 'pct', 'valeur': '10.00'}]


def _tranches(entries):
    return valider_echeancier(entries, controler_somme=False)


class RegleSommeVente(SimpleTestCase):
    """``regle_somme_vente`` (pure) : Σ des NON dernières ≤ prix convenu,
    dernière = reste, tout-% = 100 — goldens du 388 (49 000)."""

    def test_acompte_libre_15000_puis_60_pct_permis(self):
        from apps.ventes.domain.modifiabilite import regle_somme_vente
        montants, reste = regle_somme_vente(
            _tranches(ECHEANCIER_LIBRE_VNT), Decimal('49000.00'))
        # 15 000 + 29 400 = 44 400 ≤ 49 000 (la règle « Σ des valeurs
        # déclarées ≤ TTC » aurait refusé 15 000 + 60 % + 10 % = 49 300).
        self.assertEqual(montants, [Decimal('15000.00'), Decimal('29400.00')])
        self.assertEqual(reste, Decimal('4600.00'))

    def test_acompte_egal_ou_superieur_au_prix_refuse(self):
        from apps.ventes.domain.modifiabilite import (
            CODE_SOMME_INVALIDE, EcheancierRefuse, regle_somme_vente)
        for acompte in (49000, 52000):
            with self.subTest(acompte=acompte), \
                    self.assertRaises(EcheancierRefuse) as ctx:
                regle_somme_vente(_tranches([
                    {'type': 'acompte', 'unite': 'montant',
                     'pct_or_montant': acompte},
                    {'type': 'solde', 'unite': 'pct', 'pct_or_montant': 10}]),
                    Decimal('49000.00'))
            self.assertEqual(ctx.exception.code, CODE_SOMME_INVALIDE)
            self.assertEqual(ctx.exception.status, 400)

    def test_somme_des_non_dernieres_au_dela_du_prix_refusee(self):
        from apps.ventes.domain.modifiabilite import (
            EcheancierRefuse, regle_somme_vente)
        with self.assertRaises(EcheancierRefuse) as ctx:
            regle_somme_vente(_tranches([
                {'type': 'acompte', 'unite': 'montant',
                 'pct_or_montant': 20000},
                {'type': 'materiel', 'unite': 'pct', 'pct_or_montant': 60},
                {'type': 'solde', 'unite': 'pct', 'pct_or_montant': 10}]),
                Decimal('49000.00'))  # 20 000 + 29 400 = 49 400
        self.assertEqual(ctx.exception.corps()['code'], 'somme_invalide')

    def test_tout_pourcentage_doit_faire_100(self):
        from apps.ventes.domain.modifiabilite import (
            EcheancierRefuse, regle_somme_vente)
        with self.assertRaises(EcheancierRefuse) as ctx:
            regle_somme_vente(_tranches([
                {'type': 'acompte', 'pct_or_montant': 30},
                {'type': 'materiel', 'pct_or_montant': 60},
                {'type': 'solde', 'pct_or_montant': 20}]),
                Decimal('49000.00'))
        self.assertEqual(ctx.exception.code, 'somme_invalide')
        self.assertIn('110', ctx.exception.detail)
        montants, reste = regle_somme_vente(
            _tranches(ECHEANCIER_30_60_10), Decimal('49000.00'))
        self.assertEqual(montants, [Decimal('14700.00'), Decimal('29400.00')])
        self.assertEqual(reste, Decimal('4900.00'))


class GesteEcheancierVente(TestCase):
    """``controler_echeancier_vente`` sur le panier réel du 388 + la trace
    « corrigé après acceptation »."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _388(self, reference, echeancier=ECHEANCIER_30_60_10, **champs):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        return creer_devis_388(self.company, self.user, self.client_obj,
                               reference, echeancier, **champs)

    def test_le_geste_est_permis_sur_un_accepte(self):
        from apps.ventes.domain import modifiabilite as mod
        devis = self._388('DEV-VNT25-V')
        self.assertTrue(mod.verdict(devis, mod.ECHEANCIER)['modifiable'])
        # L'en-tête reste figé : seul le geste ÉCHÉANCIER s'ouvre.
        self.assertFalse(mod.verdict(devis, mod.ENTETE)['modifiable'])
        for statut in ('refuse', 'expire'):
            with self.subTest(statut=statut):
                self.assertFalse(mod.verdict(
                    self._388(f'DEV-VNT25-{statut}', statut=statut),
                    mod.ECHEANCIER)['modifiable'])

    def test_388_acompte_15000_60_pct_reste_permis(self):
        from apps.ventes.domain.modifiabilite import controler_echeancier_vente
        devis = self._388('DEV-VNT25-388')
        entrees = controler_echeancier_vente(devis, ACOMPTE_LIBRE_15000)
        self.assertEqual(
            [(e['type'], e['unite'], Decimal(str(e['pct_or_montant'])))
             for e in entrees],
            [('acompte', 'montant', Decimal('15000')),
             ('materiel', 'pct', Decimal('60')),
             ('solde', 'montant', Decimal('4600'))])
        # Le contrôle n'écrit ni le devis ni son statut (règle #4).
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(devis.echeancier, ECHEANCIER_30_60_10)

    def test_acompte_au_prix_convenu_refuse_somme_invalide(self):
        from apps.ventes.domain.modifiabilite import (
            EcheancierRefuse, controler_echeancier_vente)
        devis = self._388('DEV-VNT25-PRIX')
        with self.assertRaises(EcheancierRefuse) as ctx:
            controler_echeancier_vente(devis, [
                {'cle': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
                 'valeur': '49000.00'},
                {'cle': 'solde', 'libelle': 'Solde', 'unite': 'pct',
                 'valeur': '10.00'}])
        self.assertEqual((ctx.exception.status, ctx.exception.code),
                         (400, 'somme_invalide'))

    def test_tranche_emise_modifiee_409_tranche_facturee(self):
        from apps.ventes.domain.modifiabilite import (
            EcheancierRefuse, controler_echeancier_vente)
        from apps.ventes.tests.test_echeancier_somme_total import (
            facture_tranche)
        devis = self._388('DEV-VNT25-EMIS')
        facture_tranche(devis, 'FAC-VNT25-1', 'acompte', '14700.00',
                        '12466.00', '2234.00')
        with self.assertRaises(EcheancierRefuse) as ctx:
            controler_echeancier_vente(devis, ACOMPTE_LIBRE_15000)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.corps(), {
            'detail': "La tranche « Acompte » est déjà facturée : elle ne "
                      'peut plus être modifiée.',
            'code': 'tranche_facturee',
            'tranche': {'cle': 'acompte', 'libelle': 'Acompte'}})
        # Supprimer la tranche couverte est refusé de même.
        with self.assertRaises(EcheancierRefuse) as ctx:
            controler_echeancier_vente(devis, [
                ACOMPTE_LIBRE_15000[1],
                dict(ACOMPTE_LIBRE_15000[2], unite='montant', valeur='0')])
        self.assertEqual(ctx.exception.code, 'tranche_facturee')
        # Les tranches NON couvertes se réécrivent, l'acompte inchangé.
        entrees = controler_echeancier_vente(devis, [
            dict(ECHEANCIER_30_60_10[0]),
            dict(ECHEANCIER_30_60_10[1], pct_or_montant=50),
            dict(ECHEANCIER_30_60_10[2], pct_or_montant=20)])
        self.assertEqual([e['pct_or_montant'] for e in entrees], [30, 50, 20])

    def test_version_remplacee_refusee(self):
        from apps.ventes.domain.modifiabilite import (
            DevisNonModifiable, controler_echeancier_vente)
        devis = self._388('DEV-VNT25-OLD', is_active=False)
        with self.assertRaises(DevisNonModifiable):
            controler_echeancier_vente(devis, ACOMPTE_LIBRE_15000)

    def test_trace_corrige_apres_acceptation(self):
        from apps.ventes.domain.modifiabilite import (
            consigner_correction_apres_envoi)
        devis = self._388('DEV-VNT25-TRACE')
        # Sans le drapeau, un accepté n'est pas tracé (QJR518 inchangé).
        self.assertIsNone(consigner_correction_apres_envoi(
            devis, user=self.user, objet='echeancier', resume='échéancier'))
        entree = consigner_correction_apres_envoi(
            devis, user=self.user, objet='echeancier', resume='échéancier',
            apres_acceptation=True)
        self.assertEqual(entree.field_label, 'Corrigé après acceptation')
        self.assertEqual(entree.body,
                         'Corrigé après acceptation — échéancier.')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertIn('resync_apres_envoi', devis.etude_params or {})


class ApiEcheancierVente(TestCase):
    """VNT66 — ``PUT devis/<id>/echeancier/`` : responsable 200 (devis avec
    son échéancier), Commercial 403 (palier), tranche émise modifiée 409."""

    # Même socle que le geste (panier réel du 388), sans en rejouer les tests.
    setUp = GesteEcheancierVente.setUp
    _388 = GesteEcheancierVente._388

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _put(self, devis, tranches, user=None):
        return self._api(user or self.user).put(
            f'/api/django/ventes/devis/{devis.id}/echeancier/',
            {'tranches': tranches}, format='json')

    def test_vnt66_responsable_200_echeancier_reecrit(self):
        devis = self._388('DEV-VNT66-10')
        r = self._put(devis, ACOMPTE_LIBRE_15000)
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(
            [(e['type'], e['unite']) for e in devis.echeancier],
            [('acompte', 'montant'), ('materiel', 'pct'),
             ('solde', 'montant')])
        self.assertEqual(devis.statut, 'accepte')

    def test_vnt66_commercial_403(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
        role = Role.objects.create(company=self.company, nom='Commercial 66',
                                   permissions=list(COMMERCIAL_PERMISSIONS))
        commercial = User.objects.create_user(
            username='vnt66_commercial', password='x', role=role,
            role_legacy='normal', company=self.company)
        devis = self._388('DEV-VNT66-20')
        r = self._put(devis, ACOMPTE_LIBRE_15000, user=commercial)
        self.assertEqual(r.status_code, 403, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.echeancier, ECHEANCIER_30_60_10)

    def test_vnt66_forme_publiee_400_et_regle_du_devis_409(self):
        """ENF11 — ``tranches`` requis, ``minItems: 1``, tranche de la forme
        publiée = 400 ; un corps conforme que le DEVIS refuse (somme
        au-delà du prix convenu, total en % ≠ 100) = 409 au même corps."""
        devis = self._388('DEV-VNT66-40')
        for corps in ([], [{}], [{'cle': 'a', 'valeur': 'abc'}],
                      [{'cle': 5, 'valeur': '10'}]):
            with self.subTest(tranches=corps):
                r = self._put(devis, corps)
                self.assertEqual(r.status_code, 400, r.data)
                self.assertEqual(r.data['code'], 'echeancier_invalide')
        r = self._api(self.user).put(
            f'/api/django/ventes/devis/{devis.id}/echeancier/', {},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        for tranches, code in (
                ([{'cle': 'acompte', 'libelle': 'A', 'unite': 'montant',
                   'valeur': '49000.00'},
                  {'cle': 'solde', 'libelle': 'S', 'unite': 'pct',
                   'valeur': '10.00'}], 'somme_invalide'),
                ([{'cle': 'acompte', 'libelle': 'A', 'unite': 'pct',
                   'valeur': '30.00'},
                  {'cle': 'solde', 'libelle': 'S', 'unite': 'pct',
                   'valeur': '30.00'}], None)):
            with self.subTest(code=code):
                r = self._put(devis, tranches)
                self.assertEqual(r.status_code, 409, r.data)
                if code:
                    self.assertEqual(r.data['code'], code)
        devis.refresh_from_db()
        self.assertEqual(devis.echeancier, ECHEANCIER_30_60_10)

    def test_vnt66_tranche_emise_modifiee_409(self):
        from apps.ventes.tests.test_echeancier_somme_total import (
            facture_tranche)
        devis = self._388('DEV-VNT66-30')
        facture_tranche(devis, 'FAC-VNT66-1', 'acompte', '14700.00',
                        '12466.00', '2234.00')
        r = self._put(devis, ACOMPTE_LIBRE_15000)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'tranche_facturee')
        self.assertEqual(r.data['tranche']['cle'], 'acompte')
        devis.refresh_from_db()
        self.assertEqual(devis.echeancier, ECHEANCIER_30_60_10)
