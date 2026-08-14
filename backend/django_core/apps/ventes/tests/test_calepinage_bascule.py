"""AOF164 — bascule A/B du devis résidentiel sur le moteur de calepinage.

Ce module verrouille les promesses de la bascule, et rien de plus :

  1. **Drapeau OFF = comportement bit-identique.** C'est le défaut. Aucun appel
     moteur, aucun journal, le même devis qu'hier — un drapeau de bascule qui
     change quelque chose quand il est baissé n'est pas un drapeau de bascule.
  2. **Drapeau ON = compte issu du moteur + écart journalisé.** L'arbitrage se
     juge sur des écarts mesurés, pas sur une conviction.
  3. **Un devis déjà émis n'est JAMAIS recalculé.** Un client qui a reçu
     « 24 panneaux » a reçu 24 panneaux, quelle que soit l'opinion ultérieure
     du moteur.
  4. **Les mots-clés de classification de ``solar.js`` sont INCHANGÉS** — ils
     sont le contrat d'alignement avec ``quote_engine/builder.py`` dont dépend
     le découpage des options du PDF (CLAUDE.md, règle #4). Cette tâche ne
     touche que le COMPTE.
  5. **PVG2 — le moteur ne gagne que DANS la tolérance.** Un écart de quelques
     modules est une correction (c'est le but de la bascule) ; un écart énorme
     est une ANOMALIE : le compte historique est conservé et l'écart part en
     avertissement structuré. Sécurité par défaut, jamais un remplacement
     silencieux (décision fondateur).

Run :
    python manage.py test apps.ventes.tests.test_calepinage_bascule -v2
"""
import io
import math
import os
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes import selectors, services
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_from_layout

User = get_user_model()

#: Racine du dépôt — remontée depuis backend/django_core/apps/ventes/tests/.
RACINE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '..'))
SOLAR_JS = os.path.join(RACINE, 'frontend', 'src', 'features', 'ventes',
                        'solar.js')

#: Ancre géographique de la toiture d'essai (Casablanca).
LAT0, LNG0 = 33.5731, -7.5898
#: Rectangle 14 m (est-ouest) × 10 m (nord-sud), CENTRÉ sur l'ancre.
DEMI_LARGEUR_M, DEMI_HAUTEUR_M = 7.0, 5.0
RAYON_TERRE_M = 6378137.0


def _vers_geo(est_m, nord_m):
    """(est, nord) mètres -> (lng, lat), projection ENU locale sur l'ancre."""
    m_par_deg_lat = RAYON_TERRE_M * math.pi / 180.0
    m_par_deg_lng = m_par_deg_lat * math.cos(math.radians(LAT0))
    return (LNG0 + est_m / m_par_deg_lng, LAT0 + nord_m / m_par_deg_lat)


def layout_avec_geometrie(panels=12, kwc=6.6):
    """Layout roofPro11 RÉALISTE : un pan plat avec ses ``vertices`` LngLat."""
    sommets = [
        list(_vers_geo(-DEMI_LARGEUR_M, -DEMI_HAUTEUR_M)),
        list(_vers_geo(DEMI_LARGEUR_M, -DEMI_HAUTEUR_M)),
        list(_vers_geo(DEMI_LARGEUR_M, DEMI_HAUTEUR_M)),
        list(_vers_geo(-DEMI_LARGEUR_M, DEMI_HAUTEUR_M)),
    ]
    return {
        'scenario': 'reseau',
        'panelWatt': 550,
        'result': {'panels': panels, 'kwc': kwc,
                   'annualKwh': 10800, 'savings': 9200},
        'zones': [{
            'id': 'Z1',
            'label': 'Toit principal',
            'vertices': sommets,
            'obstacles': [],
            'roofType': 'flat',
            'pitchDeg': 0,
            'facingAzimuthDeg': 0,
            'neededPanels': panels,
            'result': {'count': panels, 'kwc': kwc, 'areaM2': 140.0},
        }],
    }


def layout_sans_geometrie(panels=12, kwc=6.6):
    """Le layout HISTORIQUE : un bloc ``result`` et rien d'autre."""
    return {'scenario': 'reseau', 'panelWatt': 550,
            'result': {'panels': panels, 'kwc': kwc,
                       'annualKwh': 10800, 'savings': 9200}}


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company):
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku, prix_vente=Decimal(prix),
            prix_achat=Decimal('1'), quantite_stock=100)
    mk('Panneau Jinko 550W', 'PAN-%s' % company.pk, 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', 'ONDR-%s' % company.pk, 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', 'ONDH-%s' % company.pk, 17000)
    mk('Batterie Deyness 5 kWh', 'BAT-%s' % company.pk, 17000)


