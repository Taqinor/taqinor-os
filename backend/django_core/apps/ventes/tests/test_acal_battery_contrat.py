"""ACAL86 (C-ACAL-100) — ``battery`` au format du contrat roof_layout_v2
(objet non vide ou ``null``, jamais un booléen).

* « Appliquer cette taille » écrit un OBJET (``{'kwh': …}`` quand le module
  est connu, sinon ``{'declaree': True}``), et le document passe
  ``valider_document`` ;
* un document HISTORIQUE à ``battery`` booléen est normalisé À LA LECTURE
  (``geometrie.battery_du_document``) : rien n'est réécrit en base ;
* export puis import d'un projet dont le document porte ``battery: True``
  réussit ;
* ``layout_hash`` est identique (il lit ``bool(battery)``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_battery_contrat"
"""
from types import SimpleNamespace
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.export_projet import (
    _analyser_projet, document_de_projet, importer_projet)
from apps.calepinage.services.io_layout import valider_document
from apps.crm.models import Lead
from apps.ventes import offres_tailles as ot
from apps.ventes.domain.geometrie import battery_du_document, layout_hash
from apps.ventes.models import Devis
from apps.ventes.tests.test_offres_tailles import _Base

HISTORIQUE = {
    'version': 2,
    'scenario': 'avec_batterie',
    'panelWatt': 710,
    'battery': True,
    'result': {'panels': 14, 'kwc': 9.94},
}


class BatteryAuContrat(_Base):

    def _contexte(self, devis):
        return SimpleNamespace(panel_watt=710.0, module_batterie_kwh=5.0,
                               entrees={'company': devis.company})

    def test_appliquer_taille_ecrit_battery_objet_valide_au_schema(self):
        devis = self._devis('acal86-app')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        devis.refresh_from_db()
        ot.enregistrer_config(devis, 'recommande', {'nb_panneaux': 16})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        battery = (devis.roof_layout or {}).get('battery')
        self.assertIsInstance(battery, dict)
        self.assertTrue(battery)
        self.assertNotIsInstance(battery, bool)
        self.assertEqual(devis.roof_layout.get('scenario'), 'avec_batterie')
        valider_document(devis.roof_layout)  # ne lève pas

    def test_lecture_normalise_battery_true_sans_ecrire(self):
        devis = self._devis('acal86-lecture')
        Devis.objects.filter(pk=devis.pk).update(
            roof_layout=dict(HISTORIQUE),
            layout_hash=layout_hash(HISTORIQUE))
        devis.refresh_from_db()
        self.assertEqual(battery_du_document(devis.roof_layout),
                         {'declaree': True})
        self.assertIsNone(battery_du_document(dict(HISTORIQUE,
                                                   battery=False)))
        self.assertIsNone(battery_du_document({}))
        self.assertEqual(battery_du_document({'battery': {'kwh': 10}}),
                         {'kwh': 10})
        valider_document(devis.roof_layout)  # lecture tolérante
        devis.refresh_from_db()
        # Rien n'est réécrit : le booléen historique reste stocké.
        self.assertIs(devis.roof_layout['battery'], True)

    def test_export_import_d_un_document_battery_true_reussit(self):
        devis = self._devis('acal86-export')
        lead = Lead.objects.filter(company=devis.company).first()
        calepinage = Calepinage.objects.create(
            company=devis.company, lead_id=lead.pk, titre='ACAL86',
            roof_layout=dict(HISTORIQUE),
            layout_hash=layout_hash(HISTORIQUE))
        document = document_de_projet(calepinage)
        plan = _analyser_projet(document)
        self.assertEqual(plan['roof_layout']['battery'], {'declaree': True})
        autre = Lead.objects.create(
            company=devis.company, nom='Lead', prenom='acal86-import',
            telephone='+212600000086')
        resume = importer_projet(document, devis.company, lead_id=autre.pk,
                                 apercu=True)
        self.assertIsInstance(resume, dict)
        calepinage.refresh_from_db()
        self.assertIs(calepinage.roof_layout['battery'], True)

    def test_layout_hash_inchange(self):
        normalise = dict(HISTORIQUE,
                         battery=battery_du_document(HISTORIQUE))
        self.assertEqual(layout_hash(HISTORIQUE), layout_hash(normalise))
        faux = dict(HISTORIQUE, battery=False)
        self.assertEqual(layout_hash(faux),
                         layout_hash(dict(faux,
                                          battery=battery_du_document(faux))))
