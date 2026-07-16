"""QX52 — parité mode↔type sur 4 modes (côté webhook).

Le mapping _MARKET_MODE_ALIASES du site → Lead.type_installation doit être
cohérent : commercial→commercial, professionnel/professional→industriel, et
aucun mode ne tombe dans le libellé d'un autre. (Rien à changer côté webhook —
ce test verrouille la cohérence.)

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qx52_mode_parity -v 2
"""
from django.test import SimpleTestCase

from .webhooks import _MARKET_MODE_ALIASES
from .models import Lead


class TestMarketModeAliases(SimpleTestCase):
    def test_commercial_routes_to_commercial(self):
        self.assertEqual(_MARKET_MODE_ALIASES['commercial'], 'commercial')

    def test_professionnel_routes_to_industriel(self):
        self.assertEqual(_MARKET_MODE_ALIASES['professionnel'], 'industriel')
        self.assertEqual(_MARKET_MODE_ALIASES['professional'], 'industriel')

    def test_four_canonical_modes_present(self):
        self.assertEqual(_MARKET_MODE_ALIASES['residentiel'], 'residentiel')
        self.assertEqual(_MARKET_MODE_ALIASES['industriel'], 'industriel')
        self.assertEqual(_MARKET_MODE_ALIASES['agricole'], 'agricole')

    def test_no_mode_falls_into_another_label(self):
        # Chaque valeur cible est un type d'installation valide et self-cohérent :
        # un mode source ne doit jamais viser un libellé qui n'est pas le sien.
        valid = {'residentiel', 'commercial', 'industriel', 'agricole'}
        self.assertTrue(set(_MARKET_MODE_ALIASES.values()) <= valid)
        # commercial et industriel restent DISTINCTS (le bug historique corrigé).
        self.assertNotEqual(_MARKET_MODE_ALIASES['commercial'],
                            _MARKET_MODE_ALIASES['industriel'])

    def test_lead_has_commercial_type(self):
        # Le choix commercial existe côté modèle Lead (parité de bout en bout).
        self.assertIn('commercial', dict(Lead.TypeInstallation.choices))
