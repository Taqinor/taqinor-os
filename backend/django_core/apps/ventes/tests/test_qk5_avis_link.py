"""QK5 — Fix the dead taqinor.ma/avis link in the residential PDF trust strip.

The residential PDF's trust strip linked « Avis clients vérifiés » →
taqinor.ma/avis, a route that does not exist on the site. QK5 repoints it to
an existing route (/realisations — real client projects) and NEVER fabricates
reviews. This link-check test guards against the 404 coming back.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qk5_avis_link -v 2
"""
from django.test import SimpleTestCase, tag


class TestAvisLinkDefaults(SimpleTestCase):
    """The renderer defaults must not point at /avis (which 404s)."""

    def test_residential_renderer_avis_default_is_realisations(self):
        from apps.ventes.quote_engine.residential import renderer
        d = renderer._augment(_min_residential_data())
        self.assertNotIn('/avis', d['links']['avis'])
        self.assertIn('/realisations', d['links']['avis'])

    def test_agricole_renderer_avis_default_is_realisations(self):
        # agricole renderer._augment needs economics; test the links dict shape
        # by calling with a minimal agricole data set via a direct dict.
        from apps.ventes.quote_engine.agricole import renderer as ag
        data = _min_residential_data()
        data['all_items'] = [{'designation': 'Pompe', 'quantite': 1,
                              'prix_unit_ht': 8000, 'prix_unit_ttc': 9600,
                              'taux_tva': 20.0, 'marque': ''}]
        data['mode_installation'] = 'agricole'
        d = ag._augment(data)
        self.assertNotIn('/avis', d['links']['avis'])
        self.assertIn('/realisations', d['links']['avis'])


@tag('pdf')
class TestResidentialPdfHasNoAvis404(SimpleTestCase):
    def test_residential_page3_has_no_avis_link(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        d = renderer._augment(_residential_sample_data())
        html = render.build_html(d)
        # No dead /avis link anywhere in the rendered proposal.
        self.assertNotIn('/avis', html)
        self.assertNotIn('taqinor.ma/avis', html)
        # The trust link still points somewhere real (realisations).
        self.assertIn('realisations', html)


def _min_residential_data():
    """Minimal quote data with the residential two-option shape so
    renderer._augment doesn't raise Unsupported (only the links dict matters)."""
    def _item(desig, q, ht, taux=20.0):
        return {"designation": desig, "marque": "", "description": "",
                "garantie": "", "quantite": float(q), "prix_unit_ht": float(ht),
                "prix_unit_ttc": round(float(ht) * (1 + taux / 100), 2),
                "taux_tva": float(taux)}

    def _tot(rows):
        ht = round(sum(r["quantite"] * r["prix_unit_ht"] for r in rows), 2)
        tva = round(ht * 0.20, 2)
        return {"ht_brut": ht, "remise": 0.0, "ht_net": ht, "tva": tva,
                "tva_par_taux": [{"taux": 20.0, "montant": tva, "ht_net": ht}],
                "ttc": round(ht + tva)}

    shared = [_item("Panneau mono 550W", 10, 1200),
              _item("Installation", 1, 4000)]
    sans = shared + [_item("Onduleur réseau 8kW", 1, 14000)]
    avec = shared + [_item("Onduleur hybride 8kW", 1, 20000),
                     _item("Batterie 10 kWh", 1, 22000)]
    eco = 12000
    sf = [1 / 12] * 12
    eco_m = [round(eco * f) for f in sf]
    return {
        "ref": "DEV-QK5", "date": "01/07/2026",
        "client_name": "Test", "client_full": "Test",
        "client_addr": "", "client_phone": "+212600000000",
        "inst_type": "Résidentielle",
        "puissance_kwc": 5.5, "nb_panneaux": 10, "watt_par_panneau": 550,
        "prod_kwh": 8000,
        "total_sans": _tot(sans)["ttc"], "total_avec": _tot(avec)["ttc"],
        "totaux_sans": _tot(sans), "totaux_avec": _tot(avec),
        "roi_s": 5.0, "roi_a": 5.5,
        "eco_s_ann": eco, "eco_a_ann": eco, "eco_a_cumul": eco,
        "eco_s_monthly": eco_m, "eco_a_monthly": eco_m,
        "factures_mensuelles": [round(v / 0.85) for v in eco_m],
        "sans_items": sans, "avec_items": avec,
        "sans_bullets": ["10 panneaux 550 W"], "avec_bullets": ["10 panneaux 550 W"],
        "scenario": "Les deux (Sans + Avec)", "recommended": "Avec batterie",
        "tva_note": "TVA 20 %", "payment_terms": {"acompte": 30, "materiel": 60, "solde": 10},
        "discount_pct": 0.0, "taux_tva": 20.0,
    }
