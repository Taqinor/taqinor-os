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
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_auto, AutoDevisError
from apps.ventes.domain import taille as domaine_taille

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
    nb, watt, source, _avec = domaine_taille._panneaux_dimensionnement_horaire(
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

    def test_taille_de_la_fiche_ecrit_une_alerte_au_vendeur(self):
        """RGEN1 — Given un lead avec taille souhaitée 16 kWc ET une facture,
        When on construit le devis auto, Then le journal dit au vendeur que la
        facture n'a pas servi ; sans taille, aucune phrase de ce genre."""
        journal = {}
        build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('16'),
                            facture_hiver=Decimal('1800')),
            user=self.user, company=self.company, journal_auto=journal)
        self.assertTrue(any(
            'Taille demandée sur la fiche du lead : 16 kWc' in a['message']
            and a['code'] == 'taille_demandee'
            for a in journal.get('alertes', [])), journal)

        journal2 = {}
        build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            email='sans-taille@ex.com'),
            user=self.user, company=self.company, journal_auto=journal2)
        self.assertFalse(any(
            a['code'] == 'taille_demandee'
            for a in journal2.get('alertes', [])), journal2)

    def test_site_sans_reseau_dit_que_la_batterie_est_ajoutee(self):
        """RGEN1 — Given un lead « sans batterie » au raccordement « aucun »,
        When on construit le devis auto, Then le vendeur lit que la batterie
        est ajoutée d'office — que le catalogue de test sache ou non composer
        le kit autonome (l'alerte précède la composition)."""
        journal = {}
        try:
            build_devis_auto(
                lead=self._lead(taille_souhaitee_kwc=Decimal('5'),
                                raccordement='aucun',
                                batterie_souhaitee='sans',
                                email='isole@ex.com'),
                user=self.user, company=self.company, journal_auto=journal)
        except AutoDevisError:
            pass
        self.assertTrue(any(
            a['code'] == 'batterie_hors_reseau'
            and 'ajoutée d\'office' in a['message']
            for a in journal.get('alertes', [])), journal)

    def test_le_compte_de_panneaux_couvre_toujours_la_taille_demandee(self):
        """U1 — invariant du PLAFOND, sur tout le domaine résidentiel utile.

        Le cas signalé par le fondateur (5 kWc → 8 panneaux, jamais 7) n'est
        qu'un point ; la règle est que la puissance RÉELLEMENT posée n'est
        jamais inférieure à la taille demandée, et jamais gonflée d'un panneau
        entier de trop.
        """
        from apps.ventes.domain.taille import _residential_panel_count
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
        from apps.ventes.domain.taille import _residential_panel_count
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
        nb, watt, source, _avec = domaine_taille._panneaux_dimensionnement_horaire(
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
            domaine_taille._residential_panel_count).parameters
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

    def test_reponse_dit_l_option_unique_et_pourquoi(self):
        """T4-V2-013/015 — le bandeau « Devis créé » lisait les chiffres de
        l'option avec batterie sans le dire, et rien ne disait qu'un lead qui
        souhaite une batterie n'a QU'UNE option. La réponse sert les deux
        options (``options``) ou l'option unique et sa raison."""
        deux = Lead.objects.create(
            company=self.company, nom='Deux', prenom='Options', ville=VILLE_ANCRE,
            facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': deux.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual([o['variante'] for o in resp.data['options']], ['sans', 'avec'])
        self.assertIsNone(resp.data['option_unique'])
        for souhait, batterie in (('avec', True), ('sans', False)):
            lead = Lead.objects.create(
                company=self.company, nom='Une', prenom=souhait, ville=VILLE_ANCRE,
                facture_hiver=Decimal('1800'), batterie_souhaitee=souhait)
            resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            self.assertEqual(resp.data['option_unique'],
                             {'batterie': batterie, 'souhait_fiche': True}, souhait)

    def test_cross_tenant_lead_404(self):
        other = make_company('autoep-other')
        other_lead = Lead.objects.create(
            company=other, nom='Foreign', facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': other_lead.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_corps_ou_ids_mal_types_400(self):
        # CI #997 — ``client: [null, null]`` (TypeError du filtre ``pk=``) et
        # un corps tableau (AttributeError) finissaient en 500.
        for corps in ({'lead': None, 'client': [None, None]}, [None, None],
                      {'lead': 'abc'}):
            resp = self.api.post(AUTO_URL, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.data))
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_non_residential_422(self):
        # AGR124 — un lead agricole sans donnée hydraulique : 422 nommant le
        # premier champ manquant (AGR403), plus « type_installation ».
        lead = Lead.objects.create(
            company=self.company, nom='Agri', facture_hiver=Decimal('1800'),
            type_installation='agricole')
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)  # CI #997 fuzz : refus d'état, 409
        self.assertEqual(resp.data.get('field'), 'pompe_hmt_m')

    def test_requires_auth(self):
        lead = Lead.objects.create(
            company=self.company, nom='NoAuth', facture_hiver=Decimal('1800'))
        resp = APIClient().post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertIn(resp.status_code, (401, 403))