class _Base(TestCase):
    def setUp(self):
        self.company = make_company('aof164-co')
        self.user = User.objects.create_user(
            username='aof164', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self):
        return Lead.objects.create(
            company=self.company, nom='Bascule', prenom='Villa',
            email='bascule@ex.com')

    def _panneaux(self, devis):
        for ligne in devis.lignes.all():
            if 'Panneau' in ligne.designation:
                return int(ligne.quantite)
        return 0


class LeDrapeauEstBaisseParDefaut(SimpleTestCase):
    def test_absence_de_reglage_vaut_off(self):
        """Un réglage ABSENT vaut OFF — jamais l'inverse."""
        self.assertFalse(services.moteur_calepinage_actif())

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_le_drapeau_se_leve(self):
        self.assertTrue(services.moteur_calepinage_actif())

    def test_off_court_circuite_avant_tout_calcul(self):
        """Drapeau OFF : ``arbitrer`` rend ``None`` sans toucher au moteur."""
        appels = []

        def _mouchard(_layout, **_kwargs):
            appels.append(1)
            return {'modules': 999, 'pans': ()}

        original = services.compte_moteur_du_layout
        services.compte_moteur_du_layout = _mouchard
        try:
            self.assertIsNone(
                services.arbitrer_compte_calepinage(
                    layout_avec_geometrie(), 12))
        finally:
            services.compte_moteur_du_layout = original
        self.assertEqual(appels, [])


class DrapeauOffLeComportementNeBougePas(_Base):
    def test_le_compte_reste_celui_du_layout(self):
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(panels=12, kwc=6.6),
            user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 12)
        self.assertEqual(devis.etude_params['puissance_kwc'], 6.6)

    def test_un_layout_sans_geometrie_reste_identique(self):
        devis = build_devis_from_layout(
            layout=layout_sans_geometrie(panels=9, kwc=4.95),
            user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 9)

    def test_le_devis_reste_un_brouillon(self):
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(), user=self.user,
            company=self.company, lead=self._lead())
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


@override_settings(USE_MOTEUR_CALEPINAGE=True)
class DrapeauOnLeMoteurDonneLeCompte(_Base):
    def _layout_a_un_module_pres(self):
        """Layout dont le compte TypeScript diverge d'UN module du moteur.

        PVG2 — la bascule ne gagne QUE dans sa tolérance : un layout qui annonce
        n'importe quoi (12 face à 40) est désormais une ANOMALIE, pas une
        correction. On mesure donc le moteur d'abord et on fait annoncer au
        layout un module de moins : l'écart reste une vraie divergence, mais du
        genre que la bascule a été construite pour corriger.

        (``_zone_villa_depuis_pan`` ne transmet NI ``neededPanels`` NI
        ``result.count`` au moteur : changer le compte annoncé ne change donc
        jamais ce que le moteur compte sur cette géométrie.)
        """
        mesure = services.compte_moteur_du_layout(layout_avec_geometrie())
        self.assertIsNotNone(mesure)
        self.assertGreater(mesure['modules'], 1)
        annonce = mesure['modules'] - 1
        return mesure, layout_avec_geometrie(
            panels=annonce, kwc=round(annonce * 0.55, 3))

    def test_le_compte_vient_du_moteur_et_diverge_du_typescript(self):
        """Le layout annonce un compte ; le moteur tranche (écart toléré)."""
        mesure, layout = self._layout_a_un_module_pres()
        # Le test n'aurait aucune valeur si les deux comptes coïncidaient : la
        # divergence EST ce que la bascule doit corriger.
        self.assertNotEqual(mesure['modules'], layout['result']['panels'])
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertEqual(self._panneaux(devis), mesure['modules'])

    def test_le_kwc_suit_le_compte(self):
        mesure, layout = self._layout_a_un_module_pres()
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        attendu = round(mesure['modules'] * 550 / 1000.0, 3)
        self.assertAlmostEqual(devis.etude_params['puissance_kwc'], attendu, 3)

    def test_l_ecart_est_journalise(self):
        with self.assertLogs('apps.ventes.services', level='INFO') as journal:
            services.arbitrer_compte_calepinage(layout_avec_geometrie(), 12)
        self.assertTrue(any('AOF164' in ligne and 'écart' in ligne
                            for ligne in journal.output), journal.output)

    def test_sans_geometrie_le_moteur_se_tait_et_rien_ne_change(self):
        self.assertIsNone(
            services.compte_moteur_du_layout(layout_sans_geometrie()))
        self.assertIsNone(
            services.arbitrer_compte_calepinage(layout_sans_geometrie(), 9))
        devis = build_devis_from_layout(
            layout=layout_sans_geometrie(panels=9, kwc=4.95),
            user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 9)

    def test_une_panne_du_moteur_ne_casse_jamais_la_creation(self):
        """Le devis se construit même si le moteur explose — compte historique."""
        def _explose(_layout, **_kwargs):
            raise RuntimeError('moteur indisponible')

        original = services.compte_moteur_du_layout
        services.compte_moteur_du_layout = _explose
        try:
            self.assertIsNone(
                services.arbitrer_compte_calepinage(
                    layout_avec_geometrie(), 12))
            devis = build_devis_from_layout(
                layout=layout_avec_geometrie(panels=12, kwc=6.6),
                user=self.user, company=self.company, lead=self._lead())
        finally:
            services.compte_moteur_du_layout = original
        self.assertEqual(self._panneaux(devis), 12)

    def test_un_pan_a_la_geometrie_invalide_est_ignore(self):
        casse = layout_avec_geometrie()
        casse['zones'][0]['vertices'] = [[0, 0], [1, 1]]
        self.assertIsNone(services.compte_moteur_du_layout(casse))

    def test_aucune_ligne_ao_n_est_creee_par_un_devis_villa(self):
        from apps.ao.models import AppelOffre, ToitureAO, VarianteCalepinage

        avant = (AppelOffre.objects.count(), ToitureAO.objects.count(),
                 VarianteCalepinage.objects.count())
        build_devis_from_layout(
            layout=layout_avec_geometrie(), user=self.user,
            company=self.company, lead=self._lead())
        apres = (AppelOffre.objects.count(), ToitureAO.objects.count(),
                 VarianteCalepinage.objects.count())
        self.assertEqual(avant, apres)


