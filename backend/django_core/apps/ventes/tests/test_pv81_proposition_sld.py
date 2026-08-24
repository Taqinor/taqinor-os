"""PV81 — la proposition client porte le schéma unifilaire (SVG, sans prix).

Deux garanties :

* le bloc n'existe QUE lorsque la conception électrique (PV41) a été faite —
  jamais une esquisse fabriquée à la volée pour remplir la page ;
* la charge utile publique reste sans AUCUN prix : le moteur électrique n'en
  connaît aucun, et le test le vérifie sur le SVG servi par le jeton.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv81_proposition_sld -v 2
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import (
    _conception_electrique_publique,
    _PUBLIC_CABLE,
    _PUBLIC_CHAINE,
    _PUBLIC_PROTECTION,
    _safe_sld_svg,
)
from authentication.models import Company

User = get_user_model()


class MontageDevisElectrique:
    """Montage PARTAGÉ (pas un TestCase) : un devis réel avec sa toiture, son
    panneau et son onduleur, plus les deux raccourcis « concevoir » et
    « jeton ». En faire un mixin plutôt qu'une classe parente évite qu'une
    sous-classe RE-JOUE les tests de l'autre."""

    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv81-acme")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV81", email="pv81@example.com")
        self.devis = Devis.objects.create(
            company=self.company, reference="DV-PV81-1",
            client=self.crm_client,
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 14, "azimut_deg": 180,
                 "inclinaison_deg": 20}]})
        panneau = Produit.objects.create(
            company=self.company, nom="Panneau PV 550W mono",
            sku="PV81-PAN", prix_vente=Decimal("1234"),
            prix_achat=Decimal("789"), quantite_stock=100)
        onduleur = Produit.objects.create(
            company=self.company, nom="Onduleur réseau 10kW triphasé",
            sku="PV81-OND", prix_vente=Decimal("12345"),
            prix_achat=Decimal("9876"), quantite_stock=10)
        # PVFCH (fondateur 20/08/2026) — « never invent numbers » : un schéma
        # unifilaire ne se dessine QU'À PARTIR des fiches techniques du
        # matériel. Sans elles, ``rendre_schema_du_devis`` rend ``None``.
        FicheTechnique.objects.create(
            company=self.company, produit=panneau, type_fiche="module",
            pmax_wc=Decimal("550.00"), voc_v=Decimal("49.90"),
            isc_a=Decimal("14.02"), vmp_v=Decimal("41.80"),
            imp_a=Decimal("13.16"),
            temp_coeff_voc_pct_c=Decimal("-0.270"),
            temp_coeff_pmax_pct_c=Decimal("-0.350"))
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche="onduleur",
            ond_ac_kw=Decimal("10.00"), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal("200.0"), ond_mppt_v_max=Decimal("950.0"),
            ond_v_max_abs=Decimal("1100.0"),
            ond_i_max_mppt_a=Decimal("26.0"),
            ond_rendement_euro_pct=Decimal("98.0"), ond_bat_aucune=True)
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau,
            designation="Panneau PV 550W mono", quantite=14,
            prix_unitaire=Decimal("1234"))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation="Onduleur réseau 10kW triphasé", quantite=1,
            prix_unitaire=Decimal("12345"))

    def _concevoir(self):
        from apps.ventes.electrical_service import build_electrical_design
        return build_electrical_design(self.devis)

    def _token(self):
        jeton = str(uuid.uuid4())
        # L-NIV (24/08) : un lien NEUF vaut 'standard' (SLD/câbles dégradés) —
        # ces pins du dossier technique complet passent en 'confiance'.
        ShareLink.objects.create(
            company=self.company, devis=self.devis, token=jeton,
            niveau=ShareLink.NIVEAU_CONFIANCE)
        return jeton


