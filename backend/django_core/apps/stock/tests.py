"""
Tests for the seed_catalogue management command (devis-simulator catalogue).

Run:
    docker compose exec django_core python manage.py test apps.stock -v 2
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.stock.models import Produit, MouvementStock


def make_company(slug='test-cat-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test Catalogue Co'},
    )
    return company


def seed(company, **options):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out,
                 **options)
    return out.getvalue()


class TestSeedCatalogue(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_seeds_full_catalogue(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # 31 solaire + 9 pompage + 16 VEICHI + 11 pompes OSP + 22 câbles/protections
        # + 1 batterie Deye BOS-B Pro HV 16 kWh (PVG4, identité PVLV2)
        # (PVLV2 21/08/2026 : les 2 doublons « Deye basse tension 15/20 kW »
        # du 18/08 ne sont PLUS seedés — les SKU historiques SONT les LV)
        self.assertEqual(qs.count(), 92)
        # Spot-check key items: HT price = simulator TTC / 1.2
        huawei_10t = qs.get(sku='OND-R-HUA-10T')
        self.assertEqual(huawei_10t.nom, 'Onduleur réseau Huawei 10kW Triphasé')
        self.assertEqual(huawei_10t.prix_vente, Decimal('16666.67'))  # 20 000 TTC
        # Réforme TVA : panneau à 10 % — HT dérivé pour préserver 1 400 TTC
        panneau = qs.get(sku='PAN-CS-710')
        self.assertEqual(panneau.prix_vente, Decimal('1272.73'))      # 1 400 TTC @ 10 %
        self.assertEqual(panneau.tva, Decimal('10.00'))
        bat10 = qs.get(sku='BAT-DEY-10')
        self.assertEqual(bat10.prix_vente, Decimal('25000.00'))       # 30 000 TTC
        socles = qs.get(sku='SOC-BET')
        self.assertEqual(socles.prix_vente, Decimal('66.67'))         # 80 TTC
        # Stock available so auto-fill is never blocked
        self.assertTrue(all(p.quantite_stock > 0 for p in qs))
        # Traceability: one entry movement per product
        self.assertEqual(
            MouvementStock.objects.filter(
                company=self.company, reference='SEED-CATALOGUE').count(), 92,
        )

    def test_fiches_and_pompage_seeded(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # Fiches commerciales remplies (marque/description/garantie)
        huawei = qs.get(sku='OND-R-HUA-10T')
        self.assertEqual(huawei.marque, 'Huawei')
        self.assertIn('FusionSolar', huawei.description)
        self.assertIn('10 ans', huawei.garantie)
        panneau = qs.get(sku='PAN-CS-710')
        self.assertIn('30 ans performance', panneau.garantie)
        # Pompage : specs de dimensionnement + prix d'achat laissé vide
        pompe = qs.get(sku='PMP-IMM-5.5T')
        self.assertEqual(str(pompe.pompe_cv), '5.50')
        self.assertEqual(pompe.prix_achat, 0)
        self.assertEqual(pompe.categorie.nom, 'Pompes')
        # Prix existants jamais modifiés par la passe fiches
        self.assertEqual(huawei.prix_vente, Decimal('16666.67'))

    def test_pv9_fiches_techniques_seeded_with_sourced_values_only(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        cs = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        fiche_cs = FicheTechnique.objects.get(produit=cs)
        self.assertEqual(fiche_cs.type_fiche, 'module')
        self.assertEqual(fiche_cs.longueur_mm, 2384)
        self.assertEqual(fiche_cs.largeur_mm, 1303)
        self.assertEqual(fiche_cs.epaisseur_mm, 35)
        self.assertEqual(fiche_cs.temp_coeff_pmax_pct_c, Decimal('-0.290'))
        # PV85 — datasheet CS7N-710TB-AG complète (valeurs STC).
        self.assertEqual(fiche_cs.pmax_wc, Decimal('710.00'))
        self.assertEqual(fiche_cs.voc_v, Decimal('48.30'))
        self.assertEqual(fiche_cs.isc_a, Decimal('18.59'))
        self.assertEqual(fiche_cs.vmp_v, Decimal('40.40'))
        self.assertEqual(fiche_cs.imp_a, Decimal('17.59'))
        self.assertEqual(fiche_cs.rendement_pct, Decimal('22.90'))
        self.assertEqual(fiche_cs.poids_kg, Decimal('37.90'))
        self.assertEqual(fiche_cs.temp_coeff_voc_pct_c, Decimal('-0.250'))
        self.assertTrue(fiche_cs.bifacial)
        self.assertIn('TOPCon', fiche_cs.techno_cellule)

        jk = Produit.objects.get(company=self.company, sku='PAN-JK-710')
        fiche_jk = FicheTechnique.objects.get(produit=jk)
        self.assertEqual(fiche_jk.type_fiche, 'module')
        self.assertEqual(fiche_jk.temp_coeff_pmax_pct_c, Decimal('-0.290'))
        self.assertEqual(fiche_jk.temp_coeff_voc_pct_c, Decimal('-0.250'))
        # PVOND-H (19/08/2026) — la fiche Jinko est désormais SOURCÉE sur la
        # datasheet officielle JKM710-735N-66HL5-BDV-Z3-EU (elle n'avait
        # aucune valeur électrique avant) : le pin « dimensions absentes »
        # d'hier documente ce qui MANQUAIT, celui-ci ce qui est VÉRIFIÉ.
        self.assertEqual(fiche_jk.pmax_wc, Decimal('710.00'))
        self.assertEqual(fiche_jk.voc_v, Decimal('48.73'))
        self.assertEqual(fiche_jk.isc_a, Decimal('18.53'))
        self.assertEqual(fiche_jk.vmp_v, Decimal('40.65'))
        self.assertEqual(fiche_jk.imp_a, Decimal('17.47'))
        self.assertEqual(fiche_jk.longueur_mm, 2384)
        self.assertEqual(fiche_jk.largeur_mm, 1303)

    def test_pv9_fiches_techniques_idempotent_second_run(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        cs = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        fiche = FicheTechnique.objects.get(produit=cs)
        # Un run seedeur ne re-crée ni ne modifie une fiche existante.
        seed(self.company)
        self.assertEqual(
            FicheTechnique.objects.filter(produit=cs).count(), 1)
        fiche.refresh_from_db()
        self.assertEqual(fiche.temp_coeff_pmax_pct_c, Decimal('-0.290'))

    def test_pv85_fiche_technique_reappliquee_sur_base_deja_seedee(self):
        """PV85 — `--reappliquer-fiches` repose les champs SOURCÉS.

        Sans cette porte, une correction de datasheet (le 10 kW triphasé passé
        de SG04LP3 à SG05LP3 : 26 A/MPPT au lieu de 16 A) resterait bloquée sur
        les bases déjà seedées. Elle est EXPLICITE depuis l'ordre fondateur du
        18/08/2026 (un run nu comble seulement les vides, cf. les deux tests
        PVOND ci-dessous). Ce qui reste intouchable dans les deux modes : tout
        champ que le catalogue ne source pas.
        """
        from apps.stock.models import FicheTechnique
        seed(self.company)
        cs = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        FicheTechnique.objects.filter(produit=cs).delete()
        ancienne = FicheTechnique.objects.create(
            company=self.company, produit=cs, type_fiche='module',
            longueur_mm=1, largeur_mm=1,
            # Champ NON déclaré par le catalogue pour ce SKU : saisie manuelle.
            bat_kwh_nominal=Decimal('42.00'))
        call_command('seed_catalogue', company_slug=self.company.slug,
                     reappliquer_fiches=True, stdout=StringIO())
        ancienne.refresh_from_db()
        # Champs SOURCÉS → ré-appliqués depuis la datasheet.
        self.assertEqual(ancienne.longueur_mm, 2384)
        self.assertEqual(ancienne.largeur_mm, 1303)
        self.assertEqual(ancienne.temp_coeff_pmax_pct_c, Decimal('-0.290'))
        # Champ NON sourcé → jamais touché par le seeder.
        self.assertEqual(ancienne.bat_kwh_nominal, Decimal('42.00'))
        # Toujours une seule fiche par produit.
        self.assertEqual(
            FicheTechnique.objects.filter(produit=cs).count(), 1)

    # ── PVOND (18/08/2026) — LE SEEDER COMBLE, IL N'ÉCRASE PLUS ──────────────
    # Le bandeau « Onduleur(s) non chiffrable(s) » du fondateur ne venait pas
    # d'un manque de données SOURCÉES (le seeder les portait déjà) : elles
    # n'avaient jamais atteint les LIGNES EXISTANTES de la base de production.
    # Le seeder tourne désormais à chaque déploiement — il doit donc réparer
    # sans jamais détruire une saisie.
    def test_pvond_les_specs_vides_d_une_fiche_existante_sont_comblees(self):
        """Fiche déjà là mais VIDE (le cas de la prod) → le seeder la remplit."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        FicheTechnique.objects.filter(produit=p).delete()
        nue = FicheTechnique.objects.create(
            company=self.company, produit=p, type_fiche='onduleur')
        self.assertIsNone(nue.ond_i_max_mppt_a)

        seed(self.company)   # run NU, sans --reappliquer-fiches

        nue.refresh_from_db()
        self.assertEqual(nue.ond_n_mppt, 2)
        self.assertEqual(nue.ond_i_max_mppt_a, Decimal('26.0'))
        self.assertEqual(nue.ond_ac_kw, Decimal('10'))
        self.assertEqual(nue.ond_rendement_euro_pct, Decimal('97.0'))
        # …et l'onduleur redevient chiffrable, ce qui est TOUT le sujet.
        from apps.stock.selectors import onduleur_specs_manquantes
        p.refresh_from_db()
        self.assertEqual(onduleur_specs_manquantes(p), [])

    def test_pvond_une_valeur_saisie_par_le_fondateur_n_est_jamais_ecrasee(self):
        """« Rends-moi facile de saisir les infos. » Ce que le fondateur tape
        survit à TOUS les redéploiements — c'est ce qui rend sûr l'appel du
        seeder depuis deploy-prod.ps1."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        fiche = FicheTechnique.objects.get(produit=p)
        # Le fondateur corrige à l'écran : 30 A au lieu des 26 A du catalogue,
        # et vide un autre champ pour prouver que le vide, LUI, est comblé.
        fiche.ond_i_max_mppt_a = Decimal('30.0')
        fiche.ond_rendement_euro_pct = None
        fiche.save(update_fields=['ond_i_max_mppt_a', 'ond_rendement_euro_pct'])

        seed(self.company)   # run NU (celui du déploiement)

        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('30.0'))   # INTACTE
        self.assertEqual(fiche.ond_rendement_euro_pct, Decimal('97.0'))  # comblée

        # …et la porte explicite existe toujours pour une correction datasheet.
        call_command('seed_catalogue', company_slug=self.company.slug,
                     reappliquer_fiches=True, stdout=StringIO())
        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('26.0'))

    # ── PVLV2 (fondateur 21/08/2026) — le 20 kW EST le SG05LP3 basse tension ──
    def test_pvlv2_le_20kw_est_le_sg05lp3_basse_tension_avec_ses_prix(self):
        """« I only know 15 and 20kw on LV » : le SKU HISTORIQUE porte le
        modèle basse tension, ses prix d'origine et une fiche complète."""
        from apps.stock.models import FicheTechnique
        from apps.stock.selectors import (
            onduleur_specs_manquantes, plage_batterie_onduleur,
        )
        from apps.ventes.services import _has_price
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-20T')
        self.assertEqual(p.nom, 'Onduleur hybride Deye 20kW Triphasé')
        self.assertEqual(p.prix_vente, Decimal('40000.00'))   # 48 000 TTC
        self.assertEqual(p.prix_achat, Decimal('35000.00'))   # 42 000 TTC
        self.assertEqual(p.marque, 'Deye')
        self.assertIn('Modèle confirmé fondateur : Deye SUN-20K-SG05LP3-EU-SM2',
                      p.description)
        self.assertNotIn('Modèle supposé', p.description)
        self.assertNotIn('SG01HP3', p.description)
        self.assertTrue(_has_price(p))
        # Basse tension : la plage batterie 48 V de la famille SG05LP3 —
        # les Dyness 51,2 V s'y accrochent (le parc réel du fondateur).
        self.assertEqual(plage_batterie_onduleur(p), (40.0, 60.0))
        self.assertEqual(onduleur_specs_manquantes(p), [])
        fiche = FicheTechnique.objects.get(produit=p)
        self.assertEqual(fiche.ond_ac_kw, Decimal('20'))
        self.assertEqual(fiche.ond_phases, 3)
        self.assertEqual(fiche.ond_mppt_v_min, Decimal('160.0'))
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('650.0'))
        self.assertEqual(fiche.ond_v_max_abs, Decimal('800.0'))
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('20.0'))
        self.assertEqual(fiche.ond_rendement_euro_pct, Decimal('97.0'))
        self.assertEqual(fiche.ond_v_demarrage_v, Decimal('160.0'))
        self.assertEqual(fiche.ond_isc_max_mppt_a, Decimal('30.0'))

    def test_pvlv2_les_doublons_basse_tension_ne_renaissent_jamais(self):
        """PVLV2 — les SKU « Basse Tension » du 18/08 étaient des DOUBLONS nés
        d'une fausse identification : une base neuve ne les crée plus, et une
        base ancienne qui les porte encore les voit ARCHIVÉS par le seeder
        (``ARTEFACTS_ONDULEUR_SKUS``), jamais supprimés."""
        legacy = Produit.objects.create(
            company=self.company,
            nom='Onduleur hybride Deye 15kW Triphasé Basse Tension',
            sku='OND-DEY-15K-LV', prix_vente=Decimal('0'),
            quantite_stock=0)
        seed(self.company)
        legacy.refresh_from_db()
        self.assertTrue(legacy.is_archived)
        self.assertFalse(Produit.objects.filter(
            company=self.company, sku='OND-DEY-20K-LV').exists())

    def test_pvond_completer_les_specs_ne_resynchronise_aucun_devis(self):
        """PVSYNC — vérification du chemin de resynchronisation.

        ``ventes.services.resynchroniser_devis_pour_produit`` ne suit QUE le
        nom et le prix de vente d'un produit. Quand le seeder comble une fiche
        technique, RIEN ne doit donc être propagé aux devis — et c'est le bon
        comportement : un devis déjà émis est un DOCUMENT (désignations et prix
        figés), tandis que le contrat de complétude (le grisage d'un onduleur)
        est recalculé EN DIRECT à chaque ouverture du générateur. Ce test fige
        cette frontière : élargir la liste ferait réécrire des documents à
        chaque déploiement, puisque le seeder tourne désormais à chaque fois.
        """
        from apps.stock.views.produit import CHAMPS_PRODUIT_SUIVIS_DEVIS
        self.assertEqual(CHAMPS_PRODUIT_SUIVIS_DEVIS, ('nom', 'prix_vente'))

    def test_pv85_deye_10t_modele_confirme_fondateur(self):
        """PV85 — SG05LP3 tranché par le fondateur : plus « supposé »."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        self.assertIn('Modèle confirmé fondateur : '
                      'Deye SUN-10K-SG05LP3-EU-SM2', p.description)
        self.assertNotIn('Modèle supposé', p.description)
        self.assertNotIn('SG04LP3', p.description)
        fiche = FicheTechnique.objects.get(produit=p)
        self.assertEqual(fiche.ond_n_mppt, 2)
        self.assertEqual(fiche.ond_mppt_v_min, Decimal('200.0'))
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('650.0'))
        self.assertEqual(fiche.ond_v_max_abs, Decimal('800.0'))
        # Révision actuelle du manuel (nov-2025) : 26 A par MPPT, pas 20 A.
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('26.0'))
        self.assertEqual(fiche.ond_ac_kw, Decimal('10'))
        self.assertEqual(fiche.ond_phases, 3)
        self.assertEqual(fiche.ond_rendement_euro_pct, Decimal('97.0'))

    def test_g4_deye_5m_mono_est_sg05lp1_pas_sg04lp1(self):
        """G4 (2026-08-19, plainte fondateur) — le SG04LP1 ne doit plus
        survivre nulle part sur le 5 kW monophasé : ni le modèle affiché, ni
        les caractéristiques électriques de sa FicheTechnique (re-sourcées sur
        la datasheet officielle deyeinverter.com SUN-5K-SG05LP1-EU)."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-5M')
        self.assertIn('Modèle supposé : Deye SUN-5K-SG05LP1-EU(-SM2)', p.description)
        self.assertNotIn('SG04', p.description)
        fiche = FicheTechnique.objects.get(produit=p)
        self.assertEqual(fiche.ond_n_mppt, 2)
        self.assertEqual(fiche.ond_mppt_v_min, Decimal('150.0'))
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('425.0'))
        # Rated PV Input Voltage 370 (125-500) V sur la fiche SG05LP1 : 500 V,
        # PAS 600 V (l'ancienne valeur, jamais vérifiée sur une fiche SG05LP1).
        self.assertEqual(fiche.ond_v_max_abs, Decimal('500.0'))
        # L-22A (fondateur 24/08/2026) — « increase their mppt current to more
        # then 20A so they accept the canadian solar pannels » : les DEUX
        # bornes de courant sont DÉCLARÉES à 22 A (elles valaient 13 A d'Imp
        # et 17 A d'Isc, identification datasheet SG05LP1). Le reste de la
        # fiche reste sourcé sur cette datasheet — c'est tout l'objet de ce
        # test, que la correction L-22A ne dilue pas.
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('22.0'))
        self.assertEqual(fiche.ond_isc_max_mppt_a, Decimal('22.0'))
        self.assertEqual(fiche.ond_ac_kw, Decimal('5'))
        self.assertEqual(fiche.ond_phases, 1)
        self.assertEqual(fiche.ond_rendement_euro_pct, Decimal('96.5'))

    # ── PVG4 — Fiches techniques onduleurs/batteries (modèle supposé) ───────
    def test_pvg4_onduleur_fiche_sourced_values_only(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p5m = Produit.objects.get(company=self.company, sku='OND-R-HUA-5M')
        f5m = FicheTechnique.objects.get(produit=p5m)
        self.assertEqual(f5m.type_fiche, 'onduleur')
        self.assertEqual(f5m.ond_n_mppt, 2)
        self.assertEqual(f5m.ond_mppt_v_min, Decimal('90.0'))
        self.assertEqual(f5m.ond_mppt_v_max, Decimal('560.0'))
        self.assertEqual(f5m.ond_v_max_abs, Decimal('600.0'))
        # L-22A (fondateur 24/08/2026) — bornes de courant DÉCLARÉES à 22 A
        # (l'Imp valait 12,5 A, SUN2000-5KTL-L1 ; l'Isc n'avait jamais été
        # seedé du tout — le champ était NULL, il est maintenant DÉCLARÉ).
        self.assertEqual(f5m.ond_i_max_mppt_a, Decimal('22.0'))
        self.assertEqual(f5m.ond_isc_max_mppt_a, Decimal('22.0'))
        self.assertEqual(f5m.ond_ac_kw, Decimal('5'))
        self.assertEqual(f5m.ond_phases, 1)
        self.assertEqual(f5m.ond_rendement_euro_pct, Decimal('97.8'))
        self.assertIn('Modèle supposé : Huawei SUN2000-5KTL-L1', p5m.description)
        self.assertIn('à confirmer fondateur', p5m.description)

    def test_pvond_courants_asymetriques_retiennent_le_tracker_faible(self):
        """PVOND (ordre fondateur 2026-08-18, « ne laisse rien griser ») — un
        courant ASYMÉTRIQUE par tracker est tranché sur LE PLUS FAIBLE : le
        moteur de chaînes ne peut alors jamais produire une configuration qui
        surcharge le tracker faible."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        # « 30 A / 20 A » (fiche famille SUN2000-12-25KTL-M5) → 20 A.
        for sku in ('OND-R-HUA-15T', 'OND-R-HUA-20T', 'OND-R-HUA-25T'):
            fiche = FicheTechnique.objects.get(
                produit=Produit.objects.get(company=self.company, sku=sku))
            self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('20.0'), sku)
        # « 36+20 A » (SG05LP3 14-20K, PVLV2 — les 15/20 kW SONT cette
        # famille basse tension) → 20 A.
        for sku in ('OND-H-DEY-15T', 'OND-H-DEY-20T'):
            fiche = FicheTechnique.objects.get(
                produit=Produit.objects.get(company=self.company, sku=sku))
            self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('20.0'), sku)

        p15t = Produit.objects.get(company=self.company, sku='OND-R-HUA-15T')
        f15t = FicheTechnique.objects.get(produit=p15t)
        # Rendement euro 98,0 % : valeur OFFICIELLE de la famille 12-25KTL-M5
        # (remplace le « interpolé » de PVG4).
        self.assertEqual(f15t.ond_rendement_euro_pct, Decimal('98.0'))
        # Plage MPPT/Vmax, elles, sont sourcées explicitement (inchangé).
        self.assertEqual(f15t.ond_mppt_v_min, Decimal('200.0'))
        self.assertEqual(f15t.ond_mppt_v_max, Decimal('1000.0'))

    def test_pvond_huawei_50t_seede_en_edition_m3(self):
        """Édition présumée M3 (gamme EMEA courante) : 4 MPPT / 30 A / 98,0 %.
        Le M0 (22 A / 98,5 %) reste documenté en commentaire, à confirmer à
        l'achat."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p50t = Produit.objects.get(company=self.company, sku='OND-R-HUA-50T')
        f50t = FicheTechnique.objects.get(produit=p50t)
        self.assertEqual(f50t.ond_n_mppt, 4)
        self.assertEqual(f50t.ond_i_max_mppt_a, Decimal('30.0'))
        self.assertEqual(f50t.ond_rendement_euro_pct, Decimal('98.0'))
        self.assertIn('Modèle supposé : Huawei SUN2000-50KTL-M3', p50t.description)

    def test_pvond_deye_10m_tranche_sur_la_revision_validee_fondateur(self):
        """La divergence de sources est CONSERVÉE en commentaire, mais la
        valeur est tranchée : 26 A/MPPT (révision validée en production le
        2026-08-16, fiche 2024 = 20 A documentée) et la plage MPPT de la
        datasheet SG02LP1-EU-AM3 du modèle nommé."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10M')
        f = FicheTechnique.objects.get(produit=p)
        self.assertEqual(f.type_fiche, 'onduleur')
        self.assertEqual(f.ond_n_mppt, 2)
        self.assertEqual(f.ond_mppt_v_min, Decimal('150.0'))
        self.assertEqual(f.ond_mppt_v_max, Decimal('425.0'))
        self.assertEqual(f.ond_v_max_abs, Decimal('600.0'))
        self.assertEqual(f.ond_i_max_mppt_a, Decimal('26.0'))
        self.assertEqual(f.ond_rendement_euro_pct, Decimal('97.0'))
        self.assertIn('Modèle supposé : Deye SUN-10K-SG02LP1-EU-AM3', p.description)

    def test_pvond_huawei_mono_10_12kw_sont_archives_jamais_supprimes(self):
        """OND-R-HUA-10M/12M : ARTEFACTS (aucun Huawei mono réseau réel à ces
        puissances). Ordre fondateur 2026-08-18 : plus grisés mais ARCHIVÉS —
        donc hors catalogue de composition, et JAMAIS supprimés."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        for sku in ('OND-R-HUA-10M', 'OND-R-HUA-12M'):
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertTrue(p.is_archived, sku)
            self.assertFalse(FicheTechnique.objects.filter(produit=p).exists(), sku)
            # Pas de mention de modèle supposé non plus (rien à confirmer).
            self.assertNotIn('Modèle supposé', p.description)

    def test_pvg4_batteries_seeded_with_sourced_values(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        b5 = Produit.objects.get(company=self.company, sku='BAT-DEY-5')
        f5 = FicheTechnique.objects.get(produit=b5)
        self.assertEqual(f5.type_fiche, 'batterie')
        self.assertEqual(f5.bat_kwh_nominal, Decimal('5.12'))
        self.assertEqual(f5.bat_kwh_usable, Decimal('4.60'))
        self.assertEqual(f5.bat_dod_pct, Decimal('90.0'))
        self.assertEqual(f5.bat_v_nominal, Decimal('51.2'))
        self.assertEqual(f5.bat_max_charge_kw, Decimal('3.84'))
        self.assertIn('Modèle supposé : Dyness DL5.0C', b5.description)
        # L-DECH — décharge SOURCÉE datasheet DL5.0C (20250228-EN) :
        # « Charge 75 A / Discharge 100 A » ⇒ 100 A × 51,2 V = 5,12 kW. La
        # charge et la décharge DIFFÈRENT sur ce pack : c'est la preuve vivante
        # qu'on ne déduit jamais l'une de l'autre.
        self.assertEqual(f5.bat_max_decharge_kw, Decimal('5.12'))
        self.assertNotEqual(f5.bat_max_decharge_kw, f5.bat_max_charge_kw)

        b10 = Produit.objects.get(company=self.company, sku='BAT-DEY-10')
        f10 = FicheTechnique.objects.get(produit=b10)
        self.assertEqual(f10.bat_kwh_nominal, Decimal('10.24'))
        self.assertEqual(f10.bat_kwh_usable, Decimal('9.22'))
        self.assertEqual(f10.bat_max_charge_kw, Decimal('5.12'))
        # Powerbox Pro : un seul champ combiné publié (100 A) ⇒ même valeur
        # dans les deux sens, et la règle générale du fondateur (100 A × ~52 V)
        # est confirmée à l'ampère près.
        self.assertEqual(f10.bat_max_decharge_kw, Decimal('5.12'))

    def test_ldech_port_batterie_des_hybrides_seede_par_datasheet(self):
        """L-DECH — le PORT BATTERIE des cinq hybrides Deye, sourcé colonne par
        colonne du bloc « Battery Input Data » et converti à 51,2 V (la MÊME
        tension que ``bat_v_nominal`` des packs, sans quoi le min(packs, port)
        du moteur comparerait deux conventions).

        Une valeur par MODÈLE, jamais reportée d'un modèle à l'autre : le 15T
        et le 20T partagent leur datasheet mais PAS leur colonne (280 vs
        350 A). Deux de ces chiffres (120 A du 5M, 210 A du 10T) figuraient
        déjà en commentaire « NON seedés faute de champ » — ils ont un champ.
        """
        from apps.stock.models import FicheTechnique
        seed(self.company)
        attendus = {
            'OND-H-DEY-5M': Decimal('6.14'),    # 120 A x 51,2 V
            'OND-H-DEY-10M': Decimal('11.26'),  # 220 A
            'OND-H-DEY-10T': Decimal('10.75'),  # 210 A
            'OND-H-DEY-15T': Decimal('14.34'),  # 280 A
            'OND-H-DEY-20T': Decimal('17.92'),  # 350 A
        }
        for sku, attendu in attendus.items():
            with self.subTest(sku=sku):
                produit = Produit.objects.get(company=self.company, sku=sku)
                fiche = FicheTechnique.objects.get(produit=produit)
                # Charge et décharge portent la MÊME valeur sur ces cinq
                # datasheets — deux lignes distinctes qui coïncident.
                self.assertEqual(fiche.ond_bat_max_charge_kw, attendu)
                self.assertEqual(fiche.ond_bat_max_decharge_kw, attendu)
        # Les onduleurs RÉSEAU n'ont aucun port batterie : rien n'est inventé
        # pour eux, le champ reste NULL et ne bornera donc rien.
        reseau = Produit.objects.filter(
            company=self.company, sku='OND-R-HUA-100T').first()
        if reseau is not None:
            fiche = FicheTechnique.objects.filter(produit=reseau).first()
            if fiche is not None:
                self.assertIsNone(fiche.ond_bat_max_decharge_kw)

    def test_pvg4_idempotent_second_run_never_overwrites(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        fiche = FicheTechnique.objects.get(produit=p)
        seed(self.company)
        self.assertEqual(FicheTechnique.objects.filter(produit=p).count(), 1)
        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_ac_kw, Decimal('10'))
        p.refresh_from_db()
        self.assertEqual(
            p.description.count('Modèle confirmé fondateur'), 1,
            "la mention ne doit jamais être dupliquée sur un second run")

        # PV85 → PVOND 19/08 : par DÉFAUT le seeder COMBLE sans jamais écraser —
        # une valeur posée par le fondateur (même fantaisiste) survit au run.
        # Le ré-alignement datasheet est désormais une porte EXPLICITE
        # (--reappliquer-fiches), testé juste en dessous.
        p20t = Produit.objects.get(company=self.company, sku='OND-H-DEY-20T')
        FicheTechnique.objects.filter(produit=p20t).delete()
        ancienne = FicheTechnique.objects.create(
            company=self.company, produit=p20t, type_fiche='onduleur',
            ond_ac_kw=Decimal('99'), bat_dod_pct=Decimal('77.0'))
        seed(self.company)
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.ond_ac_kw, Decimal('99'),
                         'comble-jamais-écrase : la valeur fondateur survit')
        seed(self.company, reappliquer_fiches=True)
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.ond_ac_kw, Decimal('20'),
                         'porte explicite : la datasheet ré-aligne')
        self.assertEqual(ancienne.bat_dod_pct, Decimal('77.0'))

    def test_veichi_seeded_with_real_buy_and_sell_prices(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        v75 = qs.get(sku='VEI-SI23-7.5-380')
        self.assertEqual(v75.nom, 'VARIATEUR VEICHI SI23 7.5KW 380V')
        self.assertEqual(v75.prix_vente, Decimal('3333.33'))   # 4 000 TTC public
        self.assertEqual(v75.prix_achat, Decimal('2875.00'))   # 3 450 TTC revendeur
        self.assertEqual(str(v75.pompe_kw), '7.50')
        self.assertEqual(v75.tension_v, 380)
        self.assertEqual(v75.marque, 'VEICHI')
        self.assertEqual(v75.categorie.nom, 'Variateurs')
        # L'afficheur n'a pas de kW : il ne peut jamais être pris pour le variateur
        aff = qs.get(sku='VEI-SI22-AFF')
        self.assertIsNone(aff.pompe_kw)
        self.assertEqual(aff.prix_vente, Decimal('350.00'))    # 420 TTC
        self.assertEqual(aff.prix_achat, Decimal('300.00'))    # 360 TTC

    def test_osp_pumps_seeded_with_curves_and_empty_price(self):
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='PMP-OSP-30-8')
        self.assertEqual(p.prix_vente, Decimal('0'))   # à renseigner par le fondateur
        self.assertEqual(p.prix_achat, Decimal('0'))
        self.assertEqual(str(p.pompe_cv), '10.00')
        self.assertEqual(str(p.pompe_kw), '7.50')
        self.assertEqual(p.tension_v, 380)
        self.assertEqual(p.courbe_pompe['debits_m3h'], [0, 12, 24, 30, 36, 39])
        self.assertEqual(p.courbe_pompe['hmt_m'], [91, 85, 70, 60, 43, 34])

    # ── PVG3 — Câbles & protections (prix vides, approuvé fondateur) ────────
    def test_pvg3_cables_protections_seeded_with_empty_prices(self):
        seed(self.company)
        skus = [
            'CAB-H1Z2Z2-4-M', 'CAB-H1Z2Z2-6-M', 'CAB-H1Z2Z2-10-M', 'CAB-H1Z2Z2-16-M',
            'FUS-GPV-1000-15A', 'FUS-GPV-1000-20A', 'PF-1000',
            'PARA-DC-T2-1000', 'PARA-AC-T2', 'SECT-DC-1000-25A',
            'DISJ-AC-C-16-1P', 'DISJ-AC-C-20-1P', 'DISJ-AC-C-25-1P', 'DISJ-AC-C-32-1P',
            'DISJ-AC-C-16-4P', 'DISJ-AC-C-20-4P', 'DISJ-AC-C-25-4P', 'DISJ-AC-C-32-4P',
            'DDR-A-300-40', 'DDR-A-300-63', 'COF-DC-2STR', 'COF-AC',
        ]
        self.assertEqual(len(skus), 22)
        for sku in skus:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.prix_vente, Decimal('0'), sku)   # à renseigner par le fondateur
            self.assertEqual(p.prix_achat, Decimal('0'), sku)
            self.assertGreater(p.quantite_stock, 0, sku)  # stock présent, seul le prix manque
            self.assertTrue(p.description, sku)  # description FR courte saisie
        cable = Produit.objects.get(company=self.company, sku='CAB-H1Z2Z2-6-M')
        self.assertIn('mètre', cable.nom)
        self.assertEqual(cable.categorie.nom, 'Câbles')
        disjoncteur = Produit.objects.get(company=self.company, sku='DISJ-AC-C-32-4P')
        self.assertEqual(disjoncteur.categorie.nom, 'Protection & accessoires')

    def test_pvg3_cables_protections_idempotent_second_run(self):
        seed(self.company)
        first_count = Produit.objects.filter(
            company=self.company, sku='COF-DC-2STR').count()
        seed(self.company)
        self.assertEqual(
            Produit.objects.filter(company=self.company, sku='COF-DC-2STR').count(),
            first_count)
        self.assertEqual(first_count, 1)
        # Un second run ne crée rien de plus et ne touche pas les prix (0).
        p = Produit.objects.get(company=self.company, sku='DISJ-AC-C-16-1P')
        self.assertEqual(p.prix_vente, Decimal('0'))

    def test_pvg3_priceless_products_excluded_like_osp_guard(self):
        """Même garde que les pompes OSP (apps.ventes.services._has_price) :
        un produit à prix_vente=0 n'est jamais auto-chiffré."""
        from apps.ventes.services import _has_price
        seed(self.company)
        osp = Produit.objects.get(company=self.company, sku='PMP-OSP-30-8')
        cable = Produit.objects.get(company=self.company, sku='CAB-H1Z2Z2-6-M')
        disjoncteur = Produit.objects.get(company=self.company, sku='DISJ-AC-C-16-1P')
        self.assertFalse(_has_price(osp))
        self.assertFalse(_has_price(cable))
        self.assertFalse(_has_price(disjoncteur))
        # Contrôle négatif : un produit normalement prisé passe la garde.
        priced = Produit.objects.get(company=self.company, sku='OND-R-HUA-10T')
        self.assertTrue(_has_price(priced))

    # ── DC35/G1 (2026-08-19) — le fondateur ne pose que du câble Nexans : la
    # marque doit être visible sur TOUTE ligne câble solaire du catalogue, pas
    # seulement sur les deux SKU dont le nom la porte déjà (CAB-NEX-DC-6/TER-6).
    def test_toutes_les_lignes_cable_solaire_portent_la_marque_nexans(self):
        seed(self.company)
        skus_cable = [
            'CAB-6MM-M', 'CAB-H1Z2Z2-4-M', 'CAB-H1Z2Z2-6-M',
            'CAB-H1Z2Z2-10-M', 'CAB-H1Z2Z2-16-M',
            'CAB-NEX-DC-6', 'CAB-NEX-TER-6',
        ]
        for sku in skus_cable:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.marque, 'Nexans', sku)
            self.assertTrue(p.description, sku)

    def test_cable_dc_h1z2z2k_cite_la_norme_et_le_conducteur(self):
        """Les câbles DC (H1Z2Z2-K) portent des faits VÉRIFIÉS — jamais un
        câble de terre : NF EN 50618 est une norme de câble PV, pas de mise à
        la terre (aucun numéro inventé, cf. règle fondateur « faits vérifiés
        uniquement »)."""
        seed(self.company)
        for sku in ('CAB-6MM-M', 'CAB-H1Z2Z2-6-M', 'CAB-NEX-DC-6'):
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertIn('H1Z2Z2-K', p.description, sku)
            self.assertIn('NF EN 50618', p.description, sku)

    def test_fiche_nexans_idempotente_et_sans_prix_touche(self):
        seed(self.company)
        avant = Produit.objects.get(company=self.company, sku='CAB-NEX-DC-6')
        self.assertEqual(avant.prix_vente, Decimal('12.00'))  # 14,4 TTC / 1,2
        self.assertEqual(avant.prix_achat, Decimal('0'))
        seed(self.company)
        apres = Produit.objects.get(company=self.company, sku='CAB-NEX-DC-6')
        self.assertEqual(apres.marque, 'Nexans')
        self.assertEqual(apres.prix_vente, avant.prix_vente)
        self.assertEqual(apres.prix_achat, avant.prix_achat)
        self.assertEqual(
            Produit.objects.filter(company=self.company, sku='CAB-NEX-DC-6').count(), 1)

    # ── PVG4 — Onduleur Deye 15 kW basse tension (décision fondateur
    # 2026-08-18, SUN-15K-SG05LP3-EU-SM2) ─────────────────────────────────
    def test_pvlv2_le_15kw_est_le_sg05lp3_basse_tension_avec_ses_prix(self):
        """PVLV2 (fondateur 21/08/2026) — le 15 kW du catalogue est le SKU
        HISTORIQUE OND-H-DEY-15T : SG05LP3 basse tension, prix d'origine,
        fiche complète sur la datasheet 14-20K."""
        from apps.stock.models import FicheTechnique
        from apps.ventes.services import _has_price
        seed(self.company)
        # Le doublon du 18/08 n'existe plus sur une base neuve.
        self.assertFalse(Produit.objects.filter(
            company=self.company, sku='OND-DEY-15K-LV').exists())
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-15T')
        self.assertEqual(p.nom, 'Onduleur hybride Deye 15kW Triphasé')
        self.assertEqual(p.prix_vente, Decimal('30000.00'))   # 36 000 TTC
        self.assertEqual(p.prix_achat, Decimal('25000.00'))   # 30 000 TTC
        self.assertEqual(p.marque, 'Deye')
        self.assertIn('Modèle confirmé fondateur : Deye SUN-15K-SG05LP3-EU-SM2',
                      p.description)
        self.assertTrue(_has_price(p))

        fiche = FicheTechnique.objects.get(produit=p)
        self.assertEqual(fiche.type_fiche, 'onduleur')
        self.assertEqual(fiche.ond_n_mppt, 2)
        self.assertEqual(fiche.ond_mppt_v_min, Decimal('160.0'))
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('650.0'))
        self.assertEqual(fiche.ond_v_max_abs, Decimal('800.0'))
        self.assertEqual(fiche.ond_ac_kw, Decimal('15'))
        self.assertEqual(fiche.ond_phases, 3)
        self.assertEqual(fiche.ond_rendement_euro_pct, Decimal('97.0'))
        # Courant asymétrique 36/20 A sur 2 trackers : valeur retenue = le
        # tracker LE PLUS FAIBLE (20 A) ; Isc maxi 54/30 A → 30 A, même règle.
        self.assertEqual(fiche.ond_i_max_mppt_a, Decimal('20.0'))
        self.assertEqual(fiche.ond_isc_max_mppt_a, Decimal('30.0'))

    # ── PVG4 — Batterie Dyness haute tension, 16 kWh (décision fondateur
    # 2026-08-18) ───────────────────────────────────────────────────────
    def test_pvlv2_batterie_hv_16kwh_est_une_deye_bosb_pro(self):
        """PVLV2 (21/08/2026) — l'identité est CONNUE : facture Solarex
        S26/001708 → Deye BOS-B-Pack16-A3 (BOS-B Pro). SKU historique
        inchangé, prix d'achat réel, fiche sourcée SANS tension nominale
        (51,2 V = tension MODULE, jamais celle que voit l'onduleur)."""
        from apps.stock.models import FicheTechnique
        from apps.ventes.services import _has_price
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='BAT-DYN-HV-16')
        self.assertEqual(p.nom, 'Batterie Deye BOS-B Pro haute tension — 16 kWh')
        self.assertEqual(p.prix_vente, Decimal('40000.00'))   # 48 000 TTC / tranche
        self.assertEqual(p.prix_achat, Decimal('28000.00'))   # 33 600 TTC (facture)
        self.assertEqual(p.tva, Decimal('20.00'))
        self.assertEqual(p.categorie.nom, 'Batteries')
        self.assertEqual(p.marque, 'Deye')
        self.assertEqual(p.unite_stock, 'tranche')
        self.assertIn('rack et control box', p.description.lower())
        self.assertIn('BOS-B-Pack16-A3', p.description)
        self.assertIn('10 ans', p.garantie)
        # Un vrai prix de vente → PAS exclu de l'auto-composition par _has_price
        # (le mot-clé « haute tension » du nom, lui, garde le vivier LV).
        self.assertTrue(_has_price(p))
        fiche = FicheTechnique.objects.get(produit=p)
        self.assertEqual(fiche.bat_kwh_nominal, Decimal('16.08'))
        self.assertEqual(fiche.bat_dod_pct, Decimal('90.0'))
        self.assertEqual(fiche.bat_max_charge_kw, Decimal('9.22'))
        # L-DECH — brochure officielle BOS-B Pro-A3 (2025-09-28) : un SEUL
        # champ combiné « Nominal Charge/Discharge Current » = 180 A, donc la
        # même valeur dans les deux sens (180 × 51,2 V = 9,216 kW). ÉCART
        # ASSUMÉ vs la règle générale du fondateur (100 A) : la datasheet fait
        # foi, et ce module HV de 16 kWh n'est pas un mural de 5/10 kWh.
        self.assertEqual(fiche.bat_max_decharge_kw, Decimal('9.22'))
        self.assertIsNone(fiche.bat_v_nominal)

    def test_pvg4_new_products_idempotent_second_run(self):
        seed(self.company)
        seed(self.company)
        # PVLV2 — le doublon 15K-LV ne renaît sur AUCUN passage.
        self.assertEqual(
            Produit.objects.filter(company=self.company, sku='OND-DEY-15K-LV').count(), 0)
        self.assertEqual(
            Produit.objects.filter(company=self.company, sku='BAT-DYN-HV-16').count(), 1)
        bat = Produit.objects.get(company=self.company, sku='BAT-DYN-HV-16')
        self.assertEqual(bat.prix_vente, Decimal('40000.00'))

    def test_pvg4_batterie_dyness_hv_never_auto_selected_low_voltage(self):
        """Garde fondateur (2026-08-18) : la batterie HAUTE TENSION ne doit
        JAMAIS être choisie par l'auto-composition résidentielle basse
        tension, même si elle devenait la moins chère du catalogue."""
        from apps.ventes.services import (
            _is_battery_basse_tension, _pick_product, composition_residentielle,
            catalogue_de_la_societe)
        seed(self.company)
        hv = Produit.objects.get(company=self.company, sku='BAT-DYN-HV-16')
        self.assertFalse(_is_battery_basse_tension(hv.nom))

        # _pick_product (résynchronisation / from-layout) ne la retourne
        # jamais, même artificiellement rendue la moins chère du catalogue.
        hv.prix_vente = Decimal('1')
        hv.save(update_fields=['prix_vente'])
        picked = _pick_product(self.company, _is_battery_basse_tension)
        self.assertIsNotNone(picked)
        self.assertNotEqual(picked.sku, 'BAT-DYN-HV-16')

        # Le vivier de composition_residentielle ne la retient pas non plus.
        produits = catalogue_de_la_societe(self.company)
        lignes = composition_residentielle(
            produits, kwc=9.94, panel_watt=710, avec_batterie=True)
        skus_batterie = [li.produit.sku for li in lignes
                         if li.produit and 'batterie' in (li.produit.nom or '').lower()]
        self.assertNotIn('BAT-DYN-HV-16', skus_batterie)

    def test_placeholder_coffrets_archived_prices_intact(self):
        # Un ancien coffret placeholder existant est archivé par le seeder
        # (autorisation fondateur) — jamais supprimé, prix jamais modifié.
        old = Produit.objects.create(
            company=self.company, nom='Variateur pompage solaire 5.5 CV Triphasé (coffret complet)',
            sku='VFD-PMP-5.5T', prix_vente=Decimal('5416.67'), quantite_stock=20,
        )
        seed(self.company)
        old.refresh_from_db()
        self.assertTrue(old.is_archived)
        self.assertEqual(old.prix_vente, Decimal('5416.67'))
        # Et le seeder ne les recrée jamais
        self.assertEqual(
            Produit.objects.filter(
                company=self.company, sku__startswith='VFD-PMP').count(), 1)

    def test_fiches_update_is_idempotent_and_price_safe(self):
        seed(self.company)
        before = dict(Produit.objects.filter(company=self.company)
                      .values_list('sku', 'prix_vente'))
        seed(self.company)
        after = dict(Produit.objects.filter(company=self.company)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(before, after)

    def test_idempotent_second_run_creates_nothing(self):
        seed(self.company)
        count_after_first = Produit.objects.filter(company=self.company).count()
        out = seed(self.company)
        self.assertEqual(
            Produit.objects.filter(company=self.company).count(), count_after_first)
        # PVLV2 — les deux doublons « Basse Tension » ne sont plus créés.
        self.assertIn('0 created, 92 already present', out)

    def test_never_overwrites_existing_product(self):
        # Pre-existing product with the same name but a different price
        existing = Produit.objects.create(
            company=self.company, nom='Structures acier', sku='STR-LEGACY',
            prix_vente=Decimal('375.00'), prix_achat=Decimal('280.00'),
            quantite_stock=10,
        )
        out = seed(self.company)
        existing.refresh_from_db()
        # Untouched, no duplicate created under the catalogue SKU
        self.assertEqual(existing.prix_vente, Decimal('375.00'))
        self.assertFalse(
            Produit.objects.filter(company=self.company, sku='STR-ACIER').exists())
        self.assertEqual(
            Produit.objects.filter(
                company=self.company, nom__iexact='Structures acier').count(), 1)
        self.assertIn('Structures acier', out)

    def test_archived_product_frees_its_name_for_the_catalogue(self):
        # Un produit démo ARCHIVÉ ne bloque plus la création de la version
        # catalogue portant le même nom (l'actif, lui, bloque toujours).
        Produit.objects.create(
            company=self.company, nom='Structures acier', sku='STR-LEGACY2',
            prix_vente=Decimal('375.00'), quantite_stock=5, is_archived=True,
        )
        seed(self.company)
        actifs = Produit.objects.filter(
            company=self.company, nom__iexact='Structures acier',
            is_archived=False)
        self.assertEqual(actifs.count(), 1)
        self.assertEqual(actifs.first().sku, 'STR-ACIER')
        self.assertEqual(actifs.first().prix_vente, Decimal('416.67'))  # 500 TTC

    def test_tva_reform_panels_10_others_20_ttc_preserved(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # TOUS les panneaux à 10 %, TTC strictement préservé
        for p in qs.filter(nom__icontains='panneau'):
            self.assertEqual(p.tva, Decimal('10.00'), p.nom)
            ttc = p.prix_vente * Decimal('1.10')
            self.assertEqual(ttc.quantize(Decimal('1')), Decimal('1400'), p.nom)
        # Tout le reste à 20 % (onduleurs, batteries, structures, pompes…)
        for p in qs.exclude(nom__icontains='panneau'):
            self.assertEqual(p.tva, Decimal('20.00'), p.nom)
        # Idempotent : un second passage ne retouche plus les prix
        before = dict(qs.values_list('sku', 'prix_vente'))
        seed(self.company)
        after = dict(Produit.objects.filter(company=self.company)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(before, after)

    def test_tva_reform_converts_existing_panel_preserving_ttc(self):
        # Un panneau créé AVANT la réforme (HT à 20 %) est converti :
        # 1 166,67 HT @20 % (1 400 TTC) → 1 272,73 HT @10 % (1 400 TTC)
        p = Produit.objects.create(
            company=self.company, nom='Panneau Maison 550W', sku='PAN-LEGACY',
            prix_vente=Decimal('1166.67'), prix_achat=Decimal('1000.00'),
            quantite_stock=5, tva=Decimal('20.00'),
        )
        seed(self.company)
        p.refresh_from_db()
        self.assertEqual(p.tva, Decimal('10.00'))
        self.assertEqual(p.prix_vente, Decimal('1272.73'))
        self.assertEqual(p.prix_achat, Decimal('1090.91'))  # 1 200 TTC préservé

    def test_taxonomy_every_product_in_exactly_one_ordered_category(self):
        from apps.stock.models import Categorie
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # chaque produit a une catégorie de la taxonomie (jamais orphelin)
        noms_taxo = {
            'Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides',
            'Batteries', 'Structures & fixation', 'Protection & accessoires',
            'Câbles', 'Pompes', 'Variateurs', 'Services & prestations',
        }
        for p in qs:
            self.assertIsNotNone(p.categorie, p.nom)
            self.assertIn(p.categorie.nom, noms_taxo, p.nom)
        # hybrides et réseau SÉPARÉS, spot-checks de rangement
        by = {p.sku: p.categorie.nom for p in qs}
        self.assertEqual(by['OND-R-HUA-10T'], 'Onduleurs réseau')
        self.assertEqual(by['OND-H-DEY-5M'], 'Onduleurs hybrides')
        self.assertEqual(by['PAN-CS-710'], 'Panneaux photovoltaïques')
        self.assertEqual(by['VEI-SI23-7.5-380'], 'Variateurs')
        self.assertEqual(by['VEI-SI22-AFF'], 'Variateurs')
        self.assertEqual(by['PMP-OSP-30-8'], 'Pompes')
        self.assertEqual(by['STR-ACIER'], 'Structures & fixation')
        self.assertEqual(by['SOC-BET'], 'Structures & fixation')
        self.assertEqual(by['CAB-6MM-M'], 'Câbles')
        self.assertEqual(by['SMART-MET'], 'Protection & accessoires')
        self.assertEqual(by['INST-CAT'], 'Services & prestations')
        self.assertEqual(by['SUIVI-2A'], 'Services & prestations')
        # ordre délibéré : panneaux d'abord, services en dernier
        cats = list(Categorie.objects.filter(
            company=self.company, nom__in=noms_taxo).order_by('ordre'))
        self.assertEqual(cats[0].nom, 'Panneaux photovoltaïques')
        self.assertEqual(cats[-1].nom, 'Services & prestations')
        # un produit du fondateur hors seed est aussi rangé (re-catégorisation)
        perso = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Growatt 6kW',
            sku='OND-H-GRW-6', prix_vente=Decimal('15000'), quantite_stock=1)
        seed(self.company)
        perso.refresh_from_db()
        self.assertEqual(perso.categorie.nom, 'Onduleurs hybrides')

    def test_stock_read_only_role_writes_rejected(self):
        """Rôle fin « Commerciale » (stock_voir uniquement) : lecture OK,
        toute écriture Stock rejetée côté serveur ; un responsable hérité
        (sans rôle fin) garde l'écriture — rien ne change pour lui."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model
        from apps.roles.models import Role

        User = get_user_model()
        role = Role.objects.create(
            company=self.company, nom='Commerciale', permissions=[
                'stock_voir', 'crm_voir', 'crm_creer', 'crm_modifier',
                'ventes_voir', 'ventes_creer', 'ventes_modifier',
                'ventes_valider', 'ventes_pdf', 'reporting_voir',
                'parametres_voir', 'users_voir',
            ])
        commerciale = User.objects.create_user(
            username='test_commerciale', password='x',
            company=self.company, role=role)
        legacy = User.objects.create_user(
            username='test_resp_legacy', password='x',
            company=self.company, role_legacy='responsable')
        seed(self.company)
        produit = Produit.objects.filter(company=self.company).first()

        http = APIClient()
        http.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commerciale)}')
        # Lecture : autorisée
        self.assertEqual(http.get('/api/django/stock/produits/').status_code, 200)
        # Écritures : toutes rejetées
        r = http.patch(f'/api/django/stock/produits/{produit.id}/',
                       {'prix_vente': '1.00'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = http.post('/api/django/stock/produits/',
                      {'nom': 'X', 'prix_vente': '1'}, format='json')
        self.assertEqual(r.status_code, 403)
        r = http.post('/api/django/stock/mouvements/',
                      {'produit': produit.id, 'type_mouvement': 'entree',
                       'quantite': 1}, format='json')
        self.assertEqual(r.status_code, 403)
        produit.refresh_from_db()
        self.assertNotEqual(produit.prix_vente, 0)  # rien n'a bougé

        # Responsable hérité : l'écriture passe toujours
        http2 = APIClient()
        http2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(legacy)}')
        r = http2.patch(f'/api/django/stock/produits/{produit.id}/',
                        {'seuil_alerte': 9}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_scoped_to_target_company_only(self):
        other = make_company(slug='test-cat-other')
        seed(self.company)
        self.assertEqual(Produit.objects.filter(company=other).count(), 0)


# ── Correction de marque « Deyness » → « Dyness » (fondateur, 2026-08-18) ─────
class TestOrthographeDyness(TestCase):
    """La vraie marque de batteries est Dyness (dyness.com).

    Deux garanties, indissociables :
      1. le SEEDER pose désormais la bonne orthographe sur une base neuve ;
      2. la MIGRATION de données corrige une base DÉJÀ seedée — le seeder étant
         strictement additif, lui seul ne renommerait jamais l'existant.
    Les SKU ``BAT-DEY-*`` ne bougent pas : ce sont des codes catalogue, pas la
    marque, et tout l'appariement (fiches techniques, simulateur de batterie du
    site) s'y accroche.
    """
    # Le module de migration se charge par son chemin : son nom commence par un
    # chiffre, donc `import` ne peut pas le nommer.
    MIGRATION = 'apps.stock.migrations.0121_dyness_orthographe_marque'

    def setUp(self):
        self.company = make_company(slug='test-cat-dyness')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def test_le_seeder_pose_la_bonne_orthographe(self):
        seed(self.company)
        b5 = Produit.objects.get(company=self.company, sku='BAT-DEY-5')
        b10 = Produit.objects.get(company=self.company, sku='BAT-DEY-10')
        self.assertEqual(b5.nom, 'Batterie Dyness 5 kWh')
        self.assertEqual(b10.nom, 'Batterie Dyness 10 kWh')
        self.assertEqual(b5.marque, 'Dyness')
        self.assertEqual(b10.marque, 'Dyness')
        for produit in Produit.objects.filter(company=self.company):
            self.assertNotIn('Deyness', produit.nom)
            self.assertNotIn('Deyness', produit.marque or '')

    def test_un_reseed_ne_duplique_pas_une_batterie_a_lancien_nom(self):
        """L'appariement du seeder se fait par SKU AVANT le nom : une base
        encore à l'ancienne orthographe (migration pas encore passée) est
        retrouvée et SAUTÉE, jamais re-créée. C'est ce qui rend l'ordre
        migration / re-seed indifférent."""
        seed(self.company)
        total = Produit.objects.filter(company=self.company).count()
        Produit.objects.filter(company=self.company, sku='BAT-DEY-5').update(
            nom='Batterie Deyness 5 kWh', marque='Deyness')
        seed(self.company)
        self.assertEqual(
            Produit.objects.filter(company=self.company).count(), total,
            "le re-seed a re-créé un produit au lieu de retrouver son SKU")
        self.assertEqual(
            Produit.objects.filter(company=self.company,
                                   sku='BAT-DEY-5').count(), 1)

    def test_la_migration_renomme_le_catalogue_existant(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        Produit.objects.filter(company=self.company, sku='BAT-DEY-5').update(
            nom='Batterie Deyness 5 kWh', marque='Deyness')
        Produit.objects.filter(company=self.company, sku='BAT-DEY-10').update(
            nom='Batterie Deyness 10 kWh', marque='deyness')

        migration.corriger_orthographe(registre, None)

        b5 = Produit.objects.get(company=self.company, sku='BAT-DEY-5')
        b10 = Produit.objects.get(company=self.company, sku='BAT-DEY-10')
        self.assertEqual(b5.nom, 'Batterie Dyness 5 kWh')
        self.assertEqual(b5.marque, 'Dyness')
        self.assertEqual(b10.nom, 'Batterie Dyness 10 kWh')
        # La casse d'origine est respectée (minuscule → minuscule).
        self.assertEqual(b10.marque, 'dyness')
        # Ni SKU, ni prix, ni quantités ne bougent.
        self.assertEqual(b5.sku, 'BAT-DEY-5')
        self.assertEqual(b5.prix_vente, Decimal('14166.67'))   # 17 000 TTC @ 20 %
        self.assertEqual(b10.prix_vente, Decimal('25000.00'))  # 30 000 TTC @ 20 %

    def test_la_migration_est_reversible(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        migration.retablir_orthographe(registre, None)
        b5 = Produit.objects.get(company=self.company, sku='BAT-DEY-5')
        self.assertEqual(b5.nom, 'Batterie Deyness 5 kWh')
        self.assertEqual(b5.marque, 'Deyness')

        migration.corriger_orthographe(registre, None)
        b5.refresh_from_db()
        self.assertEqual(b5.nom, 'Batterie Dyness 5 kWh')
        self.assertEqual(b5.marque, 'Dyness')

    def test_la_migration_est_idempotente(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        migration.corriger_orthographe(registre, None)
        migration.corriger_orthographe(registre, None)
        self.assertEqual(
            Produit.objects.get(company=self.company, sku='BAT-DEY-5').nom,
            'Batterie Dyness 5 kWh')


# ── Le câble solaire porte Nexans dans le NOM, pas seulement la fiche
#    (fondateur, 2026-08-20 — même patron que TestOrthographeDyness) ─────────
class TestCableNexansDansLeNom(TestCase):
    """Constat fondateur : la ligne de devis affichait « Câble solaire 6mm²
    (au mètre) » — aucune mention Nexans dans la DÉSIGNATION elle-même, alors
    que ``FICHES[...]['marque']`` valait déjà 'Nexans' depuis a002d459.

    Deux garanties, indissociables (même structure que Dyness) :
      1. le SEEDER pose désormais « Nexans » dans le nom sur une base neuve ;
      2. la MIGRATION 0123 renomme une base DÉJÀ seedée — le seeder étant
         strictement additif, lui seul ne renommerait jamais l'existant.
    Les SKU ne bougent pas ; CAB-NEX-DC-6/TER-6 (déjà « Nexans » au nom
    depuis le 18/08) ne sont pas concernés par cette migration.
    """
    MIGRATION = 'apps.stock.migrations.0123_cable_nexans_dans_le_nom'

    SKUS_RENOMMES = {
        # SANS espace avant « mm² » : DÉLIBÉRÉ, voir le commentaire DC35/G3
        # dans seed_catalogue.py — 'Câble solaire Nexans 6 mm² (au mètre)'
        # (AVEC espace) est déjà le nom EXACT de CAB-NEX-DC-6, et le garde-fou
        # anti-doublon du seeder (nom__iexact) saute la création d'un second
        # produit actif portant ce nom.
        'CAB-6MM-M': 'Câble solaire Nexans 6mm² (au mètre)',
        'CAB-H1Z2Z2-4-M': 'Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre)',
        'CAB-H1Z2Z2-6-M': 'Câble solaire Nexans H1Z2Z2-K 6 mm² (au mètre)',
        'CAB-H1Z2Z2-10-M': 'Câble solaire Nexans H1Z2Z2-K 10 mm² (au mètre)',
        'CAB-H1Z2Z2-16-M': 'Câble solaire Nexans H1Z2Z2-K 16 mm² (au mètre)',
    }

    def setUp(self):
        self.company = make_company(slug='test-cat-cable-nexans')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def test_le_seeder_pose_nexans_dans_le_nom(self):
        seed(self.company)
        for sku, nom_attendu in self.SKUS_RENOMMES.items():
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.nom, nom_attendu, sku)
            self.assertIn('Nexans', p.nom, sku)
            # La fiche (marque) reste posée, sans changer.
            self.assertEqual(p.marque, 'Nexans', sku)

    def test_un_reseed_ne_duplique_pas_un_cable_a_lancien_nom(self):
        """Comme Dyness : l'appariement du seeder se fait par SKU AVANT le
        nom, donc une base encore à l'ancien libellé (migration pas encore
        passée) est retrouvée et SAUTÉE, jamais re-créée."""
        seed(self.company)
        total = Produit.objects.filter(company=self.company).count()
        Produit.objects.filter(company=self.company, sku='CAB-6MM-M').update(
            nom='Câble solaire 6mm² (au mètre)')
        seed(self.company)
        self.assertEqual(
            Produit.objects.filter(company=self.company).count(), total,
            "le re-seed a re-créé un produit au lieu de retrouver son SKU")
        self.assertEqual(
            Produit.objects.filter(company=self.company,
                                   sku='CAB-6MM-M').count(), 1)

    def test_la_migration_renomme_le_catalogue_existant(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        Produit.objects.filter(company=self.company, sku='CAB-6MM-M').update(
            nom='Câble solaire 6mm² (au mètre)')
        Produit.objects.filter(
            company=self.company, sku='CAB-H1Z2Z2-4-M').update(
            nom='Câble solaire H1Z2Z2-K 4 mm² (au mètre)')

        migration.marquer_nexans(registre, None)

        c6 = Produit.objects.get(company=self.company, sku='CAB-6MM-M')
        c4 = Produit.objects.get(company=self.company, sku='CAB-H1Z2Z2-4-M')
        self.assertEqual(c6.nom, 'Câble solaire Nexans 6mm² (au mètre)')
        self.assertEqual(c4.nom,
                         'Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre)')
        # Ni SKU, ni prix, ni quantités ne bougent.
        self.assertEqual(c6.sku, 'CAB-6MM-M')
        self.assertEqual(c6.prix_vente, Decimal('10.83'))   # 13 TTC / 1,2
        self.assertEqual(c6.prix_achat, Decimal('0'))

    def test_la_migration_ne_touche_pas_un_nom_deja_personnalise(self):
        """Une ligne dont le nom ne correspond plus EXACTEMENT à l'ancien
        libellé (déjà renommée à la main par le fondateur) n'est pas
        écrasée : l'appariement est par SKU + ancien nom exact."""
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        Produit.objects.filter(company=self.company, sku='CAB-6MM-M').update(
            nom='Câble solaire spécial toiture (au mètre)')

        migration.marquer_nexans(registre, None)

        p = Produit.objects.get(company=self.company, sku='CAB-6MM-M')
        self.assertEqual(p.nom, 'Câble solaire spécial toiture (au mètre)')

    def test_la_migration_est_reversible(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        Produit.objects.filter(company=self.company, sku='CAB-6MM-M').update(
            nom='Câble solaire 6mm² (au mètre)')

        migration.marquer_nexans(registre, None)
        p = Produit.objects.get(company=self.company, sku='CAB-6MM-M')
        self.assertEqual(p.nom, 'Câble solaire Nexans 6mm² (au mètre)')

        migration.demarquer_nexans(registre, None)
        p.refresh_from_db()
        self.assertEqual(p.nom, 'Câble solaire 6mm² (au mètre)')

        migration.marquer_nexans(registre, None)
        p.refresh_from_db()
        self.assertEqual(p.nom, 'Câble solaire Nexans 6mm² (au mètre)')

    def test_la_migration_est_idempotente(self):
        from django.apps import apps as registre
        migration = self._migration()
        seed(self.company)
        migration.marquer_nexans(registre, None)
        migration.marquer_nexans(registre, None)
        self.assertEqual(
            Produit.objects.get(company=self.company, sku='CAB-6MM-M').nom,
            'Câble solaire Nexans 6mm² (au mètre)')

    def test_classification_categorie_et_h1z2z2k_inchangees(self):
        """GARDE-FOU : la classification par mot-clé (« cable » substring,
        classify_categorie) et les faits H1Z2Z2-K/NF EN 50618 continuent de
        matcher malgré le mot « Nexans » inséré dans le nom."""
        seed(self.company)
        for sku in self.SKUS_RENOMMES:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.categorie.nom, 'Câbles', sku)
        c4 = Produit.objects.get(company=self.company, sku='CAB-H1Z2Z2-4-M')
        self.assertIn('H1Z2Z2-K', c4.description)
        self.assertIn('NF EN 50618', c4.description)

    def test_aucun_nom_de_cable_nexans_ne_collisionne_entre_sections_du_catalogue(self):
        """RÉGRESSION (CI run 32320136461, PR #542) : le garde-fou anti-doublon
        du seeder (``nom__iexact`` sur produits actifs) SAUTE la création de
        tout produit dont le nom égale — insensible à la casse — un produit
        DÉJÀ créé par une AUTRE section du catalogue (ex. CAB-6MM-M du
        POMPAGE arrive APRÈS CAB-NEX-DC-6 de CATALOGUE). Un renommage qui
        rend deux noms byte-identiques fait donc SAUTER silencieusement la
        création du second, sans qu'aucune exception ne le signale au moment
        du seed — seul un ``Produit.objects.get(sku=...)`` ultérieur échoue.
        Ce test verrouille que les 7 SKU câble Nexans sont TOUS créés, avec
        7 noms mutuellement DISTINCTS."""
        seed(self.company)
        skus_cable_nexans = list(self.SKUS_RENOMMES) + ['CAB-NEX-DC-6', 'CAB-NEX-TER-6']
        noms = []
        for sku in skus_cable_nexans:
            p = Produit.objects.get(company=self.company, sku=sku)
            noms.append(p.nom)
        self.assertEqual(
            len(noms), len(set(noms)),
            f"noms de câble Nexans en collision : {noms}")