@override_settings(USE_MOTEUR_CALEPINAGE=True)
class UnDevisDejaEmisNEstJamaisRecalcule(_Base):
    def _devis_au_statut(self, statut):
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(panels=12, kwc=6.6),
            user=self.user, company=self.company, lead=self._lead())
        Devis.objects.filter(pk=devis.pk).update(statut=statut)
        devis.refresh_from_db()
        return devis

    def test_envoye_refuse_le_recalcul(self):
        devis = self._devis_au_statut(Devis.Statut.ENVOYE)
        rapport = selectors.comparaison_calepinage_devis(devis)
        self.assertFalse(rapport['recalculable'])
        self.assertIn('jamais recalculé', rapport['motif'])
        self.assertIsNone(rapport['compte_moteur'])

    def test_accepte_refuse_le_recalcul(self):
        devis = self._devis_au_statut(Devis.Statut.ACCEPTE)
        rapport = selectors.comparaison_calepinage_devis(devis)
        self.assertFalse(rapport['recalculable'])
        self.assertIsNone(rapport['ecart'])

    def test_la_comparaison_n_ecrit_rien_du_tout(self):
        devis = self._devis_au_statut(Devis.Statut.ENVOYE)
        avant = {
            'quantites': [str(li.quantite) for li in devis.lignes.all()],
            'etude': dict(devis.etude_params or {}),
            'layout_hash': devis.layout_hash,
            'statut': devis.statut,
        }
        selectors.comparaison_calepinage_devis(devis)
        devis.refresh_from_db()
        apres = {
            'quantites': [str(li.quantite) for li in devis.lignes.all()],
            'etude': dict(devis.etude_params or {}),
            'layout_hash': devis.layout_hash,
            'statut': devis.statut,
        }
        self.assertEqual(avant, apres)

    def test_un_brouillon_reste_comparable(self):
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(), user=self.user,
            company=self.company, lead=self._lead())
        rapport = selectors.comparaison_calepinage_devis(devis)
        self.assertTrue(rapport['recalculable'])
        self.assertIsNotNone(rapport['compte_moteur'])


class _MoteurAuCompteImpose:
    """Remplace ``compte_moteur_du_layout`` par un compte CHOISI.

    Les trois régimes de PVG2 se jugent sur l'ÉCART, pas sur la géométrie : un
    moteur au compte imposé rend le test déterministe (et indépendant de toute
    évolution future du calepineur).
    """

    def __init__(self, modules):
        self.modules = modules
        self.appels = []

    def __call__(self, layout, **kwargs):
        self.appels.append(kwargs)
        return {'modules': self.modules, 'pans': ({'zone': 'Z1'},),
                'produit_panneau': None}