class CompositionImposeeTest(TestCase):
    """COP2-V3 — « 10 panneaux, onduleur triphasé de 10 kW, batterie de
    5 kWh » : composition IMPOSÉE sur ``POST devis/auto/`` (résidentiel),
    résolue par le résolveur catalogue unique ; 409 ``choix`` quand un élément
    a zéro ou plusieurs candidats ; jamais un prix d'achat dans la réponse."""

    CORPS = {'nb_panneaux': 10, 'onduleur_kw': 10, 'onduleur_phase': 'triphase',
             'batterie_kwh': 5}

    def setUp(self):
        self.company = make_company('cop2-impose')
        self.user = User.objects.create_user(
            username='cop2imp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)

        def mk(nom, prix, company=None, stock=100):
            return Produit.objects.create(
                company=company or self.company, nom=nom,
                sku='CI-%s' % Produit.objects.count(),
                prix_vente=Decimal(prix), prix_achat=Decimal('123.45'),
                quantite_stock=stock)
        self.mk = mk
        self.panneau = mk('Panneau Canadien Solar 710W', '1400')
        mk('Panneau Jinko 550W', '1100')
        self.hybride = mk('Onduleur hybride Deye 10kW Triphasé', '28000')
        mk('Onduleur réseau Huawei 10kW Triphasé', '20000')
        mk('Onduleur hybride Deye 5kW Monophasé', '17000')
        self.batterie = mk('Batterie Dyness 5 kWh', '14000')

    def _lead(self, **extra):
        extra.setdefault('ville', VILLE_ANCRE)
        return Lead.objects.create(company=self.company, nom='Imp',
                                   prenom='Lead', **extra)

    def _post(self, lead, **corps):
        return self.api.post(AUTO_URL, {'lead': lead.id, **self.CORPS, **corps},
                             format='json')

    def test_lead_sans_facture_compose_le_kit_demande(self):
        lead = self._lead()
        resp = self._post(lead)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['devis_id'], resp.data['id'])
        self.assertEqual(resp.data['lead_id'], lead.id)
        par_nom = {li['designation']: li for li in resp.data['composition']}
        self.assertEqual(par_nom['Panneau Canadien Solar 710W']['quantite'], 10)
        self.assertEqual(
            par_nom['Onduleur hybride Deye 10kW Triphasé']['quantite'], 1)
        self.assertEqual(par_nom['Batterie Dyness 5 kWh']['quantite'], 1)
        self.assertNotIn('Onduleur réseau Huawei 10kW Triphasé', par_nom)
        # Sans consommation : aucune économie inventée.
        self.assertIsNone(resp.data['economie_an_1_ht'])
        self.assertIsNone(resp.data['retour_ans'])
        codes = {a['code'] for a in resp.data['alertes']}
        self.assertIn('composition_imposee', codes)
        self.assertIn('raccordement_suppose', codes)
        texte = str(resp.data).lower()
        self.assertNotIn('prix_achat', texte)
        self.assertNotIn('123.45', texte)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        marqueur = devis.etude_params['composition_imposee']
        self.assertEqual(marqueur['produits']['onduleur'], self.hybride.pk)
        self.assertEqual(marqueur['par'], self.user.pk)

    def test_la_contradiction_kwh_bloque_toujours(self):
        lead = self._lead(facture_hiver=Decimal('1800'),
                          conso_mensuelle_kwh=Decimal('40'))
        resp = self._post(lead)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'conso_mensuelle_kwh')

    def test_deux_batteries_candidates_409_choix_sans_rien_creer(self):
        self.mk('Batterie Dyness BX 5 kWh', '14500')
        resp = self._post(self._lead())
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'batterie_produit_id')
        self.assertEqual(len(resp.data['choix']), 2)
        self.assertTrue(all(c['produit_id'] for c in resp.data['choix']))
        for choix in resp.data['choix']:
            self.assertIn('produit %s' % choix['produit_id'],
                          resp.data['detail'])
        self.assertNotIn('123.45', str(resp.data))
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

    def test_aucune_batterie_de_7_kwh_409_nomme_les_tailles(self):
        resp = self._post(self._lead(), batterie_kwh=7)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'batterie_kwh')
        self.assertEqual(resp.data['choix'], [])
        self.assertIn('5 kWh', resp.data['detail'])

    def test_triphase_impose_sur_lead_monophase_refuse(self):
        resp = self._post(self._lead(raccordement='monophase'))
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'raccordement')
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

    def test_produit_etranger_ou_sans_prix_refuse(self):
        etranger = self.mk('Onduleur hybride Deye 10kW Triphasé', '28000',
                           company=make_company('cop2-imp-autre'))
        sans_prix = self.mk('Onduleur hybride Solis 10kW Triphasé', '0')
        for produit in (etranger, sans_prix):
            with self.subTest(produit=produit.pk):
                resp = self.api.post(AUTO_URL, {
                    'lead': self._lead().id, 'nb_panneaux': 10,
                    'onduleur_produit_id': produit.pk, 'batterie_kwh': 5},
                    format='json')
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(resp.data['field'], 'onduleur_produit_id')

    def test_target_kwc_les_deux_et_marche_non_residentiel_refuses(self):
        for corps, champ in (({'target_kwc': 6}, 'target_kwc'),
                             ({'scenario': 'les_deux'}, 'scenario')):
            with self.subTest(champ=champ):
                resp = self._post(self._lead(), **corps)
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(resp.data['field'], champ)
        resp = self._post(self._lead(type_installation='commercial'))
        self.assertEqual(resp.data['field'], 'type_installation')

    def test_rejeu_idempotent_rend_la_meme_composition(self):
        lead = self._lead()
        premier = self._post(lead)
        second = self._post(lead)
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['id'], premier.data['id'])
        self.assertEqual(second.data['composition'],
                         premier.data['composition'])
        self.assertEqual(second.data['lead_id'], lead.id)

    def test_le_marqueur_ne_se_forge_pas_par_le_corps(self):
        resp = self.api.post(AUTO_URL, {
            'lead': self._lead(facture_hiver=Decimal('1800')).id,
            'etude_params': {'composition_imposee': {'par': 1}}},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'etude_params')
        self.assertFalse(any(
            'composition_imposee' in (d.etude_params or {})
            for d in Devis.objects.filter(company=self.company)))

    def test_marque_epinglee_absente_sur_un_role_non_impose_refuse(self):
        """Revue E — une marque épinglée (Gammes) sans produit sur un rôle NON
        imposé (structure) refuse comme le devis automatique ordinaire :
        jamais un devis qui perd sa ligne en silence."""
        from apps.ventes.models import ParametresGammes
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'structure_acier': 'Inexistante'}})
        resp = self._post(self._lead())
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['field'], 'marques')
        self.assertFalse(Devis.objects.filter(company=self.company).exists())

    def test_regenerer_sans_configuration_garde_le_marqueur(self):
        """Revue D — « régénérer » une taille qui n'a rien de stocké ne fait
        rien : le marqueur de composition imposée reste."""
        cree = self._post(self._lead())
        self.assertEqual(cree.status_code, 201, cree.data)
        resp = self.api.post(
            '/api/django/ventes/devis/%s/offres-tailles/regenerer/'
            % cree.data['id'], {'cle': 'eco'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis = Devis.objects.get(pk=cree.data['id'])
        self.assertIn('composition_imposee', devis.etude_params)

    def test_sans_imposition_la_reponse_porte_aussi_la_composition(self):
        resp = self.api.post(AUTO_URL, {
            'lead': self._lead(facture_hiver=Decimal('1800')).id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['devis_id'], resp.data['id'])
        self.assertTrue(resp.data['composition'])
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertNotIn('composition_imposee', devis.etude_params or {})


class MarqueurCompositionImposeeTest(SimpleTestCase):
    """Revue B / C — le marqueur ``composition_imposee`` (sans base)."""

    def test_permutation_abstenue_seulement_si_un_onduleur_est_impose(self):
        from types import SimpleNamespace
        from apps.ventes.domain.composition_imposee import abstention_onduleur
        ligne = SimpleNamespace(designation='Onduleur réseau Huawei 5kW')
        impose = SimpleNamespace(etude_params={'composition_imposee': {
            'produits': {'onduleur': 88, 'panneau': 12}}})
        panneaux_seuls = SimpleNamespace(etude_params={'composition_imposee': {
            'produits': {'onduleur': None, 'panneau': 12}}})
        avertissements = []
        self.assertTrue(abstention_onduleur(impose, ligne, avertissements))
        self.assertEqual(len(avertissements), 1)
        avertissements = []
        self.assertFalse(abstention_onduleur(panneaux_seuls, ligne,
                                             avertissements))
        self.assertFalse(abstention_onduleur(
            SimpleNamespace(etude_params={}), ligne, avertissements))
        self.assertEqual(avertissements, [])

    def test_le_marqueur_ne_passe_jamais_a_une_copie(self):
        from apps.ventes.domain.etudes import etude_params_pour_copie
        copie = etude_params_pour_copie({
            'composition_imposee': {'produits': {'onduleur': 88}},
            'scenario': 'Avec batterie'})
        self.assertNotIn('composition_imposee', copie)
        self.assertEqual(copie.get('scenario'), 'Avec batterie')


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
        from apps.agent.registry import RISK_OUTWARD
        # COP-G3 — tout ce qui change un montant du devis → confirmation.
        for action in (LIGNE_AJOUTER, LIGNE_MODIFIER, REMISE_DEVIS,
                       LIGNE_SUPPRIMER):
            self.assertEqual(action.risk, RISK_OUTWARD, action.key)
            self.assertTrue(action.confirm_summary, action.key)

    def test_creer_auto_inputs_have_no_company(self):
        from apps.ventes.agent_actions import CREER_AUTO
        self.assertNotIn('company', CREER_AUTO.inputs.get('properties', {}))


#: ADEV142 — les noyaux de calcul d'une conception résidentielle (module, nom) :
#: leurs appelants les importent à l'appel, l'espion du module les compte tous.
NOYAUX_RESIDENTIELS = (
    ('apps.ventes.domain.creation_auto_residentiel', '_panneaux_dimensionnement_horaire'),
    ('apps.ventes.dimensionnement', 'recommander_taille'),
    ('apps.ventes.etude_horaire', 'etude_horaire_pour_devis'),
    ('apps.ventes.profils_comparatifs', 'profils_comparatifs_estampilles'),
)


class DevisAutoDepuisLaConceptionTest(TestCase):
    """ADEV142 (D-ACAL-97) — le devis automatique LIT la conception courante
    du lead : à jour ⇒ aucun noyau appelé ; absente ou périmée ⇒ UNE relance
    (le moteur tourne une fois, dans la requête) ; le devis reste brouillon."""

    def setUp(self):
        from unittest import mock

        self.company = make_company('auto-conception')
        self.user = User.objects.create_user(
            username='auto-conception', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)
        coupure = mock.patch('urllib.request.urlopen', side_effect=OSError('ADEV142 hors réseau'))
        coupure.start()
        self.addCleanup(coupure.stop)

    def _lead(self, **extra):
        return Lead.objects.create(company=self.company, nom='Conception', prenom='Lead',
                                   ville=VILLE_ANCRE, facture_hiver=Decimal('1800'), **extra)

    def _compter(self, noyaux):
        """``{nom: espion}`` : chaque noyau espionné (``wraps``) jusqu'à la fin du test."""
        import importlib
        from unittest import mock

        compteurs = {}
        for module, nom in noyaux:
            cible = importlib.import_module(module)
            espion = mock.patch.object(cible, nom, wraps=getattr(cible, nom))
            compteurs[nom] = espion.start()
            self.addCleanup(espion.stop)
        return compteurs

    @staticmethod
    def _espions(noyaux):
        """Les mêmes espions, le temps d'un bloc (``with``)."""
        import contextlib
        import importlib
        from unittest import mock

        @contextlib.contextmanager
        def bloc():
            with contextlib.ExitStack() as pile:
                yield {nom: pile.enter_context(mock.patch.object(
                    importlib.import_module(module), nom,
                    wraps=getattr(importlib.import_module(module), nom))) for module, nom in noyaux}
        return bloc()

    @staticmethod
    def _appels(compteurs):
        return {nom: espion.call_count for nom, espion in compteurs.items()}

    def _relancer(self, lead):
        from apps.ventes.conception.service import relancer
        with self.captureOnCommitCallbacks(execute=True):
            return relancer(lead, company=self.company, declencheur={'origine': 'remplissage', 'champs': []})

    def _creer(self, lead):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as requetes, self.captureOnCommitCallbacks(execute=True):
            devis = build_devis_auto(lead=lead, user=self.user, company=self.company)
        self.requetes = len(requetes)
        return devis

    def test_conception_a_jour_aucun_noyau_appele(self):
        from apps.ventes.models import ConceptionLead

        lead = self._lead()
        version = self._relancer(lead).conception
        compteurs = self._compter(NOYAUX_RESIDENTIELS)
        devis = self._creer(lead)
        self.assertEqual(self._appels(compteurs), {nom: 0 for nom in compteurs})  # mutant « rappeler le moteur »
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 1)  # aucune version de plus
        panneaux = {li.variante or '': int(li.quantite) for li in devis.lignes.all() if 'Panneau' in li.designation}
        attendu = {option: valeurs['nb_panneaux']['valeur'] for option, valeurs in version.valeurs.items()}
        self.assertEqual({option: panneaux.get(option, panneaux.get('')) for option in attendu}, attendu)
        # Mesuré le 24/11/2026 : 370 requêtes (budget e2e de la route : 15 s).
        self.assertLess(self.requetes, 450, self.requetes)

    def _absente_ou_perimee(self, perimee):
        from apps.ventes.models import ConceptionLead

        lead = self._lead()
        if perimee:
            self._relancer(lead)
            Lead.objects.filter(pk=lead.pk).update(facture_hiver=Decimal('2600'))
            lead.refresh_from_db()
        from apps.ventes.conception.moteur import calculer_conception
        with self._espions(NOYAUX_RESIDENTIELS) as compteurs:  # UNE exécution du moteur, rien d'écrit
            calculer_conception(lead, self.company)
        une_execution = self._appels(compteurs)
        with self._espions(NOYAUX_RESIDENTIELS) as compteurs:
            devis = self._creer(lead)
        # Le moteur tourne UNE fois (la relance) ; le devis n'appelle aucun noyau de plus.
        appels = self._appels(compteurs)
        self.assertEqual(appels, une_execution)  # mutant « dimensionner au devis » : un appel de plus
        self.assertEqual(appels['_panneaux_dimensionnement_horaire'], 1, appels)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        courante = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(courante.version, 2 if perimee else 1)
        self.assertEqual(courante.entrees_utilisees['facture_hiver']['valeur'], 2600.0 if perimee else 1800.0)
        # Mesuré le 24/11/2026 : 527 (absente) / 569 (périmée) requêtes, moteur compris.
        self.assertLess(self.requetes, 700, self.requetes)
        return appels

    def test_conception_absente_une_relance_le_moteur_tourne_une_fois(self):
        self._absente_ou_perimee(False)

    def test_conception_perimee_une_relance_le_moteur_tourne_une_fois(self):
        self._absente_ou_perimee(True)
