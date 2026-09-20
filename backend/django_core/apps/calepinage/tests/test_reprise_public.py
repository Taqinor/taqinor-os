"""CAL110 — reprendre le tracé public « mon toit » dans un calepinage.

Ce qui est prouvé ici :

* un lead issu de « mon toit » ouvre un calepinage PRÉ-TRACÉ, **plusieurs
  zones comprises** — c'est tout l'objet de la tâche : le lead ne sait porter
  qu'un contour unique ;
* un lead SANS tracé exploitable ne crée AUCUN calepinage (zéro création
  silencieuse), et un lead déjà repris n'en reçoit pas un second ;
* ``roof_outline`` et ``roof_point`` du lead restent renseignés À L'IDENTIQUE
  — aucune écriture croisée vers les modèles crm ;
* l'ordre des axes est tenu : ``roof_outline`` est en ``[lat, lng]``,
  ``zones[].vertices`` en ``[lng, lat]``. Les inverser produit une toiture
  retournée, plausible et fausse ;
* le contrat publié (``contract_samples/lead_layout_public.json``) et le code
  parlent de la MÊME clé (PACT10) ;
* le récepteur est branché sur ``core.events.lead_created`` avec un
  ``dispatch_uid`` stable, et il est BEST-EFFORT : une reprise en échec ne
  casse jamais la création du lead.

Les classes ``…SansBase`` tournent sans base de données ; celles qui créent un
lead réel exigent la base (comme tout test d'API du module).

Run :
    python manage.py test apps.calepinage.tests.test_reprise_public -v2
"""
import io
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.reprise_public import (
    CHAMP_PORTEUR, CLE_LAYOUT, document_public_du_lead, latlng_vers_lnglat,
)

#: Le contour que le visiteur trace, tel que le lead le stocke : [lat, lng].
CONTOUR_LATLNG = [[33.4999, -7.6001], [33.4999, -7.5999],
                  [33.5001, -7.5999], [33.5001, -7.6001]]


class LeadFactice:
    """Un lead RÉDUIT à ce que la reprise lit — aucune base nécessaire."""

    def __init__(self, **champs):
        self.pk = champs.pop('pk', 1)
        self.roof_point = champs.pop('roof_point', None)
        self.roof_outline = champs.pop('roof_outline', None)
        setattr(self, CHAMP_PORTEUR, champs.pop(CHAMP_PORTEUR, None))
        for cle, valeur in champs.items():
            setattr(self, cle, valeur)


def _document_multi_zones():
    return {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'zones': [
            {'id': 'z1', 'vertices': [[-7.6001, 33.4999], [-7.5999, 33.4999],
                                      [-7.5999, 33.5001]]},
            {'id': 'z2', 'vertices': [[-7.5998, 33.4999], [-7.5997, 33.4999],
                                      [-7.5997, 33.5]]},
        ],
    }