class LaGardeDeToleranceProtegeLeDevis(_Base):
    """PVG2 — sécurité par défaut : un GRAND écart ne remplace jamais en silence.

    Trois régimes, et rien d'autre :

      1. drapeau OFF  → strictement rien (aucun appel moteur, aucun arbitrage) ;
      2. drapeau ON, écart DANS la tolérance (modules OU %) → le moteur gagne,
         exactement comme AOF164 ;
      3. drapeau ON, écart AU-DELÀ → le compte HISTORIQUE est conservé et
         l'anomalie part en avertissement structuré (les deux comptes + motif).
    """

    def _arbitrage(self, historique, compte_moteur, layout=None):
        moteur = _MoteurAuCompteImpose(compte_moteur)
        with patch.object(services, 'compte_moteur_du_layout', moteur):
            resultat = services.arbitrer_compte_calepinage(
                layout or layout_avec_geometrie(), historique)
        return resultat, moteur

    # ── Régime 1 : drapeau baissé ────────────────────────────────────────────
    def test_off_zero_appel_zero_changement(self):
        arbitrage, moteur = self._arbitrage(12, 999)
        self.assertIsNone(arbitrage)
        self.assertEqual(moteur.appels, [])

    def test_off_le_devis_garde_son_compte_meme_avec_un_moteur_delirant(self):
        moteur = _MoteurAuCompteImpose(999)
        with patch.object(services, 'compte_moteur_du_layout', moteur):
            devis = build_devis_from_layout(
                layout=layout_avec_geometrie(panels=12, kwc=6.6),
                user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 12)
        self.assertEqual(devis.etude_params['puissance_kwc'], 6.6)
        self.assertEqual(moteur.appels, [])

    # ── Régime 2 : écart toléré → le moteur gagne ────────────────────────────
    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_ecart_en_modules_tolere_le_moteur_gagne(self):
        arbitrage, _ = self._arbitrage(12, 14)   # +2 modules = la limite
        self.assertEqual(arbitrage['retenu'], 14)
        self.assertEqual(arbitrage['ecart'], 2)
        self.assertFalse(arbitrage['hors_tolerance'])
        self.assertEqual(arbitrage['motif'], '')

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_un_ecart_tolere_en_moins_passe_aussi(self):
        arbitrage, _ = self._arbitrage(12, 10)   # -2 modules
        self.assertEqual(arbitrage['retenu'], 10)
        self.assertFalse(arbitrage['hors_tolerance'])

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_ecart_en_pourcentage_tolere_sur_une_grande_toiture(self):
        """200 modules : +8 dépasse la tolérance ABSOLUE mais fait 4 %."""
        arbitrage, _ = self._arbitrage(200, 208)
        self.assertEqual(arbitrage['retenu'], 208)
        self.assertFalse(arbitrage['hors_tolerance'])

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_la_frontiere_des_5_pourcent_est_inclusive(self):
        self.assertEqual(self._arbitrage(200, 210)[0]['retenu'], 210)  # 5,0 %
        hors = self._arbitrage(200, 211)[0]                            # 5,5 %
        self.assertEqual(hors['retenu'], 200)
        self.assertTrue(hors['hors_tolerance'])

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_le_devis_prend_le_compte_moteur_quand_l_ecart_est_tolere(self):
        moteur = _MoteurAuCompteImpose(13)
        with patch.object(services, 'compte_moteur_du_layout', moteur):
            devis = build_devis_from_layout(
                layout=layout_avec_geometrie(panels=12, kwc=6.6),
                user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 13)
        self.assertAlmostEqual(devis.etude_params['puissance_kwc'], 7.15, 3)

    # ── Régime 3 : écart hors tolérance → compte historique + alerte ─────────
    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_ecart_hors_tolerance_le_compte_historique_est_conserve(self):
        arbitrage, _ = self._arbitrage(12, 40)
        self.assertEqual(arbitrage['ancien'], 12)
        self.assertEqual(arbitrage['nouveau'], 40)
        self.assertEqual(arbitrage['ecart'], 28)
        # Le compte du moteur reste LISIBLE (l'arbitrage se juge sur des écarts
        # mesurés) mais n'est PAS appliqué.
        self.assertEqual(arbitrage['retenu'], 12)
        self.assertTrue(arbitrage['hors_tolerance'])
        self.assertIn('tolérance', arbitrage['motif'])

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_ecart_hors_tolerance_l_anomalie_est_journalisee(self):
        moteur = _MoteurAuCompteImpose(40)
        with patch.object(services, 'compte_moteur_du_layout', moteur):
            with self.assertLogs('apps.ventes.services',
                                 level='WARNING') as journal:
                services.arbitrer_compte_calepinage(
                    layout_avec_geometrie(), 12)
        alerte = [ligne for ligne in journal.output if 'PVG2' in ligne]
        self.assertTrue(alerte, journal.output)
        texte = alerte[0]
        self.assertIn('écart au-delà de la tolérance', texte)
        self.assertIn('compte historique conservé', texte)
        # Les DEUX comptes sont dans l'alerte : diagnosticable sans rejouer.
        self.assertIn('12', texte)
        self.assertIn('40', texte)

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_le_devis_garde_ses_panneaux_quand_l_ecart_est_aberrant(self):
        moteur = _MoteurAuCompteImpose(40)
        with patch.object(services, 'compte_moteur_du_layout', moteur):
            devis = build_devis_from_layout(
                layout=layout_avec_geometrie(panels=12, kwc=6.6),
                user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), 12)
        # Le kWc ne suit pas un compte qu'on n'a pas retenu.
        self.assertEqual(devis.etude_params['puissance_kwc'], 6.6)

    # ── La règle elle-même, unitairement ─────────────────────────────────────
    def test_les_deux_tolerances_sont_nommees(self):
        self.assertEqual(services.TOLERANCE_ARBITRAGE_MODULES, 2)
        self.assertEqual(services.TOLERANCE_ARBITRAGE_PCT, 5.0)

    def test_un_compte_historique_nul_n_a_que_la_tolerance_en_modules(self):
        """Aucune division par zéro : 0 → 2 est toléré, 0 → 3 ne l'est pas."""
        self.assertTrue(services._ecart_dans_la_tolerance(0, 2))
        self.assertFalse(services._ecart_dans_la_tolerance(0, 3))
        self.assertTrue(services._ecart_dans_la_tolerance(-5, -1))


