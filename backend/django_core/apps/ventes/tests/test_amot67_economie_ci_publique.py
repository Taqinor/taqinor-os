"""AMOT67 (C-AMOT-050) — ``economie_ci`` ne quitte plus ``quote`` sur la
charge publique (la page lit ``synthese_ci``) : la case « économies »
décochée ne laisse partir ni économie an 1, ni flux, ni TRI, et un devis
COMMERCIAL ne publie ni VAN, ni LCOE, ni sensibilités (D-CIQ-10), à aucun
niveau. Sonde VC lci6 : ``200 eci True argent False lcoe 0.09654 … tri 68.9``.

Charge RÉELLE (``build_quote_data`` jamais mocké ; seule la production PVGIS
est simulée, patron CIQ210/CIQ306).

Test-du-test : remettre ``economie_ci`` dans ``quote`` ⇒
``test_economie_ci_jamais_dans_quote`` (et le volet « décochée ») rougit.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_amot67_economie_ci_publique -v 2
"""
import uuid

from django.test import Client as DjangoClient

from apps.ventes.models import Devis, ShareLink
from apps.ventes.tests.test_ciq210_branchement import _BaseDevis

#: Ce que la case « économies » décochée retire : économie an 1, flux, TRI.
CLES_ARGENT = {'economie_annee1', 'flux_ht', 'flux_ttc', 'tri_pct'}
#: D-CIQ-10 — industriel seulement.
CLES_INDUSTRIEL = {'van_mad', 'lcoe_mad_kwh', 'lcoe_actualise',
                   'sensibilites'}


def _cles(valeur):
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield cle
            yield from _cles(sous)
    elif isinstance(valeur, list):
        for sous in valeur:
            yield from _cles(sous)


class EconomieCiPubliqueTests(_BaseDevis):

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
        cas = (
            self._devis('DEV-AMOT67-0010', mode='commercial', tension='bt'),
            self._devis('DEV-AMOT67-0020', mode='industriel', tension='mt'),
        )
        Devis.objects.filter(pk__in=[d.pk for d in cas]).update(
            statut='envoye')
        return tuple(Devis.objects.get(pk=d.pk) for d in cas)

    def test_economie_ci_jamais_dans_quote(self):
        for devis in self._cas():
            for sections in (None, {'economies': False}):
                with self.subTest(devis=devis.reference, sections=sections):
                    payload = self._payload(devis, sections)
                    self.assertNotIn('economie_ci', payload['quote'])
                    self.assertNotIn('economie_ci', set(_cles(payload)))

    def test_case_economies_decochee_aucun_argent(self):
        commercial, industriel = self._cas()
        # Prémisse : cochée, l'argent industriel part bien (synthese_ci).
        servi = self._payload(industriel)
        self.assertIn('argent', servi['synthese_ci'])
        self.assertTrue(CLES_ARGENT & set(_cles(servi)))
        for devis in (commercial, industriel):
            with self.subTest(devis=devis.reference):
                retire = self._payload(devis, {'economies': False})
                self.assertNotIn('argent', retire['synthese_ci'])
                self.assertEqual(CLES_ARGENT & set(_cles(retire)), set())

    def test_commercial_ni_van_ni_lcoe_ni_sensibilites(self):
        commercial, _industriel = self._cas()
        for sections in (None, {'economies': False}):
            with self.subTest(sections=sections):
                payload = self._payload(commercial, sections)
                self.assertEqual(
                    CLES_INDUSTRIEL & set(_cles(payload)), set())