class PropositionSldTest(MontageDevisElectrique, TestCase):
    def test_none_sans_conception_electrique(self):
        self.assertIsNone(self.devis.electrical_design)
        self.assertIsNone(_safe_sld_svg(self.devis))

    def test_svg_apres_conception(self):
        self._concevoir()
        svg = _safe_sld_svg(self.devis)
        self.assertIsNotNone(svg)
        self.assertTrue(svg.startswith('<svg'))
        self.assertTrue(svg.endswith('</svg>'))
        self.assertIn('Schéma unifilaire', svg)
        self.assertIn('Client PV81', svg)      # cartouche : son propre nom
        self.assertIn('DV-PV81-1', svg)

    def test_aucun_prix_dans_le_svg(self):
        self._concevoir()
        svg = _safe_sld_svg(self.devis)
        # Aucun vocabulaire monétaire (les coordonnées SVG, elles, sont des
        # nombres nus : on n'y cherche donc pas des chiffres au hasard mais
        # les MONTANTS tels qu'ils s'écriraient s'ils fuyaient).
        for interdit in ('prix', 'marge', 'mad', 'ttc', 'remise', 'total'):
            self.assertNotIn(interdit, svg.lower())
        for montant in ('1 234', '12 345', '1234,00', '12345,00',
                        '17 276', '29 621'):
            self.assertNotIn(montant, svg)

    def test_servi_par_le_jeton_public(self):
        self._concevoir()
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sld_svg', resp.json())
        self.assertIn('<svg', resp.json()['sld_svg'])

    def test_cle_toujours_presente_meme_sans_design(self):
        # Une clé absente forcerait la page publique à deviner : elle vaut
        # None, jamais rien.
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        charge = resp.json()
        self.assertIn('sld_svg', charge)
        self.assertIsNone(charge['sld_svg'])

    def test_lecture_pure_aucune_ecriture(self):
        self._concevoir()
        self.devis.refresh_from_db()
        statut, empreinte = self.devis.statut, self.devis.electrical_design_hash
        _safe_sld_svg(self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut)
        self.assertEqual(self.devis.electrical_design_hash, empreinte)
        self.assertEqual(self.devis.lignes.count(), 2)


