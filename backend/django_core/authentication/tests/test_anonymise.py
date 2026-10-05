"""qa_export_anonymise → qa_import_anonymise : instantané anonymisé pour la QA de nuit.

Ce qui est verrouillé ici :
* aller-retour : nombres, études, lignes, statuts IDENTIQUES ;
* chaque champ d'identité DIFFÈRE de la source, et AUCUNE valeur d'identité
  source n'apparaît dans les octets du fichier exporté ;
* intégrité des FK après import (tout pointe dans la société cible) ;
* les autres sociétés ne bougent pas ; ré-import idempotent ;
* garde DEBUG ; fail-closed : un champ texte inconnu est brouillé par défaut ;
* 400 leads Odoo à identifiants distincts de 3 chiffres : 0 ignoré, index unique
  respecté, même valeur → même faux (défaut du 30/09/2026 sur les données
  réelles). Les tests SANS base du brouilleur : ``test_anonymise_unicite.py``.
"""
import gzip
import itertools
import json
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, models
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication import anonymise
from authentication.models import Company, CustomUser

SOURCE_SLUG = 'taqinor-demo'
TARGET_SLUG = 'taqinor-anon-test'
_seq = itertools.count(1)

# Valeurs d'identité SOURCE volontairement distinctives (jamais dans les
# listes de faux noms) : on les cherche ensuite dans les octets exportés.
ID_CLIENT = {
    'nom': 'Quenzaoui', 'prenom': 'Zoubeirane',
    'email': 'zoubeirane.quenzaoui@source-exemple.ma',
    'telephone': '+212 6 61 99 88 77', 'adresse': '17 derb Zitoune, Fès',
    'cin': 'ZX998877', 'ice': '001122334455667',
}
ID_LEAD = {
    'nom': 'Xaverbrahim', 'prenom': 'Yamoussa', 'societe': 'Ferme Xaverbrahim',
    'email': 'yamoussa.x@source-exemple.ma', 'telephone': '0662334455',
    'whatsapp': '+212 6 62 33 44 56', 'adresse': '3 douar Ouled Qsiba',
    'note': 'Rappeler Mme Xaverbrahim après 18h au 0662334455',
}

