"""QJR602 (D-QJR5-13, fondateur 30/09/2026) — une taille EXPLICITE est
respectée TELLE QUELLE partout : même nombre de panneaux par le bouton du
cockpit (``autoQuote.js``), par ``POST /ventes/devis/auto/``
(``build_devis_auto``) et par le tunnel (``creer_devis_automatique_depuis_lead``).

Avant QJR602, un lead à 6,5 kWc donnait 8 panneaux au bouton (arrondi au
palier de 5 kWc, côté écran seulement) et 10 côté serveur
(plafond(6 500 / 710) = 10). Le bouton compose désormais la cible brute : il
envoie ``target_kwc = 10 × 710 / 1000 = 7,1`` kWc, que le serveur reconvertit
en ces MÊMES 10 panneaux (verrou d'aller-retour ci-dessous). Le côté écran est
exécuté dans ``frontend/src/features/ventes/autoQuote.tailleExplicite.test.jsx``.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_taille_cible_parite -v 2
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.services import (
    build_devis_auto, creer_devis_automatique_depuis_lead,
)
from apps.ventes.tests.test_qjr_bascule_auto import _BaseAuto

# plafond(6 500 / 710) = plafond(9,15…) = 10 — la conversion du bouton
# (`panneauxPourKwc(6.5, 710)`) et du serveur (`_residential_panel_count`).
TAILLE_LEAD_KWC = Decimal('6.5')
PANNEAUX_ATTENDUS = 10
# Ce que le bouton envoie pour ce lead : 10 panneaux × 710 W.
TARGET_KWC_BOUTON = '7.1'


class TailleExpliciteParite(_BaseAuto):

    def _panneaux(self, devis):
        return sum(
            Decimal(str(li.quantite)) for li in devis.lignes.all()
            if li.produit_id == self.panneau.pk)

    def test_build_devis_auto_respecte_la_taille_du_lead(self):
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=TAILLE_LEAD_KWC,
                            email='parite-auto@example.com'),
            user=self.user, company=self.company)
        self.assertEqual(self._panneaux(devis), PANNEAUX_ATTENDUS)

    def test_le_tunnel_respecte_la_taille_du_lead(self):
        lead = self._lead(taille_souhaitee_kwc=TAILLE_LEAD_KWC,
                          email='parite-tunnel@example.com')
        devis = creer_devis_automatique_depuis_lead(
            lead_id=lead.pk, company_id=self.company.pk)
        self.assertIsNotNone(devis)
        self.assertEqual(self._panneaux(devis), PANNEAUX_ATTENDUS)

    def test_la_cible_envoyee_par_le_bouton_redonne_le_meme_compte(self):
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=TAILLE_LEAD_KWC,
                            email='parite-bouton@example.com'),
            user=self.user, company=self.company, target_kwc=TARGET_KWC_BOUTON)
        self.assertEqual(self._panneaux(devis), PANNEAUX_ATTENDUS)

    def test_cible_dit_le_motif_du_refus(self):
        """ACAL1145 — lead résidentiel sans facture ni taille ⇒ ``motif_code``
        'facture_absente' (lu sur l'``AutoDevisError``), taille souhaitée ⇒
        None ; les cinq clés d'avant restent."""
        from apps.ventes.selectors import cible_depuis_lead
        # ``_BaseAuto._lead`` pose par défaut ``taille_souhaitee_kwc`` = 7,1 :
        # « sans taille » doit l'ôter, sinon la taille du lead est souveraine
        # (``source: 'lead'``, aucun refus, ``motif_code`` None — le rouge CI).
        sans = cible_depuis_lead(self._lead(taille_souhaitee_kwc=None,
                                            email='acal1145-sans@example.com'), self.company)
        self.assertEqual(sans['motif_code'], 'facture_absente')
        self.assertIsNone(sans['panneaux'])
        self.assertIn('facture', sans['refus'])
        avec = cible_depuis_lead(self._lead(taille_souhaitee_kwc=TAILLE_LEAD_KWC,
                                            email='acal1145-taille@example.com'), self.company)
        self.assertEqual(set(avec), {'panneaux', 'panel_watt', 'kwc', 'source', 'refus', 'motif_code'})
        self.assertIsNone(avec['motif_code'])


class MotifDuRefusSansBase(SimpleTestCase):
    """ACAL1145 — le motif porté par l'erreur, sans base (lectures doublées).
    Mutant : ne pas passer ``motif`` dans ``_refus_dimensionnement`` ⇒ rouge."""

    def test_le_refus_porte_son_motif(self):
        from apps.ventes.domain.taille import AutoDevisError, _refus_dimensionnement
        self.assertEqual(_refus_dimensionnement('facture_absente').motif, 'facture_absente')
        self.assertEqual(_refus_dimensionnement('facture_absente').field, 'facture_hiver')
        self.assertIsNone(AutoDevisError('x', field='y').motif)

    def test_cible_motif_code_par_cas(self):
        from apps.ventes.domain.taille import _refus_dimensionnement
        from apps.ventes.selectors import cible_depuis_lead

        def lead(**k):
            return SimpleNamespace(**dict({'type_installation': 'residentiel',
                                           'taille_souhaitee_kwc': None}, **k))
        ci = cible_depuis_lead(lead(type_installation='industriel'), None)
        self.assertIsNone(ci['motif_code'])
        self.assertEqual(set(ci) - {'motif_code'}, {'panneaux', 'panel_watt', 'kwc', 'source', 'refus'})
        self.assertIsNone(cible_depuis_lead(lead(taille_souhaitee_kwc=Decimal('6.5')), None)['motif_code'])
        with mock.patch('apps.ventes.etude_horaire.controle_kwh_declare_du_lead', return_value=None), \
                mock.patch('apps.ventes.domain.pipeline.decider_taille',
                           side_effect=_refus_dimensionnement('facture_absente')):
            self.assertEqual(cible_depuis_lead(lead(), None)['motif_code'], 'facture_absente')
        with mock.patch('apps.ventes.etude_horaire.controle_kwh_declare_du_lead',
                        return_value={'coherent': False}):
            self.assertIsNone(cible_depuis_lead(lead(), None)['motif_code'])
