"""NTI18N25 — glossaire terminologique métier par langue (statuts).

Câblage du composant frontend `StatusPill` (frontend/src/ui) : HORS
périmètre de cette lane — non couvert ici (voir docstring de
`apps.parametres.i18n_labels`).
"""
from django.test import TestCase

from authentication.models import Company
from apps.parametres.i18n_labels import statut_label
from apps.parametres.models_statuses import StatutConfig
from apps.parametres.selectors import statut_libelle


def _company(slug='nti18n25-co', nom='NTI18N25 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class StatutLabelTests(TestCase):
    def test_devis_envoye_en_and_ar(self):
        self.assertEqual(statut_label('devis', 'envoye', 'fr'), 'Envoyé')
        self.assertEqual(statut_label('devis', 'envoye', 'en'), 'Sent')
        self.assertEqual(statut_label('devis', 'envoye', 'ar'), 'مُرسَل')

    def test_facture_en_retard(self):
        self.assertEqual(
            statut_label('facture', 'en_retard', 'en'), 'Overdue')

    def test_ticket_cloture(self):
        self.assertEqual(statut_label('ticket', 'cloture', 'ar'), 'مغلق')

    def test_chantier_legacy_statut_still_covered(self):
        # Les statuts HÉRITÉS (chantiers d'avant le funnel N1) doivent rester
        # traduits, jamais affichés en clé brute.
        self.assertEqual(
            statut_label('chantier', 'raccordement_onee', 'en'),
            'Grid connection (ONEE)')

    def test_unknown_langue_falls_back_to_fr(self):
        self.assertEqual(
            statut_label('devis', 'envoye', 'darija'), 'Envoyé')

    def test_unknown_key_returns_canonical_key_never_raises(self):
        self.assertEqual(statut_label('devis', 'inconnu', 'en'), 'inconnu')
        self.assertEqual(statut_label('inconnu', 'x', 'en'), 'x')

    def test_never_touches_stages_py_keys(self):
        # Garde-fou de règle #2 fondateur : aucune clé STAGES.py (NEW,
        # CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD) n'apparaît dans le
        # catalogue de statuts métier.
        from apps.parametres.i18n_labels import STATUT_LABELS
        stages_keys = {
            'NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD'}
        for domaine_map in STATUT_LABELS.values():
            self.assertFalse(stages_keys & set(domaine_map.keys()))


class StatutLibelleSelectorTests(TestCase):
    def test_no_override_uses_i18n_dictionary(self):
        company = _company()
        self.assertEqual(
            statut_libelle(company, 'devis', 'envoye', 'en'), 'Sent')

    def test_fr_override_wins_over_dictionary_in_fr(self):
        company = _company('nti18n25-co-2', 'NTI18N25 Co 2')
        StatutConfig.objects.create(
            company=company, domaine='devis', cle='envoye',
            libelle='Transmis au client')
        self.assertEqual(
            statut_libelle(company, 'devis', 'envoye', 'fr'),
            'Transmis au client')

    def test_fr_override_never_leaks_into_other_languages(self):
        # Un override FR n'est jamais utilisé comme "traduction" EN/AR — le
        # dictionnaire NTI18N25 reste seul consommé pour les autres langues.
        company = _company('nti18n25-co-3', 'NTI18N25 Co 3')
        StatutConfig.objects.create(
            company=company, domaine='devis', cle='envoye',
            libelle='Transmis au client')
        self.assertEqual(
            statut_libelle(company, 'devis', 'envoye', 'en'), 'Sent')

    def test_devis_statut_in_db_never_touched(self):
        # Ce sélecteur ne calcule qu'un LIBELLÉ ; il ne modifie jamais la clé
        # canonique en base (aucune écriture faite ici).
        company = _company('nti18n25-co-4', 'NTI18N25 Co 4')
        before = StatutConfig.objects.count()
        statut_libelle(company, 'devis', 'envoye', 'ar')
        self.assertEqual(StatutConfig.objects.count(), before)