# Réglages de PRIX de la société SOURCE, volontairement différents des défauts
# codés (défaut du 30/09/2026 : l'export ne les portait pas, la société cible
# tarifait avec les barèmes PAR DÉFAUT et les chiffres dérivaient de la prod).
PROFILE_PRICING = {
    'tva_standard': Decimal('18.00'), 'tva_panneaux': Decimal('12.00'),
    'onee_tarif_kwh': Decimal('1.911'), 'productible_kwh_kwc': Decimal('1725.0'),
    'rendement_global': Decimal('0.790'),
    'prix_cible_kwc_defaut': Decimal('9500.00'),
    'remise_max_pct': Decimal('12.50'),
    'discount_approval_threshold': Decimal('8.00'),
    'agricole_pump_hours': Decimal('6.5'),
    # AGR208 — repères énergie agricole (ex-« bonbonne » 55 / 131).
    'reperes_energie_agricole': {
        'butane_12kg_detail': {'valeur': 55, 'source': '',
                               'releve_le': '2026-08-20'},
        'butane_12kg_non_subventionne': {'valeur': 131, 'source': '',
                                         'releve_le': '2026-08-20'},
        'gasoil_litre': {'valeur': None, 'source': '', 'releve_le': None},
    },
    'quote_validity_days': 45, 'variante_pct': Decimal('15.00'),
    'devise_defaut': 'MAD',
    'seuil_regime_declaration_kwc': Decimal('12'),
    'seuil_regime_anre_kwc': Decimal('900'),
    'payment_terms': {'residentiel': {'acompte': 40, 'materiel': 50, 'solde': 10}},
}
# Identité / coordonnées / sécurité du profil SOURCE : ne doivent JAMAIS sortir.
PROFILE_IDENTITY = {
    'nom': 'Zaghlouloune Énergies SARL',
    'adresse': '88 boulevard Zaghloul, Casablanca',
    'email': 'direction@zaghlouloune-source.ma',
    'telephone': '+212 5 22 99 88 11', 'ice': '999888777666555',
    'rib': '230 780 0001234567890123 45', 'banque': 'Banque Zaghloul',
    'siret': 'SIRET-ZAGH-01', 'login_banner_text': 'Bandeau privé Zaghloul',
    'password_min_length': 3,
}
# Tarification & ROI de la société SOURCE. Deux prix sont des CHAÎNES à 9
# chiffres (« 118.123456 », tarif hors Maroc) : un brouilleur de JSON les
# prendrait pour un téléphone et rendrait le barème illisible.
TARIFF = {
    'residential_tiers': [
        {'max_kwh': 100, 'prix_kwh_ttc': '0.951234'},
        {'max_kwh': 150, 'prix_kwh_ttc': '1.101234'},
        {'max_kwh': 210, 'prix_kwh_ttc': '1.111234'},
        {'max_kwh': 310, 'prix_kwh_ttc': '1.211234'},
        {'max_kwh': 510, 'prix_kwh_ttc': '118.123456'},
        {'max_kwh': None, 'prix_kwh_ttc': '1.711234'},
    ],
    'tolerance_kwh': 12, 'selective_threshold_kwh': 140,
    'redevance_compteur_mad_mois': Decimal('47.35'),
    'force_motrice_prix_kwh_ttc': Decimal('0.8800'),
    'surplus_injecte_compense': True,
    'surplus_prix_kwh_ttc': Decimal('0.4200'),
    'autoconsommation_pct_defaut': Decimal('64.00'),
    'pertes_systeme_pct': Decimal('17.50'), 'pvgis_actif': False,
    'productible_manuel_kwh_kwc': Decimal('1725.0'),
    'inclinaison_defaut_deg': 25, 'azimut_defaut_deg': -10, 'version': 7,
    'tou_heures': ['creuse'] * 6 + ['pleine'] * 12 + ['pointe'] * 4
    + ['pleine'] * 2,
    'tou_tarifs': {'creuse': 0.85, 'pleine': '1.150000', 'pointe': '118.123456'},
    'tou_source': 'Contrat ONEE 2026-07 n° 9988776655 (source privée)',
    'tou_date_source': date(2026, 7, 1),
    'mecanisme_compensation': 'surplus', 'report_periode': 12,
    'plafond_annuel_kwh': Decimal('15000.00'),
    'ratio_compensation': Decimal('0.8000'), 'structure_tarif': 'tranches',
    'pays_tarif': 'MA', 'prix_unique_kwh': Decimal('1.234567'),
    'poste_haut': Decimal('1.500000'), 'poste_bas': Decimal('0.700000'),
    'prix_incluent_taxes': False,
    'taxes': [{'libelle': 'TPPAN', 'taux_pct': '20.000000',
               'assiette': 'energie', 'source': 'Loi de finances 2026'}],
    'charge_minimale_mad_jour': Decimal('3.50'),
    'indexation_tarif_pct_an': Decimal('2.500'),
    'indexation_source': 'Historique des tarifs publiés 9988776655',
    # AGR207 — pompage agricole (barème société + règle FDA datée).
    'charges_pompage_solaire': [
        {'libelle': 'Nettoyage des panneaux', 'montant_mad_an': 650.0,
         'source': 'barème société'}],
    'regle_fda_pompage': {
        'taux_pct': 30, 'plafond_mad_par_ha': 3000,
        'plafond_mad_par_kwc': 3000, 'plafond_mad_par_projet': 30000,
        'base': 'a_confirmer', 'source': 'Guide FDA édition 2024, p.20-23',
        'releve_le': '2026-10-02'},
    'taux_imposition_pct': Decimal('31.00'), 'amortissement_mode': 'lineaire',
    'amortissement_duree_ans': 10,
    'amortissement_coefficient': Decimal('1.750'),
    'fiscalite_source': 'Avis fiscal 2026 référence 5544332211',
    # CIQ211 — sensibilités C&I (gardées) + mention crédit-bail (D-CIQ-15).
    'sensibilites_ci': [
        {'cle': 'indexation_tarif', 'variation_pct': 2,
         'source': 'Hypothèse saisie le 2026-10-03'}],
    'mention_credit_bail_autorisee': True,
    'mention_credit_bail_source': 'Avis juridique 2026 référence 4433221100',
}
# Champs TEXTE LIBRE de la tarification : brouillés (non vides), jamais gardés.
TARIFF_FREE_TEXT = ('tou_source', 'indexation_source', 'fiscalite_source',
                    'mention_credit_bail_source')