class SchemaRefuseUneConfigurationNonConformeTest(TestCase):
    """DEV-202608-0016 — le schéma ne DESSINE PAS un montage impossible.

    Le devis du fondateur : l'outil 3D a posé 25 Canadian Solar 710 Wc
    (Isc 18,59 A par chaîne) sur un Deye 5 kW monophasé dont chaque entrée MPPT
    admet 17 A en court-circuit. Le moteur répartissait 5 chaînes de 5 sur les
    2 entrées — « MPPT 1 · 3 chaînes », soit 55,8 A dans une entrée à 17 A — et
    le dessinait sans broncher, sur une pièce technique destinée au
    gestionnaire de réseau.

    Les fiches sont COMPLÈTES ici : le refus vient de la CONFORMITÉ, pas de
    PVFCH — et le test le prouve en vérifiant qu'aucune fiche ne manque.
    """

    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="dev16-acme")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client DEV16",
            email="dev16@example.com")
        self.devis = Devis.objects.create(
            company=self.company, reference="DV-DEV16-1",
            client=self.crm_client,
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 25, "azimut_deg": 180,
                 "inclinaison_deg": 20}]})
        # Canadian Solar CS7N-710TB-AG — les valeurs du seeder (PAN-CS-710).
        panneau = Produit.objects.create(
            company=self.company, nom="Panneau Canadien Solar 710W",
            sku="DEV16-PAN", prix_vente=Decimal("1500"),
            prix_achat=Decimal("1100"), quantite_stock=100)
        # Deye SUN-5K-SG05LP1-EU — les chiffres du seeder (OND-H-DEY-5M) :
        # 13 A par entrée, 17 A d'Isc admissible.
        onduleur = Produit.objects.create(
            company=self.company, nom="Onduleur hybride Deye 5kW Monophasé",
            sku="DEV16-OND", prix_vente=Decimal("14000"),
            prix_achat=Decimal("11000"), quantite_stock=10)
        FicheTechnique.objects.create(
            company=self.company, produit=panneau, type_fiche="module",
            pmax_wc=Decimal("710.00"), voc_v=Decimal("48.30"),
            isc_a=Decimal("18.59"), vmp_v=Decimal("40.40"),
            imp_a=Decimal("17.59"),
            temp_coeff_voc_pct_c=Decimal("-0.250"),
            temp_coeff_pmax_pct_c=Decimal("-0.290"))
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche="onduleur",
            ond_ac_kw=Decimal("5.00"), ond_phases=1, ond_n_mppt=2,
            ond_mppt_v_min=Decimal("125.0"), ond_mppt_v_max=Decimal("425.0"),
            ond_v_max_abs=Decimal("500.0"),
            ond_i_max_mppt_a=Decimal("13.0"),
            ond_isc_max_mppt_a=Decimal("17.0"),
            ond_v_demarrage_v=Decimal("125.0"),
            ond_bat_v_min=Decimal("40.0"), ond_bat_v_max=Decimal("60.0"))
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau,
            designation="Panneau Canadien Solar 710W", quantite=25,
            prix_unitaire=Decimal("1500"))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation="Onduleur hybride Deye 5kW Monophasé", quantite=1,
            prix_unitaire=Decimal("14000"))

    def _concevoir(self):
        from apps.ventes.electrical_service import build_electrical_design
        return build_electrical_design(self.devis)

    def test_les_fiches_sont_completes_le_refus_n_est_pas_pvfch(self):
        from apps.ventes.electrical_service import fiches_manquantes_du_devis
        self.assertEqual(fiches_manquantes_du_devis(self.devis), [])

    def test_l_etude_porte_le_bloquant_avec_les_amperes_des_fiches(self):
        design = self._concevoir()
        bloquants = design['conformite']['bloquants']
        self.assertFalse(design['conformite']['conforme'])
        self.assertTrue(bloquants)
        joint = ' '.join(bloquants)
        self.assertIn('55,8 A', joint)      # 3 × 18,59 A sur l'entrée MPPT 1
        self.assertIn('17,0 A', joint)      # la borne PUBLIÉE de l'entrée

    def test_aucun_schema_pour_une_configuration_non_conforme(self):
        from apps.ventes.electrical_service import rendre_schema_du_devis
        self._concevoir()
        self.assertIsNone(rendre_schema_du_devis(self.devis))
        self.assertIsNone(_safe_sld_svg(self.devis))

    def test_le_motif_est_lisible_et_nomme_la_non_conformite(self):
        from apps.ventes.electrical_service import (
            motifs_non_conformite_du_devis)
        self._concevoir()
        motifs = motifs_non_conformite_du_devis(self.devis)
        self.assertTrue(motifs)
        self.assertTrue(motifs[0].startswith(
            'Configuration électrique non conforme :'), motifs[0])
        self.assertIn('17,0 A', ' '.join(motifs))

    def test_la_page_publique_n_affiche_aucun_schema(self):
        self._concevoir()
        jeton = str(uuid.uuid4())
        # L-NIV (24/08) : un lien NEUF vaut 'standard' (SLD/câbles dégradés) —
        # ces pins du dossier technique complet passent en 'confiance'.
        ShareLink.objects.create(
            company=self.company, devis=self.devis, token=jeton,
            niveau=ShareLink.NIVEAU_CONFIANCE)
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % jeton)
        self.assertEqual(resp.status_code, 200)
        charge = resp.json()
        self.assertIn('sld_svg', charge)
        self.assertIsNone(charge['sld_svg'])

    def test_le_refus_n_ecrit_ni_statut_ni_ligne(self):
        """Règle #4 — refuser un dessin ne touche pas le document."""
        self._concevoir()
        self.devis.refresh_from_db()
        statut = self.devis.statut
        from apps.ventes.electrical_service import rendre_schema_du_devis
        rendre_schema_du_devis(self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut)
        self.assertEqual(self.devis.lignes.count(), 2)


