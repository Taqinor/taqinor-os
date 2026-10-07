"""ACAL96 (D-ACAL-1, C-ACAL-102) — ``sync-layout`` et ``POST layout`` du devis
écrivent le CALEPINAGE lié, puis resynchronisent le devis ; un seul rangement
de ``_pans_geometry`` (``creation_calepinage._calepinage_range``).

* le layout posté est relu dans ``Calepinage.roof_layout`` (une version) ;
* ``Devis.roof_layout`` n'est plus JAMAIS le corps brut : c'est l'instantané
  rangé de la conception (``_pans_geometry``), lu par la 3D publique, les
  zones d'étude et les groupes électriques ;
* un devis sans calepinage en reçoit un (adopté ou créé) ;
* un devis figé répond le 409 existant, rien n'est écrit nulle part ;
* renvoyer le même layout ⇒ « inchangé » côté calepinage ET devis.

Sources RÉELLES (aucun mock) : adoption/création, ``enregistrer_layout``,
``resynchroniser_conception``, ``extract_roof_config``.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_layout_enrichi"
"""
import copy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.electrical_service import groupes_du_devis
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.tasks import zones_etude_du_devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _pan(label, azimut, count):
    return {'label': label, 'roofType': 'pitched', 'pitchDeg': 25,
            'facingAzimuthDeg': azimut,
            'result': {'count': count, 'kwc': round(count * 0.55, 2),
                       'areaM2': count * 2.6}}


def _layout(est=6, ouest=6):
    total = est + ouest
    return {
        'version': 1, 'scenario': 'reseau', 'panelWatt': 550,
        'pin': {'lat': 33.57, 'lng': -7.59},
        'zones': [_pan('Pan Est', 90, est), _pan('Pan Ouest', 270, ouest)],
        'result': {'panels': total, 'kwc': round(total * 0.55, 2),
                   'annualKwh': 9000, 'savings': 7000},
    }


def _cle(donnees, cle):
    """La première valeur de ``cle`` dans la charge publique (imbriquée)."""
    if isinstance(donnees, dict):
        if cle in donnees:
            return donnees[cle]
        for valeur in donnees.values():
            trouve = _cle(valeur, cle)
            if trouve is not None:
                return trouve
    return None


def _sans_privees(layout):
    return {k: v for k, v in (layout or {}).items()
            if not str(k).startswith('_')}


class LayoutEnrichiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACAL96 Co',
                                              slug='acal96-co')
        self.user = User.objects.create_user(
            username='acal96', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL96')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='A96-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Growatt 10kW',
            sku='A96-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut='brouillon', lead=None, roof_layout=None):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-96{self.n:02d}',
            client=self.client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            created_by=self.user, roof_layout=roof_layout,
            layout_hash=layout_hash(roof_layout) if roof_layout else None)
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=1)
        if statut != 'brouillon':
            # Statut posé en base, sans passer par les transitions.
            Devis.objects.filter(pk=devis.pk).update(statut=statut)
            devis.refresh_from_db()
        return devis

    def _post(self, devis, route, layout, **extra):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/{route}/', layout,
            format='json', **extra)

    def _calepinage(self, devis):
        return Calepinage.objects.filter(company=self.company,
                                         devis=devis).first()

    def test_post_layout_ecrit_le_calepinage_lie_puis_resynchronise(self):
        devis = self._devis()
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            titre='ACAL96', roof_layout=_layout(6, 6),
            layout_hash=layout_hash(_layout(6, 6)))
        nouveau = _layout(8, 6)
        r = self._post(devis, 'layout', nouveau)
        self.assertEqual(r.status_code, 200, r.content)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, nouveau)
        self.assertEqual(calepinage.versions.count(), 1)
        devis.refresh_from_db()
        # Le devis est RESYNCHRONISÉ depuis le calepinage : 14 panneaux.
        self.assertEqual(
            int(devis.lignes.get(produit=self.panneau).quantite), 14)
        self.assertEqual(devis.layout_hash, layout_hash(nouveau))
        self.assertEqual(len(devis.roof_layout['_pans_geometry']), 2)
        self.assertEqual(r.data['roof_layout'], devis.roof_layout)

    def test_sync_layout_n_ecrit_jamais_devis_roof_layout_depuis_le_corps(self):
        devis = self._devis()
        corps = _layout(6, 6)
        corps['_pans_geometry'] = [{'label': 'Faux', 'kwc': 99}]
        r = self._post(devis, 'sync-layout', corps)
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        # Le corps n'est JAMAIS recopié : l'instantané est celui du
        # calepinage, rangé par la création (2 pans réels, pas le faux).
        self.assertNotEqual(devis.roof_layout, corps)
        pans = devis.roof_layout['_pans_geometry']
        self.assertEqual([p['label'] for p in pans],
                         ['Pan Est', 'Pan Ouest'])
        # La clé privée du corps n'entre pas dans la conception.
        calepinage = self._calepinage(devis)
        self.assertNotIn('_pans_geometry', calepinage.roof_layout)
        self.assertEqual(_sans_privees(devis.roof_layout),
                         calepinage.roof_layout)

    def test_devis_sans_calepinage_adopte_ou_cree(self):
        # Créé : aucun calepinage ouvert sur le lead.
        devis = self._devis()
        self.assertIsNone(self._calepinage(devis))
        r = self._post(devis, 'sync-layout', _layout(6, 6))
        self.assertEqual(r.status_code, 200, r.content)
        cree = self._calepinage(devis)
        self.assertIsNotNone(cree)
        self.assertEqual(cree.roof_layout, _layout(6, 6))
        self.assertEqual(cree.company_id, self.company.pk)
        # Adopté : l'ouvert UNIQUE du lead (sans devis) est rattaché.
        lead = Lead.objects.create(company=self.company, nom='Lead ACAL96',
                                   telephone='+212600009696')
        ouvert = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Ouvert ACAL96',
            roof_layout=_layout(5, 5), layout_hash=layout_hash(_layout(5, 5)))
        devis2 = self._devis(lead=lead)
        r = self._post(devis2, 'sync-layout', _layout(7, 5))
        self.assertEqual(r.status_code, 200, r.content)
        ouvert.refresh_from_db()
        self.assertEqual(ouvert.devis_id, devis2.pk)
        self.assertEqual(ouvert.roof_layout, _layout(7, 5))
        self.assertEqual(
            Calepinage.objects.filter(devis=devis2).count(), 1)

    def test_sync_layout_passe_par_les_portes_de_publication(self):
        """Lot 2 critique #28 — ``sync-layout`` / ``POST layout`` du devis
        resynchronisent par LA porte du module : approbation exigée et non à
        jour ⇒ 400 ``{approbation}``, verdict électrique bloquant ⇒ 422
        ``{detail, electrique}`` — lignes du devis inchangées."""
        from unittest import mock

        from apps.calepinage.services.electrique import PublicationBloquee
        from apps.calepinage.services.parametres import enregistrer_parametres

        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': True}})
        devis = self._devis()
        for route in ('sync-layout', 'layout'):
            with self.subTest(route=route):
                r = self._post(devis, route, _layout(8, 6))
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn('approbation', r.data)
                self.assertEqual(
                    int(devis.lignes.get(produit=self.panneau).quantite), 12)

        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': False}})
        bloque = PublicationBloquee(
            'Publication refusée', bloquants=[
                {'code': 'X', 'libelle': 'Isc hors spécification',
                 'detail': 'essai'}])
        with mock.patch(
                'apps.calepinage.services.electrique.garde_publication',
                side_effect=bloque):
            r = self._post(devis, 'sync-layout', _layout(9, 6))
        self.assertEqual(r.status_code, 422, r.content)
        self.assertIn('detail', r.data)
        self.assertEqual(r.data['electrique']['verdict'], 'bloquant')
        self.assertEqual(
            int(devis.lignes.get(produit=self.panneau).quantite), 12)

    def test_verrou_respecte_409(self):
        for statut in ('accepte', 'refuse', 'expire'):
            with self.subTest(statut=statut):
                devis = self._devis(statut=statut,
                                    roof_layout=_layout(6, 6))
                for route in ('sync-layout', 'layout'):
                    r = self._post(devis, route, _layout(9, 9))
                    self.assertEqual(r.status_code, 409, r.content)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, statut)
                self.assertEqual(devis.layout_hash, layout_hash(_layout(6, 6)))
                self.assertIsNone(self._calepinage(devis))
        # Jeton If-Match périmé : 409 nommé, rien n'est écrit.
        devis = self._devis()
        self._post(devis, 'sync-layout', _layout(6, 6))
        calepinage = self._calepinage(devis)
        r = self._post(devis, 'sync-layout', _layout(9, 9),
                       HTTP_IF_MATCH='"perime"')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data.get('code'), 'document_modifie')
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout, _layout(6, 6))

    def test_from_layout_puis_post_layout_garde_pans_geometry(self):
        # Un devis dont le layout stocké est BRUT (ancien POST layout) : le
        # renvoi identique le RANGE une fois (court-circuit refusé sans
        # _pans_geometry), puis le renvoi suivant est « inchangé » partout.
        brut = _layout(6, 6)
        devis = self._devis(roof_layout=copy.deepcopy(brut))
        r = self._post(devis, 'layout', brut)
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(len(devis.roof_layout['_pans_geometry']), 2)
        self.assertEqual(len(zones_etude_du_devis(devis)), 2)
        self.assertEqual(len(groupes_du_devis(devis)), 2)
        calepinage = self._calepinage(devis)
        versions = calepinage.versions.count()
        r = self._post(devis, 'sync-layout', brut)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data['inchange'])
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.versions.count(), versions)
        devis.refresh_from_db()
        self.assertEqual(len(devis.roof_layout['_pans_geometry']), 2)

    def test_json_public_porte_les_pans(self):
        devis = self._devis()
        r = self._post(devis, 'sync-layout', _layout(6, 6))
        self.assertEqual(r.status_code, 200, r.content)
        lien = ShareLink.for_devis(devis)
        pub = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(pub.status_code, 200, pub.content)
        roof = _cle(pub.data, 'roof_layout')
        self.assertIsInstance(roof, dict, pub.data)
        self.assertEqual([p.get('label') for p in roof.get('pans') or []],
                         ['Pan Est', 'Pan Ouest'])
