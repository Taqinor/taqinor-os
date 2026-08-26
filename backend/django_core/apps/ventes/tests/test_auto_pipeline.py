"""AUTO-PIPELINE — du tracé du client au devis brouillon, sans main humaine.

Ordre fondateur du 26/08/2026 : « si le client dessine son toit dans le
tunnel, une fois que le lead arrive dans notre ERP ça crée automatiquement le
devis automatique, et l'outil de calepinage dessine les panneaux tout seul —
le commercial ne fait que VÉRIFIER ce qui a été fait automatiquement. »

Ce module épingle les quatre garanties de ce câblage :

* la GÉOMÉTRIE — le contour du client devient une vraie zone roofPro11, avec
  les DEUX conventions de coordonnées de ``serializeLayout`` respectées ;
* les PORTES DE DONNÉE — un lead sans facture ne reçoit RIEN (jamais un devis
  vide), un lead sans tracé reçoit le devis d'aujourd'hui (sans calepinage) ;
* l'IDEMPOTENCE — un lead, un devis : ni un webhook re-livré, ni un rejeu de
  la tâche, ni un devis déjà saisi à la main ne peuvent en produire un second ;
* la SOCIÉTÉ — rien ne traverse jamais la frontière d'un tenant.

Run:
    python manage.py test apps.ventes.tests.test_auto_pipeline -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead, LeadActivity
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import (
    aire_contour_m2,
    auto_devis_tunnel_actif,
    build_devis_auto,
    contour_client_lnglat,
    creer_devis_automatique_depuis_lead,
    plafond_physique_du_contour,
    zone_toit_depuis_contour,
)

User = get_user_model()

# Un carré d'environ 20 m de côté à Casablanca, en [lat, lng] — la forme
# EXACTE que ``_clean_roof_outline`` (webhook) range dans ``Lead.roof_outline``.
# 0.00018° de latitude ≈ 20 m ; la longitude est corrigée du cosinus (lat 33.5).
_LAT0, _LNG0 = 33.5731, -7.5898
_DLAT = 0.00018
_DLNG = 0.000216          # ≈ 20 m à cette latitude
CONTOUR_LATLNG = [
    [_LAT0, _LNG0],
    [_LAT0, _LNG0 + _DLNG],
    [_LAT0 + _DLAT, _LNG0 + _DLNG],
    [_LAT0 + _DLAT, _LNG0],
]
CONTOUR_DICTS = [{'lat': lat, 'lng': lng} for lat, lng in CONTOUR_LATLNG]


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company, *, panneau_dims=True):
    """Catalogue minimal — mêmes désignations que ``seed_catalogue``."""
    def mk(nom, sku, prix, **extra):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100, **extra)

    dims = ({'longueur_mm': 2278, 'largeur_mm': 1134} if panneau_dims else {})
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100, **dims)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Dyness 5 kWh', f'BAT-{company.pk}', 17000)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA GÉOMÉTRIE — le tracé du client devient une zone, sans rien inventer
# ═══════════════════════════════════════════════════════════════════════════

class ContourDuClientTest(TestCase):
    """``contour_client_lnglat`` lit les DEUX formes réellement stockées."""

    def setUp(self):
        # UNE société, créée une seule fois : ces tests ne parlent pas
        # d'isolation multi-tenant, ils lisent une géométrie.
        self.company = make_company('contour-co')

    def _lead_contour(self, contour):
        return Lead.objects.create(
            company=self.company, nom='C', prenom='L', roof_outline=contour)

    def test_forme_webhook_lat_lng(self):
        anneau = contour_client_lnglat(self._lead_contour(CONTOUR_LATLNG))
        self.assertEqual(len(anneau), 4)
        # Sortie en [lng, lat] — convention builder/MapLibre. Inverser ici
        # ferait atterrir le toit à des milliers de kilomètres.
        self.assertAlmostEqual(anneau[0][0], _LNG0, places=6)
        self.assertAlmostEqual(anneau[0][1], _LAT0, places=6)

    def test_forme_dict_lat_lng(self):
        """Le trou historique : `hydrateFromLead` refusait cette forme alors
        que le calque de référence l'acceptait — le contour s'affichait mais ne
        semait aucune zone."""
        self.assertEqual(
            contour_client_lnglat(self._lead_contour(CONTOUR_DICTS)),
            contour_client_lnglat(self._lead_contour(CONTOUR_LATLNG)))

    def test_moins_de_trois_sommets_nest_pas_un_polygone(self):
        self.assertEqual(
            contour_client_lnglat(self._lead_contour(CONTOUR_LATLNG[:2])), [])

    def test_coordonnees_hors_bornes_ignorees(self):
        contour = CONTOUR_LATLNG[:2] + [[999.0, 0.0], [181.0, 500.0]]
        self.assertEqual(contour_client_lnglat(self._lead_contour(contour)), [])

    def test_absence_de_contour(self):
        self.assertEqual(contour_client_lnglat(self._lead_contour(None)), [])
        self.assertEqual(contour_client_lnglat(self._lead_contour([])), [])


class AireEtPlafondTest(TestCase):
    def test_aire_du_carre(self):
        aire = aire_contour_m2(contour_client_lnglat(
            Lead(roof_outline=CONTOUR_LATLNG)))
        # ~20 m × ~20 m : on vérifie l'ORDRE DE GRANDEUR, pas une valeur
        # magique — la formule est celle, déjà partagée, de `anneau_enu`.
        self.assertGreater(aire, 350)
        self.assertLess(aire, 450)

    def test_aire_exige_un_polygone(self):
        self.assertIsNone(aire_contour_m2([]))
        self.assertIsNone(aire_contour_m2([[0, 0], [1, 1]]))

    def test_plafond_sans_dimensions_produit_est_none(self):
        """Aucune dimension de panneau connue → AUCUN plafond deviné."""
        contour = contour_client_lnglat(Lead(roof_outline=CONTOUR_LATLNG))
        self.assertIsNone(plafond_physique_du_contour(contour, None))
        self.assertIsNone(plafond_physique_du_contour(
            contour, Produit(longueur_mm=None, largeur_mm=None)))

    def test_plafond_est_surface_sur_surface(self):
        contour = contour_client_lnglat(Lead(roof_outline=CONTOUR_LATLNG))
        panneau = Produit(longueur_mm=2278, largeur_mm=1134)
        plafond = plafond_physique_du_contour(contour, panneau)
        aire = aire_contour_m2(contour)
        attendu = int(aire // (2.278 * 1.134))
        self.assertEqual(plafond, attendu)
        self.assertGreater(plafond, 0)


class ZoneDepuisContourTest(TestCase):
    def setUp(self):
        self.company = make_company('zone-co')

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Z', prenom='L', **extra)

    def test_sans_contour_aucune_zone(self):
        self.assertEqual(
            zone_toit_depuis_contour(self._lead(), panneaux=12), {})

    def test_les_deux_conventions_de_coordonnees(self):
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        frag = zone_toit_depuis_contour(lead, panneaux=12)
        self.assertEqual(frag['version'], 2)
        self.assertEqual(frag['activeAreaId'], frag['zones'][0]['id'])
        # `outline` (racine) est en [lat, lng] — comme `serializeLayout`.
        self.assertAlmostEqual(frag['outline'][0][0], _LAT0, places=6)
        self.assertAlmostEqual(frag['outline'][0][1], _LNG0, places=6)
        # `zones[].vertices` est en [lng, lat] — comme `serializeLayout`.
        self.assertAlmostEqual(frag['zones'][0]['vertices'][0][0], _LNG0,
                               places=6)
        self.assertAlmostEqual(frag['zones'][0]['vertices'][0][1], _LAT0,
                               places=6)

    def test_la_cible_du_devis_pilote_loptimiseur(self):
        frag = zone_toit_depuis_contour(
            self._lead(roof_outline=CONTOUR_LATLNG), panneaux=17)
        zone = frag['zones'][0]
        self.assertEqual(zone['neededPanels'], 17)
        # `neededAuto=False` : c'est le nombre VENDU qui pilote, jamais un
        # remplissage « au mieux » qui inventerait des panneaux.
        self.assertFalse(zone['neededAuto'])
        self.assertEqual(zone['obstacles'], [])

    def test_pin_depuis_le_repere_du_client_sinon_centroide(self):
        pose = self._lead(roof_outline=CONTOUR_LATLNG,
                          roof_point={'lat': 33.6, 'lng': -7.6})
        self.assertEqual(
            zone_toit_depuis_contour(pose, panneaux=1)['pin'],
            {'lat': 33.6, 'lng': -7.6})
        sans = self._lead(roof_outline=CONTOUR_LATLNG)
        pin = zone_toit_depuis_contour(sans, panneaux=1)['pin']
        # Centroïde DÉRIVÉ du tracé réel — jamais une position inventée.
        self.assertAlmostEqual(pin['lat'], _LAT0 + _DLAT / 2, places=6)
        self.assertAlmostEqual(pin['lng'], _LNG0 + _DLNG / 2, places=6)


# ═══════════════════════════════════════════════════════════════════════════
# 2. LE DEVIS AUTOMATIQUE PORTE LE TOIT DU CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class BuildDevisAutoAvecContourTest(TestCase):
    def setUp(self):
        self.company = make_company('autopipe-co')
        self.user = User.objects.create_user(
            username='autopipe', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='Pipe',
            email='autopipe@ex.com', **extra)

    def test_le_layout_embarque_la_zone_du_client(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            roof_outline=CONTOUR_LATLNG),
            user=self.user, company=self.company)
        layout = devis.roof_layout
        self.assertEqual(len(layout['zones']), 1)
        self.assertEqual(len(layout['zones'][0]['vertices']), 4)
        self.assertEqual(layout['_origine_calepinage'], 'contour_client')
        # La zone porte la cible RÉELLEMENT composée, pas un nombre à part.
        self.assertEqual(layout['zones'][0]['neededPanels'],
                         layout['result']['panels'])

    def test_sans_contour_le_layout_est_celui_dhier(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company)
        self.assertNotIn('zones', devis.roof_layout)
        self.assertEqual(devis.roof_layout['result']['panels'], 16)

    def test_le_plafond_ne_peut_que_reduire(self):
        journal = {}
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            roof_outline=CONTOUR_LATLNG),
            user=self.user, company=self.company,
            plafond_toit=4, journal_auto=journal)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 4)
        self.assertEqual(journal['panneaux_avant_plafond'], 16)
        self.assertEqual(journal['plafond_applique'], 4)

    def test_un_plafond_plus_large_ne_change_rien(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company, plafond_toit=999)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 16)


# ═══════════════════════════════════════════════════════════════════════════
# 3. LE SERVICE D'ARRIVÉE — portes, idempotence, société
# ═══════════════════════════════════════════════════════════════════════════

class CreerDevisAutomatiqueDepuisLeadTest(TestCase):
    def setUp(self):
        self.company = make_company('arrivee-co')
        self.owner = User.objects.create_user(
            username='arrivee', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        extra.setdefault('facture_hiver', Decimal('1800'))
        return Lead.objects.create(
            company=self.company, nom='Arrivée', prenom='Lead',
            owner=self.owner, source=Lead.Source.SITE_WEB, **extra)

    def _creer(self, lead):
        return creer_devis_automatique_depuis_lead(
            lead_id=lead.pk, company_id=self.company.pk)

    def test_cree_un_brouillon_cale_sur_le_toit_du_client(self):
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        devis = self._creer(lead)
        self.assertIsNotNone(devis)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.lead_id, lead.pk)
        self.assertEqual(devis.company_id, self.company.pk)
        self.assertEqual(devis.created_by_id, self.owner.pk)
        self.assertEqual(len(devis.roof_layout['zones'][0]['vertices']), 4)
        # Référence par `core.numbering` (JAMAIS count()+1) : préfixe DEV.
        self.assertTrue(devis.reference.startswith('DEV-'))

    def test_note_dhistorique_a_verifier(self):
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        devis = self._creer(lead)
        notes = [a.body for a in LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)]
        note = next(n for n in notes if 'Devis automatique' in n)
        self.assertIn('à vérifier', note)
        self.assertIn(devis.reference, note)
        self.assertIn('tracé du client', note)

    # ── IDEMPOTENCE : UN LEAD, UN DEVIS ────────────────────────────────────

    def test_un_second_appel_ne_cree_pas_un_second_devis(self):
        """Webhook re-livré / tâche Celery rejouée : jamais deux devis."""
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        self.assertIsNotNone(self._creer(lead))
        self.assertIsNone(self._creer(lead))
        self.assertEqual(
            Devis.objects.filter(company=self.company, lead=lead).count(), 1)

    def test_un_devis_saisi_a_la_main_bloque_lauto(self):
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        Devis.objects.create(company=self.company, lead=lead,
                             reference='DEV-MANUEL-1')
        self.assertIsNone(self._creer(lead))
        self.assertEqual(
            Devis.objects.filter(company=self.company, lead=lead).count(), 1)

    # ── LES PORTES DE DONNÉE ───────────────────────────────────────────────

    def test_sans_facture_aucun_devis(self):
        """Un lead parasite/incomplet ne reçoit RIEN — jamais un devis vide."""
        lead = self._lead(facture_hiver=None, roof_outline=CONTOUR_LATLNG)
        self.assertIsNone(self._creer(lead))
        self.assertEqual(Devis.objects.filter(lead=lead).count(), 0)

    def test_sans_contour_un_devis_sans_calepinage(self):
        """Comportement d'aujourd'hui, préservé : le devis existe, sans zone."""
        lead = self._lead()
        devis = self._creer(lead)
        self.assertIsNotNone(devis)
        self.assertNotIn('zones', devis.roof_layout)

    def test_marche_non_residentiel_refuse(self):
        lead = self._lead(type_installation='agricole',
                          roof_outline=CONTOUR_LATLNG)
        self.assertIsNone(self._creer(lead))

    # ── LE RÉGLAGE DE SOCIÉTÉ ──────────────────────────────────────────────

    def test_actif_par_defaut_sans_profil(self):
        self.assertTrue(auto_devis_tunnel_actif(self.company))

    def test_reglage_coupe_la_creation(self):
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.create(
            company=self.company, devis_auto_depuis_tunnel=False)
        self.assertFalse(auto_devis_tunnel_actif(self.company))
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        self.assertIsNone(self._creer(lead))
        self.assertEqual(Devis.objects.filter(lead=lead).count(), 0)

    # ── LA SOCIÉTÉ ─────────────────────────────────────────────────────────

    def test_lead_dune_autre_societe_ignore(self):
        autre = make_company('arrivee-autre-co')
        etranger = Lead.objects.create(
            company=autre, nom='X', prenom='Y',
            facture_hiver=Decimal('1800'), roof_outline=CONTOUR_LATLNG)
        self.assertIsNone(creer_devis_automatique_depuis_lead(
            lead_id=etranger.pk, company_id=self.company.pk))
        self.assertEqual(Devis.objects.filter(lead=etranger).count(), 0)

    def test_societe_inconnue_ignoree(self):
        lead = self._lead()
        self.assertIsNone(creer_devis_automatique_depuis_lead(
            lead_id=lead.pk, company_id=999999))


# ═══════════════════════════════════════════════════════════════════════════
# 4. LA MISE EN FILE — le webhook ne paie jamais la composition
# ═══════════════════════════════════════════════════════════════════════════

class PlanificationTest(TestCase):
    def test_le_planificateur_met_en_file_sans_repli_en_ligne(self):
        from apps.ventes.services import planifier_devis_automatique_pour_lead

        with patch('apps.ventes.tasks.task_devis_automatique_depuis_lead'
                   '.apply_async') as file_:
            planifier_devis_automatique_pour_lead(7, 3)
        file_.assert_called_once_with(args=[7, 3], retry=False)

    def test_un_courtier_injoignable_ne_leve_jamais(self):
        """Le webhook est une surface publique : rien ici ne peut le casser —
        et surtout PAS un repli en ligne qui lui ferait payer la composition."""
        from apps.ventes.services import planifier_devis_automatique_pour_lead

        with patch('apps.ventes.tasks.task_devis_automatique_depuis_lead'
                   '.apply_async', side_effect=OSError('redis down')), \
                patch('apps.ventes.services.'
                      'creer_devis_automatique_depuis_lead') as en_ligne:
            planifier_devis_automatique_pour_lead(7, 3)
        en_ligne.assert_not_called()