# ── O1 (2026-08-20) — CORRECTION des garanties structurées Deye/génériques ──
class TestCorrectionGarantiesDeyeGeneriques(TestCase):
    """La migration 0012 (classification par mot-clé) posait deux valeurs
    fausses en ``garantie_mois`` : 60 pour les onduleurs Deye (au lieu de
    120 — la garantie constructeur officielle Deye est de 10 ans, comme
    Huawei) et 120 pour trois batteries GÉNÉRIQUES non sourcées (au lieu de
    vide). La migration 0124 corrige les deux, ciblée par SKU, ET vide le
    texte libre ``garantie`` de 38 SKU dont ``seed_catalogue.py`` a retiré la
    clé (le seeder additif ne l'aurait jamais désécrit tout seul sur une base
    déjà seedée)."""

    MIGRATION = 'apps.stock.migrations.0124_correction_garanties_deye_generiques'

    # PVLV2 (21/08/2026) — les SKU doublons OND-DEY-15K-LV/20K-LV ne sont
    # plus seedés (archivés sur bases existantes) : la migration 0124 les
    # cible encore par ``filter`` (sans erreur sur une base qui ne les a
    # pas), mais ce test de base NEUVE ne peut plus les charger.
    ONDULEURS_DEYE = (
        'OND-H-DEY-5M', 'OND-H-DEY-10M', 'OND-H-DEY-10T',
        'OND-H-DEY-15T', 'OND-H-DEY-20T',
    )
    BATTERIES_NON_SOURCEES = ('BAT-DYN-HV-16', 'BAT-LIT-5', 'BAT-GEL-22')
    TEXTE_GENERIQUE_RETIRE = (
        'PMP-IMM-1.5M', 'VEI-SI22-AFF', 'VEI-SI23-30-380',
        'PMP-OSP-30-8', 'PMP-OSP-30-35', 'BAT-LIT-5', 'BAT-GEL-22',
    )

    def setUp(self):
        self.company = make_company(slug='test-cat-garanties-deye')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def test_les_onduleurs_deye_passent_a_120_mois(self):
        from django.apps import apps as registre
        seed(self.company)
        self._migration().corriger_garanties(registre, None)
        for sku in self.ONDULEURS_DEYE:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.garantie_mois, 120, sku)

    def test_les_batteries_generiques_non_sourcees_passent_a_vide(self):
        from django.apps import apps as registre
        seed(self.company)
        self._migration().corriger_garanties(registre, None)
        for sku in self.BATTERIES_NON_SOURCEES:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertIsNone(p.garantie_mois, sku)

    def test_le_texte_garantie_generique_non_source_est_vide(self):
        """Simule une base seedée AVANT le retrait de la clé ``garantie`` côté
        seeder (donc encore porteuse du texte « Garantie constructeur 2 ans »
        ou équivalent, comme une base de production non encore migrée) : la
        migration efface le texte libre — le seeder additif ne l'aurait
        jamais fait tout seul (il ne pose que les clés PRÉSENTES dans FICHES)."""
        from django.apps import apps as registre
        seed(self.company)
        Produit.objects.filter(
            company=self.company, sku__in=self.TEXTE_GENERIQUE_RETIRE[:-2],
        ).update(garantie='Garantie constructeur 2 ans')
        Produit.objects.filter(company=self.company, sku='BAT-LIT-5').update(
            garantie='Garantie 5 ans · ≥ 6 000 cycles (80 % DoD)')
        Produit.objects.filter(company=self.company, sku='BAT-GEL-22').update(
            garantie='Garantie 2 ans')

        self._migration().corriger_garanties(registre, None)

        for sku in self.TEXTE_GENERIQUE_RETIRE:
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.garantie, '', sku)

    def test_la_batterie_dyness_basse_tension_reste_a_120_mois(self):
        """BAT-DEY-5/10 (la batterie de la fiche web `batterie-dyness`) n'est
        PAS concernée par la correction : 120 mois y est la valeur correcte
        (harmonisée avec warranty.ts côté web), et 0124 doit la LAISSER
        intacte — c'est cela que ce test garantit.

        La prémisse a été corrigée : les 120 mois viennent de la règle de
        données de la migration 0012 (« Batteries / stockage » → 120), qui
        s'est appliquée aux produits EXISTANTS à son passage.
        ``seed_catalogue`` ne pose PAS ``garantie_mois`` (aucune occurrence
        dans le seeder) : sur une base de test fraîche, les produits sont
        créés APRÈS 0012 et sortent donc à NULL. On reproduit donc ici l'état
        d'une base réelle — 120 déjà en place — avant d'exécuter 0124, sans
        quoi le test vérifiait un préalable que rien ne produit.
        """
        from django.apps import apps as registre
        seed(self.company)
        # État d'une base réelle après 0012 (cf. docstring).
        Produit.objects.filter(
            company=self.company, sku__in=('BAT-DEY-5', 'BAT-DEY-10'),
        ).update(garantie_mois=120)

        self._migration().corriger_garanties(registre, None)

        for sku in ('BAT-DEY-5', 'BAT-DEY-10'):
            p = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(p.garantie_mois, 120, sku)

    def test_la_migration_est_idempotente(self):
        from django.apps import apps as registre
        seed(self.company)
        migration = self._migration()
        migration.corriger_garanties(registre, None)
        migration.corriger_garanties(registre, None)
        p = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        self.assertEqual(p.garantie_mois, 120)

    def test_la_migration_est_reversible(self):
        from django.apps import apps as registre
        seed(self.company)
        migration = self._migration()

        migration.corriger_garanties(registre, None)
        onduleur = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        batterie = Produit.objects.get(company=self.company, sku='BAT-GEL-22')
        veichi = Produit.objects.get(company=self.company, sku='VEI-SI22-AFF')
        self.assertEqual(onduleur.garantie_mois, 120)
        self.assertIsNone(batterie.garantie_mois)
        self.assertEqual(veichi.garantie, '')

        migration.retablir_garanties_0012(registre, None)
        onduleur.refresh_from_db()
        batterie.refresh_from_db()
        veichi.refresh_from_db()
        self.assertEqual(onduleur.garantie_mois, 60)
        self.assertEqual(batterie.garantie_mois, 120)
        self.assertEqual(veichi.garantie, 'Garantie constructeur 2 ans')

        migration.corriger_garanties(registre, None)
        veichi.refresh_from_db()
        self.assertEqual(veichi.garantie, '')

        migration.corriger_garanties(registre, None)
        onduleur.refresh_from_db()
        batterie.refresh_from_db()
        self.assertEqual(onduleur.garantie_mois, 120)
        self.assertIsNone(batterie.garantie_mois)


