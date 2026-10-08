"""CIQ306 — ``proposal_data`` sert ``synthese_ci`` : la MÊME fonction que le
PDF (``quote_engine/ci/synthese.synthese_ci``), prouvée par la parité clé par
clé ; ``mode_kpis`` C&I v2 en est une projection (aucune clé d'étude JS lue).

Patron ``test_pvcov_synthese_servie.py`` / ``test_agr308`` : charge utile
RÉELLE (client Django, ``build_quote_data`` jamais mocké ; seule la
production PVGIS est simulée, comme CIQ210).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq306_synthese_ci_servie"
"""
import json
import uuid
from decimal import Decimal

from django.test import Client as DjangoClient
from rest_framework.utils.encoders import JSONEncoder

from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.tests.test_ciq210_branchement import _BaseDevis
from apps.ventes.tests.test_proposal_data_shape import make_devis_agricole


def _json(valeur):
    """La valeur telle que la page la reçoit (encodeur DRF)."""
    return json.loads(json.dumps(valeur, cls=JSONEncoder))


def _cles(valeur):
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield cle
            yield from _cles(sous)
    elif isinstance(valeur, list):
        for sous in valeur:
            yield from _cles(sous)


class SyntheseCiServieTest(_BaseDevis):

    def _payload(self, devis, sections=None):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.co, devis=devis, token=token,
            **({'sections': sections} if sections is not None else {}))
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def _cas(self):
        # ADEV11 — le jeton client ne sert plus un BROUILLON (404) ;
        # ``_devis`` (CIQ210) crée un brouillon : on le passe « envoyé »,
        # seul état où un lien client existe réellement.
        cas = (
            self._devis('DEV-CIQ306-0010', mode='commercial', tension='bt'),
            self._devis('DEV-CIQ306-0020', mode='industriel', tension='mt'),
        )
        Devis.objects.filter(pk__in=[d.pk for d in cas]).update(
            statut='envoye')
        return tuple(Devis.objects.get(pk=d.pk) for d in cas)

    def test_parite_cle_par_cle_avec_la_fonction_du_pdf(self):
        for devis in self._cas():
            with self.subTest(devis=devis.reference):
                servie = self._payload(devis)['synthese_ci']
                attendue = _json(synthese_ci(self._data(devis)))
                self.assertEqual(sorted(servie), sorted(attendue))
                for cle in attendue:
                    self.assertEqual(servie[cle], attendue[cle], cle)

    def test_industriel_mt_sert_l_argent_et_mode_kpis_projete(self):
        devis = self._cas()[1]
        payload = self._payload(devis)
        synthese = payload['synthese_ci']
        self.assertEqual(synthese['segment'], 'industriel')
        self.assertIn('argent', synthese)
        argent = synthese['argent']
        kpis = payload['mode_kpis']
        self.assertEqual(kpis['payback'], argent['indicateurs']['retour_ans'])
        self.assertEqual(kpis['economies_annuelles'],
                         argent['economie_annee1']['total_mad'])
        self.assertEqual(kpis['taux_autoconso'],
                         synthese['energie']['taux_autoconso_pct'])
        self.assertEqual(kpis['taux_couverture'],
                         synthese['energie']['taux_couverture_pct'])

    def test_mode_kpis_ne_lit_plus_l_etude_js(self):
        devis = self._cas()[0]
        params = dict(devis.etude_params, payback=1.1,
                      economies_annuelles=987653, taux_autoconso=99)
        Devis.objects.filter(pk=devis.pk).update(etude_params=params)
        payload = self._payload(Devis.objects.get(pk=devis.pk))
        self.assertNotEqual(payload['mode_kpis']['payback'], 1.1)
        self.assertNotEqual(payload['mode_kpis']['taux_autoconso'], 99)
        self.assertNotIn('987653', json.dumps(payload['mode_kpis']))

    def test_case_economies_decochee_l_argent_ne_part_pas(self):
        devis = self._cas()[1]
        payload = self._payload(devis, sections={'economies': False})
        self.assertNotIn('argent', payload['synthese_ci'])
        self.assertIsNone(payload['mode_kpis']['payback'])
        self.assertIsNone(payload['mode_kpis']['economies_annuelles'])

    def test_absente_hors_ci(self):
        residentiel = Devis.objects.create(
            company=self.co, reference='DEV-CIQ306-0030',
            client=self.client_obj, statut='envoye', taux_tva=Decimal('20'),
            mode_installation='residentiel', etude_params={})
        LigneDevis.objects.create(
            devis=residentiel, produit=self.panneau,
            designation='Panneau 710W', quantite=Decimal('10'),
            prix_unitaire=Decimal('1272.73'), remise=Decimal('0'))
        # Un devis résidentiel sans onduleur est REFUSÉ par le moteur (règle
        # dure « aucune option sans onduleur », builder) ⇒ 404 public : la
        # fixture doit être un devis rendable pour prouver l'ABSENCE de clé.
        LigneDevis.objects.create(
            devis=residentiel, produit=self.ond,
            designation='Onduleur réseau', quantite=Decimal('1'),
            prix_unitaire=Decimal('8000'), remise=Decimal('0'))
        agricole = make_devis_agricole(self.co, self.user, self.client_obj,
                                       'DEV-CIQ306-0040')
        for devis in (residentiel, agricole):
            with self.subTest(devis=devis.reference):
                self.assertNotIn('synthese_ci', self._payload(devis))

    def test_aucun_prix_achat(self):
        for devis in self._cas():
            with self.subTest(devis=devis.reference):
                synthese = self._payload(devis)['synthese_ci']
                self.assertNotIn('prix_achat', set(_cles(synthese)))
                self.assertNotIn('marge', set(_cles(synthese)))
