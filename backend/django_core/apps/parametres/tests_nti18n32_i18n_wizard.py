"""NTI18N32 — assistant de migration "chaîne en dur -> clé i18n".

Couvre la logique pure (``i18n_wizard_core``) et la commande
``manage.py i18n_wizard`` de bout en bout sur des fixtures TEMPORAIRES
(jamais les vrais catalogues `frontend/src/i18n/catalogs/*.json` — la
commande accepte `--catalogs-dir` explicitement pour cela).
"""
import json
import os
import shutil
import tempfile

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.parametres.i18n_wizard_core import (
    appliquer_remplacements,
    domaine_et_section,
    entrees_catalogues,
    litteraux_candidats,
    proposer_cle,
)

JSX_FIXTURE = """export default function Exemple() {
  return (
    <div>
      <h1>Bonjour le monde</h1>
      <button title="Enregistrer">Envoyer</button>
    </div>
  );
}
"""


class LitterauxCandidatsTests(SimpleTestCase):
    def test_detects_jsx_child_text(self):
        candidats = litteraux_candidats(JSX_FIXTURE)
        textes = [c['texte'] for c in candidats]
        self.assertIn('Bonjour le monde', textes)
        self.assertIn('Envoyer', textes)

    def test_detects_attribute_value(self):
        candidats = litteraux_candidats(JSX_FIXTURE)
        attributs = [(c['attribut'], c['texte']) for c in candidats
                     if c['type'] == 'attribut']
        self.assertIn(('title', 'Enregistrer'), attributs)

    def test_ignores_jsx_expressions(self):
        contenu = '<span>{variable}</span>'
        self.assertEqual(litteraux_candidats(contenu), [])

    def test_ignores_purely_numeric_text(self):
        contenu = '<span>123</span>'
        self.assertEqual(litteraux_candidats(contenu), [])


class ProposerCleTests(SimpleTestCase):
    def test_key_format(self):
        cle = proposer_cle('ventes', 'devis_form', 'Bonjour le monde')
        self.assertEqual(cle, 'ventes.devis_form.bonjour_le_monde')

    def test_accents_stripped(self):
        cle = proposer_cle('crm', 'lead', 'Créer le prospect')
        self.assertEqual(cle, 'crm.lead.creer_le_prospect')

    def test_domaine_et_section_from_path(self):
        domaine, section = domaine_et_section(
            'frontend/src/features/ventes/DevisForm.jsx')
        self.assertEqual(domaine, 'ventes')
        self.assertEqual(section, 'devisform')


class AppliquerRemplacementsTests(SimpleTestCase):
    def test_replaces_by_position_not_global_string_replace(self):
        contenu = '<span>Envoyer</span><span>Envoyer</span>'
        candidats = litteraux_candidats(contenu)
        # Ne confirme QUE le premier des deux littéraux identiques.
        remplacements = [{**candidats[0], 'cle': 'x.y.envoyer'}]
        resultat = appliquer_remplacements(contenu, remplacements)
        self.assertEqual(
            resultat, "<span>{t('x.y.envoyer')}</span><span>Envoyer</span>")

    def test_entrees_catalogues_fr_reel_en_ar_todo(self):
        remplacements = [
            {'texte': 'Bonjour', 'cle': 'ui.h1.bonjour'},
        ]
        entrees = entrees_catalogues(remplacements)
        self.assertEqual(entrees['fr']['ui.h1.bonjour'], 'Bonjour')
        self.assertEqual(entrees['en']['ui.h1.bonjour'], 'TODO_TRADUCTION')
        self.assertEqual(entrees['ar']['ui.h1.bonjour'], 'TODO_TRADUCTION')


class I18nWizardCommandTests(SimpleTestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='nti18n32-')
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.jsx_dir = os.path.join(self.tmp_dir, 'ventes')
        os.makedirs(self.jsx_dir)
        self.jsx_path = os.path.join(self.jsx_dir, 'Exemple.jsx')
        with open(self.jsx_path, 'w', encoding='utf-8') as f:
            f.write(JSX_FIXTURE)

        self.catalogs_dir = os.path.join(self.tmp_dir, 'catalogs')
        os.makedirs(self.catalogs_dir)
        for langue in ('fr', 'en', 'ar'):
            with open(
                    os.path.join(self.catalogs_dir, f'{langue}.json'),
                    'w', encoding='utf-8') as f:
                json.dump({'existing.key': 'valeur'}, f)

    def test_dry_run_never_writes_anything(self):
        call_command(
            'i18n_wizard', self.jsx_path, '--dry-run',
            catalogs_dir=self.catalogs_dir)
        with open(self.jsx_path, encoding='utf-8') as f:
            self.assertEqual(f.read(), JSX_FIXTURE)
        with open(
                os.path.join(self.catalogs_dir, 'fr.json'),
                encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'existing.key': 'valeur'})

    def test_yes_applies_replacement_and_updates_catalogs(self):
        call_command(
            'i18n_wizard', self.jsx_path, '--yes',
            catalogs_dir=self.catalogs_dir)

        with open(self.jsx_path, encoding='utf-8') as f:
            nouveau_contenu = f.read()
        self.assertIn(
            "{t('ventes.exemple.bonjour_le_monde')}", nouveau_contenu)
        self.assertIn("{t('ventes.exemple.envoyer')}", nouveau_contenu)
        self.assertNotIn('Bonjour le monde', nouveau_contenu)

        with open(
                os.path.join(self.catalogs_dir, 'fr.json'),
                encoding='utf-8') as f:
            fr = json.load(f)
        with open(
                os.path.join(self.catalogs_dir, 'en.json'),
                encoding='utf-8') as f:
            en = json.load(f)
        with open(
                os.path.join(self.catalogs_dir, 'ar.json'),
                encoding='utf-8') as f:
            ar = json.load(f)

        # Les entrées PRÉ-EXISTANTES du catalogue sont conservées (additif).
        self.assertEqual(fr['existing.key'], 'valeur')
        self.assertEqual(fr['ventes.exemple.bonjour_le_monde'], 'Bonjour le monde')
        self.assertEqual(en['ventes.exemple.bonjour_le_monde'], 'TODO_TRADUCTION')
        self.assertEqual(ar['ventes.exemple.bonjour_le_monde'], 'TODO_TRADUCTION')

    def test_missing_file_raises_clear_error(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command(
                'i18n_wizard', '/chemin/inexistant.jsx',
                catalogs_dir=self.catalogs_dir)