# ── PVOND — VERROU DE COMPLÉTUDE sur le catalogue onduleur ──────────────────
class TestContratOnduleurSeede(TestCase):
    """Ajouter un onduleur demain doit être de la pure SAISIE — donc le seeder
    ne doit jamais laisser passer, EN SILENCE, une référence à qui il manque
    une variable du contrat.

    La règle testée ici est « tout manque est DÉCLARÉ » : un onduleur
    incomplet doit figurer dans ``ONDULEURS_CONTRAT_INCOMPLET`` avec son motif ;
    un onduleur complet ne doit PAS y figurer. Les deux sens comptent — sans le
    second, la table deviendrait un cimetière de motifs périmés.

    ORDRE FONDATEUR (2026-08-18, « ne laisse rien griser ») : la table est
    VIDE — plus AUCUNE référence du catalogue n'est grisée. Le mécanisme, lui,
    reste armé pour les références futures : c'est ce que prouve
    ``test_le_verrou_refuse_encore_un_incomplet_non_declare`` sur une fixture
    SYNTHÉTIQUE (jamais une référence du catalogue).
    """

    def setUp(self):
        self.company = make_company(slug='test-cat-pvond')

    def _onduleurs(self):
        """Onduleurs ACTIFS du catalogue — un produit archivé (les artefacts
        Huawei mono 10/12 kW) est hors catalogue de composition, donc hors
        contrat."""
        from apps.stock.selectors import est_onduleur
        return [p for p in Produit.objects.filter(
                    company=self.company, is_archived=False)
                if est_onduleur(p)]

    def test_tout_onduleur_incomplet_est_declare_avec_son_motif(self):
        from apps.stock.management.commands.seed_catalogue import (
            ONDULEURS_CONTRAT_INCOMPLET,
        )
        from apps.stock.selectors import onduleur_specs_manquantes

        seed(self.company)
        onduleurs = self._onduleurs()
        self.assertTrue(onduleurs, 'aucun onduleur seedé — test sans objet')

        for produit in onduleurs:
            manquantes = onduleur_specs_manquantes(produit)
            declare = produit.sku in ONDULEURS_CONTRAT_INCOMPLET
            if manquantes:
                self.assertTrue(
                    declare,
                    f'{produit.sku} : contrat onduleur incomplet '
                    f'({", ".join(manquantes)}) et NON déclaré dans '
                    'ONDULEURS_CONTRAT_INCOMPLET — un onduleur qu\'on ne sait '
                    'pas dimensionner ne doit jamais entrer au catalogue sans '
                    'que le motif soit écrit.')
                self.assertTrue(
                    ONDULEURS_CONTRAT_INCOMPLET[produit.sku].strip(),
                    f'{produit.sku} : motif vide')
            else:
                self.assertFalse(
                    declare,
                    f'{produit.sku} : déclaré incomplet alors que son contrat '
                    'est complet — retirez-le de ONDULEURS_CONTRAT_INCOMPLET.')

    def test_aucune_reference_du_catalogue_n_est_grisee(self):
        """Ordre fondateur 2026-08-18 : plus rien ne grise. Les neuf manques
        sont tranchés (valeur + source + date en commentaire du seeder), les
        deux artefacts Huawei mono 10/12 kW sont ARCHIVÉS."""
        from apps.stock.management.commands.seed_catalogue import (
            ONDULEURS_CONTRAT_INCOMPLET,
        )
        from apps.stock.selectors import onduleur_specs_manquantes

        self.assertEqual(ONDULEURS_CONTRAT_INCOMPLET, {})
        seed(self.company)
        grises = {p.sku: onduleur_specs_manquantes(p)
                  for p in self._onduleurs() if onduleur_specs_manquantes(p)}
        self.assertEqual(grises, {}, f'onduleurs encore grisés : {grises}')

    def test_le_verrou_refuse_encore_un_incomplet_non_declare(self):
        """Le MÉCANISME survit à la table vide : une référence FUTURE à qui il
        manque une variable est toujours détectée et nommée en français.
        Fixture SYNTHÉTIQUE — jamais une référence du catalogue."""
        from apps.stock.management.commands.seed_catalogue import (
            ONDULEURS_CONTRAT_INCOMPLET,
        )
        from apps.stock.models import FicheTechnique
        from apps.stock.selectors import onduleur_specs_manquantes

        produit = Produit.objects.create(
            company=self.company, nom='Onduleur hybride SYNTHÉTIQUE 8kW',
            sku='OND-TEST-SYNTH', prix_achat=Decimal('1'),
            prix_vente=Decimal('1'), quantite_stock=1,
            description='Plage batterie : 40-60 V',
            garantie='Garantie constructeur 10 ans')
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='onduleur',
            ond_n_mppt=2, ond_mppt_v_min=Decimal('200.0'),
            ond_mppt_v_max=Decimal('650.0'), ond_v_max_abs=Decimal('800.0'),
            ond_ac_kw=Decimal('8'), ond_phases=1,
            ond_rendement_euro_pct=Decimal('97.0'))
        produit.refresh_from_db()

        self.assertEqual(onduleur_specs_manquantes(produit),
                         ['courant maxi par MPPT (A)'])
        self.assertNotIn(produit.sku, ONDULEURS_CONTRAT_INCOMPLET)

    def test_chaque_onduleur_declare_sa_plage_batterie(self):
        """La plage batterie est la variable qui décide de l'appairage : elle
        est déclarée pour TOUS les onduleurs, y compris « aucune » pour un
        onduleur réseau (une valeur pleine, pas un trou)."""
        from apps.stock.selectors import plage_batterie_onduleur

        seed(self.company)
        for produit in self._onduleurs():
            self.assertIsNotNone(
                plage_batterie_onduleur(produit),
                f'{produit.sku} : aucune ligne « Plage batterie : … » sur sa '
                'fiche produit')

    def test_la_plage_batterie_des_deye_basse_tension_est_48V(self):
        # PVLV2 — TOUT le parc hybride triphasé est SG05LP3 basse tension.
        seed(self.company)
        from apps.stock.selectors import plage_batterie_onduleur
        for sku in ('OND-H-DEY-10T', 'OND-H-DEY-15T', 'OND-H-DEY-20T'):
            produit = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(plage_batterie_onduleur(produit), (40.0, 60.0))

    def test_pvlv2_aucun_onduleur_haute_tension_au_catalogue(self):
        """PVLV2 (fondateur 21/08/2026) — « i dont even have them in high
        voltage » : plus AUCUN onduleur du catalogue ne déclare une plage
        batterie haute tension (l'ancien 160-700 V venait de la fausse
        identification SG01HP3)."""
        seed(self.company)
        from apps.stock.selectors import plage_batterie_onduleur
        for produit in self._onduleurs():
            plage = plage_batterie_onduleur(produit)
            if plage is None:
                continue
            self.assertNotEqual(plage, (160.0, 700.0), produit.sku)

    def test_les_huawei_reseau_declarent_aucune_batterie(self):
        seed(self.company)
        from apps.stock.selectors import plage_batterie_onduleur
        for sku in ('OND-R-HUA-10T', 'OND-R-HUA-100T'):
            produit = Produit.objects.get(company=self.company, sku=sku)
            self.assertEqual(plage_batterie_onduleur(produit), (0.0, 0.0))

    def test_le_reseed_ne_duplique_pas_la_ligne_de_plage_batterie(self):
        seed(self.company)
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        self.assertEqual(
            (produit.description or '').count('Plage batterie :'), 1)

    # PVOND-H (fondateur 19/08/2026) — les dix onduleurs Deye/Huawei du
    # catalogue portent désormais LE CHAMP DÉDIÉ, pas seulement la ligne de
    # description historique.
    def test_le_seeder_pose_le_champ_dedie_pas_seulement_la_description(self):
        from apps.stock.models import FicheTechnique
        seed(self.company)
        hybride = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        f_hybride = FicheTechnique.objects.get(produit=hybride)
        self.assertEqual(f_hybride.ond_bat_v_min, Decimal('40.0'))
        self.assertEqual(f_hybride.ond_bat_v_max, Decimal('60.0'))
        self.assertFalse(f_hybride.ond_bat_aucune)
        reseau = Produit.objects.get(company=self.company, sku='OND-R-HUA-10T')
        f_reseau = FicheTechnique.objects.get(produit=reseau)
        self.assertTrue(f_reseau.ond_bat_aucune)
        self.assertIsNone(f_reseau.ond_bat_v_min)
        self.assertIsNone(f_reseau.ond_bat_v_max)

    def test_le_champ_dedie_prime_sur_une_ligne_de_description_divergente(self):
        """PVOND-H — ordre de lecture : si le champ DÉDIÉ est renseigné, il
        fait foi même quand une vieille ligne de description dit autre
        chose (une base migrée sans --reappliquer-fiches ne doit jamais
        rendre une valeur incohérente entre les deux mécanismes)."""
        from apps.stock.models import FicheTechnique
        from apps.stock.selectors import plage_batterie_onduleur
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        fiche = FicheTechnique.objects.get(produit=produit)
        fiche.ond_bat_v_min = Decimal('45.0')
        fiche.ond_bat_v_max = Decimal('55.0')
        fiche.save()
        # La description garde encore l'ancienne ligne « 40-60 V » — le champ
        # dédié doit gagner.
        self.assertIn('Plage batterie : 40-60 V', produit.description)
        self.assertEqual(plage_batterie_onduleur(produit), (45.0, 55.0))


