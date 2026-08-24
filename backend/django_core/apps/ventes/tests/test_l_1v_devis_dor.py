# -*- coding: utf-8 -*-
"""L-1V — LE « DEVIS D'OR » : une seule vérité électrique sur la page client.

CE QUE CE GARDE-FOU EMPÊCHE DE REVENIR. La page de proposition affichait deux
vérités électriques CONTRADICTOIRES pour le même devis :

  * la FICHE technique (« Dans votre installation ») listait les organes issus
    d'une JOINTURE entre l'étude rangée et les LIGNES du devis, routée par une
    heuristique de texte (« dc » dans la désignation). Le jour où l'anticopie a
    fusionné les lignes du kit en un seul « Kit de fixation, câblage et
    protection complet », le poste entier est parti du côté alternatif : tous
    les organes continus (fusibles gPV, parafoudre DC, sectionneur DC) ont
    disparu de la fiche du client ;
  * le SCHÉMA unifilaire de la MÊME page, lui, continuait de les dessiner —
    parce qu'il ne lisait pas l'étude rangée : il RECALCULAIT tout depuis les
    lignes courantes à chaque rendu.

Quatre assertions, sur un devis réaliste (8 × Canadian Solar 710 Wc, Deye 5 kW
monophasé, Dyness 5,1 kWh) rendu AUX DEUX NIVEAUX de partage :

  (a) ``E_sld == E_fiche`` — le jeu des repères que la planche affiche
      (``data-repere``, émis par ``core.electrique.schema``) est EXACTEMENT
      celui des groupes servis à la fiche. L'échec NOMME les orphelins des deux
      côtés ;
  (b) non-vacuité — au moins un organe DC et un organe AC ; une égalité entre
      deux ensembles vides passerait sinon sans rien garantir ;
  (c) source unique — ``E_sld`` ⊆ les repères de l'``electrical_design``
      STOCKÉ. C'est l'assertion qui interdit le recalcul : sur l'ancien code,
      le schéma redessinait les LIGNES et affichait donc des repères absents de
      l'artefact dès que les deux divergeaient (cf.
      ``test_c_le_schema_ne_peut_plus_depasser_l_artefact``) ;
  (d) fraîcheur — muter UNE ligne par ``LigneDevisViewSet`` fait bouger les
      DEUX surfaces ENSEMBLE (classe ``FraicheurDesDeuxSurfaces``, base
      requise).

Run (hôte, sans base — (a)(b)(c)) :
    python manage.py test apps.ventes.tests.test_l_1v_devis_dor.DevisDOr -v 2
Run complet :
    DB_NAME=erp_ventes python manage.py test \\
        apps.ventes.tests.test_l_1v_devis_dor -v 2
"""
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import electrical_service as es
from apps.ventes.models import Devis, ShareLink
from apps.ventes.public_views import _conception_electrique_publique
from apps.ventes.tests.test_pv41_conception_electrique import (
    _FausseFiche, _FausseLigne, _FauxDevis, _FauxProduit)
from authentication.models import Company

User = get_user_model()

#: Les repères présents sur une planche rendue. ``data-repere`` ne porte QUE
#: des organes de protection : un bloc de topologie (champ PV, coffret de
#: chaînes, TGBT) n'en a pas, et une ligne de CÂBLE porte ``data-cable``.
_REPERE_RE = re.compile(r'data-repere="([^"]+)"')


def _reperes_du_svg(svg):
    return set(_REPERE_RE.findall(svg or ''))


def _reperes_de_la_fiche(bloc):
    """Les repères des GROUPES SERVEUR — l'union de ce que la fiche peut
    montrer, quel que soit le découpage des lignes du devis."""
    reperes = set()
    for cle in ('protections_dc', 'protections_ac', 'protections_communes'):
        for organe in (bloc or {}).get(cle) or []:
            if organe.get('repere'):
                reperes.add(organe['repere'])
    return reperes


# ── Le devis d'or, DUCK-TYPÉ (aucune base : le calcul est pur) ───────────────

