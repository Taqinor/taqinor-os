"""Copilote — devis AUTOMATIQUE (résidentiel) + garde-fou « toujours auto ».

``build_devis_auto()`` dimensionne un devis résidentiel depuis la fiche lead et
délègue à ``build_devis_from_layout``. L'agent n'a plus d'action de création
VIDE : seule ``ventes.devis.creer_auto`` subsiste, avec les actions d'édition
par chat.

RE-ANCRAGE DU 29/08/2026 (ordre fondateur « all sizing should go through the
new sizing tool, and i said ALL sizing »). Ce module épinglait la règle des
900 DH/mois (1800 MAD ⇒ 2 tranches × 8 = 16 panneaux à 710 Wc). Cette règle est
SUPPRIMÉE : une facture se dimensionne désormais par le moteur horaire. Les
tests n'épinglent donc plus un nombre magique — ils épinglent que le devis
porte EXACTEMENT ce que le moteur recommande pour ce fixture
(``panneaux_du_moteur``), et les fixtures ancrent leur ``ville`` (sans ancrage
de productible, le moteur ne peut RIEN calculer — leçon #86).

Run:
    python manage.py test apps.ventes.tests.test_devis_auto -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_auto, AutoDevisError

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company):
    """Catalogue minimal (mêmes désignations que seed_catalogue)."""
    def mk(nom, sku, prix):
        Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Dyness 5 kWh', f'BAT-{company.pk}', 17000)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


AUTO_URL = '/api/django/ventes/devis/auto/'

#: Ancrage de productible des fixtures — sans ville ni GPS, le moteur ne sait
#: pas ce que produit le site et s'abstient (leçon #86).
VILLE_ANCRE = 'Casablanca'


def panneaux_du_moteur(lead, company):
    """``(nb_panneaux, panel_watt)`` que le MOTEUR recommande pour ce lead.

    Les tests s'y adossent au lieu d'épingler un nombre : le nombre juste est
    par définition celui du moteur, et il bougera légitimement le jour où le
    catalogue ou le barème bougent. Ce qui est épinglé, c'est que le devis n'a
    pas d'AUTRE source de dimensionnement."""
    from apps.ventes import services
    nb, watt, source, _avec = services._panneaux_dimensionnement_horaire(
        lead=lead, company=company,
        phase=services.phase_client_pour_dimensionnement(lead))
    assert source == 'moteur_horaire', (
        'le moteur ne dimensionne pas ce fixture (motif « %s ») — le devis '
        'automatique le refuserait' % source)
    return nb, watt