def _tarif_lu_par_le_moteur(company):
    """Ce que le moteur de devis ET les règles d'audit lisent comme tarif de la
    société (``etude_horaire._reglages_tarifaires`` : tranches + charges fixes)."""
    from apps.ventes.etude_horaire import _reglages_tarifaires
    tranches, charges_fixes = _reglages_tarifaires(company)
    return (None if tranches is None else list(tranches),
            getattr(tranches, 'selective_threshold', None),
            getattr(tranches, 'boundary_tolerance', None), charges_fixes)


def _other_company():
    n = next(_seq)
    return Company.objects.create(slug=f'anon-autre-{n}', nom=f'Autre {n}')


@override_settings(DEBUG=True)
class AnonymiseRoundTripTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client, Lead
        from apps.crm.stages import NEW
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis

        call_command('seed_demo', verbosity=0)
        cls.source = Company.objects.get(slug=SOURCE_SLUG)
        cls.other = _other_company()
        Client.objects.create(company=cls.other, nom='Témoin autre société')

        client = Client.objects.create(company=cls.source, **ID_CLIENT)
        lead = Lead.objects.create(
            company=cls.source, client=client, stage=NEW,
            source=Lead.Source.OS_NATIVE, ville='Rabat',
            distributeur=Lead.Distributeur.SRM_RABAT,
            facture_hiver=Decimal('850.00'), facture_ete=Decimal('1240.50'),
            ete_differente=True, conso_mensuelle_kwh=Decimal('612.00'),
            gps_lat=Decimal('33.987654'), gps_lng=Decimal('-6.854321'),
            **ID_LEAD)
        produit = Produit.objects.filter(company=cls.source).first()
        cls.etude = {
            'conso_annuelle': 7344, 'distributeur': 'srm_rabat',
            'taux_autoconso': 0.62, 'scenario': 'hybride',
            'factures_mensuelles_reelles': [850, 900, 1240.5],
            'client_nom': 'Quenzaoui Zoubeirane',
            'telephone': '0661998877', 'latitude': 33.987654,
        }
        devis = Devis.objects.create(
            company=cls.source, reference='DEV-ANON-T0001', client=client,
            lead=lead, statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('7.50'),
            date_validite=timezone.now().date() + timedelta(days=30),
            etude_params=cls.etude)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Onduleur hybride 5kW',
            quantite=Decimal('2'), prix_unitaire=Decimal('11500.00'),
            remise=Decimal('0'))

        # Réglages de prix PERSONNALISÉS de la société source (profil +
        # tarification), et de quoi vérifier qu'aucune identité du profil ne sort.
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings
        profile = CompanyProfile.get(company=cls.source)
        for name, value in {**PROFILE_PRICING, **PROFILE_IDENTITY}.items():
            setattr(profile, name, value)
        profile.save()
        TariffSettings.objects.update_or_create(
            company=cls.source, defaults=TARIFF)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='anon-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.snapshot = self.tmp / 'latest.anon.json.gz'

    # ── helpers ──────────────────────────────────────────────────────────
    def _export(self):
        call_command('qa_export_anonymise', company=SOURCE_SLUG,
                     out=str(self.snapshot), verbosity=0)
        return gzip.decompress(self.snapshot.read_bytes())

    def _import(self):
        call_command('qa_import_anonymise', src=str(self.snapshot),
                     company_slug=TARGET_SLUG, verbosity=0)
        return Company.objects.get(slug=TARGET_SLUG)

    def _counts(self, company):
        from apps.crm.models import Client, Lead
        from apps.ventes.models import Devis, Facture
        return (Client.objects.filter(company=company).count(),
                Lead.all_objects.filter(company=company).count(),
                Devis.objects.filter(company=company).count(),
                Facture.objects.filter(company=company).count())

    # ── tests ────────────────────────────────────────────────────────────
    def test_no_source_identity_string_in_export_bytes(self):
        from apps.crm.models import Client, Lead
        from apps.stock.models import Fournisseur
        raw = self._export()
        needles = set()
        for c in Client.objects.filter(company=self.source):
            needles |= {c.nom, c.prenom, c.email, c.telephone, c.adresse,
                        c.cin, c.ice}
        for ld in Lead.all_objects.filter(company=self.source):
            needles |= {ld.nom, ld.prenom, ld.societe, ld.email, ld.telephone,
                        ld.whatsapp, ld.adresse, ld.note}
        for f in Fournisseur.objects.filter(company=self.source):
            needles |= {f.nom, f.contact_personne, f.email, f.telephone,
                        f.adresse}
        needles |= {'Quenzaoui Zoubeirane', '0661998877', '33.987654'}
        needles = {n for n in needles if n and len(n) >= 4}
        self.assertTrue(needles)
        for n in needles:
            self.assertNotIn(n.encode('utf-8'), raw,
                             'valeur d’identité source présente dans l’export')

    def test_round_trip_keeps_numbers_etudes_lines_statuses(self):
        from apps.ventes.models import Devis, Facture
        self._export()
        target = self._import()
        src = {d.reference: d for d in Devis.objects.filter(company=self.source)}
        dst = {d.reference: d for d in Devis.objects.filter(company=target)}
        self.assertEqual(set(src), set(dst))
        for ref, d in src.items():
            t = dst[ref]
            self.assertEqual(
                (d.statut, d.taux_tva, d.remise_globale, d.date_validite),
                (t.statut, t.taux_tva, t.remise_globale, t.date_validite))
            lines = sorted((ln.designation, ln.quantite, ln.prix_unitaire,
                            ln.remise) for ln in d.lignes.all())
            t_lines = sorted((ln.designation, ln.quantite, ln.prix_unitaire,
                              ln.remise) for ln in t.lignes.all())
            self.assertEqual(lines, t_lines, ref)
        etude = dst['DEV-ANON-T0001'].etude_params
        for key in ('conso_annuelle', 'distributeur', 'taux_autoconso',
                    'scenario', 'factures_mensuelles_reelles'):
            self.assertEqual(etude[key], self.etude[key], key)
        self.assertNotEqual(etude['client_nom'], self.etude['client_nom'])
        self.assertNotEqual(etude['telephone'], self.etude['telephone'])
        self.assertEqual(etude['latitude'], 34.0)  # 0,1° : niveau ville
        f_src = {f.reference: (f.statut, f.montant_ht, f.montant_ttc,
                               f.date_emission)
                 for f in Facture.objects.filter(company=self.source)}
        f_dst = {f.reference: (f.statut, f.montant_ht, f.montant_ttc,
                               f.date_emission)
                 for f in Facture.objects.filter(company=target)}
        self.assertEqual(f_src, f_dst)

    def test_identity_fields_differ_and_energy_profile_kept(self):
        from apps.crm.models import Client, Lead
        from apps.crm.stages import NEW
        self._export()
        target = self._import()
        lead = Lead.all_objects.get(company=target,
                                    facture_ete=Decimal('1240.50'))
        for field, value in ID_LEAD.items():
            self.assertNotEqual(getattr(lead, field), value, field)
        self.assertEqual(
            (lead.facture_hiver, lead.ete_differente, lead.distributeur,
             lead.conso_mensuelle_kwh, lead.ville, lead.stage),
            (Decimal('850.00'), True, 'srm_rabat', Decimal('612.00'),
             'Rabat', NEW))
        self.assertEqual(lead.gps_lat, Decimal('34.0'))
        self.assertEqual(lead.gps_lng, Decimal('-6.9'))
        # Colonnes de dédup recalculées depuis les FAUX (jamais la source).
        self.assertNotIn('334455', lead.phone_normalise or '')
        client = lead.client
        self.assertEqual(client.company_id, target.pk)
        for field, value in ID_CLIENT.items():
            self.assertNotEqual(getattr(client, field), value, field)
        # Déterminisme par valeur : même nom source → même faux.
        self.assertEqual(
            Client.objects.filter(company=target, nom=client.nom).count(),
            Client.objects.filter(company=self.source,
                                  nom=ID_CLIENT['nom']).count())

    def test_fk_integrity_after_import(self):
        from apps.crm.models import Lead
        from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
        self._export()
        target = self._import()
        for d in Devis.objects.filter(company=target):
            self.assertEqual(d.client.company_id, target.pk)
            if d.lead_id:
                self.assertEqual(d.lead.company_id, target.pk)
        self.assertTrue(LigneDevis.objects.filter(devis__company=target).exists())
        for ln in LigneDevis.objects.filter(devis__company=target):
            if ln.produit_id:
                self.assertEqual(ln.produit.company_id, target.pk)
        for bc in BonCommande.objects.filter(company=target):
            self.assertEqual(bc.client.company_id, target.pk)
            if bc.devis_id:
                self.assertEqual(bc.devis.company_id, target.pk)
        for f in Facture.objects.filter(company=target):
            self.assertEqual(f.client.company_id, target.pk)
            for ln in f.lignes.all():
                self.assertEqual(ln.produit.company_id, target.pk)
        for ld in Lead.all_objects.filter(company=target):
            if ld.client_id:
                self.assertEqual(ld.client.company_id, target.pk)
        admin = CustomUser.objects.get(username='anon_admin')
        self.assertEqual(admin.company_id, target.pk)
        self.assertFalse(Devis.objects.filter(company=target).exclude(
            created_by__isnull=True).exclude(created_by=admin).exists())

    def test_other_companies_untouched_and_reimport_idempotent(self):
        before_src = self._counts(self.source)
        before_other = self._counts(self.other)
        self._export()
        self.assertEqual(self._counts(self.source), before_src)  # lecture seule
        first = self._counts(self._import())
        second_company = self._import()
        self.assertEqual(self._counts(second_company), first)
        self.assertEqual(Company.objects.filter(slug=TARGET_SLUG).count(), 1)
        self.assertEqual(
            CustomUser.objects.filter(username='anon_admin').count(), 1)
        self.assertEqual(self._counts(self.source), before_src)
        self.assertEqual(self._counts(self.other), before_other)
        self.assertEqual(first, before_src)

    def test_import_refuses_non_anon_slug(self):
        self._export()
        with self.assertRaises(CommandError):
            call_command('qa_import_anonymise', src=str(self.snapshot),
                         company_slug=SOURCE_SLUG, verbosity=0)
        self.assertTrue(Company.objects.filter(slug=SOURCE_SLUG).exists())

    # ── réglages de prix de la société (défaut du 30/09/2026) ────────────────
    def test_pricing_configuration_round_trips(self):
        """Une société source au tarif PERSONNALISÉ → après export/import, le code
        de tarification lit les MÊMES valeurs pour la société cible (avant : la
        cible tarifait avec les défauts, et les règles d'audit dérivaient)."""
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings
        from apps.parametres.selectors import (
            residential_tranches_for, tariff_for)
        raw = self._export()
        target = self._import()

        lu_source = _tarif_lu_par_le_moteur(self.source)
        self.assertIsNotNone(lu_source[0])  # le fixture est un vrai barème société
        self.assertEqual(lu_source[3], 47.35)
        self.assertEqual(_tarif_lu_par_le_moteur(target), lu_source)
        self.assertEqual(residential_tranches_for(target),
                         residential_tranches_for(self.source))
        self.assertEqual(tariff_for(target), tariff_for(self.source))
        self.assertEqual(tariff_for(target)['onee_tarif_kwh'], 1.911)

        src_profile = CompanyProfile.objects.get(company=self.source)
        dst_profile = CompanyProfile.objects.get(company=target)
        for name in anonymise.PRICING_PROFILE_FIELDS:
            self.assertEqual(getattr(dst_profile, name),
                             getattr(src_profile, name), name)
        src_tariff = TariffSettings.objects.get(company=self.source)
        dst_tariff = TariffSettings.objects.get(company=target)
        for f in TariffSettings._meta.concrete_fields:
            if f.name in ('id', 'company', 'date_modification') or \
                    f.name in TARIFF_FREE_TEXT:
                continue
            self.assertEqual(getattr(dst_tariff, f.attname),
                             getattr(src_tariff, f.attname), f.name)
        # Prix en CHAÎNES à 9 chiffres : gardés tels quels (jamais un faux tel.).
        self.assertEqual(dst_tariff.residential_tiers, TARIFF['residential_tiers'])
        self.assertEqual(dst_tariff.tou_tarifs, TARIFF['tou_tarifs'])
        self.assertEqual(dst_tariff.taxes, TARIFF['taxes'])
        # Texte libre (source d'un tarif) : brouillé, mais PAS vidé — une grille
        # sans source serait refusée par les règles de saisie.
        for name in TARIFF_FREE_TEXT:
            self.assertTrue(getattr(dst_tariff, name), name)
            self.assertNotEqual(getattr(dst_tariff, name),
                                getattr(src_tariff, name), name)
        self.assertNotIn(b'9988776655', raw)
        self.assertNotIn(b'5544332211', raw)

    def test_company_profile_identity_and_security_never_leave(self):
        from apps.parametres.models import CompanyProfile
        raw = self._export()
        for name, value in PROFILE_IDENTITY.items():
            if isinstance(value, str) and len(value) >= 4:
                self.assertNotIn(value.encode('utf-8'), raw, name)
        payload = json.loads(raw)
        blocks = {b['label']: b for b in payload['models']}
        rows = blocks['parametres.CompanyProfile']['rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]['f']), set(anonymise.PRICING_PROFILE_FIELDS))
        target = self._import()
        profile = CompanyProfile.objects.get(company=target)
        # La société cible garde SON identité anonyme et sa politique par défaut.
        self.assertEqual((profile.nom, profile.email),
                         ('TAQINOR Anonymisé (QA)', 'anon@taqinor.local'))
        self.assertEqual(
            profile.password_min_length,
            CompanyProfile._meta.get_field('password_min_length').get_default())
        for name in ('ice', 'rib', 'banque', 'telephone', 'siret'):
            self.assertNotEqual(getattr(profile, name),
                                PROFILE_IDENTITY[name], name)

    def test_pricing_settings_import_is_idempotent_and_scoped(self):
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings
        before = (list(TariffSettings.objects.filter(
            company=self.other).values()),
            list(CompanyProfile.objects.filter(company=self.other).values()))
        self._export()
        self._import()
        second = self._import()  # la société cible est vidée puis rechargée
        self.assertEqual(
            TariffSettings.objects.filter(company__slug=TARGET_SLUG).count(), 1)
        self.assertEqual(
            CompanyProfile.objects.filter(company__slug=TARGET_SLUG).count(), 1)
        self.assertEqual(TariffSettings.objects.get(company=second).version, 7)
        self.assertEqual(
            (list(TariffSettings.objects.filter(company=self.other).values()),
             list(CompanyProfile.objects.filter(company=self.other).values())),
            before)


class AnonymiseGuardsTest(TestCase):

    @override_settings(DEBUG=False)
    def test_import_refused_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command('qa_import_anonymise', src='nimporte.anon.json.gz',
                         verbosity=0)
        self.assertFalse(Company.objects.filter(slug='taqinor-anon').exists())

    def test_out_path_guard(self):
        base = Path(settings.BASE_DIR)
        self.assertIsNotNone(anonymise.check_out_path(
            str(base / 'snap.anon.json.gz')))           # dans le code source
        self.assertIsNotNone(anonymise.check_out_path(
            str(Path(tempfile.gettempdir()) / 'snap.json.gz')))  # suffixe
        self.assertIsNone(anonymise.check_out_path(
            str(base / 'var' / 'anon' / 'latest.anon.json.gz')))
        self.assertIsNone(anonymise.check_out_path('-'))

    def test_unknown_text_field_is_scrambled_by_default(self):
        """Fail-closed : un champ AJOUTÉ demain, que personne n'a classé."""
        for label in ('crm.Lead', 'crm.Client', 'ventes.Devis',
                      'modele.Inexistant'):
            for field in (models.CharField(max_length=80),
                          models.TextField(),
                          models.EmailField(),
                          models.URLField()):
                field.set_attributes_from_name('champ_tout_neuf')
                self.assertEqual(anonymise.classify(label, field),
                                 anonymise.SCRAMBLE, (label, field))
            js = models.JSONField()
            js.set_attributes_from_name('json_tout_neuf')
            self.assertEqual(anonymise.classify(label, js), anonymise.SCRUB)

            class ChampExotique(models.Field):
                pass
            weird = ChampExotique()
            weird.set_attributes_from_name('exotique')
            self.assertEqual(anonymise.classify(label, weird), anonymise.DROP)
        scr = anonymise.Scrambler()
        self.assertNotEqual(scr.fake('generic', 'Valeur secrète'),
                            'Valeur secrète')

    def test_no_exported_text_field_is_kept_unless_listed(self):
        """Balayage du schéma RÉEL : un champ texte sans choices n'est gardé
        que s'il est nommé dans MODEL_POLICY[...]['keep']."""
        for label, _kind, model in anonymise.exported_models():
            keep = anonymise.MODEL_POLICY.get(label, {}).get('keep', set())
            for f in anonymise.concrete_fields(model):
                if f.is_relation or not isinstance(
                        f, (models.CharField, models.TextField)):
                    continue
                verdict = anonymise.classify(label, f)
                if f.name in keep or (f.choices and not isinstance(
                        f, (models.EmailField, models.URLField))):
                    continue
                self.assertIn(verdict, (anonymise.SCRAMBLE, anonymise.DROP),
                              f'{label}.{f.name}')

    def test_scrambler_deterministic_within_export_not_across(self):
        a, b = anonymise.Scrambler(), anonymise.Scrambler()
        self.assertEqual(a.fake('nom', 'Bennani'), a.fake('nom', ' bennani '))
        self.assertEqual(a.fake('phone', '+212 6 61 11 22 33'),
                         a.fake('phone', '0661112233'))
        self.assertNotEqual(a.fake('email', 'x@y.ma'), b.fake('email', 'x@y.ma'))

    def test_pricing_profile_export_is_a_whitelist(self):
        """Le profil société porte l'identité légale, le RIB, la sécurité… : on
        n'en exporte QUE les repères de prix, listés un par un."""
        label = 'parametres.CompanyProfile'
        model = anonymise.model_for(label)
        names = {f.name for f in model._meta.concrete_fields}
        # Une faute de frappe dans la liste ferait disparaître un réglage en
        # silence : chaque nom doit être un vrai champ du profil.
        self.assertEqual(anonymise.PRICING_PROFILE_FIELDS - names, set())
        exported = anonymise.exported_fields(label, model)
        self.assertEqual({f.name for f in exported},
                         set(anonymise.PRICING_PROFILE_FIELDS))
        for f in exported:
            # Nombres/énumérations gardés, JSON de barème nettoyé : jamais vidé.
            self.assertIn(anonymise.classify(label, f),
                          (anonymise.KEEP, anonymise.SCRUB), f.name)
        for never in ('nom', 'adresse', 'email', 'telephone', 'siret',
                      'tva_intra', 'ice', 'identifiant_fiscal', 'rc', 'patente',
                      'cnss', 'rib', 'banque', 'site_web', 'logo_key',
                      'signature_key', 'responsable_defaut_leads',
                      'default_installer', 'password_min_length',
                      'lockout_max_attempts', 'login_banner_text',
                      'conditions_generales', 'instructions_paiement'):
            self.assertNotIn(never, {f.name for f in exported}, never)

    def test_tariff_settings_export_drops_nothing_and_scrambles_only_sources(self):
        label = 'parametres.TariffSettings'
        model = anonymise.model_for(label)
        verdicts = {f.name: anonymise.classify(label, f)
                    for f in anonymise.exported_fields(label, model)
                    if not f.is_relation}
        # Aucun champ de tarification n'est vidé en silence (un champ numérique
        # dont le nom ressemblerait à une identité le serait), et un nouveau
        # champ JSON (SCRUB par défaut) oblige à décider s'il se garde tel quel.
        self.assertNotIn(anonymise.DROP, verdicts.values(), verdicts)
        self.assertNotIn(anonymise.SCRUB, verdicts.values(), verdicts)
        self.assertEqual(
            {n for n, v in verdicts.items() if v == anonymise.SCRAMBLE},
            set(TARIFF_FREE_TEXT))
        self.assertEqual(set(TARIFF) - set(verdicts), set())  # fixture complet


@override_settings(DEBUG=True)
class AnonymiseUniqueIdentifiersTest(TestCase):
    """Défaut du 30/09/2026 sur les vraies données : 80 leads sur 1 022 rejetés à
    l'import par ``uniq_lead_external_ref`` — deux identifiants Odoo DIFFÉRENTS de
    3 chiffres recevaient le même faux (le faux gardait la longueur : 10³
    possibilités pour 426 valeurs)."""

    SOURCE_SLUG = 'anon-ids-source'
    TARGET_SLUG = 'taqinor-anon-ids'

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead

        cls.source = Company.objects.create(
            slug=cls.SOURCE_SLUG, nom='Source identifiants')
        cls.real_ids = [str(100 + i) for i in range(400)]
        leads = [
            Lead(company=cls.source, nom=f'Prospect {i}',
                 source=Lead.Source.ODOO_IMPORT_TEST,
                 external_system='odoo', external_id=ext)
            for i, ext in enumerate(cls.real_ids)]
        # Le MÊME identifiant réel sous un AUTRE système : l'index unique
        # (société, système, identifiant) l'autorise, et son faux doit être le
        # MÊME que celui du lead Odoo (déterminisme par valeur).
        leads.append(Lead(
            company=cls.source, nom='Prospect méta',
            source=Lead.Source.META_LEAD_ADS, external_system='meta',
            external_id=cls.real_ids[0]))
        Lead.objects.bulk_create(leads)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='anon-ids-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.snapshot = self.tmp / 'ids.anon.json.gz'

    def _round_trip(self):
        call_command('qa_export_anonymise', company=self.SOURCE_SLUG,
                     out=str(self.snapshot), verbosity=0)
        out = StringIO()
        call_command('qa_import_anonymise', src=str(self.snapshot),
                     company_slug=self.TARGET_SLUG, verbosity=1, stdout=out)
        return Company.objects.get(slug=self.TARGET_SLUG), out.getvalue()

    def test_400_odoo_leads_round_trip_with_nothing_skipped(self):
        from apps.crm.models import Lead
        target, report = self._round_trip()
        self.assertNotIn('ignorées', report)
        leads = list(Lead.all_objects.filter(company=target).order_by('pk'))
        self.assertEqual(len(leads), 401)
        odoo = [ld for ld in leads if ld.external_system == 'odoo']
        self.assertEqual(len(odoo), 400)
        fakes = [ld.external_id for ld in odoo]
        self.assertEqual(len(set(fakes)), 400)  # l'index unique est respecté
        # Format gardé tant que l'espace n'est pas rempli à plus de moitié.
        self.assertTrue(all(len(x) == 3 and x.isdigit() for x in fakes))
        # Un faux n'est jamais l'identifiant réel (l'ordre des pk est celui de
        # l'export, donc celui de la source).
        for real, lead in zip(self.real_ids, odoo):
            self.assertNotEqual(lead.external_id, real)

    def test_same_real_identifier_maps_to_the_same_fake(self):
        from apps.crm.models import Lead
        target, _report = self._round_trip()
        leads = list(Lead.all_objects.filter(company=target).order_by('pk'))
        odoo = [ld for ld in leads if ld.external_system == 'odoo']
        meta = [ld for ld in leads if ld.external_system == 'meta']
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0].external_id, odoo[0].external_id)


