"""AGR104 — articles des options du kit pompage (prix à renseigner) + rôles
des articles existants (migration de données gardée sur « rôle vide »).
"""
import importlib
from decimal import Decimal
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.stock.management.commands import seed_catalogue as seed_mod
from apps.stock.models import Produit
from authentication.models import Company
from core.product_roles import ROLES_POMPAGE

migration = importlib.import_module(
    'apps.stock.migrations.0162_agr104_roles_pompage')


def _seed(company):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out)
    return out.getvalue()


class OptionsPompageTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agr104-co', defaults={'nom': 'AGR104 Co'})[0]

    def test_options_creees_a_prix_vide_avec_role_declare(self):
        _seed(self.co)
        for nom, sku, role, _q, _s in seed_mod.OPTIONS_POMPAGE:
            p = Produit.objects.get(company=self.co, sku=sku)
            self.assertEqual(p.nom, nom)
            self.assertEqual(p.role_pompage, role)
            self.assertIn(role, ROLES_POMPAGE)
            self.assertEqual(p.prix_vente, 0)
            self.assertEqual(p.prix_achat, 0)

    def test_sept_options_du_kit(self):
        self.assertEqual(
            {r for _n, _s, r, _q, _t in seed_mod.OPTIONS_POMPAGE},
            {'sonde_niveau', 'compteur_eau', 'cable_descente',
             'colonne_refoulement', 'clapet', 'tuyauterie', 'bassin'})

    def test_seeder_rejoue_deux_fois_aucun_doublon_aucun_prix_modifie(self):
        _seed(self.co)
        avant = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        nb = Produit.objects.filter(company=self.co).count()
        _seed(self.co)
        self.assertEqual(Produit.objects.filter(company=self.co).count(), nb)
        apres = dict(Produit.objects.filter(company=self.co)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(avant, apres)
        for _n, sku, _r, _q, _s in seed_mod.OPTIONS_POMPAGE:
            self.assertEqual(
                Produit.objects.filter(company=self.co, sku=sku).count(), 1)

    def test_dacal118_protections_du_kit_semees_a_prix_vide_avec_role(self):
        """D-ACAL-118 — coffret DC, disjoncteurs AC et parafoudre AC : rôle
        pompage déclaré à la création, prix VIDES (jamais un prix inventé),
        servis par ``produits_pompage`` ; différentiels et coffret AC sans
        rôle pompage."""
        from apps.stock.selectors import produits_pompage
        _seed(self.co)
        for sku, role in seed_mod.ROLE_POMPAGE_PVG3.items():
            p = Produit.objects.get(company=self.co, sku=sku)
            self.assertEqual(p.role_pompage, role, sku)
            self.assertIn(role, ROLES_POMPAGE)
            # D-ACAL-127/128 : prix confirmés posés HT (parafoudre AC compris).
            self.assertEqual(p.prix_vente,
                             seed_mod.ht(seed_mod.PRIX_TTC_PVG3.get(sku, 0)), sku)
            self.assertEqual(p.prix_achat, 0, sku)
        self.assertEqual(Produit.objects.get(
            company=self.co, sku='PARA-AC-T2').prix_vente, Decimal('833.33'))
        self.assertEqual(
            {s for s, r in seed_mod.ROLE_POMPAGE_PVG3.items()
             if r == 'protection_ac'},
            {s for _n, s, _q, _t in seed_mod.CABLES_PROTECTIONS_VIDES
             if s.startswith('DISJ-AC-') or s == 'PARA-AC-T2'})
        for sku in ('DDR-A-300-40', 'COF-AC'):
            self.assertEqual(Produit.objects.get(
                company=self.co, sku=sku).role_pompage, '')
        roles = {e['sku']: e['role_pompage'] for e in produits_pompage(self.co)}
        self.assertEqual(roles.get('PARA-AC-T2'), 'protection_ac')
        self.assertEqual(roles.get('COF-DC-2STR'), 'protection_dc')

    def test_dacal118_role_saisi_et_prix_saisi_jamais_reecrits(self):
        Produit.objects.create(
            company=self.co, nom='Parafoudre AC du fondateur',
            sku='PARA-AC-T2', prix_vente=250, role_pompage='')
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='PARA-AC-T2')
        self.assertEqual((p.nom, p.prix_vente, p.role_pompage),
                         ('Parafoudre AC du fondateur', 250, ''))

    def test_dacal127_prix_confirmes_semes_ht(self):
        """D-ACAL-127 — les neuf prix TTC confirmés (mrelec.ma, 25/11/2026)
        sont semés HT par la conversion du seeder ; achat jamais touché."""
        _seed(self.co)
        attendus = {
            'DISJ-AC-C-16-1P': '66.67', 'DISJ-AC-C-20-1P': '66.67',
            'DISJ-AC-C-25-1P': '66.67', 'DISJ-AC-C-32-1P': '69.17',
            'DISJ-AC-C-16-4P': '106.67', 'DISJ-AC-C-20-4P': '110.00',
            'DISJ-AC-C-25-4P': '113.33', 'DISJ-AC-C-32-4P': '117.50',
            'COF-DC-2STR': '1666.67'}
        for sku, prix in attendus.items():
            p = Produit.objects.get(company=self.co, sku=sku)
            self.assertEqual(p.prix_vente, Decimal(prix), sku)
            self.assertEqual(p.prix_achat, 0, sku)
            self.assertEqual(p.tva, Decimal('20.00'), sku)

    def test_dacal127_prix_saisi_jamais_reecrit_par_le_seeder(self):
        Produit.objects.create(
            company=self.co, nom='Disjoncteur du fondateur',
            sku='DISJ-AC-C-16-1P', prix_vente=Decimal('250'))
        _seed(self.co)
        _seed(self.co)
        qs = Produit.objects.filter(company=self.co, sku='DISJ-AC-C-16-1P')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.get().prix_vente, Decimal('250'))

    def test_option_existante_jamais_reecrite(self):
        Produit.objects.create(
            company=self.co, nom='Clapet saisi par le fondateur',
            sku='CLAP-AR', prix_vente=77, role_pompage='')
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='CLAP-AR')
        self.assertEqual(p.nom, 'Clapet saisi par le fondateur')
        self.assertEqual(p.prix_vente, 77)
        self.assertEqual(p.role_pompage, '')


