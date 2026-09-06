"""AUD311 (SCA42) — les 5 sites nommés passent enfin ``company=``.

``store_attachment(file)`` appelé SANS ``company=`` retombe en silence sur la
clé PLATE ``attachments/{uuid}.ext`` au lieu du préfixe SCA42
``attachments/{company_id}/{uuid}.ext``.

REQUALIFIÉ (deux verdicts concordants) : non exploitable aujourd'hui — toute
lecture applicative est déjà scopée société via ``Attachment.company`` et aucun
endpoint n'accepte un ``file_key`` arbitraire. C'est une défense en profondeur.

Le garde SCA42 ne détectait que la CONSTRUCTION LITTÉRALE d'une clé plate,
jamais un appelant qui OMET l'argument — la façon dont une clé plate naît
réellement. Cette classe entière lui était invisible ; ce test verrouille les
deux moitiés : les 5 sites corrigés ET le détecteur étendu.
"""
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[2]

#: Les 5 sites nommés par le constat (4 installations + 1 ventes).
SITES = (
    'apps/installations/views/intervention.py',
    'apps/installations/views/installation.py',
    'apps/ventes/views/bon_commande.py',
)


class TestCleStockageScopeeSociete(SimpleTestCase):
    def test_les_cinq_sites_passent_company(self):
        """ROUGE avant le correctif : les 5 appels étaient nus."""
        from apps.records.platform_guards import (
            scan_store_attachment_sans_company)
        for relpath in SITES:
            with self.subTest(fichier=relpath):
                texte = (DJANGO_CORE / relpath).read_text(encoding='utf-8')
                self.assertIn('store_attachment', texte)
                self.assertFalse(
                    scan_store_attachment_sans_company(relpath, texte),
                    f'{relpath} appelle encore store_attachment sans company=')

    def test_le_detecteur_voit_un_appel_nu(self):
        """Preuve que le garde étendu VOIT : sans cette preuve, un garde vert
        ne dit rien (leçon OR3 — garde sémantique, jamais un nombre épinglé)."""
        from apps.records.platform_guards import (
            scan_store_attachment_sans_company)
        nu = ('from apps.records.storage import store_attachment\n'
              'meta, err = store_attachment(fichier)\n')
        avec = 'meta, err = store_attachment(fichier, company=obj.company)\n'
        self.assertTrue(
            scan_store_attachment_sans_company('apps/neuf/views.py', nu))
        self.assertFalse(
            scan_store_attachment_sans_company('apps/neuf/views.py', avec))

    def test_les_fichiers_geles_ne_rougissent_pas(self):
        """La reprise se fait app par app : les 11 fichiers qui omettent
        encore l'argument sont gelés, pas ignorés."""
        from apps.records.platform_guards import (
            GRANDFATHERED_STORE_ATTACHMENT_CALLERS,
            scan_store_attachment_sans_company)
        nu = 'meta, err = store_attachment(fichier)\n'
        for relpath in GRANDFATHERED_STORE_ATTACHMENT_CALLERS:
            with self.subTest(fichier=relpath):
                self.assertFalse(
                    scan_store_attachment_sans_company(relpath, nu))
        # Aucun des 5 sites corrigés n'a été glissé dans le gel.
        for relpath in SITES:
            self.assertNotIn(relpath, GRANDFATHERED_STORE_ATTACHMENT_CALLERS)
