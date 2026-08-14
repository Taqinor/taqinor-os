"""AOF164 — bascule A/B du devis résidentiel sur le moteur de calepinage.

Ce module verrouille les quatre promesses de la bascule, et rien de plus :

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

Run :
    python manage.py test apps.ventes.tests.test_calepinage_bascule -v2
"""
import io
import math
import os
from decimal import Decimal

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
    def test_le_compte_vient_du_moteur_et_diverge_du_typescript(self):
        """Le layout annonce 12 ; le moteur compte ce que la toiture porte."""
        mesure = services.compte_moteur_du_layout(layout_avec_geometrie())
        self.assertIsNotNone(mesure)
        self.assertGreater(mesure['modules'], 0)
        # Le test n'aurait aucune valeur si les deux comptes coïncidaient par
        # hasard : la divergence EST ce que la bascule doit faire remonter.
        self.assertNotEqual(mesure['modules'], 12)
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(panels=12, kwc=6.6),
            user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(self._panneaux(devis), mesure['modules'])

    def test_le_kwc_suit_le_compte(self):
        mesure = services.compte_moteur_du_layout(layout_avec_geometrie())
        devis = build_devis_from_layout(
            layout=layout_avec_geometrie(panels=12, kwc=6.6),
            user=self.user, company=self.company, lead=self._lead())
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