class LeDocumentPublicSansBase(SimpleTestCase):

    def test_le_document_transporte_garde_toutes_ses_zones(self):
        lead = LeadFactice(**{CHAMP_PORTEUR: {
            CLE_LAYOUT: _document_multi_zones()}})
        document = document_public_du_lead(lead)
        self.assertEqual([z['id'] for z in document['zones']], ['z1', 'z2'])

    def test_le_contour_seul_donne_une_zone(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG,
                           roof_point={'lat': 33.5, 'lng': -7.6})
        document = document_public_du_lead(lead)
        self.assertEqual(len(document['zones']), 1)
        self.assertEqual(document['pin'], {'lat': 33.5, 'lng': -7.6})

    def test_l_ordre_des_axes_est_inverse_entre_lead_et_zone(self):
        """``roof_outline`` = [lat, lng] ; ``vertices`` = [lng, lat]."""
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG)
        sommets = document_public_du_lead(lead)['zones'][0]['vertices']
        for (lng, lat), (lat_source, lng_source) in zip(sommets,
                                                        CONTOUR_LATLNG):
            self.assertEqual(lat, lat_source)
            self.assertEqual(lng, lng_source)

    def test_l_outline_du_document_reste_en_lat_lng(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG)
        self.assertEqual(document_public_du_lead(lead)['outline'],
                         [[lat, lng] for lat, lng in CONTOUR_LATLNG])

    def test_la_conversion_nommee_refuse_un_point_illisible(self):
        self.assertEqual(latlng_vers_lnglat([[33.5, -7.6], ['x', 2]]), [])
        self.assertEqual(latlng_vers_lnglat([[33.5]]), [])
        self.assertEqual(latlng_vers_lnglat(None), [])

    def test_un_lead_sans_trace_ne_donne_aucun_document(self):
        self.assertIsNone(document_public_du_lead(LeadFactice()))
        self.assertIsNone(document_public_du_lead(None))

    def test_un_contour_a_deux_sommets_ne_donne_aucun_document(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG[:2])
        self.assertIsNone(document_public_du_lead(lead))

    def test_un_document_transporte_sans_zone_retombe_sur_le_contour(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG,
                           **{CHAMP_PORTEUR: {CLE_LAYOUT: {'zones': []}}})
        document = document_public_du_lead(lead)
        self.assertEqual(len(document['zones']), 1)

    def test_aucun_chiffre_n_est_invente(self):
        """Ni puissance, ni cote de module, ni estimation."""
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG)
        document = document_public_du_lead(lead)
        for cle in ('panelWatt', 'panelLengthM', 'panelWidthM', 'result',
                    'billKwh'):
            self.assertNotIn(cle, document)

    def test_l_epingle_du_lead_ne_remplace_pas_celle_du_document(self):
        document = _document_multi_zones()
        lead = LeadFactice(roof_point={'lat': 0.0, 'lng': 0.0},
                           **{CHAMP_PORTEUR: {CLE_LAYOUT: document}})
        self.assertEqual(document_public_du_lead(lead)['pin'],
                         {'lat': 33.5, 'lng': -7.6})

    def test_une_epingle_illisible_est_ignoree(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG,
                           roof_point={'lat': 'nord', 'lng': -7.6})
        self.assertNotIn('pin', document_public_du_lead(lead))


class LeContratEtLeCodeParlentDeLaMemeCle(SimpleTestCase):
    """PACT10 : le champ publié est celui que le serveur lit."""

    def setUp(self):
        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'lead_layout_public.json')
        with io.open(chemin, encoding='utf-8') as fichier:
            self.contrat = json.load(fichier)

    def test_le_champ_ajoute_porte_le_nom_lu_par_le_service(self):
        self.assertEqual(self.contrat['champ_ajoute']['nom'], CLE_LAYOUT)

    def test_le_porteur_erp_declare_est_celui_que_le_service_lit(self):
        self.assertIn(CHAMP_PORTEUR, self.contrat['champ_ajoute']['porteur_erp'])

    def test_l_exemple_du_contrat_rend_un_document_multi_zones(self):
        lead = LeadFactice(
            roof_point=self.contrat['exemple']['roof_point'],
            roof_outline=self.contrat['exemple']['roof_outline'],
            **{CHAMP_PORTEUR: {
                CLE_LAYOUT: self.contrat['exemple'][CLE_LAYOUT]}})
        self.assertEqual(len(document_public_du_lead(lead)['zones']), 2)

    def test_l_exemple_sans_trace_ne_rend_aucun_document(self):
        exemple = self.contrat['exemple_sans_trace']
        lead = LeadFactice(roof_point=exemple['roof_point'],
                           roof_outline=exemple['roof_outline'])
        self.assertIsNone(document_public_du_lead(lead))

    def test_l_exemple_de_repli_rend_une_zone(self):
        exemple = self.contrat['exemple_repli_contour_seul']
        lead = LeadFactice(roof_point=exemple['roof_point'],
                           roof_outline=exemple['roof_outline'])
        self.assertEqual(len(document_public_du_lead(lead)['zones']), 1)