class LeContratDeClassificationEstIntact(SimpleTestCase):
    """``solar.js`` garde ses mots-clés : le PDF en dépend (règle #4)."""

    #: Les prédicats de classification, TEXTUELLEMENT tels qu'ils doivent
    #: rester. Un renommage silencieux casserait le découpage des options du
    #: PDF sans qu'aucun autre test ne s'en aperçoive.
    LIGNES_GELEES = (
        "export const isBattery = (d) => _norm(d).includes('batterie')",
        "export const isHybridInverter = (d) => _norm(d).includes('onduleur')"
        " && _norm(d).includes('hybride')",
        "export const isPanel = (d) => _norm(d).includes('panneau')",
        "return n.includes('onduleur') && (n.includes('reseau')"
        " || n.includes('injection'))",
    )

    def test_solar_js_existe(self):
        self.assertTrue(os.path.exists(SOLAR_JS), SOLAR_JS)

    def test_les_mots_cles_de_solar_js_sont_inchanges(self):
        with io.open(SOLAR_JS, encoding='utf-8') as fh:
            source = fh.read()
        for ligne in self.LIGNES_GELEES:
            self.assertIn(ligne, source,
                          'mot-clé de classification modifié : %s' % ligne)

    def test_le_backend_classe_avec_les_MEMES_mots_cles(self):
        """L'alignement front/back est le contrat, pas une coïncidence."""
        self.assertTrue(services._is_panel('Panneau Jinko 550W'))
        self.assertTrue(services._is_battery('Batterie Deyness 5 kWh'))
        self.assertTrue(services._is_hybrid_inverter('Onduleur hybride Deye'))
        self.assertTrue(services._is_reseau_inverter('Onduleur réseau Huawei'))
        self.assertTrue(services._is_reseau_inverter('Onduleur injection X'))
        self.assertFalse(services._is_reseau_inverter('Onduleur hybride Deye'))

    def test_la_bascule_ne_touche_pas_le_moteur_de_devis_client(self):
        """Règle #4 : aucune fonction d'AOF164 n'importe ``quote_engine``."""
        import inspect

        source = inspect.getsource(services.compte_moteur_du_layout)
        source += inspect.getsource(services.arbitrer_compte_calepinage)
        source += inspect.getsource(services._zone_villa_depuis_pan)
        self.assertNotIn('quote_engine', source)