def _panneau_cs710():
    """Canadian Solar TOPHiKu7 710 Wc — valeurs de la fiche constructeur."""
    return _FauxProduit("Panneau PV 710 Wc mono", marque="Canadian Solar",
                        fiche=_FausseFiche(
                            "module",
                            pmax_wc=Decimal("710.00"),
                            voc_v=Decimal("48.30"),
                            isc_a=Decimal("18.59"),
                            vmp_v=Decimal("40.40"),
                            imp_a=Decimal("17.59"),
                            temp_coeff_voc_pct_c=Decimal("-0.250"),
                            temp_coeff_pmax_pct_c=Decimal("-0.290"),
                            longueur_mm=2384, largeur_mm=1303))


def _onduleur_deye_5k():
    """Deye SUN-5K-SG05LP3 — hybride monophasé, 2 MPPT."""
    return _FauxProduit("Onduleur hybride Deye 5 kW", marque="Deye",
                        fiche=_FausseFiche(
                            "onduleur",
                            ond_ac_kw=Decimal("5.00"),
                            ond_phases=1,
                            ond_n_mppt=2,
                            ond_mppt_v_min=Decimal("125.0"),
                            ond_mppt_v_max=Decimal("500.0"),
                            ond_v_max_abs=Decimal("800.0"),
                            ond_i_max_mppt_a=Decimal("26.0"),
                            ond_rendement_euro_pct=None,
                            ond_v_demarrage_v=None,
                            ond_isc_max_mppt_a=Decimal("39.0"),
                            ond_bat_aucune=False,
                            ond_bat_v_min=Decimal("40.0"),
                            ond_bat_v_max=Decimal("60.0")))


def _batterie_dyness():
    return _FauxProduit("Batterie Dyness 5,1 kWh", marque="Dyness",
                        fiche=_FausseFiche(
                            "batterie",
                            bat_kwh_nominal=Decimal("5.12"),
                            bat_kwh_usable=Decimal("4.86"),
                            bat_dod_pct=Decimal("95.0"),
                            bat_v_nominal=Decimal("51.2"),
                            bat_max_charge_kw=Decimal("2.56")))


def _devis_dor():
    """8 × CS 710 + Deye 5 kW mono + Dyness 5,1 kWh, sur un pan unique.

    C'est la composition résidentielle courante : celle qui a révélé la
    contradiction, et celle que l'anticopie fusionne en une seule ligne de kit.
    """
    devis = _FauxDevis(
        lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 8,
                         produit=_panneau_cs710()),
            _FausseLigne("Onduleur hybride Deye 5 kW", 1,
                         produit=_onduleur_deye_5k()),
            _FausseLigne("Batterie Dyness 5,1 kWh", 1,
                         produit=_batterie_dyness()),
            # La ligne KIT telle que l'anticopie la produit : elle ne dit ni
            # « DC » ni « AC ». C'est elle qui faisait tomber tout le dossier
            # du côté alternatif quand la page routait par le libellé.
            _FausseLigne("Kit de fixation, câblage et protection complet", 1),
        ],
        roof_layout={"_pans_geometry": [
            {"label": "Sud", "nb_panneaux": 8, "azimut_deg": 180,
             "inclinaison_deg": 20}]},
        layout_hash="devis-dor")
    devis.reference = "DEV-OR-0001"
    devis.client = None
    devis.date_creation = None
    return devis


