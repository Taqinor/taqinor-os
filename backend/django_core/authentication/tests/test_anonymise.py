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
import shutil
import tempfile
from datetime import timedelta
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
