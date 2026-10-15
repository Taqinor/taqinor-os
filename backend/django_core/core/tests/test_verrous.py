"""ENF15 — ``core.verrous.sous_verrou`` : atomique, ligne verrouillée puis relue."""
from unittest import mock

from django.test import SimpleTestCase

from core.verrous import sous_verrou


class _Doc:
    pk = 7
    company_id = 3

    def __init__(self):
        self.releu = False

    def refresh_from_db(self):
        self.releu = True


class SousVerrouTests(SimpleTestCase):

    def _decore(self):
        @sous_verrou('doc')
        def fonction(doc, *, option=1):
            return (doc.releu, option)

        return fonction

    def test_verrouille_la_ligne_de_la_societe_puis_relit_avant_le_corps(self):
        doc = _Doc()
        gestionnaire = mock.MagicMock()
        _Doc._default_manager = gestionnaire
        with mock.patch('core.verrous.transaction.atomic'):
            resultat = self._decore()(doc, option=2)
        self.assertEqual(resultat, (True, 2))
        gestionnaire.select_for_update.return_value.filter.assert_called_once_with(
            pk=7, company_id=3)

    def test_sans_societe_filtre_sur_le_pk_seul(self):
        doc = _Doc()
        doc.company_id = None
        gestionnaire = mock.MagicMock()
        _Doc._default_manager = gestionnaire
        with mock.patch('core.verrous.transaction.atomic'):
            self._decore()(doc)
        gestionnaire.select_for_update.return_value.filter.assert_called_once_with(pk=7)