class TestPvfchDescriptionSansSpecs(TestCase):
    """PVFCH (fondateur 20/08/2026) — la DESCRIPTION raconte, elle ne chiffre pas.

    Les descriptions seedées portaient des specs chiffrées qui vivent DÉJÀ dans
    un champ structuré de ``FicheTechnique`` (« 710 Wc » = ``pmax_wc``,
    « 51,2 V » = ``bat_v_nominal``, « rendement euro 97,0 % » =
    ``ond_rendement_euro_pct``, « plage 40-60 V » = ``ond_bat_v_min/max``,
    « ≈ −0,29 %/°C » = ``temp_coeff_pmax_pct_c``).

    Deux copies d'un même nombre finissent toujours par diverger — et c'est la
    copie en PROSE, celle que personne ne recalcule, qui part sur la fiche
    produit du PDF client. La preuve était déjà là : la prose annonçait
    « rendement max ≈ 98,6 % » à l'identique pour les DIX Huawei, quand leurs
    champs disent 97,8 à 98,4 % selon le palier.

    Le test garde les DEUX SENS : un nombre porté par un champ ne doit plus
    être en prose, ET un nombre qu'aucun champ ne porte doit y RESTER (le
    supprimer serait l'erreur symétrique — une perte de donnée sourcée).
    """

    #: ``champ de fiche`` → comment ce nombre s'écrirait en prose française.
    #: Le rendu suit les conventions du dépôt (virgule décimale, unité collée
    #: au nombre par une espace) ; on teste les deux précisions usuelles pour
    #: qu'un « 710 » comme un « 710,00 » soit attrapé.
    UNITES = {
        'pmax_wc': 'Wc',
        'bat_v_nominal': 'V',
        'bat_kwh_nominal': 'kWh',
        'ond_rendement_euro_pct': '%',
        'ond_v_max_abs': 'V',
        'ond_mppt_v_min': 'V',
        'ond_mppt_v_max': 'V',
    }

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='pvfch-desc', defaults={'nom': 'PVFCH'})

    @staticmethod
    def _ecritures_francaises(valeur):
        """Les façons plausibles d'écrire ce nombre dans une phrase FR."""
        brut = Decimal(valeur)
        formes = set()
        for gabarit in ('%g', '%.1f', '%.2f'):
            texte = (gabarit % brut).replace('.', ',')
            formes.add(texte)
            if texte.endswith(',0'):
                formes.add(texte[:-2])
        return formes

    def test_aucune_spec_portee_par_un_champ_ne_reste_en_prose(self):
        from apps.stock.management.commands.seed_catalogue import (
            FICHES, FICHES_TECHNIQUES)

        fautes = []
        for sku, fiche in FICHES_TECHNIQUES.items():
            description = (FICHES.get(sku) or {}).get('description') or ''
            if not description:
                continue
            for champ, unite in self.UNITES.items():
                valeur = fiche.get(champ)
                if valeur is None:
                    continue
                for forme in self._ecritures_francaises(valeur):
                    aiguille = '%s %s' % (forme, unite)
                    if aiguille in description:
                        fautes.append(
                            '%s : « %s » est déjà porté par %s'
                            % (sku, aiguille, champ))
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def test_les_valeurs_retirees_vivent_bien_dans_un_champ(self):
        """Aucune PERTE : chaque nombre sorti de la prose est encore lisible."""
        from apps.stock.management.commands.seed_catalogue import (
            FICHES_TECHNIQUES)

        self.assertEqual(FICHES_TECHNIQUES['PAN-CS-710']['pmax_wc'],
                         Decimal('710.00'))
        self.assertEqual(FICHES_TECHNIQUES['PAN-JK-710']['pmax_wc'],
                         Decimal('710.00'))
        self.assertEqual(
            FICHES_TECHNIQUES['PAN-CS-710']['temp_coeff_pmax_pct_c'],
            Decimal('-0.290'))
        self.assertEqual(FICHES_TECHNIQUES['BAT-DEY-5']['bat_v_nominal'],
                         Decimal('51.2'))
        self.assertEqual(FICHES_TECHNIQUES['BAT-DEY-10']['bat_v_nominal'],
                         Decimal('51.2'))
        # PVLV2 — le 15 kW est le SKU historique OND-H-DEY-15T (SG05LP3).
        self.assertEqual(
            FICHES_TECHNIQUES['OND-H-DEY-15T']['ond_rendement_euro_pct'],
            Decimal('97.0'))
        # La plage batterie des Deye LV, retirée de la parenthèse en prose,
        # reste portée par le champ dédié (fusionné depuis la source unique
        # PLAGE_BATTERIE_ONDULEUR).
        self.assertEqual(FICHES_TECHNIQUES['OND-H-DEY-15T']['ond_bat_v_min'],
                         Decimal('40'))
        self.assertEqual(FICHES_TECHNIQUES['OND-H-DEY-15T']['ond_bat_v_max'],
                         Decimal('60'))

    def test_un_nombre_sans_champ_reste_en_prose(self):
        """L'erreur SYMÉTRIQUE : retirer un nombre qui n'a pas d'autre
        domicile le perdrait. ``BAT-LIT-5`` n'a AUCUNE ``FicheTechnique`` —
        sa tension et sa capacité ne vivent que là."""
        from apps.stock.management.commands.seed_catalogue import (
            FICHES, FICHES_TECHNIQUES)

        self.assertNotIn('BAT-LIT-5', FICHES_TECHNIQUES)
        description = FICHES['BAT-LIT-5']['description']
        self.assertIn('51,2 V', description)
        self.assertIn('5 kWh', description)
        # Idem pour le rendement de MODULE et la dégradation annuelle : aucun
        # champ de FicheTechnique ne les porte, ils restent en prose.
        self.assertIn('22,9 %', FICHES['PAN-CS-710']['description'])
        self.assertIn('0,4 %/an', FICHES['PAN-CS-710']['description'])

    def test_la_ligne_marquee_plage_batterie_est_intacte(self):
        """La parenthèse « (plage 40-60 V…) » a disparu de la prose, mais la
        LIGNE MARQUÉE — lue par ``plage_batterie_onduleur`` en repli — est
        posée par un autre mécanisme et reste écrite telle quelle."""
        seed(self.company)
        # PVLV2 — même vérification, sur le SKU historique (SG05LP3).
        produit = Produit.objects.get(company=self.company,
                                      sku='OND-H-DEY-15T')
        self.assertIn('Plage batterie : 40-60 V', produit.description)
        # …et la prose ne redit plus la même plage juste au-dessus.
        self.assertNotIn('(plage 40-60 V', produit.description)


