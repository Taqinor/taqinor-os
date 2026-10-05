"""VEIL21 — Tri IA hors ligne : export des fiches (liste blanche), import des
verdicts (erreurs FR ligne par ligne, humain jamais écrasé), script
``tools/veille_tri/trier.py`` (mode ``--a-blanc`` sans appel)."""
import importlib.util
import json
import pathlib
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company

from apps.adsengine import veille_decouverte as vd
from apps.adsengine.models import VeilleAnnonceur

RACINE = pathlib.Path(__file__).resolve().parents[5]
SCRIPT = RACINE / 'tools' / 'veille_tri' / 'trier.py'


def charger_script():
    spec = importlib.util.spec_from_file_location('veille_trier', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@override_settings(VEILLE_SOCIETES_AUTORISEES=[])
class FichesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-fiches')
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            self.dec = vd.creer_decouverte(self.company, None, {
                'mots_cles': [{'texte': 'robe', 'pays': ['FR']}],
                'plafond_appels': 5, 'plafond_pages_par_requete': 5})
        pubs = [
            {'id': str(i), 'page_id': 'A' if i < 12 else 'B',
             'page_name': 'Boutique A' if i < 12 else 'Boutique B',
             'ad_creative_bodies': [f'Texte {i}'],
             'ad_creative_link_captions': ['boutique-a.fr'],
             'ad_creative_link_titles': ['Robes'],
             'beneficiary_payers': [{'payer': 'ACME SAS'}],
             'ad_delivery_start_time': '2026-09-01',
             'ad_snapshot_url': 'https://www.facebook.com/ads/archive/'
                                f'render_ad/?id={i}&access_token=EAAPIEGE'}
            for i in range(14)]
        vd.ingerer_page(self.dec.requetes.get(),
                        {'pubs': pubs, 'a_suivant': False}, 1)

    def _exporter(self):
        sortie = StringIO()
        call_command('veille_exporter_fiches', '--decouverte',
                     str(self.dec.pk), stdout=sortie)
        return [json.loads(x) for x in sortie.getvalue().splitlines() if x]

    def test_export_liste_blanche(self):
        fiches = self._exporter()
        self.assertEqual(len(fiches), 2)
        brut = json.dumps(fiches)
        self.assertNotIn('access_token', brut)
        self.assertNotIn('render_ad', brut)
        self.assertNotIn('ad_snapshot_url', brut)
        for fiche in fiches:
            self.assertEqual(tuple(fiche), vd.CHAMPS_FICHE)
        a = next(f for f in fiches if f['page_id'] == 'A')
        self.assertEqual(len(a['textes']), 10)       # ≤ 10 dédoublonnés
        self.assertEqual(a['domaines'], ['boutique-a.fr'])
        self.assertEqual(a['payeurs'], ['ACME SAS'])
        self.assertEqual(a['debut_min'], '2026-09-01')

    def test_export_exclut_decision_humaine(self):
        a = VeilleAnnonceur.objects.get(page_id='A')
        vd.poser_verdict_humain(a, None, 'incertain')
        self.assertEqual([f['page_id'] for f in self._exporter()], ['B'])

    def _importer(self, lignes):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False,
                                         encoding='utf-8') as fichier:
            for ligne in lignes:
                fichier.write((ligne if isinstance(ligne, str)
                               else json.dumps(ligne)) + '\n')
        sortie, erreurs = StringIO(), StringIO()
        call_command('veille_importer_verdicts', fichier.name, '--company',
                     str(self.company.id), stdout=sortie, stderr=erreurs)
        pathlib.Path(fichier.name).unlink()
        return sortie.getvalue(), erreurs.getvalue()

    def test_import_refus_ligne_par_ligne(self):
        sortie, erreurs = self._importer([
            {'page_id': 'A', 'classe': 'vendeur', 'confiance': 0.9,
             'dropshipper': 'non', 'indices': []},                  # modele ?
            {'page_id': 'A', 'classe': 'dropshipper', 'modele': 'haiku'},
            'pas du json',
            {'page_id': 'B', 'classe': 'vendeur', 'confiance': 0.8,
             'dropshipper': 'oui', 'modele': 'claude-haiku',
             'indices': [{'champ': 'page_name', 'valeur': 'Boutique B'}],
             'jetons_entree': 120, 'jetons_sortie': 30},
        ])
        self.assertIn('ligne 1 : « modele » manquant', erreurs)
        self.assertIn('ligne 2 : classe hors contrat', erreurs)
        self.assertIn('ligne 3 : JSON illisible', erreurs)
        self.assertIn('1 importé(s)', sortie)
        b = VeilleAnnonceur.objects.get(page_id='B')
        self.assertEqual(b.classe, 'vendeur')
        v = b.verdict_courant
        self.assertEqual((v.decide_par, v.modele, v.jetons_entree,
                          v.jetons_sortie), ('ia', 'claude-haiku', 120, 30))
        self.assertEqual(b.dropshipper_probable, 'oui')
        a = VeilleAnnonceur.objects.get(page_id='A')
        self.assertEqual(a.classe, 'incertain')

    def test_import_n_ecrase_jamais_l_humain(self):
        a = VeilleAnnonceur.objects.get(page_id='A')
        vd.poser_verdict_humain(a, None, 'hors_sujet', 'non')
        sortie, erreurs = self._importer([
            {'page_id': 'A', 'classe': 'vendeur', 'modele': 'haiku',
             'dropshipper': 'oui'}])
        self.assertIn('décision humaine conservée', erreurs)
        a.refresh_from_db()
        self.assertEqual(a.classe, 'hors_sujet')
        self.assertEqual(a.dropshipper_probable, 'non')