class Pompage(TestCase):
    """AGQ36 (C-AGQ-004) — le kit minimum a un article de structure AU SOL
    à chiffrer (rôle ``structure_sol``), jamais la structure de toiture."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agq36-co', defaults={'nom': 'AGQ36 Co'})[0]

    def test_structure_sol_semee_a_prix_vide(self):
        from apps.stock.selectors import produits_pompage
        from core.product_roles import est_panneau
        _seed(self.co)
        p = Produit.objects.get(company=self.co, sku='STR-SOL-PMP')
        self.assertEqual(p.role_pompage, 'structure_sol')
        self.assertEqual(p.prix_vente, 0)
        self.assertEqual(p.prix_achat, 0)
        # Jamais lu comme un panneau (puissance crête, décompte de modules).
        self.assertFalse(est_panneau(p.nom))
        self.assertEqual(p.fiche_technique.struct_type_pose, 'sol')
        roles = {e['sku']: e.get('role_pompage')
                 for e in produits_pompage(self.co)}
        self.assertEqual(roles.get('STR-SOL-PMP'), 'structure_sol')
        # La structure de TOITURE reste sans rôle pompage.
        for toit in Produit.objects.filter(company=self.co,
                                           nom='Structures acier'):
            self.assertNotEqual(toit.role_pompage, 'structure_sol')

    def test_structure_sol_rejouee_sans_doublon_prix_saisi_garde(self):
        _seed(self.co)
        Produit.objects.filter(company=self.co, sku='STR-SOL-PMP').update(
            prix_vente=450)
        _seed(self.co)
        qs = Produit.objects.filter(company=self.co, sku='STR-SOL-PMP')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.get().prix_vente, 450)


class MigrationRolesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='agr104-mig-co', defaults={'nom': 'AGR104 Mig Co'})[0]
        _seed(self.co)
        # Le seeder ne déclare pas le rôle des SKU historiques : état de prod.
        Produit.objects.filter(company=self.co).exclude(
            sku__in=[r[1] for r in seed_mod.OPTIONS_POMPAGE]
        ).update(role_pompage='')

    def _role(self, sku):
        return Produit.objects.get(company=self.co, sku=sku).role_pompage

    def test_roles_declares_par_code(self):
        migration.declarer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-5.5T'), 'pompe')
        self.assertEqual(self._role('PMP-SUR-3T'), 'pompe')
        self.assertEqual(self._role('PMP-OSP-30-8'), 'pompe')
        self.assertEqual(self._role('VEI-SI23-5.5-380'), 'variateur_pompage')
        self.assertEqual(self._role('VEI-SI22-AFF'), 'afficheur_variateur')
        self.assertEqual(self._role('PARA-DC-T2-1000'), 'protection_dc')
        self.assertEqual(self._role('CAB-6MM-M'), 'cable_dc')
        # protections AC : jamais déclarées
        self.assertEqual(self._role('DISJ-AC-C-16-1P'), '')

    def test_aucun_prix_ni_nom_touche(self):
        avant = {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                 for p in Produit.objects.filter(company=self.co)}
        migration.declarer_roles(django_apps, None)
        apres = {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                 for p in Produit.objects.filter(company=self.co)}
        self.assertEqual(avant, apres)

    def test_role_deja_saisi_pas_reecrit(self):
        Produit.objects.filter(
            company=self.co, sku='PMP-IMM-3M').update(role_pompage='bassin')
        migration.declarer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-3M'), 'bassin')

    def test_aller_retour(self):
        migration.declarer_roles(django_apps, None)
        migration.declarer_roles(django_apps, None)  # idempotent
        self.assertEqual(self._role('PMP-IMM-4T'), 'pompe')
        migration.retirer_roles(django_apps, None)
        self.assertEqual(self._role('PMP-IMM-4T'), '')
        self.assertEqual(self._role('VEI-SI22-AFF'), '')
        # les options du seeder (rôle déclaré à la création) ne sont pas dans
        # la table de la migration : le retour n'y touche pas.
        self.assertEqual(self._role('SONDE-NIV'), 'sonde_niveau')

    def test_dacal118_migration_0190_protection_ac(self):
        m0190 = importlib.import_module(
            'apps.stock.migrations.0190_dacal118_protection_ac_pompage')
        Produit.objects.filter(company=self.co, sku='DISJ-AC-C-20-4P').update(
            role_pompage='cloture')
        avant = {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                 for p in Produit.objects.filter(company=self.co)}
        m0190.declarer_roles(django_apps, None)
        m0190.declarer_roles(django_apps, None)  # idempotent
        self.assertEqual(self._role('DISJ-AC-C-16-1P'), 'protection_ac')
        self.assertEqual(self._role('DISJ-AC-C-32-4P'), 'protection_ac')
        self.assertEqual(self._role('PARA-AC-T2'), 'protection_ac')
        self.assertEqual(self._role('DISJ-AC-C-20-4P'), 'cloture')  # saisi
        self.assertEqual(self._role('DDR-A-300-40'), '')
        self.assertEqual(self._role('COF-AC'), '')
        self.assertEqual(avant, {p.sku: (p.nom, p.prix_vente, p.prix_achat)
                                 for p in Produit.objects.filter(company=self.co)})
        m0190.retirer_roles(django_apps, None)
        self.assertEqual(self._role('PARA-AC-T2'), '')
        self.assertEqual(self._role('DISJ-AC-C-20-4P'), 'cloture')

    def _prix(self, sku):
        return Produit.objects.get(company=self.co, sku=sku).prix_vente

    def test_dacal127_migration_0191_prix_vides_seulement(self):
        m0191 = importlib.import_module(
            'apps.stock.migrations.0191_dacal127_prix_protections_pompage')
        # État de prod : les neuf articles à 0 ; l'un déjà chiffré à la main.
        Produit.objects.filter(company=self.co, sku__in=[*m0191.PRIX_HT, 'PARA-AC-T2']
                               ).update(prix_vente=0)
        Produit.objects.filter(company=self.co, sku='DISJ-AC-C-25-4P').update(
            prix_vente=Decimal('199'))
        autre = Company.objects.get_or_create(
            slug='agr104-mig-co-2', defaults={'nom': 'AGR104 Mig Co 2'})[0]
        Produit.objects.create(company=autre, nom='Coffret DC', sku='COF-DC-2STR',
                               prix_vente=0, prix_achat=Decimal('900'))
        avant = {p.sku: (p.nom, p.prix_achat, p.quantite_stock, p.role_pompage)
                 for p in Produit.objects.filter(company=self.co)}
        nb = Produit.objects.count()
        m0191.poser_prix(django_apps, None)
        m0191.poser_prix(django_apps, None)  # idempotent
        self.assertEqual(Produit.objects.count(), nb)  # aucun article créé
        self.assertEqual(self._prix('DISJ-AC-C-16-1P'), Decimal('66.67'))
        self.assertEqual(self._prix('DISJ-AC-C-32-4P'), Decimal('117.50'))
        self.assertEqual(self._prix('COF-DC-2STR'), Decimal('1666.67'))
        self.assertEqual(self._prix('DISJ-AC-C-25-4P'), Decimal('199'))  # saisi
        self.assertEqual(self._prix('PARA-AC-T2'), 0)
        cof = Produit.objects.get(company=autre, sku='COF-DC-2STR')
        self.assertEqual((cof.prix_vente, cof.prix_achat),
                         (Decimal('1666.67'), Decimal('900')))
        self.assertEqual(avant, {
            p.sku: (p.nom, p.prix_achat, p.quantite_stock, p.role_pompage)
            for p in Produit.objects.filter(company=self.co)})
        m0191.retirer_prix(django_apps, None)
        self.assertEqual(self._prix('DISJ-AC-C-16-1P'), 0)
        self.assertEqual(self._prix('DISJ-AC-C-25-4P'), Decimal('199'))
        self.assertEqual(Produit.objects.get(
            company=autre, sku='COF-DC-2STR').prix_vente, 0)

    def test_dacal128_migration_0192_parafoudre_ac(self):
        m0192 = importlib.import_module(
            'apps.stock.migrations.0192_dacal128_prix_parafoudre_ac')
        Produit.objects.filter(company=self.co, sku='PARA-AC-T2').update(prix_vente=0)
        autre = Company.objects.get_or_create(
            slug='agr104-mig-co-3', defaults={'nom': 'AGR104 Mig Co 3'})[0]
        Produit.objects.create(company=autre, nom='Parafoudre saisi', sku='PARA-AC-T2',
                               prix_vente=Decimal('250'))
        avant = {p.sku: (p.nom, p.prix_achat, p.quantite_stock, p.role_pompage)
                 for p in Produit.objects.filter(company=self.co)}
        nb = Produit.objects.count()
        m0192.poser_prix(django_apps, None)
        m0192.poser_prix(django_apps, None)  # idempotent
        self.assertEqual(Produit.objects.count(), nb)
        self.assertEqual(self._prix('PARA-AC-T2'), Decimal('833.33'))
        saisi = Produit.objects.get(company=autre, sku='PARA-AC-T2')
        self.assertEqual(saisi.prix_vente, Decimal('250'))  # jamais réécrit
        self.assertEqual(avant, {
            p.sku: (p.nom, p.prix_achat, p.quantite_stock, p.role_pompage)
            for p in Produit.objects.filter(company=self.co)})
        m0192.retirer_prix(django_apps, None)
        self.assertEqual(self._prix('PARA-AC-T2'), 0)
        saisi.refresh_from_db()
        self.assertEqual(saisi.prix_vente, Decimal('250'))


class PrixFigesDacal127Tests(SimpleTestCase):
    """D-ACAL-127 — la table HT figée de la migration 0191 égale la
    conversion du seeder (``ht``) de chaque TTC confirmé — sans base."""

    def test_ht_fige_egale_conversion_du_seeder(self):
        m0191 = importlib.import_module(
            'apps.stock.migrations.0191_dacal127_prix_protections_pompage')
        m0192 = importlib.import_module(
            'apps.stock.migrations.0192_dacal128_prix_parafoudre_ac')
        figes = {**m0191.PRIX_HT, **m0192.PRIX_HT}
        self.assertFalse(set(m0191.PRIX_HT) & set(m0192.PRIX_HT))
        self.assertEqual(set(figes), set(seed_mod.PRIX_TTC_PVG3))
        for sku, ttc in seed_mod.PRIX_TTC_PVG3.items():
            self.assertEqual(figes[sku], seed_mod.ht(ttc), sku)
        self.assertEqual(m0192.PRIX_HT, {'PARA-AC-T2': Decimal('833.33')})

    def test_dacal129_fiches_figees_egales_au_seeder(self):
        m0193 = importlib.import_module(
            'apps.stock.migrations.0193_dacal129_fiches_variateurs_veichi')
        self.assertEqual(m0193.FICHES, seed_mod.FICHES_VARIATEURS_VEICHI)
        variateurs = {sku for _n, sku, *_r in seed_mod.VEICHI} - {'VEI-SI22-AFF'}
        self.assertEqual(set(m0193.FICHES), variateurs)
        self.assertEqual(len(m0193.FICHES), 15)
        for sku, valeurs in m0193.FICHES.items():
            self.assertEqual(set(valeurs), {'ond_v_max_abs', 'var_voc_reco_min_v',
                                            'var_voc_reco_max_v'}, sku)
            attendu = ('780.0' if sku.endswith('-380') else
                       '400.0' if sku.startswith('VEI-SI22') else '450.0')
            self.assertEqual(valeurs['ond_v_max_abs'], Decimal(attendu), sku)

    def test_dacal129_cv_figes_et_tension_par_la_phase_du_kit(self):
        """0194 — table FIGÉE : sa phase égale aujourd'hui la lecture du kit
        (``alimentation_produit``) sur la désignation ; ses CV, le seeder."""
        from core.pompage.selection import alimentation_produit
        from apps.stock.management.commands._articles_pompage import tension_pompe
        m0194 = importlib.import_module(
            'apps.stock.migrations.0194_dacal129_tension_cv_petites_pompes')
        designations = {sku: nom for nom, sku, *_r in seed_mod.POMPAGE
                        if sku.startswith('PMP-')}
        self.assertEqual(len(designations), 8)
        designations['Pmp-imm-2m'] = 'Pompe immergée solaire 2 CV Monophasé'
        self.assertEqual({s.upper() for s in designations}, set(m0194.POMPES))
        for sku, nom in designations.items():
            phase, _cv = m0194.POMPES[sku.upper()]
            self.assertEqual(alimentation_produit({'nom': nom}), phase, sku)
            self.assertEqual(tension_pompe(nom), m0194.TENSIONS[phase], sku)
        cv_seeder = {sku: Decimal(cv) for _n, sku, _t, _q, _s, cv, _h, _d in seed_mod.POMPAGE
                     if sku.startswith('PMP-')}
        self.assertEqual({s: cv for s, (_p, cv) in m0194.POMPES.items()},
                         {**cv_seeder, 'PMP-IMM-2M': None})
        self.assertEqual(m0194.TENSIONS, {'mono': 220, 'tri': 380})
        self.assertIsNone(tension_pompe('Câble solaire Nexans 6mm² (au mètre)'))


class FichesVariateursDacal129Tests(TestCase):
    """D-ACAL-129 — fiche « variateur de pompage » des variateurs VEICHI :
    tension DC max et Voc recommandée publiées ; MPPT et courant vides."""

    def setUp(self):
        from apps.stock.models import FicheTechnique
        self.Fiche = FicheTechnique
        self.co = Company.objects.get_or_create(
            slug='dacal129-co', defaults={'nom': 'DACAL129 Co'})[0]

    def _fiche(self, sku):
        return self.Fiche.objects.filter(
            produit__company=self.co, produit__sku=sku).first()

    def test_seeder_cree_les_fiches_publiees(self):
        _seed(self.co)
        _seed(self.co)  # idempotent
        for sku, valeurs in seed_mod.FICHES_VARIATEURS_VEICHI.items():
            fiche = self._fiche(sku)
            self.assertEqual(fiche.type_fiche, 'variateur_pompage', sku)
            for champ, valeur in valeurs.items():
                self.assertEqual(getattr(fiche, champ), valeur, (sku, champ))
            self.assertIsNone(fiche.ond_mppt_v_min, sku)
            self.assertIsNone(fiche.ond_mppt_v_max, sku)
            self.assertIsNone(fiche.ond_i_max_mppt_a, sku)
        self.assertIsNone(self._fiche('VEI-SI22-AFF'))
        self.assertEqual(self._fiche('VEI-SI23-11-380').ond_v_max_abs,
                         Decimal('780.0'))

    def test_seeder_ne_complete_jamais_une_fiche_existante(self):
        p = Produit.objects.create(company=self.co, nom='Variateur saisi',
                                   sku='VEI-SI23-4-380', prix_vente=100)
        self.Fiche.objects.create(company=self.co, produit=p,
                                  type_fiche='onduleur')
        _seed(self.co)
        fiche = self._fiche('VEI-SI23-4-380')
        self.assertEqual(fiche.type_fiche, 'onduleur')
        self.assertIsNone(fiche.ond_v_max_abs)
        self.assertIsNone(fiche.var_voc_reco_max_v)

    def test_migration_0193_aller_retour(self):
        m0193 = importlib.import_module(
            'apps.stock.migrations.0193_dacal129_fiches_variateurs_veichi')
        _seed(self.co)
        self.Fiche.objects.filter(produit__sku__in=list(m0193.FICHES)).delete()
        # Une fiche saisie à la main (autre type) et une fiche partielle.
        saisie = self.Fiche.objects.create(
            company=self.co, type_fiche='onduleur',
            produit=Produit.objects.get(company=self.co, sku='VEI-SI23-4-380'))
        partielle = self.Fiche.objects.create(
            company=self.co, type_fiche='variateur_pompage',
            ond_v_max_abs=Decimal('800.0'),
            produit=Produit.objects.get(company=self.co, sku='VEI-SI23-7.5-380'))
        Produit.objects.filter(company=self.co, sku='VEI-SI22-2.2-220').update(
            sku='vei-si22-2.2-220')  # casse de la prod
        nb_produits = Produit.objects.count()
        m0193.creer_fiches(django_apps, None)
        m0193.creer_fiches(django_apps, None)  # idempotent
        self.assertEqual(Produit.objects.count(), nb_produits)
        self.assertEqual(self.Fiche.objects.filter(
            produit__company=self.co, produit__sku__in=list(m0193.FICHES)).count(),
            14)  # 12 créées + les 2 existantes (la 13e est au SKU en minuscules)
        si22 = self._fiche('vei-si22-2.2-220')
        self.assertEqual((si22.company_id, si22.ond_v_max_abs, si22.var_voc_reco_min_v),
                         (self.co.id, Decimal('400.0'), Decimal('360.0')))
        saisie.refresh_from_db()
        partielle.refresh_from_db()
        self.assertEqual(saisie.type_fiche, 'onduleur')
        self.assertIsNone(saisie.ond_v_max_abs)
        self.assertEqual(partielle.ond_v_max_abs, Decimal('800.0'))
        self.assertIsNone(partielle.var_voc_reco_min_v)  # jamais complétée
        # Une fiche de la migration retouchée à la main survit au retour.
        retouchee = self._fiche('VEI-SI23-11-380')
        retouchee.var_v_sortie_v = Decimal('380.0')
        retouchee.save()
        m0193.supprimer_fiches(django_apps, None)
        restantes = set(self.Fiche.objects.filter(
            produit__company=self.co, produit__sku__in=list(m0193.FICHES)
        ).values_list('produit__sku', flat=True))
        self.assertEqual(restantes, {'VEI-SI23-4-380', 'VEI-SI23-7.5-380',
                                     'VEI-SI23-11-380'})
        self.assertIsNone(self._fiche('vei-si22-2.2-220'))


class PetitesPompesDacal129Tests(TestCase):
    """D-ACAL-129 — tension 220/380 V et CV des petites pompes du lot POMPAGE."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='dacal129-pmp', defaults={'nom': 'DACAL129 Pompes'})[0]
        _seed(self.co)

    def _p(self, sku):
        return Produit.objects.get(company=self.co, sku=sku)

    def test_seeder_pose_la_tension_des_petites_pompes(self):
        for _n, sku, _t, _q, _s, cv, _h, _d in seed_mod.POMPAGE:
            if not sku.startswith('PMP-'):
                continue
            p = self._p(sku)
            self.assertEqual(p.tension_v, 220 if sku.endswith('M') else 380, sku)
            self.assertEqual(p.pompe_cv, Decimal(cv), sku)
            self.assertIsNone(p.pompe_kw, sku)
        self.assertEqual(self._p('PMP-OSP-30-8').tension_v, 380)  # OSP intacte
        self.assertIsNone(self._p('CAB-6MM-M').tension_v)

    def test_migration_0194_champs_vides_seulement_aller_retour(self):
        m0194 = importlib.import_module(
            'apps.stock.migrations.0194_dacal129_tension_cv_petites_pompes')
        skus = [s for s in m0194.POMPES if s != 'PMP-IMM-2M']
        Produit.objects.filter(company=self.co, sku__in=skus).update(
            tension_v=None, pompe_cv=None)
        Produit.objects.filter(company=self.co, sku='PMP-IMM-3M').update(
            tension_v=380, pompe_cv=Decimal('2'))  # saisis : jamais réécrits
        deux = Produit.objects.create(
            company=self.co, nom='Pompe immergée solaire 2 CV Monophasé',
            sku='Pmp-imm-2m', prix_vente=Decimal('5000'))
        osp_avant = (self._p('PMP-OSP-30-8').tension_v, self._p('PMP-OSP-30-8').pompe_kw)
        nb = Produit.objects.count()
        m0194.poser(django_apps, None)
        m0194.poser(django_apps, None)  # idempotent
        self.assertEqual(Produit.objects.count(), nb)
        self.assertEqual((self._p('PMP-IMM-1.5M').tension_v, self._p('PMP-IMM-1.5M').pompe_cv),
                         (220, Decimal('1.50')))
        self.assertEqual((self._p('PMP-IMM-10T').tension_v, self._p('PMP-IMM-10T').pompe_cv),
                         (380, Decimal('10.00')))
        self.assertEqual((self._p('PMP-SUR-3T').tension_v, self._p('PMP-SUR-3T').pompe_kw),
                         (380, None))
        self.assertEqual((self._p('PMP-IMM-3M').tension_v, self._p('PMP-IMM-3M').pompe_cv),
                         (380, Decimal('2.00')))
        deux.refresh_from_db()
        self.assertEqual((deux.tension_v, deux.pompe_cv, deux.pompe_kw), (220, None, None))
        self.assertEqual(osp_avant, (self._p('PMP-OSP-30-8').tension_v,
                                     self._p('PMP-OSP-30-8').pompe_kw))
        m0194.retirer(django_apps, None)
        self.assertEqual((self._p('PMP-IMM-4T').tension_v, self._p('PMP-IMM-4T').pompe_cv),
                         (None, None))
        deux.refresh_from_db()
        self.assertIsNone(deux.tension_v)
        # La tension saisie 380 n'est pas celle de la table (220) : gardée ; ses
        # CV saisis (2) ne sont pas ceux de la table (3) : gardés.
        self.assertEqual((self._p('PMP-IMM-3M').tension_v, self._p('PMP-IMM-3M').pompe_cv),
                         (380, Decimal('2.00')))


