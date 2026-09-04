"""QJR410 — trois petits écarts de chiffre CLIENT sur le document, corrigés
ensemble parce qu'ils vivent dans le même bloc de rendu.

TESTS ROUGES D'ABORD, un par écart :

(a) **S8-F6** — ``_ref_total = total_sans if sans_ok else total_avec`` était
    clavé sur ``sans_ok``, et ``etude["payback"] = roi["roi_s"]`` câblé en dur
    sur le ROI « sans ». Sur un document dont l'option TITRÉE est « avec », la
    carte « Prix par kWc » et le payback décrivaient donc l'option SANS — un
    chiffre CLIENT qui décrit une offre que le document ne porte pas.

(b) **S8-F8** — le document arrondissait le prix unitaire remisé à 2 décimales
    AVANT de le multiplier par la quantité, puis alimentait le noyau monnaie
    avec ce PU déjà arrondi, là où ``Devis.total_ht`` appelle LE MÊME
    ``totaux()`` sur les lignes BRUTES : même fonction, deux entrées.

(c) **S8-F7** — ``domain.scenario.puissance_kwc_du_devis``, unique
    propriétaire déclaré du kWc d'un devis, SOMMAIT les lignes panneau des
    DEUX variantes : sur un devis à deux options aux champs PV divergents il
    stockait un compte de panneaux qui n'existe sur aucune des deux options.
    (Constat « low » : aucune surface client prouvée — aucun impact client
    n'est inventé ici.)

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr410_chiffres_document"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


LIGNES_DEUX_OPTIONS = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: (b) — une ligne REMISÉE de quantité 3 : 999,99 × (1 − 7 %) = 929,9907, un
#: prix unitaire dont l'arrondi à 2 décimales change le total de la ligne.
LIGNE_REMISEE = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Optimiseur de puissance', '3', '999.99'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
]

#: (c) — deux champs PV DIVERGENTS : 12 panneaux « sans », 16 « avec ».
LIGNES_VARIANTES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', 'sans'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', 'avec'),
    ('Batterie Dyness 10 kWh', '1', '25000', 'avec'),
    ('Panneau Canadian Solar 710W', '12', '1166.67', 'sans'),
    ('PV Panneau Canadian Solar 710W', '16', '1166.67', 'avec'),
    ('Installation', '1', '5000', ''),
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._seq = 0

    def _devis(self, lignes, etude_params=None, variantes=False):
        self._seq += 1
        devis = make_devis(
            self.company, self.user, self.client_obj,
            [ligne[:3] for ligne in lignes],
            reference='DEV-QJR410-%04d' % self._seq,
            etude_params=etude_params)
        if variantes:
            for ligne, source in zip(devis.lignes.order_by('id'), lignes):
                ligne.variante = source[3]
                ligne.save(update_fields=['variante'])
        return devis


class A_PrixKwcEtPaybackSuiventLOptionTitree(_Base):
    """(a) S8-F6."""

    ETUDE = dict(DEUX_OPTIONS, production_annuelle=14000,
                 economies_annuelles=20000)

    def test_le_payback_decrit_l_option_titree(self):
        """ROUGE AVANT : payback = total « sans » / économies, alors que le
        document titre l'option « avec »."""
        devis = self._devis(LIGNES_DEUX_OPTIONS, etude_params=self.ETUDE)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['nb_options'], 2)
        attendu = round(data['total_avec'] / 20000, 1)
        self.assertEqual(data['etude']['payback'], attendu)

    def test_le_prix_par_kwc_decrit_l_option_titree(self):
        devis = self._devis(LIGNES_DEUX_OPTIONS, etude_params=self.ETUDE)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        kwc = data['puissance_kwc']
        self.assertTrue(kwc)
        self.assertEqual(data['etude']['prix_kwc'],
                         round(data['total_avec'] / kwc))


class B_LeTotalDuDocumentEgaleCeluiDuDevis(_Base):
    """(b) S8-F8 — même fonction, une seule entrée."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(LIGNE_REMISEE,
                                 etude_params={'scenario': 'Sans batterie'})
        LigneDevis.objects.filter(
            devis=self.devis,
            designation='Optimiseur de puissance').update(remise=Decimal('7'))
        self.devis.refresh_from_db()

    def test_le_document_et_le_devis_sont_d_accord_au_centime(self):
        """ROUGE AVANT : le PU remisé était arrondi à 2 décimales AVANT d'être
        multiplié par 3 — les deux totaux dérivaient."""
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        document = Decimal(str(data['totaux_all']['ht_net']))
        devis_ht = Decimal(str(self.devis.total_ht))
        self.assertLessEqual(
            abs(document - devis_ht), Decimal('0.01'),
            'document %s != Devis.total_ht %s' % (document, devis_ht))

    def test_le_total_de_ligne_imprime_est_celui_qui_est_facture(self):
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        ligne = [it for it in data['all_items']
                 if it['designation'] == 'Optimiseur de puissance'][0]
        exact = (Decimal('999.99') * Decimal('0.93') * Decimal('3'))
        imprime = (Decimal(str(ligne['prix_unit_ht']))
                   * Decimal(str(ligne['quantite'])))
        self.assertLessEqual(abs(imprime - exact), Decimal('0.01'))


class C_LeKwcStockeEstCeluiDUneOption(_Base):
    """(c) S8-F7."""

    def test_le_kwc_n_est_pas_la_somme_des_deux_variantes(self):
        """ROUGE AVANT : 12 + 16 = 28 panneaux, un compte qui n'existe sur
        aucune des deux options."""
        from apps.ventes.domain.scenario import puissance_kwc_du_devis
        devis = self._devis(LIGNES_VARIANTES,
                            etude_params=dict(DEUX_OPTIONS), variantes=True)
        kwc = puissance_kwc_du_devis(devis)
        self.assertIsNotNone(kwc)
        # L'option AVEC porte 16 panneaux × 710 W = 11,36 kWc.
        self.assertEqual(kwc, round(16 * 710 / 1000, 2))


class NonRegressionMonoOptionNonRemise(_Base):
    """Un devis mono-option non remisé est inchangé sur les trois axes."""

    def setUp(self):
        super().setUp()
        self.devis = self._devis(
            [('Onduleur réseau Huawei 10kW Triphasé', '1', '16000'),
             ('Panneau Canadian Solar 710W', '14', '1200'),
             ('Installation', '1', '5000')],
            etude_params={'scenario': 'Sans batterie',
                          'production_annuelle': 14000,
                          'economies_annuelles': 20000})

    def test_les_trois_axes_sont_inchanges(self):
        from apps.ventes.domain.scenario import puissance_kwc_du_devis
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['nb_options'], 1)
        # (a) mono-option « sans » : la branche titrée EST « sans ».
        self.assertEqual(data['etude']['payback'],
                         round(data['total_sans'] / 20000, 1))
        # (b) aucune remise ⇒ prix unitaires entiers, totaux inchangés.
        document = Decimal(str(data['totaux_all']['ht_net']))
        self.assertLessEqual(
            abs(document - Decimal(str(self.devis.total_ht))),
            Decimal('0.01'))
        # (c) une seule option ⇒ aucun filtre, kWc des lignes.
        self.assertEqual(puissance_kwc_du_devis(self.devis),
                         round(14 * 710 / 1000, 2))