class BuildDevisAutoServiceTest(TestCase):
    def setUp(self):
        self.company = make_company('auto-co')
        self.user = User.objects.create_user(
            username='autouser', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        extra.setdefault('ville', VILLE_ANCRE)
        extra.setdefault('email', 'auto@ex.com')
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='Lead', **extra)

    def test_la_facture_est_dimensionnee_par_le_moteur(self):
        """RE-ANCRÉ (29/08/2026) — le lead n'a QU'UNE facture d'hiver et aucun
        profil d'appel : c'est exactement le cas qui partait hier sur la règle
        des 900 DH/mois (1800 ⇒ 16 panneaux à 710 Wc). Il doit désormais sortir
        AU CHIFFRE DU MOTEUR, panneau catalogue réel compris."""
        lead = self._lead(facture_hiver=Decimal('1800'))
        attendu, watt = panneaux_du_moteur(lead, self.company)
        devis = build_devis_auto(
            lead=lead, user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), attendu)
        # La règle historique aurait dit 16 panneaux de 710 Wc : le devis ne
        # doit surtout pas être tombé là-dessus par hasard.
        self.assertEqual(
            float(devis.etude_params['puissance_kwc']),
            round(attendu * watt / 1000, 2))
        # U2 (fondateur 20/08/2026) — le lead ne dit rien de la batterie, donc
        # le devis propose LES DEUX options (et non plus le réseau seul).
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'],
                         'Les deux (Sans + Avec)')

    def test_deux_leads_meme_facture_meme_taille_avec_ou_sans_profil(self):
        """L'INCIDENT test18/test19, en test. Deux leads à 2500 MAD de facture
        d'hiver : l'un porte un profil d'appel (occupation déclarée), l'autre
        rien. Hier ils repartaient de DEUX règles différentes (moteur pour le
        premier, 900 DH pour le second — 16 panneaux). Aujourd'hui les deux
        passent par le moteur ; la présence d'un profil peut légitimement
        CHANGER la taille (c'est tout son intérêt), mais plus jamais la RÈGLE.
        """
        for email, extra in (('sans-profil@ex.com', {}),
                             ('avec-profil@ex.com',
                              {'occupation_jour': 'present'})):
            lead = self._lead(facture_hiver=Decimal('2500'), email=email,
                              **extra)
            attendu, _watt = panneaux_du_moteur(lead, self.company)
            devis = build_devis_auto(lead=lead, user=self.user,
                                     company=self.company)
            panel = next(li for li in devis.lignes.all()
                         if 'Panneau' in li.designation)
            self.assertEqual(int(panel.quantite), attendu, email)

    def test_sizes_from_taille_souhaitee(self):
        # U1 (fondateur 20/08/2026) — le compte de panneaux est un PLAFOND :
        # 6 kWc → ceil(6000 / 710) = 9 panneaux. Avec l'arrondi au plus proche
        # d'hier (8 panneaux = 5,68 kWc), le client payait 6 kWc et recevait
        # moins ; on ne descend JAMAIS sous la puissance vendue.
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('6')),
            user=self.user, company=self.company)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 9)

    def test_le_compte_de_panneaux_couvre_toujours_la_taille_demandee(self):
        """U1 — invariant du PLAFOND, sur tout le domaine résidentiel utile.

        Le cas signalé par le fondateur (5 kWc → 8 panneaux, jamais 7) n'est
        qu'un point ; la règle est que la puissance RÉELLEMENT posée n'est
        jamais inférieure à la taille demandée, et jamais gonflée d'un panneau
        entier de trop.
        """
        from apps.ventes.services import _residential_panel_count
        for kwc_x10 in range(10, 205, 5):           # 1,0 → 20,0 kWc
            kwc = Decimal(kwc_x10) / 10
            nb = _residential_panel_count(taille_kwc=kwc)
            pose = nb * 710 / 1000
            self.assertGreaterEqual(
                pose + 1e-9, float(kwc),
                '%s kWc : %d panneaux ne couvrent que %.3f kWc' % (
                    kwc, nb, pose))
            self.assertLess(
                (nb - 1) * 710 / 1000, float(kwc),
                '%s kWc : %d panneaux, un panneau de trop' % (kwc, nb))

    def test_le_plafond_est_stable_par_aller_retour(self):
        """U1 — miroir Python de la garde anti-dérive flottante de solar.js :
        un compte de panneaux repassé par son kWc doit se retrouver À
        L'IDENTIQUE, sans quoi chaque aller-retour ajouterait un panneau."""
        from apps.ventes.services import _residential_panel_count
        for nb in range(1, 61):
            kwc = Decimal(str(nb * 710 / 1000))
            self.assertEqual(
                _residential_panel_count(taille_kwc=kwc), nb,
                'aller-retour instable à %d panneaux' % nb)

    def test_battery_added_when_wanted(self):
        """U2 — un choix EXPLICITE « avec » reste souverain : on ne repropose
        pas au client l'option qu'il vient d'écarter."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            batterie_souhaitee='avec'),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'], 'Avec batterie')

    def test_choix_explicite_sans_reste_sans(self):
        """U2 — l'autre moitié du choix explicite : « sans » compose le réseau
        SEUL, sans batterie ni onduleur hybride."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            batterie_souhaitee='sans'),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertFalse(any('hybride' in d for d in desigs))
        self.assertFalse(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'], 'Sans batterie')

    def test_defaut_deux_options_meme_sur_taille_souhaitee(self):
        """U2 — le défaut « les deux » ne dépend PAS du chemin de
        dimensionnement : une taille souhaitée en kWc le donne aussi."""
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('6')),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertEqual(devis.etude_params['scenario'],
                         'Les deux (Sans + Avec)')

    def test_deux_options_les_deux_paniers_sont_chiffrables(self):
        """U2 — la forme deux options n'a de sens que si CHAQUE panier tient
        debout tout seul : le panier « sans » (tout sauf batterie + hybride) et
        le panier « avec » (tout sauf réseau) doivent chacun porter des
        panneaux ET un onduleur. C'est le découpage exact que lisent l'écran
        (``optionTotalsTTC``) et le moteur PDF."""
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company)
        lignes = list(devis.lignes.all())
        sans = [li for li in lignes
                if 'Batterie' not in li.designation
                and 'hybride' not in li.designation]
        avec = [li for li in lignes if 'réseau' not in li.designation]
        for nom, panier in (('sans', sans), ('avec', avec)):
            self.assertTrue(
                any('Panneau' in li.designation for li in panier),
                'panier « %s » sans panneaux' % nom)
            self.assertTrue(
                any('Onduleur' in li.designation for li in panier),
                'panier « %s » sans onduleur' % nom)
        self.assertTrue(any('Batterie' in li.designation for li in avec))
        self.assertFalse(any('Batterie' in li.designation for li in sans))

    def test_missing_data_raises(self):
        """Aucune facture, aucune taille : le moteur n'a rien à inverser — le
        refus NOMME la facture d'hiver."""
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=self._lead(), user=self.user,
                             company=self.company)
        self.assertEqual(ctx.exception.field, 'facture_hiver')

    def test_facture_faible_le_moteur_decide_quand_meme(self):
        """RE-ANCRÉ — 500 MAD tombait sous la tranche de 900 (0 panneau ⇒
        refus). Ce seuil n'existe plus : c'est le moteur qui décide, et lui
        seul. Le test épingle donc l'ACCORD avec le moteur, quel que soit son
        verdict — jamais l'arithmétique des tranches."""
        lead = self._lead(facture_hiver=Decimal('500'))
        from apps.ventes import services
        nb, watt, source, _avec = services._panneaux_dimensionnement_horaire(
            lead=lead, company=self.company,
            phase=services.phase_client_pour_dimensionnement(lead))
        if nb > 0:
            devis = build_devis_auto(lead=lead, user=self.user,
                                     company=self.company)
            panel = next(li for li in devis.lignes.all()
                         if 'Panneau' in li.designation)
            self.assertEqual(int(panel.quantite), nb)
            self.assertEqual(source, 'moteur_horaire')
            self.assertGreater(watt, 0)
        else:
            with self.assertRaises(AutoDevisError):
                build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)

    def test_la_taille_souhaitee_du_lead_reste_souveraine(self):
        """Le commercial sait ce qu'il vend : une taille sur la fiche passe
        devant le moteur, même quand le lead porte une facture ET un profil
        que le moteur saurait parfaitement dimensionner."""
        lead = self._lead(facture_hiver=Decimal('1800'),
                          occupation_jour='present',
                          taille_souhaitee_kwc=Decimal('6'))
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        # 6 kWc → plafond ceil(6000/710) = 9 panneaux de 710 Wc : la
        # conversion, pas le moteur (qui aurait choisi son panneau catalogue).
        self.assertEqual(int(panel.quantite), 9)

    def test_target_kwc_reste_souverain(self):
        """Et la cible demandée POUR CE DEVIS passe devant tout le reste."""
        lead = self._lead(facture_hiver=Decimal('1800'),
                          taille_souhaitee_kwc=Decimal('6'))
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company,
                                 target_kwc=Decimal('3'))
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 5)   # ceil(3000/710)

    def test_moteur_sans_localisation_refuse_en_nommant_la_ville(self):
        """LE POINT DUR DE L'ORDRE FONDATEUR : quand le moteur ne peut pas
        dimensionner, on REFUSE en nommant la donnée manquante. Aucun devis ne
        doit plus naître d'une autre règle — surtout pas des 900 DH/mois, qui
        auraient donné 16 panneaux ici."""
        lead = self._lead(facture_hiver=Decimal('1800'), ville='')
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.company)
        self.assertEqual(ctx.exception.field, 'ville')
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_bouznika_est_dimensionnee_comme_rabat(self):
        """L'INCIDENT DU 31/08/2026 — un lead à Bouznika (sans GPS) était
        refusé « chantier non localisé » quand le même lead à Rabat passait.
        Bouznika est désormais une ville de table PVGIS à part entière : le
        devis automatique naît, sans réseau ni GPS."""
        lead = self._lead(facture_hiver=Decimal('1800'), ville='Bouznika')
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertTrue(any('Panneau' in li.designation
                            for li in devis.lignes.all()))

    def test_ville_du_gazetier_est_dimensionnee_par_l_ancre(self):
        """Fondateur 31/08/2026 — une ville marocaine HORS table mais au
        gazetier GeoNames (Skhirat) n'est plus refusée : le moteur la sert
        par l'ancre PVGIS la plus proche. Toute ville du Maroc passe."""
        lead = self._lead(facture_hiver=Decimal('1800'), ville='Skhirat')
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertTrue(any('Panneau' in li.designation
                            for li in devis.lignes.all()))

    def test_la_regle_des_900_dh_ne_dimensionne_plus_rien(self):
        """La branche « facture ÷ 900 × 8 » a QUITTÉ le code : la fonction de
        conversion ne connaît plus que les kWc."""
        from apps.ventes import services
        self.assertFalse(hasattr(services, '_AUTO_TRANCHE_MAD'))
        self.assertFalse(hasattr(services, '_AUTO_PANELS_PER_TRANCHE'))
        import inspect
        params = inspect.signature(
            services._residential_panel_count).parameters
        self.assertNotIn('facture_hiver', params)

    def test_non_residential_raises(self):
        for marche in ('agricole', 'industriel', 'commercial'):
            with self.assertRaises(AutoDevisError):
                build_devis_auto(
                    lead=self._lead(facture_hiver=Decimal('1800'),
                                    type_installation=marche),
                    user=self.user, company=self.company)

    def test_blank_market_treated_residential(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('900')),
            user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class AutoEndpointTest(TestCase):
    def setUp(self):
        self.company = make_company('autoep-co')
        self.user = User.objects.create_user(
            username='autoep', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def test_creates_dimensioned_devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ep', prenom='Lead',
            ville=VILLE_ANCRE, facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')
        self.assertGreater(resp.data['nb_lignes'], 0)
        self.assertTrue(resp.data['reference'].startswith('DEV-'))

    def test_cross_tenant_lead_404(self):
        other = make_company('autoep-other')
        other_lead = Lead.objects.create(
            company=other, nom='Foreign', facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': other_lead.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_non_residential_422(self):
        lead = Lead.objects.create(
            company=self.company, nom='Agri', facture_hiver=Decimal('1800'),
            type_installation='agricole')
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertEqual(resp.data.get('field'), 'type_installation')

    def test_requires_auth(self):
        lead = Lead.objects.create(
            company=self.company, nom='NoAuth', facture_hiver=Decimal('1800'))
        resp = APIClient().post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertIn(resp.status_code, (401, 403))


class GuardrailTest(TestCase):
    """Le Copilote ne peut PLUS créer un devis vide : seules l'auto-création et
    l'édition par chat subsistent au catalogue."""

    def test_empty_create_actions_gone_auto_present(self):
        from apps.agent.registry import all_actions
        keys = {a.key for a in all_actions()}
        self.assertNotIn('ventes.devis.create', keys)
        self.assertNotIn('ventes.devis.creer', keys)
        self.assertIn('ventes.devis.creer_auto', keys)

    def test_edit_actions_present_with_expected_risk(self):
        from apps.ventes.agent_actions import (
            LIGNE_AJOUTER, LIGNE_MODIFIER, LIGNE_SUPPRIMER, REMISE_DEVIS,
        )
        from apps.agent.registry import RISK_INTERNAL, RISK_OUTWARD
        self.assertEqual(LIGNE_AJOUTER.risk, RISK_INTERNAL)
        self.assertEqual(LIGNE_MODIFIER.risk, RISK_INTERNAL)
        self.assertEqual(REMISE_DEVIS.risk, RISK_INTERNAL)
        # Suppression → confirmation (outward).
        self.assertEqual(LIGNE_SUPPRIMER.risk, RISK_OUTWARD)
        self.assertTrue(LIGNE_SUPPRIMER.confirm_summary)

    def test_creer_auto_inputs_have_no_company(self):
        from apps.ventes.agent_actions import CREER_AUTO
        self.assertNotIn('company', CREER_AUTO.inputs.get('properties', {}))