class BaremePoseDacal130Tests(TestCase):
    """D-ACAL-130 — barème de la pose de pompage INST-PMP (2 000 + 250 HT par
    panneau) ; prix de vente laissé à 0."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='dacal130-co', defaults={'nom': 'DACAL130 Co'})[0]
        _seed(self.co)

    def _inst(self, co=None):
        return Produit.objects.get(company=co or self.co, sku='INST-PMP')

    def test_bareme_fige_egal_au_seeder(self):
        m0195 = importlib.import_module(
            'apps.stock.migrations.0195_dacal130_bareme_installation_pompage')
        self.assertEqual(m0195.BAREMES, seed_mod.BAREME_POMPAGE)
        inst = self._inst()
        self.assertEqual((inst.prix_fixe_ht, inst.prix_par_panneau_ht, inst.prix_vente),
                         (Decimal('2000.00'), Decimal('250.0000'), 0))

    def test_migration_0195_champs_vides_seulement_aller_retour(self):
        m0195 = importlib.import_module(
            'apps.stock.migrations.0195_dacal130_bareme_installation_pompage')
        Produit.objects.filter(company=self.co, sku='INST-PMP').update(
            prix_fixe_ht=None, prix_par_panneau_ht=0)
        autre = Company.objects.get_or_create(
            slug='dacal130-co-2', defaults={'nom': 'DACAL130 Co 2'})[0]
        Produit.objects.create(company=autre, nom='Pose pompage', sku='INST-PMP',
                               prix_vente=0, prix_fixe_ht=Decimal('1500'))
        nb = Produit.objects.count()
        m0195.poser_bareme(django_apps, None)
        m0195.poser_bareme(django_apps, None)  # idempotent
        self.assertEqual(Produit.objects.count(), nb)
        inst = self._inst()
        self.assertEqual((inst.prix_fixe_ht, inst.prix_par_panneau_ht, inst.prix_vente),
                         (Decimal('2000.00'), Decimal('250.0000'), 0))
        saisi = self._inst(autre)
        self.assertEqual((saisi.prix_fixe_ht, saisi.prix_par_panneau_ht),
                         (Decimal('1500.00'), Decimal('250.0000')))
        m0195.retirer_bareme(django_apps, None)
        inst, saisi = self._inst(), self._inst(autre)
        self.assertEqual((inst.prix_fixe_ht, inst.prix_par_panneau_ht), (None, None))
        self.assertEqual((saisi.prix_fixe_ht, saisi.prix_par_panneau_ht),
                         (Decimal('1500.00'), None))
