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


class DesignationGardeLesDeuxOptionsTests(tcl._emprunt(tcl.RelanceConceptionTests, '_relancer'),
                                          tcl._emprunt(tcl.RelanceEnTacheTests, '_calepinage_designe'),
                                          tcl._emprunt(tcl.FigeageDevisAutoTests, *tcl._FABRIQUES), TestCase):
    """D-ACAL-109 / D-ACAL-110 (fondateur, 25/11/2026) — un onduleur désigné à la main sert
    l'option qui lui convient ; l'AUTRE option reste, celle que le moteur compose sans
    désignation ; un module d'une autre puissance garde la puissance de CHAQUE option, au
    panneau le plus proche, et la conception le dit (phrase servie). Mutant « une seule
    option forcée par l'onduleur » (le comportement d'avant) : rouge."""

    def _temoin(self, cas='res_facture_dirhams'):
        from apps.ventes.selectors import conception_courante
        company, lead = self._cas(cas)
        tcl._reglages_de_la_societe(company)
        self._relancer(lead, company, tcl._declencheur())
        return company, lead, conception_courante(company, lead.pk)

    def _designer(self, company, lead, **entree):
        from apps.ventes.selectors import conception_courante
        calepinage = self._calepinage_designe(company, lead, **entree)
        self._relancer(lead, company, tcl._declencheur('pose_enregistree'), calepinage_id=calepinage.pk)
        lue = conception_courante(company, lead.pk)
        self.assertEqual(lue['etat'], 'complet', lue['refus'])
        return lue

    @staticmethod
    def _materiel(valeurs):
        return {cle: valeurs[cle]['valeur'] for cle in (
            'nb_panneaux', 'puissance_kwc', 'module_produit', 'onduleur_produit', 'batterie_produit',
            'production_annuelle', 'economies_annuelles')}

    def test_hybride_designe_l_option_sans_batterie_reste_celle_du_moteur(self):
        from apps.stock.models import Produit
        company, lead, temoin = self._temoin()
        self.assertEqual(sorted(temoin['valeurs']), ['avec', 'sans'])
        deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
        lue = self._designer(company, lead, onduleur_produit=deye.pk)
        self.assertEqual(sorted(lue['valeurs']), ['avec', 'sans'])
        self.assertEqual(lue['option_retenue'], 'avec')
        avec, sans = lue['valeurs']['avec'], lue['valeurs']['sans']
        self.assertEqual((avec['onduleur_produit']['valeur'], avec['onduleur_produit']['source']),
                         (deye.pk, 'impose'))
        self.assertEqual(sans['onduleur_produit']['source'], 'moteur')
        self.assertEqual(self._materiel(sans), self._materiel(temoin['valeurs']['sans']))
        dite = next(s for s in lue['suppositions'] if s['code'] == 'option_materiel_du_moteur')
        self.assertEqual(dite['message'], (
            "Onduleur désigné à la main « Onduleur hybride Deye 5kW Monophasé » : il sert l'option "
            "avec batterie ; l'option sans batterie garde l'onduleur choisi par le moteur."))
        self.assertEqual((dite['champ'], dite['valeur'], dite['source']), ('onduleur_produit', 'sans', 'defaut'))
        self.assertEqual(tcl._cles_interdites(lue), [])

    def test_reseau_designe_l_option_avec_batterie_reste_celle_du_moteur(self):
        from apps.stock.models import Produit
        company, lead, temoin = self._temoin()
        huawei = Produit.objects.get(company=company, nom='Onduleur réseau Huawei 5kW Monophasé')
        lue = self._designer(company, lead, onduleur_produit=huawei.pk)
        self.assertEqual((sorted(lue['valeurs']), lue['option_retenue']), (['avec', 'sans'], 'sans'))
        self.assertEqual(lue['valeurs']['sans']['onduleur_produit']['valeur'], huawei.pk)
        self.assertEqual(self._materiel(lue['valeurs']['avec']), self._materiel(temoin['valeurs']['avec']))
        dite = next(s for s in lue['suppositions'] if s['code'] == 'option_materiel_du_moteur')
        self.assertTrue(dite['message'].endswith(
            "il sert l'option sans batterie ; l'option avec batterie garde l'onduleur choisi par le moteur."))

    def test_module_designe_chaque_option_garde_sa_puissance_au_plus_proche_et_le_dit(self):
        from apps.stock.models import Produit
        from apps.ventes.domain.taille import panneaux_pour_la_meme_puissance
        from apps.ventes.selectors import conception_courante
        # Le module désigné existe AVANT le témoin : le moteur garde le sien (550 Wc, le plus puissant).
        company, lead = self._cas('res_facture_dirhams')
        module = Produit.objects.create(company=company, nom='Panneau Désigné 450W', sku='ACAL110-450',
                                        prix_vente=Decimal('1000'), prix_achat=Decimal('1'), quantite_stock=80)
        tcl._reglages_de_la_societe(company)
        self._relancer(lead, company, tcl._declencheur())
        temoin = conception_courante(company, lead.pk)
        self.assertNotIn(module.pk, {v['module_produit']['valeur'] for v in temoin['valeurs'].values()})
        lue = self._designer(company, lead, module_produit=module.pk)
        self.assertEqual(sorted(lue['valeurs']), ['avec', 'sans'])
        arrondis = {s['valeur']['option']: s for s in lue['suppositions'] if s['code'] == 'panneaux_au_module_designe'}
        for option in ('sans', 'avec'):
            with self.subTest(option=option):
                moteur = temoin['valeurs'][option]
                attendu = panneaux_pour_la_meme_puissance(moteur['puissance_kwc']['valeur'], 450)
                valeurs = lue['valeurs'][option]
                self.assertEqual((valeurs['module_produit']['valeur'], valeurs['module_produit']['source']),
                                 (module.pk, 'impose'))
                self.assertEqual(valeurs['nb_panneaux']['valeur'], attendu)
                dite = arrondis[option]
                self.assertEqual((dite['champ'], dite['valeur']['moteur']['nb_panneaux'],
                                  dite['valeur']['retenu']['nb_panneaux']),
                                 ('module_produit', moteur['nb_panneaux']['valeur'], attendu))
                label = 'sans batterie' if option == 'sans' else 'avec batterie'
                self.assertTrue(dite['message'].startswith(
                    'Module désigné « Panneau Désigné 450W » (450 Wc) : option %s à %d panneaux pour ' % (
                        label, attendu)), dite['message'])
                self.assertTrue(dite['message'].endswith(
                    ' calculés par le moteur depuis la facture (au panneau le plus proche de la même puissance).'))
        self.assertEqual(tcl._cles_interdites(lue), [])

    def test_lead_qui_demande_la_batterie_garde_une_option(self):
        from apps.stock.models import Produit
        company, lead, temoin = self._temoin('res_batterie_avec')
        self.assertEqual(sorted(temoin['valeurs']), ['avec'])
        deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
        lue = self._designer(company, lead, onduleur_produit=deye.pk)
        self.assertEqual(sorted(lue['valeurs']), ['avec'])
        self.assertNotIn('option_materiel_du_moteur', [s['code'] for s in lue['suppositions']])

    def test_devis_automatique_d_une_conception_designee_a_deux_options(self):
        from apps.stock.models import Produit
        from apps.ventes.services import build_devis_auto
        company, lead, _temoin = self._temoin()
        deye = Produit.objects.get(company=company, nom='Onduleur hybride Deye 5kW Monophasé')
        self._designer(company, lead, onduleur_produit=deye.pk)
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        self.assertEqual(set(devis.lignes.exclude(variante='').values_list('variante', flat=True)), {'avec', 'sans'})