class TestPvfchComblerFichesManquantes(TestCase):
    """PVFCH (fondateur 20/08/2026) — ``apps/ventes/electrical_service.py``
    (commit ff38e6e3) refuse le schéma unifilaire dès qu'UNE SEULE des 7
    variables MODULE ou 7 variables ONDULEUR de ``FicheTechnique`` est
    absente. ``manage.py seed_catalogue`` (qui pose ces valeurs) n'a
    longtemps jamais été appelé par ``scripts/deploy-prod.ps1`` — une base de
    production peut donc porter une fiche NULL ou partiellement remplie.

    La migration 0125 soigne ce trou : elle crée la fiche manquante ou ne
    comble QUE les champs vides, à partir du dictionnaire ``FICHES_TECHNIQUES``
    du seeder (source unique, importée) — jamais une valeur déjà saisie par
    le fondateur n'est écrasée."""

    MIGRATION = 'apps.stock.migrations.0125_pvfch_combler_fiches_manquantes'

    def setUp(self):
        self.company = make_company(slug='test-cat-pvfch-fiches')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def test_cree_la_fiche_manquante_avec_les_valeurs_du_seeder(self):
        """PAN-CS-710 seedé SANS fiche technique (base restée en arrière du
        seeder, ex. société jamais couverte par le déploiement PVOND) : la
        migration la crée avec exactement les valeurs sourcées."""
        from django.apps import apps as registre
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        FicheTechnique.objects.filter(produit=produit).delete()
        self.assertFalse(
            FicheTechnique.objects.filter(produit=produit).exists())

        self._migration().soigner_fiches_manquantes(registre, None)

        fiche = FicheTechnique.objects.get(produit=produit)
        self.assertEqual(fiche.company_id, self.company.id)
        self.assertEqual(fiche.type_fiche, 'module')
        self.assertEqual(fiche.pmax_wc, Decimal('710.00'))
        self.assertEqual(fiche.voc_v, Decimal('48.30'))
        self.assertEqual(fiche.temp_coeff_voc_pct_c, Decimal('-0.250'))
        self.assertEqual(fiche.temp_coeff_pmax_pct_c, Decimal('-0.290'))

    def test_ne_jamais_ecraser_un_champ_deja_saisi(self):
        """OND-H-DEY-5M seedé avec sa fiche : ``ond_ac_kw`` porte une valeur
        DIFFÉRENTE de celle du seeder (simule une saisie fondateur, fût-elle
        fausse) et ``ond_v_max_abs`` est vidé (champ pas encore comblé).
        Après la migration : ``ond_ac_kw`` INCHANGÉ, ``ond_v_max_abs``
        COMBLÉ."""
        from django.apps import apps as registre
        from apps.stock.management.commands.seed_catalogue import (
            FICHES_TECHNIQUES)
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='OND-H-DEY-5M')
        fiche = FicheTechnique.objects.get(produit=produit)
        valeur_seeder = FICHES_TECHNIQUES['OND-H-DEY-5M']['ond_ac_kw']
        valeur_saisie = valeur_seeder + Decimal('1')  # différente : simule une saisie fondateur
        fiche.ond_ac_kw = valeur_saisie
        fiche.ond_v_max_abs = None
        fiche.save(update_fields=['ond_ac_kw', 'ond_v_max_abs'])

        self._migration().soigner_fiches_manquantes(registre, None)

        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_ac_kw, valeur_saisie)
        self.assertEqual(
            fiche.ond_v_max_abs,
            FICHES_TECHNIQUES['OND-H-DEY-5M']['ond_v_max_abs'])

    def test_sku_absent_du_dictionnaire_reste_intact(self):
        """Un produit dont le SKU n'est PAS dans ``FICHES_TECHNIQUES`` (ex.
        un variateur VEICHI) : aucune fiche créée, rien ne bouge."""
        from django.apps import apps as registre
        from apps.stock.management.commands.seed_catalogue import (
            FICHES_TECHNIQUES)
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='VEI-SI22-AFF')
        self.assertNotIn('VEI-SI22-AFF', FICHES_TECHNIQUES)
        self.assertFalse(
            FicheTechnique.objects.filter(produit=produit).exists())

        self._migration().soigner_fiches_manquantes(registre, None)

        self.assertFalse(
            FicheTechnique.objects.filter(produit=produit).exists())

    def test_la_migration_est_idempotente(self):
        """Un second passage n'écrit rien de plus (aucune fiche dupliquée,
        aucun champ retouché)."""
        from django.apps import apps as registre
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        FicheTechnique.objects.filter(produit=produit).delete()
        migration = self._migration()

        migration.soigner_fiches_manquantes(registre, None)
        migration.soigner_fiches_manquantes(registre, None)

        self.assertEqual(
            FicheTechnique.objects.filter(produit=produit).count(), 1)
        fiche = FicheTechnique.objects.get(produit=produit)
        self.assertEqual(fiche.pmax_wc, Decimal('710.00'))

    def test_reverse_est_un_noop(self):
        """La migration inverse ne défait rien (``RunPython.noop``) — un
        champ comblé par le passage aller reste comblé après un rollback."""
        from django.apps import apps as registre
        from django.db import migrations as dj_migrations
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(company=self.company, sku='PAN-CS-710')
        FicheTechnique.objects.filter(produit=produit).delete()
        migration = self._migration()
        migration.soigner_fiches_manquantes(registre, None)

        reverse = migration.Migration.operations[0].reverse_code
        self.assertIs(reverse, dj_migrations.RunPython.noop)
        reverse(registre, None)

        fiche = FicheTechnique.objects.get(produit=produit)
        self.assertEqual(fiche.pmax_wc, Decimal('710.00'))