@mock.patch('subprocess.run', side_effect=AssertionError('aucun appel'))
class ScriptTrierTests(SimpleTestCase):
    def setUp(self):
        if not SCRIPT.exists():
            self.skipTest('tools/ absent de ce conteneur')
        self.trier = charger_script()

    def test_a_blanc_trois_fiches_sans_appel(self, _run):
        fiches = [{'page_id': str(i), 'page_name': f'P{i}'} for i in range(3)]
        with tempfile.TemporaryDirectory() as dossier:
            entree = pathlib.Path(dossier) / 'fiches.jsonl'
            sortie = pathlib.Path(dossier) / 'verdicts.jsonl'
            entree.write_text('\n'.join(json.dumps(f) for f in fiches),
                              encoding='utf-8')
            self.assertEqual(self.trier.main(
                [str(entree), str(sortie), '--a-blanc']), 0)
            verdicts = [json.loads(x) for x in
                        sortie.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(verdicts), 3)
        for verdict in verdicts:
            self.assertEqual(verdict['classe'], 'incertain')
            self.assertEqual(verdict['modele'], 'a-blanc')
            self.assertEqual(verdict['jetons_entree'], 0)
        _run.assert_not_called()

    def test_deux_passages_et_jetons_du_champ_usage(self, _run):
        appels = []

        def executer(commande, input, **kw):
            appels.append(commande)
            partie = input[input.index('## Fiches'):]
            fiches = json.loads(partie[partie.index('['):])
            confiance = 0.5 if 'haiku' in commande else 0.95
            result = json.dumps([{'page_id': f['page_id'],
                                  'classe': 'vendeur',
                                  'confiance': confiance,
                                  'dropshipper': 'non'} for f in fiches])
            sortie = {'result': result, 'total_cost_usd': 999,
                      'usage': {'input_tokens': 100,
                                'cache_read_input_tokens': 1,
                                'output_tokens': 11}}
            return mock.Mock(stdout=json.dumps(sortie))

        fiches = [{'page_id': 'a'}, {'page_id': 'b'}]
        verdicts = self.trier.trier(fiches, executer=executer, seuil=0.7)
        self.assertEqual(len(appels), 2)
        self.assertIn('haiku', appels[0])
        self.assertIn('sonnet', appels[1])
        # 101 + 101 jetons d'entrée sur 2 fiches ; 11 + 11 en sortie
        self.assertEqual(sum(v['jetons_entree'] for v in verdicts), 202)
        self.assertEqual(sum(v['jetons_sortie'] for v in verdicts), 22)
        self.assertEqual({v['modele'] for v in verdicts}, {'sonnet'})
