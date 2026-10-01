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