class TestPvlv2GammeLv(TestCase):
    """PVLV2 (fondateur 21/08/2026) — « i only know 15 and 20kw on LV » :
    OND-H-DEY-15T/20T SONT les SG05LP3 basse tension, prix d'origine intacts.
    La migration 0126 archive les SKU doublons « Basse Tension » du 18/08 et
    recale les fiches des valeurs SG01HP3 (fausse identification) vers les
    valeurs SG05LP3 — champ par champ, jamais une saisie fondateur."""

    MIGRATION = 'apps.stock.migrations.0126_pvlv_prix_deye_lv'

    def setUp(self):
        self.company = make_company(slug='test-cat-pvlv2-lv')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def _fiche_15t(self):
        from apps.stock.models import FicheTechnique
        return FicheTechnique.objects.get(
            produit__company=self.company, produit__sku='OND-H-DEY-15T')

    def _etat_ancienne_base(self):
        """Reproduit une base seedée AVANT le 21/08 : fiche 15T aux valeurs
        SG01HP3 (fausses) + SKU doublon LV présent, prix vide."""
        seed(self.company)
        fiche = self._fiche_15t()
        fiche.ond_mppt_v_min = Decimal('150.0')
        fiche.ond_mppt_v_max = Decimal('850.0')
        fiche.ond_v_max_abs = Decimal('1000.0')
        fiche.ond_v_demarrage_v = Decimal('180.0')
        fiche.ond_bat_v_min = Decimal('160.0')
        fiche.ond_bat_v_max = Decimal('700.0')
        fiche.save()
        quinze_t = Produit.objects.get(
            company=self.company, sku='OND-H-DEY-15T')
        doublon = Produit.objects.create(
            company=self.company,
            nom='Onduleur hybride Deye 15kW Triphasé Basse Tension',
            sku='OND-DEY-15K-LV', categorie=quinze_t.categorie,
            prix_vente=Decimal('0'), prix_achat=Decimal('0'),
            quantite_stock=0, seuil_alerte=5, tva=Decimal('20.00'))
        return fiche, doublon

    def test_doublon_archive_et_fiche_recalee_sg05lp3(self):
        from django.apps import apps as registre
        fiche, doublon = self._etat_ancienne_base()

        self._migration().corriger_gamme_lv(registre, None)

        doublon.refresh_from_db()
        self.assertTrue(doublon.is_archived)
        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_mppt_v_min, Decimal('160.0'))
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('650.0'))
        self.assertEqual(fiche.ond_v_max_abs, Decimal('800.0'))
        self.assertEqual(fiche.ond_v_demarrage_v, Decimal('160.0'))
        self.assertEqual(fiche.ond_bat_v_min, Decimal('40.0'))
        self.assertEqual(fiche.ond_bat_v_max, Decimal('60.0'))

    def test_saisie_fondateur_divergente_jamais_touchee(self):
        from django.apps import apps as registre
        fiche, _ = self._etat_ancienne_base()
        fiche.ond_mppt_v_max = Decimal('900.0')   # saisie fondateur
        fiche.save(update_fields=['ond_mppt_v_max'])

        self._migration().corriger_gamme_lv(registre, None)

        fiche.refresh_from_db()
        self.assertEqual(fiche.ond_mppt_v_max, Decimal('900.0'))
        # Les autres champs, eux, sont bien recalés.
        self.assertEqual(fiche.ond_v_max_abs, Decimal('800.0'))

    def test_prix_fondateur_jamais_touches(self):
        from django.apps import apps as registre
        self._etat_ancienne_base()
        avant = Produit.objects.get(
            company=self.company, sku='OND-H-DEY-15T').prix_vente
        self.assertGreater(avant, 0)

        self._migration().corriger_gamme_lv(registre, None)

        apres = Produit.objects.get(
            company=self.company, sku='OND-H-DEY-15T').prix_vente
        self.assertEqual(apres, avant)

    def test_idempotente_et_sans_effet_sur_base_neuve(self):
        from django.apps import apps as registre
        # Base NEUVE : le seeder pose déjà les valeurs SG05LP3 et ne crée
        # plus les doublons — la migration ne change strictement rien.
        seed(self.company)
        fiche = self._fiche_15t()
        avant = (fiche.ond_mppt_v_min, fiche.ond_mppt_v_max,
                 fiche.ond_v_max_abs)
        migration = self._migration()
        migration.corriger_gamme_lv(registre, None)
        migration.corriger_gamme_lv(registre, None)
        fiche.refresh_from_db()
        self.assertEqual(
            (fiche.ond_mppt_v_min, fiche.ond_mppt_v_max, fiche.ond_v_max_abs),
            avant)
        self.assertFalse(Produit.objects.filter(
            company=self.company, sku='OND-DEY-15K-LV').exists())


