"""CRX35 — code mort et pièges du CRM, retirés avec leur preuve.

Cinq constats de l'audit L3, chacun vérifié ici :

1. ``services._next_round_robin_owner_for_new_lead`` — zéro référence dans
   tout le dépôt : une deuxième implémentation de round-robin, jamais appelée.
2. ``Playbook.bloquant`` — promettait un blocage dur du changement d'étape ;
   AUCUN code ne lisait la colonne. Retiré (migration 0088).
3. Chemin Odoo — ``prenom`` était LU sans qu'aucune en-tête ne le produise, et
   un lead qui n'apportait que ``mobile`` arrivait sans ``telephone`` : la
   dédup indexée QW10 était aveugle sur lui.
4. Export clients — la colonne « RIB » était TOUJOURS vide (``crm.Client``
   n'a pas de champ ``rib``).
5. ``Lead.Source.ODOO_IMPORT_TEST`` — libellé « Import test Odoo » alors que
   la synchronisation Odoo→ERP est en production depuis le 01/09/2026. La
   VALEUR en base est inchangée.
"""
import os
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.crm import exports, services
from apps.crm.management.commands import import_odoo_leads as odoo
from apps.crm.models import Lead, Playbook
from apps.crm.serializers import PlaybookSerializer
from apps.crm.services import normalize_phone
from authentication.models import Company

#: ``backend/django_core`` — racine du code Python de l'ERP.
_RACINE_DJANGO = Path(services.__file__).resolve().parents[2]


class RoundRobinMortTests(TestCase):
    def test_la_fonction_a_disparu(self):
        self.assertFalse(
            hasattr(services, '_next_round_robin_owner_for_new_lead'))

    def test_le_round_robin_reellement_utilise_survit(self):
        """XMKT21 en a un VRAI, appelé au franchissement du seuil MQL : on ne
        supprime pas les deux."""
        self.assertTrue(hasattr(services, '_next_round_robin_commercial'))

    def test_plus_aucune_reference_dans_le_depot(self):
        restes = []
        for chemin in _RACINE_DJANGO.rglob('*.py'):
            if '__pycache__' in chemin.parts:
                continue
            if chemin.name == Path(__file__).name:
                continue
            if '_next_round_robin_owner_for_new_lead' in chemin.read_text(
                    encoding='utf-8'):
                restes.append(str(chemin.relative_to(_RACINE_DJANGO)))
        self.assertEqual(restes, [])


class PlaybookBloquantRetireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX35', slug='taqinor-crx35')

    def test_le_champ_n_existe_plus_sur_le_modele(self):
        noms = {f.name for f in Playbook._meta.get_fields()}
        self.assertNotIn('bloquant', noms)

    def test_le_serializer_ne_l_expose_plus(self):
        playbook = Playbook.objects.create(
            company=self.company, nom='Playbook CRX35', actif=True)
        donnees = PlaybookSerializer(playbook).data
        self.assertNotIn('bloquant', donnees)
        # Les champs utiles restent exposés — on n'a pas vidé le contrat.
        for attendu in ('id', 'nom', 'actif', 'condition', 'etapes'):
            self.assertIn(attendu, donnees)


class MappingsOdooTests(TestCase):
    """Vérifié PAR L'IMPORT RÉEL (fichier CSV synthétique → commande), jamais
    par une regex sur le code source."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX35 Odoo', slug='taqinor-crx35-odoo')
        self._fichiers = []

    def tearDown(self):
        for chemin in self._fichiers:
            try:
                os.remove(chemin)
            except OSError:
                pass

    def _importer(self, csv_contenu):
        fd, chemin = tempfile.mkstemp(suffix='.csv')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(csv_contenu)
        self._fichiers.append(chemin)
        call_command('import_odoo_leads', chemin,
                     '--company', self.company.slug)

    def test_prenom_a_desormais_une_source(self):
        """La lecture ``fields.get('prenom')`` était morte : aucune en-tête ne
        produisait la clé, le prénom d'un fichier restait toujours vide."""
        self.assertEqual(odoo.ODOO_FIELD_MAP.get('prenom'), 'prenom')
        self._importer(
            'id,name,prenom,email_from,phone,stage_id\n'
            '901,Benali,Amina,amina@exemple.test,0612000901,New\n')
        lead = Lead.objects.get(company=self.company, external_id='901')
        self.assertEqual(lead.prenom, 'Amina')

    def test_mobile_reste_le_numero_whatsapp(self):
        """On ne change PAS la destination : `mobile` est bien le numéro que
        wa.me utilise. C'est le repli téléphone qui manquait."""
        self.assertEqual(odoo.ODOO_FIELD_MAP.get('mobile'), 'whatsapp')

    def test_lead_sans_phone_mais_avec_mobile_reste_dedupable(self):
        """LE piège : un lead Odoo qui n'apporte QUE ``mobile`` arrivait avec
        ``telephone`` vide, donc ``phone_normalise`` vide — la dédup indexée
        (QW10) ne le voyait jamais."""
        self._importer(
            'id,name,mobile,stage_id\n'
            '902,Sans Phone,0612000902,New\n')

        lead = Lead.objects.get(company=self.company, external_id='902')
        self.assertEqual(lead.whatsapp, '0612000902')
        self.assertEqual(lead.telephone, '0612000902')
        self.assertEqual(lead.phone_normalise, normalize_phone('0612000902'))
        self.assertEqual(
            [autre.pk for autre in services.find_duplicates_by_contact(
                self.company, phone='0612000902')],
            [lead.pk])

    def test_phone_reste_prioritaire_sur_mobile(self):
        """Le repli ne doit JAMAIS écraser un vrai ``phone``."""
        self._importer(
            'id,name,phone,mobile,stage_id\n'
            '903,Deux Numeros,0612000903,0700000903,New\n')

        lead = Lead.objects.get(company=self.company, external_id='903')
        self.assertEqual(lead.telephone, '0612000903')
        self.assertEqual(lead.whatsapp, '0700000903')


class ExportClientsTests(TestCase):
    def test_la_colonne_rib_a_disparu(self):
        self.assertNotIn('RIB', exports.CLIENT_EXPORT_HEADERS)

    def test_les_identifiants_legaux_restent(self):
        for attendu in ('ICE', 'IF', 'RC', 'CIN'):
            self.assertIn(attendu, exports.CLIENT_EXPORT_HEADERS)

    def test_le_modele_client_n_a_effectivement_pas_de_rib(self):
        """La raison du retrait, prouvée plutôt qu'affirmée."""
        from apps.crm.models import Client
        noms = {f.name for f in Client._meta.get_fields()}
        self.assertNotIn('rib', noms)


class LibelleSourceOdooTests(TestCase):
    def test_la_valeur_en_base_est_inchangee(self):
        """Des milliers de lignes portent cette valeur : la renommer serait
        une migration de données pour rien."""
        self.assertEqual(Lead.Source.ODOO_IMPORT_TEST.value,
                         'odoo_import_test')

    def test_le_libelle_ne_dit_plus_test(self):
        libelle = Lead.Source.ODOO_IMPORT_TEST.label
        self.assertEqual(libelle, 'Import Odoo')
        self.assertNotIn('test', libelle.lower())
