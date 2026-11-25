"""AMOT62 (C-AMOT-052) — la synthèse C&I décrit UNE option.

Sonde VC lci8 : devis commercial « Les deux » à panneaux 50 ``sans`` / 70
``avec`` — ``option_servie sans``, ``kwc sans/avec 35.5 49.7``, mais
``etude_ci`` calculée pour 49,7 kWc ; la production 79 482 kWh était imprimée
à côté de 35,5 kWc (2 239 kWh/kWc).

Deux gardes :
  * ``rafraichir_etude_ci_devis`` calcule l'étude pour l'option SERVIE
    (CIQ302 : l'offre réseau seule, sauf option AVEC acceptée) ;
  * ``synthese._systeme`` / ``synthese_ci`` omettent production ET taux (motif
    publié) quand le kWc servi s'écarte de plus de 2 % de celui de l'étude.

PVGIS simulé (patron CIQ119/CIQ210) ; AMOT113 : plus aucun ``mock.patch``
interne — les lignes du devis sont variantées pour de vrai (50 « sans » /
70 « avec »), ``puissances_etude_horaire`` les lit.

Test-du-test : remettre ``kwc, _kwc_sans = puissances_etude_horaire(devis)``
sans usage de l'option servie ⇒ ``test_etude_calculee_pour_l_option_servie``
rougit (étude à 49,7).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_amot62_ci_options_divergentes -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_ETUDE_AUTRE_PUISSANCE, synthese_ci,
)
from apps.ventes.tests import test_conception_lead as tcl
from apps.ventes.tests.test_ciq210_branchement import _BaseDevis

KWC_AVEC, KWC_SANS = 49.7, 35.5


class CiOptionsDivergentesTests(_BaseDevis):
    """AMOT113 — sur un devis RÉEL à lignes variantées (50 « sans » / 70
    « avec ») : aucune source moquée à part PVGIS (``setUp`` de ``_BaseDevis``)."""

    def _devis_variante(self, ref, mode):
        from apps.stock.models import Produit
        from apps.ventes.models import LigneDevis
        devis = self._devis(ref, mode=mode, tension='bt')
        LigneDevis.objects.filter(devis=devis, produit=self.panneau).update(
            variante='avec', quantite=Decimal('70'))
        LigneDevis.objects.filter(devis=devis, produit=self.ond).update(
            variante='sans')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('50'), prix_unitaire=Decimal('1272.73'),
            remise=Decimal('0'), variante='sans')
        # Le builder ne sert « deux options » (donc une option SERVIE) que si
        # les deux paniers existent : hybride + batterie côté « avec ».
        for nom, prix in (('Onduleur hybride Deye 50kW Triphasé', '60000'),
                          ('Batterie Dyness 10 kWh', '14000')):
            produit, _ = Produit.objects.get_or_create(
                company=self.co, nom=nom, defaults={
                    'prix_vente': Decimal(prix), 'prix_achat': Decimal('1')})
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), variante='avec')
        return devis

    def _rafraichir(self, devis):
        from apps.ventes.domain.etude_ci import rafraichir_etude_ci_devis
        rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        return (devis.etude_params or {}).get('etude_ci') or {}

    def _synthese(self, devis):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.options_pdf import clean_pdf_options
        devis = Devis.objects.get(pk=devis.pk)
        return synthese_ci(build_quote_data(devis, clean_pdf_options({})))

    def test_etude_calculee_pour_l_option_servie(self):
        devis = self._devis_variante('DEV-AMOT62-0010', 'commercial')
        etude = self._rafraichir(devis)
        self.assertEqual((etude.get('taille') or {}).get('retenue_kwc'),
                         KWC_SANS)
        # CLAUSE PERSISTANCE : rafraîchir deux fois → étude identique.
        self.assertEqual(self._rafraichir(devis), etude)

    def test_option_avec_acceptee_l_etude_suit(self):
        devis = self._devis_variante('DEV-AMOT62-0020', 'commercial')
        Devis.objects.filter(pk=devis.pk).update(
            option_acceptee='avec_batterie')
        devis.refresh_from_db()
        etude = self._rafraichir(devis)
        self.assertEqual((etude.get('taille') or {}).get('retenue_kwc'),
                         KWC_AVEC)

    def test_lignes_variantees_synthese_commercial_et_industriel(self):
        # AMOT113 (C-AMOT-VER-012) — kWc, production et taux de la synthèse
        # = ceux de l'étude rafraîchie du MÊME enregistrement.
        for mode, ref in (('commercial', 'DEV-AMOT62-0030'),
                          ('industriel', 'DEV-AMOT62-0031')):
            devis = self._devis_variante(ref, mode)
            etude = self._rafraichir(devis)
            synthese = self._synthese(devis)
            self.assertEqual(synthese['option_servie'], 'sans_batterie', mode)
            self.assertEqual(synthese['systeme']['kwc'], KWC_SANS, mode)
            self.assertEqual(synthese['systeme']['production_kwh_an'],
                             etude['bilan']['production_kwh'], mode)
            self.assertAlmostEqual(
                synthese['energie']['taux_autoconso_pct'],
                etude['bilan']['taux_autoconso'] * 100, delta=0.1, msg=mode)
            Devis.objects.filter(pk=devis.pk).update(
                option_acceptee='avec_batterie')
            devis.refresh_from_db()
            etude = self._rafraichir(devis)
            synthese = self._synthese(devis)
            self.assertEqual(synthese['systeme']['kwc'], KWC_AVEC, mode)
            self.assertEqual(etude['taille']['retenue_kwc'], KWC_AVEC, mode)
            self.assertEqual(synthese['systeme']['production_kwh_an'],
                             etude['bilan']['production_kwh'], mode)


def _data(kwc_servi, kwc_etude):
    """Charge C&I minimale de ``synthese_ci`` : option SANS servie à
    ``kwc_servi``, étude calculée pour ``kwc_etude``."""
    return {
        'mode_installation': 'commercial',
        'option_servie': 'sans', 'sans_ok': True, 'avec_ok': True,
        'puissance_kwc': KWC_AVEC, 'puissance_kwc_sans': kwc_servi,
        'puissance_kwc_avec': KWC_AVEC,
        'nb_panneaux_sans': 50, 'nb_panneaux_avec': 70,
        'etude': {'etude_ci': {
            'taille': {'retenue_kwc': kwc_etude},
            'bilan': {'production_kwh': 79482, 'taux_autoconso': 0.6,
                      'taux_couverture': 0.4},
        }},
    }


class SyntheseUneOptionTests(TestCase):

    def test_kwc_divergent_production_et_taux_omis(self):
        synthese = synthese_ci(_data(KWC_SANS, KWC_AVEC))
        self.assertEqual(synthese['systeme']['kwc'], KWC_SANS)
        self.assertIsNone(synthese['systeme']['production_kwh_an'])
        self.assertNotIn('energie', synthese)
        motifs = {(o['bloc'], o['motif']) for o in synthese['omissions']}
        self.assertIn(('systeme.production_kwh_an',
                       MOTIF_ETUDE_AUTRE_PUISSANCE), motifs)
        self.assertIn(('energie', MOTIF_ETUDE_AUTRE_PUISSANCE), motifs)

    def test_meme_option_production_et_taux_servis(self):
        synthese = synthese_ci(_data(KWC_SANS, KWC_SANS))
        self.assertEqual(synthese['systeme']['production_kwh_an'], 79482)
        self.assertIn('energie', synthese)

    def test_tolerance_de_deux_pour_cent(self):
        self.assertIsNotNone(synthese_ci(_data(35.5, 36.0))['systeme'][
            'production_kwh_an'])
        self.assertIsNone(synthese_ci(_data(35.5, 37.0))['systeme'][
            'production_kwh_an'])


class DevisAutoDeuxOptionsTests(tcl._emprunt(tcl.RelanceConceptionTests, '_relancer'),
                                tcl._emprunt(tcl.FigeageDevisAutoTests, *tcl._FABRIQUES), TestCase):
    """T4-X6-006 / T4-X6-013 — le devis AUTOMATIQUE commercial à deux options de tailles
    différentes (cas ``ci_commercial_deux_options`` des goldens du moteur unique) : le retour
    lu par la fiche du lead et le câble DC de chaque option."""

    def test_t4x6006_payback_c_et_i_celui_que_le_pdf_imprime(self):
        """T4-X6-006 — carte « Retour … d'après le devis DEV-… » d'un commercial à deux options :
        le retour IMPRIMÉ par le PDF du même devis (« sans » : ``synthese_ci`` › ``argent`` de
        ``economie_ci_pour_devis`` ; « avec » : ``etude_ci.option_avec.retour_simple_ans``), jamais
        ``payback_publiable`` sur le TTC (6,5 ans servis contre 5,5 imprimés) ; à côté, le montant
        et l'économie de CE calcul, avec leur base (HT quand la TVA est récupérable)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto

        company, lead = self._cas('ci_commercial_deux_options')
        tcl._reglages_de_la_societe(company)
        self._relancer(lead, company, tcl._declencheur())
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        imprime = {'sans': chiffres_cles(synthese_ci(data))['payback_ans'],
                   'avec': valeur_option_avec(data)['retour_simple_ans']}
        lue = conception_courante(company, lead.pk)
        self.assertEqual(sorted(lue['valeurs']), ['avec', 'sans'])
        for option, attendu in imprime.items():
            with self.subTest(option=option):
                payback = lue['valeurs'][option]['payback']
                self.assertIsNotNone(attendu)
                self.assertEqual((payback['valeur'], payback['source']), (attendu, 'devis'))
                self.assertEqual(payback['base'], 'HT')
                self.assertGreater(payback['investissement'], 0)
                self.assertGreater(payback['economie_annuelle'], 0)
        self.assertEqual(tcl._cles_interdites(lue), [])

    def test_t4x6013_chaque_option_porte_son_cable_dc(self):
        """T4-X6-013 — deux options de tailles différentes (lead X6-f : 49 panneaux sans,
        51 avec, un hybride) : l'option « avec » n'avait AUCUN câble solaire DC. Établi : la
        fusion (``etude_ci_batterie._fusion_variantee``) garde chaque ligne ; c'est l'option
        « avec » composée sur des hybrides dont les chaînes ne se câblent pas (bloquant
        ``OND_CHAINES_NON_FAISABLES``) : ``composer_ci`` met câble DC et protections DC « à
        chiffrer après la visite » (ADEV87), ``lignes_du_devis_ci`` les écarte, rien ne le dit.
        Désormais : chaînes câblables ⇒ chaque option SA ligne de câble à SA quantité ; chaînes
        infaisables ⇒ l'option « avec » n'est pas composée et l'alerte le dit (ADEV87)."""
        from apps.stock.models import Produit
        from apps.ventes.moteur_ci import onduleurs as ond
        from apps.ventes.services import build_devis_auto

        def cables(devis):
            cable = Produit.objects.get(company=devis.company, role_ci='cable_dc')
            return {li.variante: li.quantite for li in devis.lignes.filter(produit=cable)}

        company, lead = self._cas('ci_commercial_deux_options')
        tcl._reglages_de_la_societe(company)
        user = self._utilisateur(company)
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=user, company=company)
        panneaux = {v: devis.lignes.filter(variante=v, designation__startswith='Panneau').get().quantite
                    for v in ('sans', 'avec')}
        self.assertNotEqual(panneaux['sans'], panneaux['avec'])
        self.assertEqual(sorted(cables(devis)), ['avec', 'sans'])  # chaque option SON câble
        self.assertNotEqual(cables(devis)['sans'], cables(devis)['avec'])
        vrai = ond._concevoir

        def hybride_infaisable(module, c, nb):  # le cas X6-f : 51 modules sur un hybride 20 kW
            res = vrai(module, c, nb)
            if res is not None and 'hybride' in (c.get('nom') or '').lower():
                res = dict(res, bloquants=['aucune découpe ne raccorde les modules'])
            return res
        with tcl.mock.patch.object(ond, '_concevoir', side_effect=hybride_infaisable):
            with self.captureOnCommitCallbacks(execute=True):
                journal = {}
                devis2 = build_devis_auto(lead=lead, user=user, company=company, journal_auto=journal)
        self.assertFalse(devis2.lignes.filter(variante='avec').exists())  # jamais une option sans son câble
        self.assertEqual(list(cables(devis2).values()), [cables(devis)['sans']])
        alertes = [a for a in journal.get('alertes') or [] if a.get('code') == 'OPTION_BATTERIE_NON_COMPOSEE']
        self.assertEqual(len(alertes), 1, journal.get('alertes'))  # dit au vendeur (alerte du devis créé)
        self.assertIn('chaînes non câblables', alertes[0]['message'])