class TestPvlvIdentiteBatterieBosb(TestCase):
    """PVLV (21/08/2026) — la batterie HV « 16 kWh » est une Deye BOS-B Pro
    (facture Solarex S26/001708), pas une Dyness. La migration 0127 corrige
    nom + marque sur les bases existantes, SKU inchangé ; un nom retouché par
    le fondateur n'est jamais touché."""

    MIGRATION = 'apps.stock.migrations.0127_pvlv_identite_batterie_bosb'
    ANCIEN = 'Batterie Dyness haute tension — 16 kWh'
    NOUVEAU = 'Batterie Deye BOS-B Pro haute tension — 16 kWh'

    def setUp(self):
        self.company = make_company(slug='test-cat-pvlv-bosb')

    def _migration(self):
        import importlib
        return importlib.import_module(self.MIGRATION)

    def _etat_ancienne_base(self):
        seed(self.company)
        produit = Produit.objects.get(
            company=self.company, sku='BAT-DYN-HV-16')
        produit.nom = self.ANCIEN
        produit.marque = 'Dyness'
        produit.save(update_fields=['nom', 'marque'])
        return produit

    def test_rename_nom_et_marque_sku_inchange(self):
        from django.apps import apps as registre
        produit = self._etat_ancienne_base()

        self._migration().corriger_identite(registre, None)

        produit.refresh_from_db()
        self.assertEqual(produit.nom, self.NOUVEAU)
        self.assertEqual(produit.marque, 'Deye')
        self.assertEqual(produit.sku, 'BAT-DYN-HV-16')
        # Le mot-clé de la garde anti-composition basse tension survit.
        self.assertIn('haute tension', produit.nom.lower())

    def test_nom_retouche_par_le_fondateur_intouchable(self):
        from django.apps import apps as registre
        produit = self._etat_ancienne_base()
        produit.nom = 'Batterie HV projet Bouskoura'
        produit.save(update_fields=['nom'])

        self._migration().corriger_identite(registre, None)

        produit.refresh_from_db()
        self.assertEqual(produit.nom, 'Batterie HV projet Bouskoura')
        # La marque, elle, reste corrigeable (Dyness était factuellement faux).
        self.assertEqual(produit.marque, 'Deye')

    def test_idempotente_et_base_neuve_sans_effet(self):
        from django.apps import apps as registre
        seed(self.company)   # base NEUVE : le seeder crée déjà le bon nom
        migration = self._migration()
        migration.corriger_identite(registre, None)
        migration.corriger_identite(registre, None)
        produit = Produit.objects.get(
            company=self.company, sku='BAT-DYN-HV-16')
        self.assertEqual(produit.nom, self.NOUVEAU)
        self.assertEqual(produit.marque, 'Deye')

    def test_le_seeder_neuf_pose_la_fiche_bosb(self):
        """La fiche (16,08 kWh / DoD 90 / 9,22 kW) est posée par le seeder —
        et ``bat_v_nominal`` reste ABSENT (tension MODULE ≠ tension système :
        la poser ferait entrer ce composant HV dans la fenêtre 40-60 V des
        onduleurs basse tension)."""
        from apps.stock.models import FicheTechnique
        seed(self.company)
        produit = Produit.objects.get(
            company=self.company, sku='BAT-DYN-HV-16')
        fiche = FicheTechnique.objects.get(produit=produit)
        self.assertEqual(fiche.bat_kwh_nominal, Decimal('16.08'))
        self.assertEqual(fiche.bat_dod_pct, Decimal('90.0'))
        self.assertEqual(fiche.bat_max_charge_kw, Decimal('9.22'))
        self.assertIsNone(fiche.bat_v_nominal)