class DevisDOr(SimpleTestCase):
    """(a)(b)(c) — sans base : le moteur et les projections sont purs."""

    NIVEAUX = (ShareLink.NIVEAU_CONFIANCE, ShareLink.NIVEAU_STANDARD)

    def setUp(self):
        self.devis = _devis_dor()
        self.design = es.build_electrical_design(self.devis)
        self.assertTrue(self.design["chaines"],
                        "montage cassé : aucune chaîne calculée")
        self.assertFalse(self.design["conformite"]["bloquants"],
                         self.design["conformite"]["bloquants"])

    # ── (a) ─────────────────────────────────────────────────────────────────
    def test_a_le_schema_et_la_fiche_montrent_les_memes_organes(self):
        for niveau in self.NIVEAUX:
            with self.subTest(niveau=niveau):
                standard = niveau == ShareLink.NIVEAU_STANDARD
                sld = _reperes_du_svg(
                    es.rendre_schema_du_devis(self.devis, standard=standard))
                fiche = _reperes_de_la_fiche(
                    _conception_electrique_publique(self.devis, niveau))
                self.assertEqual(
                    sld, fiche,
                    "DEUX VÉRITÉS ÉLECTRIQUES au niveau « %s » — "
                    "sur le SCHÉMA mais absents de la FICHE : %s ; "
                    "sur la FICHE mais absents du SCHÉMA : %s"
                    % (niveau, sorted(sld - fiche) or "aucun",
                       sorted(fiche - sld) or "aucun"))

    # ── (b) ─────────────────────────────────────────────────────────────────
    def test_b_les_deux_cotes_sont_reellement_peuples(self):
        """Deux ensembles VIDES seraient égaux : l'égalité (a) ne vaut que si
        les deux côtés portent réellement des organes."""
        for niveau in self.NIVEAUX:
            with self.subTest(niveau=niveau):
                bloc = _conception_electrique_publique(self.devis, niveau)
                self.assertTrue(bloc["protections_dc"],
                                "aucun organe CONTINU servi — c'est très "
                                "exactement le symptôme d'origine")
                self.assertTrue(bloc["protections_ac"],
                                "aucun organe ALTERNATIF servi")
                svg = es.rendre_schema_du_devis(
                    self.devis,
                    standard=niveau == ShareLink.NIVEAU_STANDARD)
                reperes = _reperes_du_svg(svg)
                self.assertTrue(
                    {r for r in reperes if r.startswith(("F", "PDC", "QDC"))},
                    "le schéma ne montre AUCUN organe continu")
                self.assertTrue(
                    {r for r in reperes
                     if r.startswith(("QAC", "PAC", "DDR"))},
                    "le schéma ne montre AUCUN organe alternatif")

    # ── (c) ─────────────────────────────────────────────────────────────────
    def test_c_le_schema_ne_peut_plus_depasser_l_artefact(self):
        """SOURCE UNIQUE — le schéma se rend depuis l'étude STOCKÉE.

        La preuve est faite en RETIRANT un organe de l'artefact sans toucher
        aux lignes : le devis reste identique, seule l'étude rangée change.
        L'ancien code (qui rappelait ``concevoir()`` sur les lignes) redessinait
        l'organe retiré et cette assertion serait ROUGE ; le code actuel ne
        peut dessiner que ce que l'artefact porte.
        """
        artefact = dict(self.devis.electrical_design)
        organes = list(artefact["protections"])
        self.assertGreater(len(organes), 1)
        retire = organes[0]["repere"]
        artefact["protections"] = organes[1:]
        self.devis.electrical_design = artefact

        for niveau in self.NIVEAUX:
            with self.subTest(niveau=niveau):
                sld = _reperes_du_svg(es.rendre_schema_du_devis(
                    self.devis,
                    standard=niveau == ShareLink.NIVEAU_STANDARD))
                stockes = {o["repere"] for o in artefact["protections"]}
                self.assertTrue(
                    sld <= stockes,
                    "le schéma affiche des repères ABSENTS de l'étude "
                    "stockée (donc recalculés depuis les lignes) : %s"
                    % sorted(sld - stockes))
                self.assertNotIn(
                    retire, sld,
                    "« %s » a été retiré de l'étude et le schéma le dessine "
                    "encore : le schéma ne lit pas l'artefact" % retire)

    def test_c_bis_la_fiche_lit_le_meme_artefact(self):
        """Le pendant de (c) côté fiche : elle non plus ne peut pas dépasser
        l'étude stockée (elle ne la joint plus aux lignes du devis)."""
        artefact = dict(self.devis.electrical_design)
        artefact["protections"] = artefact["protections"][1:]
        self.devis.electrical_design = artefact
        stockes = {o["repere"] for o in artefact["protections"]}
        for niveau in self.NIVEAUX:
            with self.subTest(niveau=niveau):
                fiche = _reperes_de_la_fiche(
                    _conception_electrique_publique(self.devis, niveau))
                self.assertTrue(fiche <= stockes, sorted(fiche - stockes))

    # ── L-NIV — la même règle de dégradation des deux côtés ────────────────
    def test_le_niveau_standard_retire_les_calibres_des_deux_surfaces(self):
        """Standard = désignations + quantités + repères, JAMAIS un calibre.

        L'ancienne dégradation ôtait le tableau de nomenclature ENTIER du SVG
        mais laissait les calibres dans les sous-titres des blocs, pendant que
        la liste, elle, les cachait : le même lien disait et cachait la même
        chose.
        """
        calibres = {o["calibre"] for o in self.devis.electrical_design[
            "protections"] if o.get("calibre")}
        self.assertTrue(calibres, "montage cassé : aucun calibre à masquer")
        svg_std = es.rendre_schema_du_devis(self.devis, standard=True)
        svg_conf = es.rendre_schema_du_devis(self.devis, standard=False)
        for calibre in calibres:
            self.assertNotIn(calibre, svg_std,
                             "calibre « %s » encore lisible au niveau "
                             "standard" % calibre)
        self.assertTrue(any(c in svg_conf for c in calibres),
                        "le niveau confiance doit, lui, tout montrer")
        bloc = _conception_electrique_publique(
            self.devis, ShareLink.NIVEAU_STANDARD)
        for cle in ('protections', 'protections_dc', 'protections_ac',
                    'protections_communes'):
            for organe in bloc[cle]:
                self.assertNotIn('calibre', organe)
        # …mais les REPÈRES restent, aux deux niveaux et sur les deux surfaces.
        self.assertTrue(_reperes_du_svg(svg_std))

    def test_le_niveau_standard_ne_change_pas_le_jeu_des_organes(self):
        """La dégradation retire des GRANDEURS, jamais un organe : les deux
        niveaux montrent le même dossier."""
        self.assertEqual(
            _reperes_du_svg(es.rendre_schema_du_devis(self.devis,
                                                      standard=True)),
            _reperes_du_svg(es.rendre_schema_du_devis(self.devis,
                                                      standard=False)))

    # ── Estampille (étape 4) ───────────────────────────────────────────────
    def test_le_cartouche_imprime_la_version_de_l_artefact(self):
        from core.electrique.version import VERSION_MOTEUR
        self.assertEqual(self.devis.electrical_design["version_moteur"],
                         VERSION_MOTEUR)
        svg = es.rendre_schema_du_devis(self.devis)
        self.assertIn("v%s" % VERSION_MOTEUR, svg)
        # Version de l'ARTEFACT, pas du moteur du jour : on la change dans
        # l'étude rangée (même MAJEUR ⇒ aucun rejeu) et le cartouche suit.
        artefact = dict(self.devis.electrical_design)
        majeur = VERSION_MOTEUR.split(".")[0]
        artefact["version_moteur"] = "%s.99.99" % majeur
        self.devis.electrical_design = artefact
        self.assertIn("v%s.99.99" % majeur,
                      es.rendre_schema_du_devis(self.devis))

    def test_un_artefact_de_majeur_perime_est_rejoue_jamais_melange(self):
        """Un MAJEUR qui bouge invalide l'artefact : on le REJOUE plutôt que
        de dessiner un mélange de deux moteurs."""
        artefact = dict(self.devis.electrical_design)
        artefact["version_moteur"] = "0.0.1"
        self.devis.electrical_design = artefact
        self.assertTrue(es.artefact_a_rejouer(artefact))
        svg = es.rendre_schema_du_devis(self.devis)
        self.assertTrue(svg)
        from core.electrique.version import VERSION_MOTEUR
        self.assertEqual(self.devis.electrical_design["version_moteur"],
                         VERSION_MOTEUR)

    def test_un_artefact_sans_materiel_est_rejoue_pas_perdu(self):
        """Format antérieur (aucune clé ``materiel``) : rejeu one-shot, jamais
        un crash ni un schéma qui disparaît."""
        artefact = {c: v for c, v in self.devis.electrical_design.items()
                    if c not in ("materiel", "version_moteur")}
        self.devis.electrical_design = artefact
        self.assertTrue(es.artefact_a_rejouer(artefact))
        self.assertTrue(es.rendre_schema_du_devis(self.devis))

    def test_les_cotes_viennent_du_moteur(self):
        """Chaque organe rangé porte SON côté — plus rien à déduire en aval."""
        cotes = {o["repere"]: o["cote"]
                 for o in self.devis.electrical_design["protections"]}
        for repere, cote in cotes.items():
            attendu = ("dc" if repere.startswith(("F", "PDC", "QDC"))
                       else "ac" if repere.startswith(("QAC", "PAC", "DDR"))
                       else "commun")
            self.assertEqual(cote, attendu, repere)


