"""NTADM43 — garde-fou écrasement de l'import CSV du référentiel Entités.

`import_service.commit()` rapproche les lignes par `(company, code)` : une
entité DÉJÀ EN BASE peut donc voir son `nom`/`parent` réécrit par un fichier
obsolète. Ces tests couvrent les trois protections ajoutées, qui réutilisent
la primitive plateforme `apps.dataimport.services` (jamais un diff/journal
maison) : aperçu avant écriture, remplissage seul par défaut, journal
réversible (AuditLog + ImportJob/ImportJobRow).
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from ..models import Entite
from ..services import creer_entite


def _company(nom='EntiteImportCo'):
    return Company.objects.create(nom=nom)


class ApercuEcrasementTests(TestCase):
    """`dry_run()` signale les écrasements AVANT toute écriture."""

    def setUp(self):
        self.company = _company()

    def test_apercu_signale_ecrasement_champ_par_champ_sans_ecrire(self):
        from ..import_service import dry_run

        creer_entite(self.company, nom='Ancien Nom', code='H')
        csv_bytes = b'code,nom,code_parent\nH,Nouveau Nom,\n'

        result = dry_run(csv_bytes, 'f.csv', self.company)

        self.assertEqual(result['erreurs'], [])
        self.assertEqual(len(result['conflits']), 1)
        conflit = result['conflits'][0]
        self.assertEqual(conflit['code'], 'H')
        self.assertEqual(conflit['ecrasements'], [
            {'champ': 'nom', 'ancienne': 'Ancien Nom', 'nouvelle': 'Nouveau Nom'},
        ])
        # L'aperçu n'écrit rien : la fiche réelle n'a pas bougé.
        h = Entite.objects.get(company=self.company, code='H')
        self.assertEqual(h.nom, 'Ancien Nom')

    def test_apercu_ne_signale_rien_pour_une_creation(self):
        from ..import_service import dry_run

        csv_bytes = b'code,nom,code_parent\nNEW,Toute Nouvelle,\n'
        result = dry_run(csv_bytes, 'f.csv', self.company)
        self.assertEqual(result['conflits'], [])


class RemplissageSeulTests(TestCase):
    """`commit()` par défaut (`ecraser=False`) : jamais de remplacement silencieux."""

    def setUp(self):
        self.company = _company()

    def test_remplissage_seul_preserve_champ_deja_rempli_et_le_signale_dans_refuses(self):
        from ..import_service import commit

        creer_entite(self.company, nom='Ancien Nom', code='H')
        csv_bytes = b'code,nom,code_parent\nH,Nouveau Nom,\n'

        result = commit(csv_bytes, 'f.csv', self.company)

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['ecrasements'], [])
        self.assertEqual(len(result['refuses']), 1)
        self.assertEqual(result['refuses'][0]['champ'], 'nom')
        self.assertEqual(result['refuses'][0]['ancienne'], 'Ancien Nom')
        self.assertEqual(result['refuses'][0]['nouvelle'], 'Nouveau Nom')
        # La valeur réelle n'a PAS été remplacée.
        h = Entite.objects.get(company=self.company, code='H')
        self.assertEqual(h.nom, 'Ancien Nom')

    def test_mise_a_jour_legitime_remplissage_champ_vide_fonctionne_sans_opt_in(self):
        """Un rattachement de parent encore VIDE se remplit sans `ecraser=True` :
        ce n'est jamais destructeur (le garde-fou ne bloque que les
        remplacements de valeurs déjà saisies)."""
        from ..import_service import commit

        holding = creer_entite(self.company, nom='Holding', code='H')
        filiale = creer_entite(self.company, nom='Filiale', code='F1')
        self.assertIsNone(filiale.parent_id)
        csv_bytes = b'code,nom,code_parent\nH,Holding,\nF1,Filiale,H\n'

        result = commit(csv_bytes, 'f.csv', self.company)

        self.assertEqual(result['erreurs'], [])
        filiale.refresh_from_db()
        self.assertEqual(filiale.parent_id, holding.id)

    def test_cellule_vide_ne_vide_jamais_une_valeur_existante(self):
        """Une ligne sans `code_parent` ne touche jamais un rattachement déjà
        en place — vrai même avec `ecraser=True`, qui n'autorise que le
        remplacement d'une valeur EXPLICITEMENT fournie par le fichier."""
        from ..import_service import commit

        holding = creer_entite(self.company, nom='Holding', code='H')
        filiale = creer_entite(self.company, nom='Filiale', code='F1', parent=holding)
        csv_bytes = b'code,nom,code_parent\nF1,Filiale,\n'

        commit(csv_bytes, 'f.csv', self.company, ecraser=True)

        filiale.refresh_from_db()
        self.assertEqual(filiale.parent_id, holding.id)