class ConceptionEtDevisOptionsDivergentesTests(tcl._emprunt(tcl.RelanceConceptionTests, '_relancer'),
                                               tcl._emprunt(tcl.FigeageDevisAutoTests, *tcl._FABRIQUES), TestCase):
    """T4-X7-022 / T4-X7-001 (résidentiel) — le souhait de batterie change les options de la
    conception, et le retour servi d'une conception à une option sur un devis à deux options
    porte sur les lignes de CETTE option seulement."""

    def test_t4x7022_batterie_avec_puis_les_deux_options_range_les_deux(self):
        """T4-X7-022 — « Batterie » Avec → « Les deux options » : la carte gardait UNE taille
        (empreinte des entrées sans les souhaits ⇒ rien rangé) quand le devis auto en donnait
        deux. Le souhait entre dans l'empreinte : version suivante, les deux options, et la
        lecture ne la dit périmée qu'avant ce rangement."""
        from apps.crm.models import Lead
        from apps.ventes.selectors_conception import _empreinte_des_entrees

        company, lead = self._cas('res_batterie_avec')
        tcl._reglages_de_la_societe(company)
        premiere = self._relancer(lead, company, tcl._declencheur())
        self.assertEqual(set(premiere.conception.valeurs), {'avec'})
        Lead.objects.filter(pk=lead.pk).update(batterie_souhaitee='les_deux')
        lead.refresh_from_db()
        self.assertNotEqual(_empreinte_des_entrees(premiere.conception), premiere.conception.empreinte)
        suivante = self._relancer(lead, company, tcl._declencheur(
            'lead_entrees_modifiees', batterie_souhaitee=('avec', 'les_deux')))
        self.assertTrue(suivante.ecrite)  # mutant « souhaits hors empreinte » : False, une option
        self.assertEqual(set(suivante.conception.valeurs), {'sans', 'avec'})
        self.assertEqual(_empreinte_des_entrees(suivante.conception), suivante.conception.empreinte)

    def test_t4x7001_conception_a_une_option_sur_un_devis_a_deux_options(self):
        """T4-X7-001 — « Retour 16,4 ans — 97 400 MAD pour 7 987 MAD/an » : la conception n'a qu'une
        option (batterie « Avec ») mais le devis de référence en porte deux ; le montant servi
        était la somme des lignes des DEUX options. Il est celui des lignes de CETTE option,
        découpées comme le PDF, et le retour est calculé dessus."""
        from apps.crm.models import Lead
        from apps.ventes.selectors import conception_courante
        from apps.ventes.services import build_devis_auto
        from apps.ventes.utils.options import (AVEC_BATTERIE, deux_options_declarees, filter_lines_for_option,
                                               lignes_avec_produit, option_totaux)

        company, lead = self._cas('res_batterie_avec')
        tcl._reglages_de_la_societe(company)
        Lead.objects.filter(pk=lead.pk).update(batterie_souhaitee='les_deux')
        lead.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        devis.refresh_from_db()
        self.assertTrue(deux_options_declarees(devis))
        Lead.objects.filter(pk=lead.pk).update(batterie_souhaitee='avec')
        lead.refresh_from_db()
        self._relancer(lead, company, tcl._declencheur('lead_entrees_modifiees',
                                                       batterie_souhaitee=('les_deux', 'avec')))
        lue = conception_courante(company, lead.pk)
        self.assertEqual((set(lue['valeurs']), lue['payback_devis']['devis_ref']), ({'avec'}, devis.reference))
        lignes = list(lignes_avec_produit(devis))
        de_l_option = option_totaux(devis, '', lignes=filter_lines_for_option(lignes, AVEC_BATTERIE, devis=devis))
        payback = lue['valeurs']['avec']['payback']
        self.assertLess(de_l_option['ttc'], option_totaux(devis, '', lignes=lignes)['ttc'])
        self.assertAlmostEqual(payback['investissement_ttc'], float(de_l_option['ttc']), places=2)  # mutant : la somme