class ConceptionElectriquePubliqueTest(MontageDevisElectrique, TestCase):
    """Décision fondateur 2026-08-18 — LE DÉTAIL ÉLECTRIQUE EST EXPOSÉ AU CLIENT.

    Le client paie « Tableau De Protection AC/DC » et « Accessoires » sans
    jamais savoir ce qu'il y a dedans. Le bloc `conception_electrique` de la
    charge utile publique le lui dit — chaînes, organes nominatifs avec leurs
    calibres, sections et longueurs de câble — et RIEN d'autre.

    Trois garanties, exactement celles demandées :
      1. le bloc apparaît quand l'étude électrique existe ;
      2. il est absent (None) sinon — jamais une composition fabriquée ;
      3. aucun champ hors liste blanche ne franchit la frontière publique.

    Réutilise le montage de PropositionSldTest (même devis, même jeton).
    """

    #: Ce qui ne doit JAMAIS sortir : nomenclature d'achat, paramètres du
    #: calcul, verdicts d'ingénierie, tensions de chaîne, chute de tension.
    INTERDITS_RACINE = ('bom', 'parametres', 'conformite',
                        'ratio_dc_ac', 'ratio_ac_dc', 'note')

    def test_absent_sans_conception_electrique(self):
        self.assertIsNone(self.devis.electrical_design)
        self.assertIsNone(_conception_electrique_publique(self.devis))

    def test_present_apres_conception(self):
        self._concevoir()
        bloc = _conception_electrique_publique(self.devis)
        self.assertIsNotNone(bloc)
        self.assertEqual(set(bloc), {'chaines', 'protections', 'cables'})
        # Les trois clés sont TOUJOURS là (une page qui ferait `.map()` sur
        # `undefined` planterait), et l'étude dit au moins quelque chose.
        for cle in ('chaines', 'protections', 'cables'):
            self.assertIsInstance(bloc[cle], list)
        self.assertTrue(any(bloc.values()), 'bloc public entièrement vide')

    def test_aucun_champ_hors_liste_blanche(self):
        self._concevoir()
        bloc = _conception_electrique_publique(self.devis)
        interne = self.devis.electrical_design
        # (a) rien de l'étude interne ne s'invite à la racine du bloc public…
        for cle in self.INTERDITS_RACINE:
            self.assertNotIn(cle, bloc, f"« {cle} » ne doit pas être publié")
        # …et ces clés existent BIEN dans le contrat interne : le test prouve
        # donc un retrait, pas une absence de départ.
        self.assertIn('bom', interne)
        self.assertIn('parametres', interne)
        # (b) chaque élément est projeté sur SA liste blanche, clé par clé.
        for chaine in bloc['chaines']:
            self.assertTrue(set(chaine) <= set(_PUBLIC_CHAINE), chaine)
        for organe in bloc['protections']:
            self.assertTrue(set(organe) <= set(_PUBLIC_PROTECTION), organe)
        for cable in bloc['cables']:
            self.assertTrue(set(cable) <= set(_PUBLIC_CABLE), cable)
        # (c) les grandeurs d'ingénierie par élément restent côté vendeur.
        for chaine in bloc['chaines']:
            for cle in ('vmp_froid_v', 'voc_froid_v', 'vmp_chaud_v', 'conforme'):
                self.assertNotIn(cle, chaine)
        for cable in bloc['cables']:
            self.assertNotIn('chute_pct', cable)

    def test_aucun_prix_dans_le_bloc_public(self):
        self._concevoir()
        texte = str(_conception_electrique_publique(self.devis)).lower()
        for interdit in ('prix', 'marge', 'mad', 'ttc', 'remise', 'total',
                         'achat'):
            self.assertNotIn(interdit, texte)
        # Les montants du devis, tels qu'ils s'écriraient s'ils fuyaient.
        for montant in ('1234', '12345', '1 234', '12 345'):
            self.assertNotIn(montant, texte)

    def test_servi_par_le_jeton_public(self):
        self._concevoir()
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        bloc = resp.json()['conception_electrique']
        self.assertIsNotNone(bloc)
        self.assertEqual(set(bloc), {'chaines', 'protections', 'cables'})

    def test_cle_toujours_presente_meme_sans_design(self):
        # Une clé absente forcerait la page publique à deviner : elle vaut
        # None, jamais rien.
        resp = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % self._token())
        self.assertEqual(resp.status_code, 200)
        charge = resp.json()
        self.assertIn('conception_electrique', charge)
        self.assertIsNone(charge['conception_electrique'])

    def test_valeur_absente_omise_jamais_un_zero(self):
        # Le contrat interne peut porter un None (grandeur non calculée) : la
        # clé DISPARAÎT du bloc public plutôt que de valoir 0 — la page web
        # applique la règle dure « valeur absente ⇒ rien affiché ».
        self._concevoir()
        design = dict(self.devis.electrical_design)
        design['cables'] = [{'liaison': 'Chaîne 1 → coffret DC',
                             'longueur_m': None, 'section_mm2': 6,
                             'chute_pct': 0.62}]
        self.devis.electrical_design = design
        self.devis.save(update_fields=['electrical_design'])
        cable = _conception_electrique_publique(self.devis)['cables'][0]
        self.assertEqual(cable, {'liaison': 'Chaîne 1 → coffret DC',
                                 'section_mm2': 6})

    def test_lecture_pure_aucune_ecriture_du_bloc_public(self):
        self._concevoir()
        self.devis.refresh_from_db()
        statut, empreinte = self.devis.statut, self.devis.electrical_design_hash
        _conception_electrique_publique(self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut)
        self.assertEqual(self.devis.electrical_design_hash, empreinte)
        self.assertEqual(self.devis.lignes.count(), 2)
