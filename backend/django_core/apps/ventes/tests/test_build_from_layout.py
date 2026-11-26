"""Q3 — build_devis_from_layout() turns a finalized layout into a Devis.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_build_from_layout -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.services import build_devis_from_layout

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company, with_prices=True):
    """Minimal seeded catalogue mirroring seed_catalogue naming."""
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Dyness 5 kWh', f'BAT-{company.pk}', 17000)


class TestBuildFromLayout(TestCase):
    def setUp(self):
        self.company = make_company('q3-co')
        self.user = User.objects.create_user(
            username='q3user', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Layout', prenom='Lead',
            email='layout@ex.com', **extra)

    def test_residential_reseau(self):
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 6.6,
                       'annualKwh': 10800, 'savings': 9200},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(devis.company_id, self.company.id)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('Panneau' in d for d in desigs))
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertFalse(any('Batterie' in d for d in desigs))
        # production stored
        self.assertEqual(devis.etude_params['production_annuelle'], 10800)
        # panel qty matches the layout
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 12)
        # totals coherent (non-zero)
        self.assertGreater(devis.total_ttc, 0)
        # reference uses the DEV-YYYYMM-NNNN scheme (never count()+1)
        self.assertTrue(devis.reference.startswith('DEV-'))

    def test_lead_structure_produit_fallback_chemin_3d(self):
        # STKCAT8/STKCAT9 (bis) — sans choix explicite, le chemin 3D lit la
        # structure épinglée sur le lead : une pergola typée « structure »,
        # sans le mot acier/alu, devient LA ligne structure du devis.
        from apps.stock.models import Categorie
        cat = Categorie.objects.create(
            company=self.company, nom='Pergolas', type_equipement='structure')
        pergola = Produit.objects.create(
            company=self.company, nom='Pergola 4x3', prix_vente=Decimal('900'),
            categorie=cat)
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 6.6,
                       'annualKwh': 10800, 'savings': 9200},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead(structure_produit=pergola))
        lignes = list(devis.lignes.all())
        self.assertTrue(any(li.produit_id == pergola.id for li in lignes))
        self.assertFalse(any('Structures acier' in li.designation for li in lignes))

    def test_hybride_with_battery(self):
        layout = {
            'scenario': 'avec_batterie',
            'result': {'panels': 10, 'kwc': 5.5,
                       'annualKwh': 9000, 'savings': 8000},
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d for d in desigs))

    def test_priceless_product_never_quoted(self):
        # A price-less panel must be skipped even if it matches the keyword.
        Produit.objects.filter(nom__startswith='Panneau').update(prix_vente=0)
        # add an alternative priced panel so we can confirm selection skips 0.
        Produit.objects.create(
            company=self.company, nom='Panneau Pricey 550W',
            sku=f'PANP-{self.company.pk}', prix_vente=Decimal('1200'),
            prix_achat=Decimal('1'), quantite_stock=10)
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertGreater(panel.prix_unitaire, 0)
        self.assertEqual(panel.designation, 'Panneau Pricey 550W')

    def test_all_priceless_is_refused_before_any_write(self):
        """QJR95 — CE TEST A CHANGÉ DE VERDICT, DÉLIBÉRÉMENT.

        Il attendait un devis à ZÉRO LIGNE : un document né vide, sans un mot
        pour dire pourquoi, qu'un commercial pouvait envoyer tel quel. Depuis
        que ce chemin passe par ``pipeline.appliquer``, la pré-vérification
        (QJR82) tourne AVANT toute écriture et REFUSE en nommant la donnée
        manquante — le même message français que le calepinage prononçait déjà
        dans sa vue.

        Refuser vaut mieux que créer puis effacer : un devis effacé rendrait sa
        référence au compteur, et le numéro suivant la reprendrait."""
        from apps.ventes.domain.etape_composer import MSG_SANS_ONDULEUR_RESEAU
        from apps.ventes.domain.taille import AutoDevisError

        Produit.objects.all().update(prix_vente=0)
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4}}
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_from_layout(
                layout=layout, user=self.user, company=self.company,
                lead=self._lead())
        self.assertIn(MSG_SANS_ONDULEUR_RESEAU, str(leve.exception))
        from apps.ventes.models import Devis
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_client_resolved_from_lead_no_duplicate(self):
        lead = self._lead()
        d1 = build_devis_from_layout(
            layout={'result': {'panels': 4, 'kwc': 2.2}},
            user=self.user, company=self.company, lead=lead)
        d2 = build_devis_from_layout(
            layout={'result': {'panels': 4, 'kwc': 2.2}},
            user=self.user, company=self.company, lead=lead)
        self.assertEqual(d1.client_id, d2.client_id)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_other_tenant_catalogue_not_used(self):
        other = make_company('q3-other')
        # other company's products must not leak into this company's quote
        Produit.objects.create(
            company=other, nom='Panneau Foreign 550W', sku='PAN-FOR',
            prix_vente=Decimal('1'), prix_achat=Decimal('1'),
            quantite_stock=1)
        layout = {'result': {'panels': 6, 'kwc': 3.3}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        for li in devis.lignes.all():
            self.assertNotIn('Foreign', li.designation)


class TestFG248RoofBridge(TestCase):
    """FG248 — pont 3D toiture web → ERP : import surface/pans/orientation/kWc."""

    def setUp(self):
        self.company = make_company('fg248-co')
        self.user = User.objects.create_user(
            username='fg248user', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Roof', prenom='Lead',
            email='roof@ex.com', **extra)

    def test_extract_roof_config_pure(self):
        from apps.ventes.services import extract_roof_config
        # ``facingAzimuthDeg`` est l'AZIMUT BOUSSOLE du builder : 180 = Sud,
        # 90 = Est (le builder convertit lui-même en aspect PVGIS par −180,
        # cf. roofPro11/prodWindow.ts). Ce fixture disait 0 pour « Sud » —
        # la convention PVGIS, pas celle du champ : il décrivait donc un pan
        # plein NORD tout en l'appelant « Pan Sud », et la fonction rendait
        # « Sud » par la même erreur de repère. Corrigé des DEUX côtés.
        layout = {
            'areas': [
                {'label': 'Pan Sud', 'roofType': 'pitched', 'pitchDeg': 30,
                 'facingAzimuthDeg': 180,
                 'result': {'count': 12, 'kwc': 6.6, 'areaM2': 24.0}},
                {'label': 'Pan Est', 'roofType': 'pitched', 'pitchDeg': 25,
                 'facingAzimuthDeg': 90,
                 'result': {'count': 4, 'kwc': 2.2, 'areaM2': 9.0}},
            ],
        }
        cfg = extract_roof_config(layout)
        self.assertEqual(cfg['nb_pans'], 2)
        self.assertEqual(cfg['nb_panneaux'], 16)
        self.assertAlmostEqual(cfg['surface_m2'], 33.0, places=1)
        self.assertAlmostEqual(cfg['kwc'], 8.8, places=2)
        # Orientation principale = pan le plus puissant (Sud).
        self.assertEqual(cfg['orientation_principale'], 'Sud')
        # `azimut_deg` reste la valeur BRUTE du layout (aucun consommateur
        # ne change de repère) : seul le LIBELLÉ est converti.
        self.assertEqual(cfg['azimut_deg'], 180)
        self.assertEqual(cfg['inclinaison_deg'], 30)
        self.assertEqual(len(cfg['pans']), 2)
        self.assertEqual(cfg['pans'][1]['orientation'], 'Est')

    def test_un_pan_plein_sud_ne_se_dit_jamais_nord(self):
        """Régression AP5 — un pan `facingAzimuthDeg: 180` (le défaut du
        builder, plein Sud) ressortait « Nord » : l'annexe « paramètres du
        site » de la proposition CLIENT publiait `orientation_deg: 180` juste
        à côté de `orientation: 'Nord'`. Deux affirmations contradictoires,
        dont une fausse, sous les yeux du client."""
        from apps.ventes.services import extract_roof_config
        cfg = extract_roof_config({'areas': [
            {'label': 'Toit', 'roofType': 'flat', 'pitchDeg': 22,
             'facingAzimuthDeg': 180,
             'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20.0}}]})
        self.assertEqual(cfg['orientation_principale'], 'Sud')
        # La clé `aspect` (convention PVGIS, 0 = Sud) reste lue TELLE QUELLE.
        cfg_pvgis = extract_roof_config({'areas': [
            {'label': 'Toit', 'roofType': 'flat', 'pitchDeg': 22,
             'aspect': 0,
             'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20.0}}]})
        self.assertEqual(cfg_pvgis['orientation_principale'], 'Sud')

    def test_extract_empty_layout_is_empty(self):
        from apps.ventes.services import extract_roof_config
        self.assertEqual(extract_roof_config({}), {})
        self.assertEqual(extract_roof_config(
            {'result': {'panels': 8}}), {})
        self.assertEqual(extract_roof_config({'areas': []}), {})

    def test_roof_config_stored_in_devis(self):
        layout = {
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800},
            'areas': [
                # 180 = Sud dans la convention BOUSSOLE du champ (cf. AP5).
                {'label': 'Toiture', 'roofType': 'pitched', 'pitchDeg': 20,
                 'facingAzimuthDeg': 180,
                 'result': {'count': 12, 'kwc': 6.6, 'areaM2': 24.0}},
            ],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        toiture = devis.etude_params['toiture']
        self.assertEqual(toiture['nb_panneaux'], 12)
        self.assertEqual(toiture['orientation_principale'], 'Sud')
        self.assertAlmostEqual(toiture['surface_m2'], 24.0, places=1)

    def test_panels_fallback_from_pans_when_result_missing(self):
        """Layout 3D sans bloc result : les panneaux viennent des pans."""
        layout = {
            'scenario': 'reseau',
            'areas': [
                {'roofType': 'pitched', 'pitchDeg': 30, 'facingAzimuthDeg': 0,
                 'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20.0}},
            ],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panel = next((li for li in devis.lignes.all()
                      if 'Panneau' in li.designation), None)
        self.assertIsNotNone(panel)
        self.assertEqual(int(panel.quantite), 10)
        self.assertEqual(devis.etude_params['toiture']['nb_pans'], 1)

    def test_legacy_layout_unchanged(self):
        """Layout sans géométrie → pas de clé toiture (rétro-compat)."""
        layout = {'scenario': 'reseau',
                  'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7000}}
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        self.assertNotIn('toiture', devis.etude_params or {})
        self.assertEqual(devis.etude_params['production_annuelle'], 7000)


# ── D-ACAL-148 (fondateur, 26/11/2026) — l'onduleur DÉSIGNÉ à l'étape Électrique ──
class OnduleurDesigneDecisionSansBase(SimpleTestCase):
    """La décision et la famille, fonctions PURES : aucune base."""

    def _decision(self, famille, scenario, **extra):
        from apps.ventes.domain.creation_calepinage import decision_onduleur_designe
        options = dict(produit_id=7, nom='Onduleur X', etat='tarife', famille=famille,
                       scenario=scenario, hors_reseau=False)
        options.update(extra)
        return decision_onduleur_designe(**options)

    def test_chiffre_quand_la_forme_le_porte(self):
        for famille, scenario, option in (('onduleur_reseau', 'sans', ''), ('onduleur_hybride', 'avec', ''),
                                          ('onduleur_reseau', 'les_deux', 'sans'),
                                          ('onduleur_hybride', 'les_deux', 'avec')):
            with self.subTest(famille=famille, scenario=scenario):
                decision = self._decision(famille, scenario, nombre=2)
                self.assertEqual(decision['impose'], {'produit_id': 7, 'categorie': famille, 'nombre': 2})
                self.assertEqual((decision['option'], decision['motif'], decision['message']), (option, None, None))
        autonome = self._decision('onduleur_offgrid', 'avec', hors_reseau=True)
        self.assertEqual(autonome['impose']['categorie'], 'onduleur_offgrid')

    def test_repli_dit_sa_raison(self):
        for attendu, famille, scenario, extra in (
                ('pas de prix de vente', 'onduleur_reseau', 'sans', {'etat': 'sans_prix'}),
                ('pas au catalogue de vente', None, 'sans', {'etat': 'introuvable'}),
                ('article de pompage', None, 'sans', {'etat': 'pompage'}),
                ('ni par son rôle, ni par sa fiche, ni par son nom', None, 'sans', {}),
                ('la pose est sans batterie', 'onduleur_hybride', 'sans', {}),
                ('il ne porte pas la batterie', 'onduleur_reseau', 'avec', {}),
                ('site est hors réseau', 'onduleur_hybride', 'avec', {'hors_reseau': True}),
                ('le site est raccordé', 'onduleur_offgrid', 'avec', {}),
                ('aucune batterie tarifée', 'onduleur_hybride', 'les_deux', {'batterie_compatible': False})):
            with self.subTest(attendu=attendu):
                decision = self._decision(famille, scenario, **extra)
                self.assertIsNone(decision['impose'])
                self.assertIn(attendu, decision['motif'])
                self.assertTrue(decision['motif'].endswith('le devis garde l’onduleur de la conception du lead'))
                self.assertIn('« Onduleur X »', decision['message'])
                self.assertIn(attendu, decision['message'])

    def test_un_reseau_n_attend_aucune_batterie(self):
        self.assertIsNotNone(self._decision('onduleur_reseau', 'les_deux', batterie_compatible=False)['impose'])

    def test_famille_role_puis_fiche_puis_nom(self):
        from types import SimpleNamespace

        from apps.ventes.domain.creation_calepinage import famille_onduleur_du_produit

        def produit(nom, role=None):
            return SimpleNamespace(nom=nom, role_devis=role)
        cas = (
            (produit('DEYE SUN-80K-SG02HP3', 'onduleur_hybride'), {}, 'onduleur_hybride'),  # rôle déclaré
            (produit('Onduleur hybride Deye 5kW', 'onduleur_reseau'), {}, 'onduleur_reseau'),  # rôle > nom
            (produit('Onduleur hybride Deye 5kW', 'panneau'), {}, None),  # déclaré d'un autre rôle
            (produit('DEYE SUN-5K-SG04LP1'), {'bat_max_charge_kw': 5}, 'onduleur_hybride'),  # fiche
            (produit('Onduleur réseau Huawei 5kW Monophasé'), {}, 'onduleur_reseau'),  # nom
            (produit('Onduleur hybride Deye 5kW Monophasé'), {}, 'onduleur_hybride'),
            (produit('Câble AC onduleur réseau'), {}, None),
            (None, {}, None),
        )
        for p, fiche, attendu in cas:
            with self.subTest(nom=getattr(p, 'nom', None)):
                self.assertEqual(famille_onduleur_du_produit(p, fiche), attendu)


class OnduleurDesigneDuCalepinage(TestCase):
    """La composition depuis un layout avec un onduleur désigné (base : CI seulement)."""

    LAYOUT = {'scenario': 'reseau', 'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200}}

    def setUp(self):
        self.company = make_company('acal148-co')
        self.user = User.objects.create_user(username='acal148', password='x', role_legacy='responsable',
                                             company=self.company)
        seed_catalogue(self.company)
        for nom, prix in (('Onduleur réseau Growatt 8kW Monophasé', 16000),
                          ('Onduleur hybride Growatt 8kW Monophasé', 20000)):
            Produit.objects.create(company=self.company, nom=nom, sku=f'A148-{nom[-16:]}-{self.company.pk}',
                                   prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=10)
        self.lead = Lead.objects.create(company=self.company, nom='Designe', prenom='Lead', email='d148@ex.com')

    def _id(self, nom):
        return Produit.objects.get(company=self.company, nom=nom).pk

    def _devis(self, scenario='reseau', designe=None, **extra):
        journal = {}
        devis = build_devis_from_layout(layout=dict(self.LAYOUT, scenario=scenario), user=self.user,
                                        company=self.company, lead=self.lead, journal=journal,
                                        onduleur_designe=designe, **extra)
        onduleurs = sorted((li.designation, li.role_devis, li.variante or '', int(li.quantite))
                           for li in devis.lignes.all() if str(li.role_devis or '').startswith('onduleur_'))
        return onduleurs, journal

    def test_sans_designation_rien_ne_change(self):
        sans, journal = self._devis()
        self.assertEqual(sans, [('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', '', 1)])
        self.assertNotIn('onduleur_designe', journal)

    def test_reseau_designe_tarife_est_chiffre(self):
        onduleurs, journal = self._devis(designe={'produit_id': self._id('Onduleur réseau Huawei 5kW Monophasé')})
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau', '', 1)])
        self.assertIsNone(journal['onduleur_designe']['motif'])

    def test_hybride_designe_avec_batterie_est_chiffre_au_nombre_accepte(self):
        onduleurs, _journal = self._devis('avec_batterie', {
            'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'), 'nombre': 2})
        self.assertEqual(onduleurs, [('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride', '', 2)])

    def test_repli_annonce_sans_prix_et_hybride_sans_batterie(self):
        Produit.objects.filter(company=self.company, nom='Onduleur réseau Huawei 5kW Monophasé').update(prix_vente=0)
        for designe, attendu in (('Onduleur réseau Huawei 5kW Monophasé', 'pas de prix de vente'),
                                 ('Onduleur hybride Deye 5kW Monophasé', 'la pose est sans batterie')):
            with self.subTest(designe=designe):
                onduleurs, journal = self._devis(designe={'produit_id': self._id(designe)})
                self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', '', 1)])
                self.assertTrue(any(attendu in m for m in journal['avertissements']), journal)

    def test_deux_options_chaque_onduleur_va_a_son_option_jamais_un_500(self):
        onduleurs, _j = self._devis(designe={'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé')},
                                    deux_options=True)
        self.assertIn(('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride', 'avec', 1), onduleurs)
        self.assertIn(('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', 'sans', 1), onduleurs)
        onduleurs, _j = self._devis(designe={'produit_id': self._id('Onduleur réseau Huawei 5kW Monophasé')},
                                    deux_options=True)
        self.assertIn(('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau', 'sans', 1), onduleurs)
        self.assertIn(('Onduleur hybride Growatt 8kW Monophasé', 'onduleur_hybride', 'avec', 1), onduleurs)

    def test_apercu_a_blanc_meme_composition_que_la_creation(self):
        from apps.ventes.services import composer_a_blanc_depuis_layout

        designe = {'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé')}
        journal = {}
        specs = composer_a_blanc_depuis_layout(layout=dict(self.LAYOUT, scenario='avec_batterie'),
                                               company=self.company, lead=self.lead,
                                               onduleur_designe=designe, journal=journal)
        a_blanc = sorted(s['designation'] for s in specs if str(s.get('role_devis') or '').startswith('onduleur_'))
        cree, _j = self._devis('avec_batterie', designe)
        self.assertEqual(a_blanc, [d for d, *_ in cree])
        self.assertEqual(journal['onduleur_designe']['impose']['categorie'], 'onduleur_hybride')
