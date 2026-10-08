"""AMOT20 (C-AMOT-018) — le une-page prouve sa postcondition sur le DERNIER
bloc de la zone (ligne Validité / Acompte / mise en marche / TVA) et sur le
HTML RENDU : une note ×60 et 3 clauses ×20 ne disparaissent plus en silence
sous la ligne de rognage — elles sont tronquées avec le renvoi DÉCLARÉ
« texte intégral sur la proposition en ligne », et la page reste unique.

Oracle : positions des boîtes de texte composées par WeasyPrint (le HTML
exact du moteur, ``render_html_for``), en fr / en / ar (rejoue la sonde VA
p4 : « Clause 2 », « Acompte », « après mise en marche » dans le HTML mais
absents des boîtes composées).

Test-du-test : ré-ancrer la mesure sur ``_formes_total_ttc`` seul (retirer
``_onepage_conditions_qui_tiennent``) ⇒ la ligne « après mise en marche »
n'a plus de boîte visible et ``test_dernier_bloc_visible`` rougit.
"""
from django.test import TestCase
from django.utils import timezone

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import i18n_labels
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

NOTE_LONGUE = ' '.join(['Note commerciale AMOT20 très détaillée'] * 60)
CLAUSES = [{'clause_id': i, 'nom': f'Clause {i}',
            'corps_texte': ' '.join([f'condition particulière {i}'] * 20),
            'type_deal': '', 'ordre': i} for i in (1, 2, 3)]


def _boites(html):
    from weasyprint import HTML
    pages = HTML(string=html).render().pages
    return pages, G._boites_texte_onepage(pages[0])


class OnepageDernierBlocTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company()
        cls.user = make_user(cls.company)
        cls.client_obj = make_client(cls.company)
        cls.devis = make_devis(cls.company, cls.user, cls.client_obj, [
            ('Panneau mono 450W', '10', '1500', '10'),
            ('Onduleur réseau 5kW', '1', '9000', '20'),
        ], reference=f'DEV-{timezone.now():%Y%m}-A020')
        cls.devis.note = NOTE_LONGUE
        cls.devis.clauses_appliquees = CLAUSES
        cls.devis.save(update_fields=['note', 'clauses_appliquees'])

    def _rendu(self, langue):
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage',
                                             'langue_sortie': langue})
        return G.render_html_for(data)

    def test_dernier_bloc_visible(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                html = self._rendu(langue)
                pages, boites = _boites(html)
                self.assertEqual(len(pages), 1)
                limite = pages[0].height - G.ONEPAGE_FOOTER_PX
                visibles = [b for b in boites
                            if b.position_y + b.height <= limite]
                texte_visible = ' '.join(b.text for b in visibles)
                libelle = i18n_labels.libelle('apres_mise_en_marche', langue)
                self.assertTrue(
                    libelle in texte_visible
                    or libelle.upper() in texte_visible,
                    'ligne Validité/Acompte/TVA sous la ligne de rognage')
                # Les conditions retirées sont DÉCLARÉES, jamais effacées.
                renvoi = G.RENVOI_TEXTE_INTEGRAL[langue]
                self.assertIn(renvoi.split()[0], texte_visible)
                # Chaque nom de clause encore dans le HTML est composé visible.
                for c in CLAUSES:
                    if c['nom'] in html:
                        self.assertIn(c['nom'], texte_visible)

    def test_note_courte_inchangee(self):
        """Une note qui tient n'est ni tronquée ni suivie du renvoi."""
        from apps.ventes.models import Devis
        Devis.objects.filter(pk=self.devis.pk).update(
            note='Livraison sous trois semaines.', clauses_appliquees=[])
        self.devis.refresh_from_db()
        html = self._rendu('fr')
        self.assertIn('Livraison sous trois semaines.', html)
        self.assertNotIn(G.RENVOI_TEXTE_INTEGRAL['fr'], html)

    def test_troncature_au_mot_sans_entite_coupee(self):
        coupe = G._couper_au_mot('abc l&#x27;eau pomp&#233;e du forage', 11)
        self.assertEqual(coupe, 'abc')
        coupe = G._couper_au_mot('l&#x27;eau', 4)
        self.assertNotIn('&', coupe)