@override_settings(DEBUG=True)
class AnonymiseSkipReportTest(TestCase):
    """L'import rapportait ``ignorées crm.Lead: IntegrityError=80`` : impossible de
    savoir POURQUOI. Il nomme désormais la contrainte de base (PostgreSQL :
    ``diag.constraint_name``), sans jamais imprimer une valeur."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='anon-skip-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    @staticmethod
    def _payload():
        """Deux leads Odoo au MÊME identifiant réel : le second viole l'index
        unique ``uniq_lead_external_ref``."""
        def lead(pk, nom):
            return {'pk': pk, 'f': {
                'nom': nom, 'source': 'os_native',
                'external_system': 'odoo', 'external_id': '777'}}
        return {'format': anonymise.FORMAT, 'models': [
            {'label': 'crm.Lead',
             'rows': [lead(1, 'Premier'), lead(2, 'Second')]}]}

    @staticmethod
    def _expected_key():
        # Le nom de contrainte vient de PostgreSQL ; une autre base ne le donne
        # pas : repli sur la classe de l'exception.
        if connection.vendor == 'postgresql':
            return 'IntegrityError[uniq_lead_external_ref]'
        return 'IntegrityError'

    def test_skipped_rows_are_counted_per_constraint_name(self):
        company = Company.objects.create(slug='anon-skip-report', nom='Rapport')
        created, skipped = anonymise.import_payload(
            self._payload(), company, SimpleNamespace(pk=None))
        self.assertEqual(created, {'crm.Lead': 1})
        self.assertEqual(skipped, {'crm.Lead': {self._expected_key(): 1}})

    def test_command_prints_the_constraint_name_and_never_a_value(self):
        snapshot = self.tmp / 'skip.anon.json.gz'
        anonymise.write_snapshot(self._payload(), str(snapshot), None)
        out = StringIO()
        call_command('qa_import_anonymise', src=str(snapshot),
                     company_slug='taqinor-anon-skip', verbosity=1, stdout=out)
        text = out.getvalue()
        self.assertIn('ignorées crm.Lead', text)
        self.assertIn(f'{self._expected_key()}=1', text)
        self.assertNotIn('777', text)  # la valeur du doublon n'est jamais dite