class EcraserExpliciteTests(TestCase):
    """`commit(..., ecraser=True)` : opt-in explicite, tout reste réversible."""

    def setUp(self):
        self.company = _company()

    def test_ecraser_applique_le_remplacement_et_journalise_la_valeur_precedente(self):
        from ..import_service import commit
        from apps.dataimport.models import ImportJob
        from apps.audit.models import AuditLog

        h = creer_entite(self.company, nom='Ancien Nom', code='H')
        csv_bytes = b'code,nom,code_parent\nH,Nouveau Nom,\n'

        result = commit(csv_bytes, 'f.csv', self.company, ecraser=True)

        self.assertEqual(len(result['ecrasements']), 1)
        ecr = result['ecrasements'][0]
        self.assertEqual(ecr['champ'], 'nom')
        self.assertEqual(ecr['ancienne'], 'Ancien Nom')
        self.assertEqual(ecr['nouvelle'], 'Nouveau Nom')

        h.refresh_from_db()
        self.assertEqual(h.nom, 'Nouveau Nom')

        # Journal du lot (ImportJob/ImportJobRow) — même primitive que le
        # reste de la plateforme.
        job = ImportJob.objects.filter(company=self.company, target='entites').first()
        self.assertIsNotNone(job)
        self.assertTrue(job.ecraser)
        row = job.rows.get(ligne=2)
        self.assertEqual(row.modifications, [
            {'champ': 'nom', 'ancienne': 'Ancien Nom', 'nouvelle': 'Nouveau Nom',
             'ecrasement': True},
        ])

        # Ligne d'audit (valeur précédente retrouvable même sans le job).
        ct = ContentType.objects.get_for_model(Entite)
        logs = AuditLog.objects.filter(content_type=ct, object_id=str(h.pk))
        self.assertTrue(logs.exists())
        self.assertIn('Ancien Nom', logs.first().detail)

    def test_ecraser_legitime_toujours_possible_pour_une_vraie_mise_a_jour_de_masse(self):
        """Le garde-fou ne doit jamais empêcher une VRAIE mise à jour de masse
        quand elle est explicitement demandée."""
        from ..import_service import commit

        creer_entite(self.company, nom='Ancien A', code='A')
        creer_entite(self.company, nom='Ancien B', code='B')
        csv_bytes = b'code,nom,code_parent\nA,Nouveau A,\nB,Nouveau B,\n'

        result = commit(csv_bytes, 'f.csv', self.company, ecraser=True)

        self.assertEqual(result['updated'], 2)
        self.assertEqual(len(result['ecrasements']), 2)
        self.assertEqual(
            Entite.objects.get(company=self.company, code='A').nom, 'Nouveau A')
        self.assertEqual(
            Entite.objects.get(company=self.company, code='B').nom, 'Nouveau B')


class IsolationMultiTenantImportTests(TestCase):
    """Le rapprochement `(company, code)` ne traverse jamais les sociétés."""

    def setUp(self):
        self.company_a = _company('A')
        self.company_b = _company('B')

    def test_rapprochement_jamais_croise_entre_companies(self):
        from ..import_service import commit

        entite_a = creer_entite(self.company_a, nom='Existant chez A', code='X')
        # Company B n'a PAS de code 'X' : la ligne doit créer une nouvelle
        # entité pour B, jamais toucher celle de A.
        csv_bytes = b'code,nom,code_parent\nX,Nouveau chez B,\n'

        result = commit(csv_bytes, 'f.csv', self.company_b, ecraser=True)

        self.assertEqual(result['created'], 1)
        self.assertEqual(result['updated'], 0)

        entite_a.refresh_from_db()
        self.assertEqual(entite_a.nom, 'Existant chez A')
        entite_b = Entite.objects.get(company=self.company_b, code='X')
        self.assertEqual(entite_b.nom, 'Nouveau chez B')