class LeRecepteurEstBrancheSansBase(SimpleTestCase):

    def test_il_est_abonne_a_lead_created(self):
        from core.events import lead_created

        # La forme interne d'une entrée de ``Signal.receivers`` a changé
        # entre versions de Django (2-uplet puis 3-uplet) : on ne lit que la
        # CLÉ, dont le premier élément est le ``dispatch_uid``.
        uids = [str(entree[0][0]) for entree in lead_created.receivers]
        self.assertIn('calepinage_reprise_trace_public', uids)

    def test_une_reprise_en_echec_ne_casse_pas_le_lead(self):
        from apps.calepinage.receivers import reprise_du_trace_public

        with mock.patch('apps.calepinage.services.reprise_public'
                        '.reprendre_trace_public',
                        side_effect=RuntimeError('boum')):
            reprise_du_trace_public(None, lead=LeadFactice(),
                                    company=object())

    def test_sans_societe_rien_n_est_tente(self):
        from apps.calepinage.receivers import reprise_du_trace_public

        with mock.patch('apps.calepinage.services.reprise_public'
                        '.reprendre_trace_public') as reprise:
            reprise_du_trace_public(None, lead=LeadFactice(company=None),
                                    company=None)
        reprise.assert_not_called()


class LaRepriseCreeUnCalepinagePreTrace(SimpleTestCase):
    """Le service, éprouvé sans base : les écritures sont MOQUÉES.

    Ce que ces tests vérifient est la DÉCISION du service (créer ou non,
    avec quel document) — les chemins d'écriture eux-mêmes ont déjà leurs
    propres tests (``services.creation``, ``services.layout``).
    """

    def _reprendre(self, lead, *, deja_repris=False):
        from apps.calepinage.services import reprise_public

        faux_calepinage = object()
        with mock.patch('apps.crm.selectors.get_company_lead',
                        return_value=lead), \
                mock.patch('apps.calepinage.selectors.liste_calepinages') \
                as liste, \
                mock.patch('apps.calepinage.services.creation.creer_pour_lead',
                           return_value=faux_calepinage) as creer, \
                mock.patch('apps.calepinage.services.layout'
                           '.enregistrer_layout') as enregistrer:
            liste.return_value.exists.return_value = deja_repris
            rendu = reprise_public.reprendre_trace_public(1, object())
        return rendu, creer, enregistrer, faux_calepinage

    def test_un_lead_trace_ouvre_un_calepinage_avec_toutes_ses_zones(self):
        lead = LeadFactice(**{CHAMP_PORTEUR: {
            CLE_LAYOUT: _document_multi_zones()}})
        rendu, creer, enregistrer, attendu = self._reprendre(lead)
        self.assertIs(rendu, attendu)
        creer.assert_called_once()
        document = enregistrer.call_args.args[1]
        self.assertEqual(len(document['zones']), 2)

    def test_un_lead_sans_trace_ne_cree_aucun_calepinage(self):
        rendu, creer, enregistrer, _ = self._reprendre(LeadFactice())
        self.assertIsNone(rendu)
        creer.assert_not_called()
        enregistrer.assert_not_called()

    def test_un_lead_deja_repris_n_en_recoit_pas_un_second(self):
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG)
        rendu, creer, _enregistrer, _ = self._reprendre(lead,
                                                        deja_repris=True)
        self.assertIsNone(rendu)
        creer.assert_not_called()

    def test_un_lead_introuvable_ne_cree_rien(self):
        rendu, creer, _enregistrer, _ = self._reprendre(None)
        self.assertIsNone(rendu)
        creer.assert_not_called()

    def test_le_lead_n_est_jamais_ecrit(self):
        """Aucune écriture croisée : le lead ressort identique."""
        lead = LeadFactice(roof_outline=CONTOUR_LATLNG,
                           roof_point={'lat': 33.5, 'lng': -7.6})
        avant = (json.dumps(lead.roof_outline), json.dumps(lead.roof_point))
        self._reprendre(lead)
        self.assertEqual(
            (json.dumps(lead.roof_outline), json.dumps(lead.roof_point)),
            avant)
