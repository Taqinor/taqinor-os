"""ACAL730 — ``GET calepinages/<pk>/soleil-legal/?date=AAAA-MM-JJ``.

Nouveau fichier car : cas HTTP avec base — ``test_calx146_soleil.py`` est tout
en ``SimpleTestCase`` (sans base ni réseau), et un 404 « autre société » exige
deux sociétés (``BaseApiCalepinage``).
"""
from apps.calepinage.models import Calepinage
from apps.calepinage.services.soleil_legal import (
    MOTIF_SANS_EPINGLE, MOTIF_SANS_FUSEAU,
)
from apps.parametres.models_company import CompanyProfile

from .test_api_liste import BaseApiCalepinage, url_detail


def _url(pk, date=None):
    base = url_detail(pk) + 'soleil-legal/'
    return base if date is None else '%s?date=%s' % (base, date)


class SoleilLegalApiTests(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            roof_layout={'version': 2, 'pin': {'lat': 33.57, 'lng': -7.59}})

    def _profil(self):
        CompanyProfile.objects.create(company=self.company,
                                      fuseau_horaire='Africa/Casablanca')

    def test_200_au_fuseau_saisi_du_profil(self):
        self._profil()
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['fuseau'], 'Africa/Casablanca')
        self.assertEqual(r.data['fuseau_source'], 'profil_societe')
        self.assertEqual(r.data['decalage_utc_min'], 60)
        self.assertEqual(r.data['longitude_deg'], -7.59)
        self.assertAlmostEqual(r.data['ecart_legal_moins_solaire_min'], 104.6,
                               delta=1.0)

    def test_400_date_absente_ou_mal_formee(self):
        self._profil()
        for date in (None, '11/02/2026', '2026-02-30'):
            with self.subTest(date=date):
                r = self.api.get(_url(self.cal.pk, date))
                self.assertEqual(r.status_code, 400)
                self.assertIn('date', r.data)

    def test_sans_epingle_l_absence_est_servie_en_200(self):
        self._profil()
        self.cal.roof_layout = {'version': 2}
        self.cal.save(update_fields=['roof_layout'])
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 200, r.data)  # T4-U4-018 : plus de 409 à chaque ouverture
        self.assertEqual(r.data, {'date': '2026-02-11', 'absence': {
            'champ': 'site.pin', 'motif': MOTIF_SANS_EPINGLE}})

    def test_t4_u1_003_centre_de_carte_par_defaut_n_est_pas_une_epingle(self):
        """Le toit créé sur la carte « niveau Maroc » arrive avec l'épingle au
        centre par défaut (31,79 ; -7,09) : même refus que sans épingle (une
        seule définition de « site posé », partagée avec la simulation)."""
        self._profil()
        self.cal.roof_layout = {'version': 2, 'pin': {
            'lat': 31.789999999984182, 'lng': -7.089999999999918}}
        self.cal.save(update_fields=['roof_layout'])
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 200, r.data)  # T4-U4-018 : plus de 409 à chaque ouverture
        self.assertEqual(r.data, {'date': '2026-02-11', 'absence': {
            'champ': 'site.pin', 'motif': MOTIF_SANS_EPINGLE}})

    def test_t4_u4_013_trace_sans_site_localise_meme_regle_que_la_simulation(self):
        """Un toit tracé à l'échelle du pays (épingle = centre du tracé, à côté
        du centre par défaut, ``siteLocalise: null``) : sans ville, refus qui
        dit quoi faire ; lead à Marrakech, calcul sur Marrakech, DIT."""
        self._profil()
        self.cal.roof_layout = {'version': 2, 'siteLocalise': None,
                                'pin': {'lat': 31.6123, 'lng': -7.3456}}
        self.cal.save(update_fields=['roof_layout'])
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('Localiser', r.data['absence']['motif'])
        self.lead.ville = 'Marrakech'
        self.lead.save(update_fields=['ville'])
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['longitude_deg'], -8.01)
        self.assertEqual(r.data['site_reference'], {
            'ville_reference': 'Marrakech',
            'libelle': 'Marrakech (ville de référence)'})
        self.cal.roof_layout = dict(self.cal.roof_layout, siteLocalise='adresse')
        self.cal.save(update_fields=['roof_layout'])
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.data['longitude_deg'], -7.3456)
        self.assertIsNone(r.data['site_reference'])

    def test_409_sans_fuseau_jamais_deduit_de_la_longitude(self):
        r = self.api.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data, {'site.fuseau': [MOTIF_SANS_FUSEAU]})

    def test_404_autre_societe(self):
        self._profil()
        r = self.api_autre.get(_url(self.cal.pk, '2026-02-11'))
        self.assertEqual(r.status_code, 404)
