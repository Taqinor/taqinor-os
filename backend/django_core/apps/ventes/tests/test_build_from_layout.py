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

    #: Un nom réel par famille : ``famille_au_nom`` est celui que la VRAIE fonction lit.
    NOMS = {'onduleur_reseau': 'Onduleur réseau Huawei 5kW', 'onduleur_hybride': 'Onduleur hybride Deye 5kW',
            'onduleur_offgrid': 'Onduleur hors réseau Deye 6kW', None: 'Coffret AC'}

    def _decision(self, famille, scenario, **extra):
        from apps.ventes.domain.creation_calepinage import decision_onduleur_designe, famille_lue_au_nom
        nom = extra.pop('nom', self.NOMS[famille])
        options = dict(produit_id=7, nom=nom, etat='tarife', famille=famille,
                       famille_au_nom=famille_lue_au_nom(nom), scenario=scenario, hors_reseau=False, nombre=1)
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
                ('il ne porte pas la batterie', 'onduleur_reseau', 'avec', {}),
                ('site est hors réseau', 'onduleur_hybride', 'avec', {'hors_reseau': True}),
                ('le site est raccordé', 'onduleur_offgrid', 'avec', {})):
            with self.subTest(attendu=attendu):
                decision = self._decision(famille, scenario, **extra)
                self.assertIsNone(decision['impose'])
                self.assertIn(attendu, decision['motif'])
                self.assertTrue(decision['motif'].endswith('le devis garde l’onduleur de la conception du lead'))
                self.assertIn('« %s »' % self.NOMS[famille], decision['message'])
                self.assertIn(attendu, decision['message'])

    def test_d_acal_159_un_hybride_fait_passer_le_devis_sans_en_avec_batterie(self):
        decision = self._decision('onduleur_hybride', 'sans')
        self.assertEqual(decision['impose']['categorie'], 'onduleur_hybride')
        self.assertEqual((decision['scenario'], decision['batterie_a_verifier']), ('avec', True))
        self.assertEqual(decision['message'], 'Le devis passe en « avec batterie » : l’onduleur désigné '
                                              '« Onduleur hybride Deye 5kW » est un hybride.')
        # « les deux » inchangé : l'hybride va à l'option avec, sans phrase.
        deux = self._decision('onduleur_hybride', 'les_deux')
        self.assertEqual((deux['scenario'], deux['option'], deux['message']), ('les_deux', 'avec', None))
        self.assertIsNone(self._decision('onduleur_reseau', 'sans')['message'])

    def test_le_nombre_vient_du_calepinage_jamais_de_la_regle_du_catalogue(self):
        """Relecture D-ACAL-148, point 1 — sans nombre établi par le calepinage, ou un nombre
        illisible (0, texte, 2,5 tronqué, booléen), le devis ne chiffre pas l'onduleur désigné et
        le dit ; jamais ⌈kWc ÷ kW⌉ ni un nombre tronqué."""
        for extra, attendu in (({'nombre': None}, 'ni établi par le schéma'),
                               ({'nombre': True}, 'ni établi par le schéma'),
                               ({'nombre': None, 'nombre_illisible': True}, 'pas un entier')):
            with self.subTest(extra=extra):
                decision = self._decision('onduleur_reseau', 'sans', **extra)
                self.assertIsNone(decision['impose'])
                self.assertIn(attendu, decision['message'])

    def test_le_raccordement_du_client_n_est_pas_contourne(self):
        """Relecture, point 5 — la règle de phase du catalogue (L-TRI ; triphasé écarté chez un
        monophasé) vaut pour l'onduleur désigné ; ``triphase`` lu par la VRAIE fonction de fiche/nom."""
        from types import SimpleNamespace

        from apps.ventes.compatibilites import PHASE_MONO, PHASE_TRI, est_triphase_produit

        mono = est_triphase_produit(SimpleNamespace(nom='Onduleur réseau Huawei 5kW Monophasé', pk=None))
        tri = est_triphase_produit(SimpleNamespace(nom='Onduleur réseau Huawei 10kW Triphasé', pk=None))
        self.assertEqual((mono, tri), (False, True))
        for phase, triphase, attendu in ((PHASE_TRI, mono, 'il est monophasé'), (PHASE_MONO, tri, 'il est triphasé')):
            with self.subTest(phase=phase):
                decision = self._decision('onduleur_reseau', 'sans', phase_client=phase, triphase=triphase)
                self.assertIsNone(decision['impose'])
                self.assertIn(attendu, decision['message'])
        for phase, triphase in ((PHASE_TRI, tri), (PHASE_MONO, mono), (None, tri)):
            with self.subTest(phase=phase, triphase=triphase):
                self.assertIsNotNone(self._decision('onduleur_reseau', 'sans', phase_client=phase,
                                                    triphase=triphase)['impose'])

    def test_un_nom_muet_n_est_pas_impose(self):
        """Relecture, point 2 — reconnu hybride par son rôle ou sa fiche, mais un nom que le PDF et
        la resynchronisation (lecture au nom) ne classent pas : repli annoncé, jamais imposé."""
        from apps.ventes.domain.creation_calepinage import famille_lue_au_nom

        self.assertIsNone(famille_lue_au_nom('DEYE SUN-80K-SG02HP3-EU-EM6'))
        self.assertEqual(famille_lue_au_nom('Onduleur hybride Deye 5kW'), 'onduleur_hybride')
        decision = self._decision('onduleur_hybride', 'avec', nom='DEYE SUN-80K-SG02HP3-EU-EM6')
        self.assertIsNone(decision['impose'])
        self.assertIn('son nom ne dit pas qu’il s’agit d’un onduleur hybride', decision['message'])
        self.assertIn('« DEYE SUN-80K-SG02HP3-EU-EM6 »', decision['message'])

    def test_la_batterie_est_jugee_par_la_composition(self):
        """Relecture, point 3 — la décision ne juge plus la batterie elle-même : elle dit à la
        génération de la faire juger par la composition (``batterie_a_verifier``), et le repli
        « aucune batterie » nomme l'onduleur désigné."""
        from apps.ventes.domain.creation_calepinage import repli_onduleur_designe

        for famille, scenario, attendu in (('onduleur_reseau', 'sans', False), ('onduleur_reseau', 'les_deux', False),
                                           ('onduleur_hybride', 'avec', True), ('onduleur_hybride', 'les_deux', True)):
            with self.subTest(famille=famille, scenario=scenario):
                self.assertIs(self._decision(famille, scenario)['batterie_a_verifier'], attendu)
        self.assertTrue(self._decision('onduleur_offgrid', 'avec', hors_reseau=True)['batterie_a_verifier'])
        repli = repli_onduleur_designe('Onduleur hybride Deye 5kW', 'batterie_non_composee')
        self.assertIsNone(repli['impose'])
        self.assertIn('« Onduleur hybride Deye 5kW »', repli['message'])
        self.assertIn('ne pose aucune batterie', repli['message'])

    def test_forme_entiere_cop2_v3_et_none_inchangees(self):
        """La forme ENTIÈRE du devis automatique (COP2-V3) et l'absence d'imposition gardent leur
        comportement : catégorie du scénario, quantité 1 ; la règle du catalogue sans imposition."""
        from apps.ventes.domain.composition_residentielle import (
            _imposition_resolue, _quantite_onduleur)

        tarifes = {88: object()}
        for avec, attendu in ((False, 'onduleur_reseau'), (True, 'onduleur_hybride')):
            imposes = _imposition_resolue(tarifes, 88, None, deux_options=False, hors_reseau=False,
                                          avec_batterie=avec)
            self.assertEqual((imposes['categorie'], imposes['onduleur']), (attendu, tarifes[88]))
        self.assertEqual(_quantite_onduleur(88, 5.0, 5.28, 6.6), 1)  # COP2-V3 : toujours 1
        self.assertEqual(_quantite_onduleur(None, 5.0, 5.28, 6.6), 2)  # catalogue : ⌈6,6 ÷ 5⌉
        self.assertEqual(_quantite_onduleur(None, 8.0, 5.28, 6.6), 1)
        designe = {'produit_id': 88, 'categorie': 'onduleur_hybride', 'nombre': 3}
        self.assertEqual(_quantite_onduleur(designe, 5.0, 5.28, 6.6), 3)
        self.assertEqual(_quantite_onduleur(dict(designe, nombre=None), 5.0, 5.28, 6.6), 1)  # jamais ⌈kWc ÷ kW⌉
        self.assertEqual(_imposition_resolue(tarifes, designe, None, deux_options=False, hors_reseau=False,
                                             avec_batterie=False)['categorie'], 'onduleur_hybride')

    def test_a_resynchro_sans_designations_rien_ne_bouge(self):
        """A — une resynchro qui ne vient pas du calepinage (apply-taille, réparation) : aucune
        décision, le marqueur stocké est gardé tel quel, le court-circuit « inchangé » reste permis."""
        from types import SimpleNamespace

        from apps.ventes.domain.creation_calepinage import (
            CLE_DESIGNATIONS, appliquer_designations_a_la_resynchro, marqueur_stocke)

        verrou = SimpleNamespace(roof_layout={CLE_DESIGNATIONS: {'onduleur': 7}})
        avertissements = []
        for cible in (None, SimpleNamespace(source='calepinage', onduleur_impose=None)):
            with self.subTest(cible=cible):
                rendu = appliquer_designations_a_la_resynchro(
                    verrou, SimpleNamespace(cible=cible), {}, False, avertissements)
                self.assertEqual(rendu, (False, {'modifiees': 0, 'a_ecrire': False, 'marqueur': {'onduleur': 7}}))
        self.assertEqual(avertissements, [])
        self.assertIsNone(marqueur_stocke(SimpleNamespace(roof_layout={})))

    def test_a_point_1_seul_un_devis_ne_sous_la_regle_recoit_les_designations(self):
        """Relecture round 4, point 1 — un devis SANS marqueur (créé avant la règle), brouillon ou
        envoyé : rien n'est appliqué, le court-circuit reste permis, UNE phrase vraie ; rien de
        désigné : aucune phrase. ACAL1320 (D-ACAL-73) — un ENVOYÉ né sous la règle n'est plus
        refusé ici (il suit la désignation, l'aperçu le dit avant) : seul le marqueur décide."""
        from types import SimpleNamespace

        from apps.ventes.domain.creation_calepinage import (
            MSG_RESYNC_AVANT_LA_REGLE, SOURCE_DESIGNATIONS, CLE_DESIGNATIONS,
            appliquer_designations_a_la_resynchro, suit_les_designations)

        cible = SimpleNamespace(source=SOURCE_DESIGNATIONS, onduleur_impose={'produit_id': 3, 'nombre': 1},
                                batterie_imposee={'produit_id': 4, 'packs': 1})
        vide = SimpleNamespace(source=SOURCE_DESIGNATIONS, onduleur_impose=None, batterie_imposee=None)
        for statut, layout, attendu in (('envoye', {}, MSG_RESYNC_AVANT_LA_REGLE),
                                        ('brouillon', {}, MSG_RESYNC_AVANT_LA_REGLE)):
            with self.subTest(statut=statut, marqueur=bool(layout)):
                verrou = SimpleNamespace(statut=statut, roof_layout=layout)
                avertissements = []
                veut, rendu = appliquer_designations_a_la_resynchro(
                    verrou, SimpleNamespace(cible=cible), {}, False, avertissements)
                self.assertEqual((veut, rendu['modifiees'], rendu['a_ecrire']), (False, 0, False))
                self.assertEqual(avertissements, [attendu % 'un onduleur et une batterie'])
                avertissements = []
                appliquer_designations_a_la_resynchro(verrou, SimpleNamespace(cible=vide), {}, False, avertissements)
                self.assertEqual(avertissements, [])
        self.assertTrue(suit_les_designations(SimpleNamespace(roof_layout={CLE_DESIGNATIONS: {}})))
        self.assertFalse(suit_les_designations(SimpleNamespace(roof_layout={})))
        # Revue du 26/11 (D-ACAL-73) — un ENVOYÉ né sous la règle, sans la carte d'aperçu confirmée
        # (source non confirmée) : rien n'est appliqué, la phrase renvoie à « Resynchroniser le devis ».
        from apps.ventes.domain.creation_calepinage import MSG_RESYNC_ENVOYE_SANS_APERCU, cible_des_designations
        avertissements = []
        verrou = SimpleNamespace(statut='envoye', roof_layout={CLE_DESIGNATIONS: {'onduleur': 3}})
        veut, rendu = appliquer_designations_a_la_resynchro(
            verrou, SimpleNamespace(cible=cible), {}, False, avertissements)
        self.assertEqual((veut, rendu['modifiees'], rendu['a_ecrire']), (False, 0, False))
        self.assertEqual(avertissements, [MSG_RESYNC_ENVOYE_SANS_APERCU % 'un onduleur et une batterie'])
        self.assertEqual(cible_des_designations(None, apercu_confirme=True).source,
                         'designations_calepinage_confirmees')
        self.assertEqual(cible_des_designations(None).source, SOURCE_DESIGNATIONS)
        # Règle combinée (fusion lot 8 / revue du 26/11) — UN prédicat : brouillon né sous la règle, toute
        # source du calepinage ; envoyé né sous la règle, seulement la source CONFIRMÉE ; jamais sans marqueur.
        from apps.ventes.domain.creation_calepinage import (
            MSG_RESYNC_OPTION_GARDEE, SOURCE_DESIGNATIONS_CONFIRMEES, designations_appliquees, option_batterie_gardee)
        confirmee = SimpleNamespace(cible=SimpleNamespace(source=SOURCE_DESIGNATIONS_CONFIRMEES))
        simple = SimpleNamespace(cible=SimpleNamespace(source=SOURCE_DESIGNATIONS))
        marque = {CLE_DESIGNATIONS: {'onduleur': 5}}
        for statut, layout, intention, attendu in (
                ('brouillon', marque, simple, True), ('brouillon', marque, confirmee, True),
                ('envoye', marque, simple, False), ('envoye', marque, confirmee, True),
                ('envoye', {}, confirmee, False), ('brouillon', {}, simple, False),
                ('accepte', marque, confirmee, False), ('envoye', marque, SimpleNamespace(cible=None), False)):
            with self.subTest(statut=statut, marqueur=bool(layout), source=getattr(intention.cible, 'source', None)):
                self.assertIs(designations_appliquees(SimpleNamespace(statut=statut, roof_layout=layout), intention),
                              attendu)
        # Cas 3 / 2 — l'invariant d'option ne joue que si les désignations ne sont PAS appliquées.
        hybride = SimpleNamespace(produit_id=5, produit=None, designation='Onduleur hybride Deye 5kW Monophasé')
        batterie = SimpleNamespace(produit_id=6, produit=None, designation='Batterie Dyness 5 kWh')
        for intention, attendu in ((simple, (True, [MSG_RESYNC_OPTION_GARDEE % hybride.designation])),
                                   (confirmee, (False, []))):
            dits = []
            rendu = option_batterie_gardee(SimpleNamespace(statut='envoye', roof_layout=marque), intention,
                                           [hybride, batterie], False, dits)
            self.assertEqual((rendu, dits), attendu)

    def test_relecture_finale_option_batterie_gardee_hors_designations_appliquees(self):
        """Lot 8, relecture finale — l'invariant : une resynchro qui n'applique pas les désignations
        (envoyé, ou hors calepinage) garde « avec batterie » au devis né par l'hybride désigné ; un
        brouillon né sous la règle qui les reçoit, un layout « avec », un devis sans marqueur, un hybride
        changé à la main ou sans batterie : rien ne change, rien n'est dit."""
        from types import SimpleNamespace

        from apps.ventes.domain.creation_calepinage import (
            CLE_DESIGNATIONS, MSG_RESYNC_OPTION_GARDEE, SOURCE_DESIGNATIONS, option_batterie_gardee)

        hybride = SimpleNamespace(produit_id=5, produit=None, designation='Onduleur hybride Deye 5kW Monophasé')
        batterie = SimpleNamespace(produit_id=6, produit=None, designation='Batterie Dyness 5 kWh')
        calepinage = SimpleNamespace(cible=SimpleNamespace(source=SOURCE_DESIGNATIONS))
        hors = SimpleNamespace(cible=None)
        marque = {CLE_DESIGNATIONS: {'onduleur': 5, 'batterie': None}}
        phrase = MSG_RESYNC_OPTION_GARDEE % hybride.designation
        for statut, layout, intention, lignes, veut, attendu in (
                ('envoye', marque, calepinage, [hybride, batterie], False, (True, [phrase])),
                ('brouillon', marque, hors, [hybride, batterie], False, (True, [phrase])),
                ('envoye', marque, hors, [hybride, batterie], False, (True, [phrase])),
                ('brouillon', marque, calepinage, [hybride, batterie], False, (False, [])),
                ('envoye', marque, calepinage, [hybride, batterie], True, (True, [])),
                ('envoye', {}, calepinage, [hybride, batterie], False, (False, [])),
                ('envoye', {CLE_DESIGNATIONS: {}}, calepinage, [hybride, batterie], False, (False, [])),
                ('envoye', marque, calepinage, [SimpleNamespace(**dict(vars(hybride), produit_id=9)), batterie],
                 False, (False, [])),
                ('envoye', marque, calepinage, [hybride], False, (False, []))):
            with self.subTest(statut=statut, layout=layout, lignes=len(lignes), veut=veut):
                avertissements = []
                rendu = option_batterie_gardee(SimpleNamespace(statut=statut, roof_layout=layout), intention,
                                               lignes, veut, avertissements)
                self.assertEqual((rendu, avertissements), attendu)

    def test_a_poser_le_produit_respecte_prix_et_quantite_saisis(self):
        from decimal import Decimal as D
        from types import SimpleNamespace

        from apps.ventes.domain.creation_calepinage import _poser_produit

        produit = SimpleNamespace(pk=9, nom='Onduleur réseau Growatt 8kW', prix_vente=D('16000'))

        def ligne(**extra):
            base = dict(produit_id=3, designation='Onduleur réseau Huawei 5kW', prix_unitaire=D('14000'),
                        role_devis='onduleur_reseau', quantite=D('1'), prix_manuel=False, quantite_manuelle=False)
            base.update(extra)
            objet = SimpleNamespace(**base)
            objet.save = lambda update_fields: setattr(objet, 'enregistre', sorted(update_fields))
            return objet

        avertissements = []
        manuelle = ligne(prix_manuel=True)
        self.assertFalse(_poser_produit(manuelle, produit, 'onduleur_reseau', avertissements))
        self.assertEqual((manuelle.produit_id, len(avertissements)), (3, 1))
        posee = ligne(quantite_manuelle=True)
        self.assertTrue(_poser_produit(posee, produit, 'onduleur_reseau', avertissements, nombre=2))
        self.assertEqual((posee.designation, posee.prix_unitaire, posee.quantite),
                         ('Onduleur réseau Growatt 8kW', D('16000'), D('1')))  # quantité saisie gardée
        self.assertEqual(posee.enregistre, ['designation', 'prix_unitaire', 'produit'])
        nombre = ligne()
        self.assertTrue(_poser_produit(nombre, produit, 'onduleur_hybride', avertissements, nombre=2))
        self.assertEqual((nombre.quantite, nombre.role_devis), (D('2'), 'onduleur_hybride'))

    def test_b_decision_de_la_batterie_designee(self):
        """D-ACAL-164 — la décision, nourrie par les VRAIES fonctions du catalogue (nom lu comme le PDF
        et la resynchro, compatibilité par le juge de la composition)."""
        from types import SimpleNamespace

        from apps.ventes.domain.catalogue import _batterie_compatible, _is_battery
        from apps.ventes.domain.creation_calepinage import decision_batterie_designee
        from apps.ventes.utils.options import texte_classement

        dyness, bos = 'Batterie Dyness 5 kWh', 'Deye BOS-B Pack16'

        def decision(nom=dyness, scenario='avec', plage=None, **extra):
            options = dict(produit_id=4, nom=nom, etat='tarife',
                           nom_dit_batterie=_is_battery(texte_classement(nom, nom)),
                           scenario=scenario, hybride_nom='Onduleur hybride Deye 5kW',
                           compatible=_batterie_compatible(SimpleNamespace(nom=nom), plage), packs=2)
            options.update(extra)
            return decision_batterie_designee(**options)

        self.assertEqual(decision()['impose'], {'produit_id': 4, 'nombre': 2, 'designee': True})
        self.assertIsNotNone(decision(plafond=2)['impose'])  # au plafond : composable
        self.assertEqual(decision(scenario='les_deux')['option'], 'avec')
        for attendu, extra in (('n’est pas mise au devis', {'scenario': 'sans'}),
                               ('son nom ne dit pas qu’il s’agit d’une batterie', {'nom': bos}),
                               ('ne convient pas à l’onduleur « Onduleur hybride Deye 5kW »', {'plage': (0, 0)}),
                               ('aucun onduleur hybride ni autonome', {'hybride_nom': None}),
                               ('aucun nombre de packs', {'packs': None}),
                               ('n’est pas un entier', {'packs': None, 'packs_illisible': True}),
                               ('pas de prix de vente', {'etat': 'sans_prix'}),
                               ('dépasse les 4 modules par banc', {'packs': 6, 'plafond': 4})):
            with self.subTest(attendu=attendu):
                rendu = decision(**extra)
                self.assertIsNone(rendu['impose'])
                self.assertIn(attendu, rendu['message'])
                self.assertIn('« %s »' % extra.get('nom', dyness), rendu['message'])

    def test_b_sans_designation_l_intention_est_inchangee(self):
        from apps.ventes.domain.creation_calepinage import _appliquer_les_designations
        from apps.ventes.domain.pipeline import ORIGINE_CALEPINAGE, CibleDevis, IntentionDevis

        intention = IntentionDevis(origine=ORIGINE_CALEPINAGE, company=None, cible=CibleDevis(nb_panneaux=12),
                                   scenario='sans', layout={'result': {}})
        journal = {}
        self.assertEqual(_appliquer_les_designations(intention, None, None, 'sans', journal), (intention, []))
        self.assertEqual(journal, {})

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
        for rang, (nom, prix) in enumerate((('Onduleur réseau Growatt 8kW Monophasé', 16000),
                                            ('Onduleur hybride Growatt 8kW Monophasé', 20000))):
            Produit.objects.create(company=self.company, nom=nom, sku=f'A148-{rang}-{self.company.pk}',
                                   prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=10)
        self.lead = Lead.objects.create(company=self.company, nom='Designe', prenom='Lead', email='d148@ex.com')

    def _id(self, nom):
        return Produit.objects.get(company=self.company, nom=nom).pk

    def _devis(self, scenario='reseau', designe=None, **extra):
        journal = {}
        devis = build_devis_from_layout(layout=dict(self.LAYOUT, scenario=scenario), user=self.user,
                                        company=self.company, lead=self.lead, journal=journal,
                                        onduleur_designe=designe, **extra)
        self.dernier = devis
        onduleurs = sorted((li.designation, li.role_devis, li.variante or '', int(li.quantite))
                           for li in devis.lignes.all() if str(li.role_devis or '').startswith('onduleur_'))
        return onduleurs, journal

    def test_sans_designation_rien_ne_change(self):
        sans, journal = self._devis()
        self.assertEqual(sans, [('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', '', 1)])
        self.assertNotIn('onduleur_designe', journal)

    def test_reseau_designe_tarife_est_chiffre(self):
        onduleurs, journal = self._devis(designe={
            'produit_id': self._id('Onduleur réseau Huawei 5kW Monophasé'), 'nombre': 1})
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau', '', 1)])
        self.assertIsNone(journal['onduleur_designe']['motif'])

    def test_hybride_designe_avec_batterie_est_chiffre_au_nombre_accepte(self):
        onduleurs, _journal = self._devis('avec_batterie', {
            'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'), 'nombre': 2})
        self.assertEqual(onduleurs, [('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride', '', 2)])

    def test_repli_annonce_sans_prix(self):
        Produit.objects.filter(company=self.company, nom='Onduleur réseau Huawei 5kW Monophasé').update(prix_vente=0)
        onduleurs, journal = self._devis(designe={
            'produit_id': self._id('Onduleur réseau Huawei 5kW Monophasé'), 'nombre': 1})
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', '', 1)])
        self.assertTrue(any('pas de prix de vente' in m for m in journal['avertissements']), journal)

    def test_d_acal_159_hybride_designe_sur_pose_sans_batterie_bascule_avec_batterie(self):
        onduleurs, journal = self._devis(designe={
            'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'), 'nombre': 1})
        self.assertEqual(onduleurs, [('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride', '', 1)])
        self.assertTrue(any(li.role_devis == 'batterie' and li.quantite > 0 for li in self.dernier.lignes.all()))
        self.assertTrue(any('Le devis passe en « avec batterie » : l’onduleur désigné « Onduleur hybride '
                            'Deye 5kW Monophasé » est un hybride.' == m for m in journal['avertissements']), journal)
        self.assertEqual(journal['onduleur_designe']['scenario'], 'avec')

    def test_relecture_finale_envoye_ne_d_acal_159_resynchronise_garde_son_option(self):
        """Lot 8, relecture finale — le devis né « avec batterie » par l'hybride désigné (layout stocké
        « sans »), ENVOYÉ, resynchronisé sur un toit d'un panneau de plus, avec puis sans les désignations
        du calepinage : le compte suit le toit, l'hybride, la batterie et sa quantité restent, le marqueur
        aussi. Mutant « sans option_batterie_gardee » ⇒ batterie retirée, hybride permuté ⇒ rouge."""
        from apps.ventes.domain.creation_calepinage import CLE_DESIGNATIONS, MSG_RESYNC_OPTION_GARDEE
        from apps.ventes.models import Devis
        from apps.ventes.services import _is_panel, sync_devis_from_layout

        nom = 'Onduleur hybride Deye 5kW Monophasé'
        designe = {'produit_id': self._id(nom), 'nombre': 1}
        self._devis(designe=designe)
        devis = self.dernier
        marqueur = devis.roof_layout[CLE_DESIGNATIONS]
        batteries = self._batteries()
        self.assertTrue(batteries)
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        for panneaux, designations in ((13, {'onduleur': designe, 'batterie': None}), (14, None)):
            with self.subTest(designations=designations):
                layout = dict(self.LAYOUT, result=dict(self.LAYOUT['result'], panels=panneaux,
                                                       kwc=round(panneaux * 0.55, 3)))
                resultat = sync_devis_from_layout(Devis.objects.get(pk=devis.pk), layout, self.user,
                                                  designations=designations)
                self.dernier = Devis.objects.get(pk=devis.pk)
                lignes = list(self.dernier.lignes.all())
                self.assertEqual([li.designation for li in lignes if str(li.role_devis or '').startswith('onduleur_')],
                                 [nom])
                self.assertEqual(self._batteries(), batteries)
                self.assertEqual(sum(int(li.quantite) for li in lignes if _is_panel(li.designation or '')), panneaux)
                self.assertEqual((resultat['scenario'], resultat['batterie']), ('avec_batterie', True), resultat)
                self.assertIn(MSG_RESYNC_OPTION_GARDEE % nom, resultat['avertissements'])
                self.assertEqual(self.dernier.roof_layout[CLE_DESIGNATIONS], marqueur)

    def test_aucune_batterie_composee_avec_l_hybride_designe_repli_dit(self):
        """Point 3 — la composition ne pose une batterie qu'en stock et en module de 5 ou 10 kWh :
        un 16 kWh seul en stock ne sert pas l'option « avec ». Le devis garde le choix du catalogue
        et le dit, en nommant l'hybride désigné ; jamais « avec » sans batterie ni option retirée
        en silence."""
        Produit.objects.filter(company=self.company, nom='Batterie Dyness 5 kWh').update(quantite_stock=0)
        Produit.objects.create(company=self.company, nom='Batterie Deye BOS-B Pack 16 kWh',
                               sku=f'A148-B16-{self.company.pk}', prix_vente=Decimal('36400'),
                               prix_achat=Decimal('1'), quantite_stock=10)
        designe = {'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'), 'nombre': 1}
        for extra in ({'scenario': 'avec_batterie'}, {'deux_options': True}):
            with self.subTest(**extra):
                onduleurs, journal = self._devis(designe=designe, **extra)
                self.assertNotIn('Onduleur hybride Deye 5kW Monophasé', [d for d, *_ in onduleurs])
                self.assertIsNone(journal['onduleur_designe']['impose'])
                self.assertTrue(any('« Onduleur hybride Deye 5kW Monophasé »' in m and 'ne pose aucune batterie' in m
                                    for m in journal['avertissements']), journal)

    def _batteries(self):
        return sorted((li.designation, int(li.quantite), li.variante or '') for li in self.dernier.lignes.all()
                      if li.role_devis == 'batterie')

    def test_b_batterie_designee_vendue_au_nombre_de_packs_meme_hors_stock(self):
        """D-ACAL-164 — vendue au nombre de packs saisi ; comme l'onduleur désigné, un prix suffit (la
        banque imposée de la composition ne lit pas le stock)."""
        Produit.objects.create(company=self.company, nom='Batterie Lithium 7 kWh', sku=f'A164-B7-{self.company.pk}',
                               prix_vente=Decimal('21000'), prix_achat=Decimal('1'), quantite_stock=0)
        batterie = {'produit_id': self._id('Batterie Lithium 7 kWh'), 'packs': 2, 'packs_illisible': False}
        for extra, variante in (({'scenario': 'avec_batterie'}, ''), ({'deux_options': True}, 'avec')):
            with self.subTest(**extra):
                _o, journal = self._devis(batterie_designee=batterie, **extra)
                self.assertEqual(self._batteries(), [('Batterie Lithium 7 kWh', 2, variante)])
                # Point 4 — vendue aux 2 packs désignés ; la règle automatique (5 kWh visés) en placerait 1.
                self.assertEqual(journal['batterie_designee']['message'],
                                 'La batterie désignée « Batterie Lithium 7 kWh » est vendue à 2 pack(s), le nombre '
                                 'saisi à l’étape Électrique ; la règle automatique du devis en placerait 1.')

    def test_b_batterie_designee_sur_pose_sans_et_sans_hybride_n_est_pas_mise_et_le_dit(self):
        batterie = {'produit_id': self._id('Batterie Dyness 5 kWh'), 'packs': 1, 'packs_illisible': False}
        _o, journal = self._devis(batterie_designee=batterie)
        self.assertEqual(self._batteries(), [])
        self.assertTrue(any('n’est pas mise au devis' in m for m in journal['avertissements']), journal)

    def test_b_batterie_sans_prix_le_choix_automatique_et_le_dit(self):
        Produit.objects.create(company=self.company, nom='Batterie Lithium 7 kWh', sku=f'A164-B0-{self.company.pk}',
                               prix_vente=Decimal('0'), prix_achat=Decimal('1'), quantite_stock=5)
        batterie = {'produit_id': self._id('Batterie Lithium 7 kWh'), 'packs': 2, 'packs_illisible': False}
        _o, journal = self._devis('avec_batterie', batterie_designee=batterie)
        self.assertEqual([d for d, *_ in self._batteries()], ['Batterie Dyness 5 kWh'])
        self.assertTrue(any('pas de prix de vente' in m and 'choix automatique' in m
                            for m in journal['avertissements']), journal)

    def test_deux_options_chaque_onduleur_va_a_son_option_jamais_un_500(self):
        onduleurs, _j = self._devis(designe={'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'),
                                             'nombre': 1}, deux_options=True)
        self.assertIn(('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride', 'avec', 1), onduleurs)
        self.assertIn(('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau', 'sans', 1), onduleurs)
        onduleurs, _j = self._devis(designe={'produit_id': self._id('Onduleur réseau Huawei 5kW Monophasé'),
                                             'nombre': 1}, deux_options=True)
        self.assertIn(('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau', 'sans', 1), onduleurs)
        self.assertIn(('Onduleur hybride Growatt 8kW Monophasé', 'onduleur_hybride', 'avec', 1), onduleurs)

    def test_apercu_a_blanc_meme_composition_que_la_creation(self):
        from apps.ventes.services import composer_a_blanc_depuis_layout

        designe = {'produit_id': self._id('Onduleur hybride Deye 5kW Monophasé'), 'nombre': 1}
        journal = {}
        specs = composer_a_blanc_depuis_layout(layout=dict(self.LAYOUT, scenario='avec_batterie'),
                                               company=self.company, lead=self.lead,
                                               onduleur_designe=designe, journal=journal)
        a_blanc = sorted(s['designation'] for s in specs if str(s.get('role_devis') or '').startswith('onduleur_'))
        cree, _j = self._devis('avec_batterie', designe)
        self.assertEqual(a_blanc, [d for d, *_ in cree])
        self.assertEqual(journal['onduleur_designe']['impose']['categorie'], 'onduleur_hybride')