# ═══════════════════════════════════════════════════════════════════════════
# (d) fraîcheur — base requise
# ═══════════════════════════════════════════════════════════════════════════

class FraicheurDesDeuxSurfaces(TestCase):
    """(d) — muter UNE ligne fait bouger les DEUX surfaces ENSEMBLE.

    ``LigneDevisViewSet`` ne rafraîchissait QUE l'étude horaire : ajouter des
    panneaux depuis l'écran de devis faisait bouger le graphe de la page client
    sans toucher à la conception électrique, et le schéma unifilaire continuait
    de décrire la composition d'avant. Sur l'ancien code, l'assertion « le
    nombre de modules de l'étude a suivi » est ROUGE.
    """

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='l1v-co', defaults={'nom': 'L-1V Co'})
        self.user = User.objects.create_user(
            username='l1v_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='L1V',
            telephone='+212600000092')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadian Solar 710 Wc',
            sku='L1V-PV710', prix_vente=Decimal('1200'), quantite_stock=100)
        FicheTechnique.objects.create(
            company=self.company, produit=self.panneau, type_fiche='module',
            pmax_wc=Decimal('710.00'), voc_v=Decimal('48.30'),
            vmp_v=Decimal('40.40'), isc_a=Decimal('18.59'),
            imp_a=Decimal('17.59'),
            temp_coeff_voc_pct_c=Decimal('-0.250'),
            temp_coeff_pmax_pct_c=Decimal('-0.290'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 5 kW',
            sku='L1V-OND5', prix_vente=Decimal('12000'), quantite_stock=10)
        FicheTechnique.objects.create(
            company=self.company, produit=self.onduleur,
            type_fiche='onduleur', ond_ac_kw=Decimal('5.00'), ond_phases=1,
            ond_n_mppt=2, ond_mppt_v_min=Decimal('125.0'),
            ond_mppt_v_max=Decimal('500.0'), ond_v_max_abs=Decimal('800.0'),
            ond_i_max_mppt_a=Decimal('26.0'),
            ond_isc_max_mppt_a=Decimal('39.0'))

    def _devis(self):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'lignes': [
                {'produit': self.panneau.id, 'quantite': '8',
                 'prix_unitaire': '1200',
                 'designation': 'Panneau Canadian Solar 710 Wc'},
                {'produit': self.onduleur.id, 'quantite': '1',
                 'prix_unitaire': '12000',
                 'designation': 'Onduleur hybride Deye 5 kW'},
            ]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return Devis.objects.get(id=resp.data['id'])

    def test_d_une_ligne_mutee_deplace_les_deux_surfaces(self):
        devis = self._devis()
        self.assertTrue(devis.electrical_design)
        modules_avant = devis.electrical_design['materiel']['nb_modules']
        sld_avant = _reperes_du_svg(es.rendre_schema_du_devis(devis))
        self.assertTrue(sld_avant)

        ligne = devis.lignes.get(produit=self.panneau)
        resp = self.api.patch(
            f'/api/django/ventes/lignes-devis/{ligne.id}/',
            {'quantite': '12'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        devis.refresh_from_db()
        modules_apres = devis.electrical_design['materiel']['nb_modules']
        self.assertNotEqual(
            modules_avant, modules_apres,
            "la conception électrique n'a PAS suivi la mutation de ligne : "
            "le schéma unifilaire décrit une composition qui n'existe plus")
        self.assertEqual(modules_apres, 12)
        # …et la FICHE bouge du même mouvement : c'est le même artefact.
        bloc = _conception_electrique_publique(
            devis, ShareLink.NIVEAU_CONFIANCE)
        self.assertEqual(_reperes_du_svg(es.rendre_schema_du_devis(devis)),
                         _reperes_de_la_fiche(bloc))

    def test_d_bis_une_ligne_supprimee_deplace_aussi_les_deux(self):
        devis = self._devis()
        self.assertTrue(devis.electrical_design)
        ligne = devis.lignes.get(produit=self.onduleur)
        resp = self.api.delete(
            f'/api/django/ventes/lignes-devis/{ligne.id}/')
        self.assertEqual(resp.status_code, 204, resp.content)
        devis.refresh_from_db()
        # Sans onduleur, plus d'étude dessinable : les DEUX surfaces se taisent
        # ensemble — jamais l'une sans l'autre.
        svg = es.rendre_schema_du_devis(devis)
        bloc = _conception_electrique_publique(
            devis, ShareLink.NIVEAU_CONFIANCE)
        self.assertEqual(_reperes_du_svg(svg), _reperes_de_la_fiche(bloc))
