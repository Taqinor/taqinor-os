"""Revue chantier 26/10/2026 — capture terrain : n° de série + photos.

Nouveau fichier car : lanes parallèles file-disjointes de la revue chantier du
26/10/2026.

Couvre :
  * ``GET interventions/<pk>/serials-attendus/`` = le contrat
    ``contract_samples/intervention_serials_attendus.json`` (clés + natures),
    comptes avec doublons, séries du parc, relevé sans produit rattaché par
    désignation, produits hors parc exclus, isolation société ;
  * ``ajouter-serial`` : produit (désignation par défaut = nom), caractéristiques
    validées, source de capture, refus sans produit ni désignation ;
  * poussée au parc d'un relevé sans produit dont la désignation désigne un
    seul produit porteur ; les autres signalés (``non_rattaches``) ;
  * avertissement CONSULTATIF « Séries manquantes » à côté des raisons de
    refus du passage à « Terminée » + ``series_manquantes`` sur la fiche ;
  * méta photo d'intervention (géoloc best-effort + instant appareil) ;
  * ``cocher-checklist`` : 409 sur une étape à photo obligatoire sans photo,
    même règle par la synchro hors-ligne.

Run :
    python manage.py test apps.installations.tests_revue_chantier_terrain -v2
"""
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.installations import field_capture, field_services
from apps.installations.models import (
    ComponentSerial, Installation, PhotoChecklistMeta,
)
from apps.installations.services import (
    TransitionRefusee, changer_statut_intervention, ensure_checklist_items,
)
from apps.installations.tests_field_capture import (
    auth, make_chantier, make_company, make_intervention, make_produit,
    png_file,
)
from apps.records.models import Attachment
from apps.sav.models import Equipement
from apps.stock.models import Categorie

User = get_user_model()
BASE = '/api/django/installations'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'intervention_serials_attendus.json')


def _nature(valeur):
    if valeur is None:
        return 'null'
    if isinstance(valeur, bool):
        return 'bool'
    if isinstance(valeur, (int, float)):
        return 'nombre'
    return type(valeur).__name__


class _Base(TestCase):
    def setUp(self):
        self.company = make_company('terrain-co', 'Terrain Co')
        self.user = User.objects.create_user(
            username='terrain_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        cats = {t: Categorie.objects.create(
            company=self.company, nom=f'Cat {t}', type_equipement=t)
            for t in ('panneau', 'onduleur', 'structure')}
        self.panneau = make_produit(self.company, 'Panneau Terrain 710W', 50)
        self.onduleur = make_produit(self.company, 'Onduleur Terrain 10kW', 5)
        self.structure = make_produit(self.company, 'Rail Terrain', 50)
        for produit, cle in ((self.panneau, 'panneau'),
                             (self.onduleur, 'onduleur'),
                             (self.structure, 'structure')):
            produit.categorie = cats[cle]
            produit.marque = 'Marque ' + cle
            produit.save(update_fields=['categorie', 'marque'])
        self.inst = make_chantier(self.company, self.user, [
            (self.panneau, 3), (self.onduleur, 1), (self.structure, 2)])
        self.iv = make_intervention(self.inst, self.company, self.user)
        self.iv2 = make_intervention(self.inst, self.company, self.user)
        self.url = f'{BASE}/interventions/{self.iv.id}'

    def _serial(self, iv, numero, produit=None, designation=''):
        return ComponentSerial.objects.create(
            company=self.company, intervention=iv, produit=produit,
            designation=designation, numero_serie=numero)


class SerialsAttendusTests(_Base):
    def test_forme_egale_au_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        exemple = contrat['exemple']
        self._serial(self.iv, 'P-1', produit=self.panneau)
        r = self.api.get(f'{self.url}/serials-attendus/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), set(exemple))
        for cle, valeur in exemple.items():
            if cle == 'produits':
                continue
            self.assertEqual(_nature(r.data[cle]), _nature(valeur), cle)
        ligne = r.data['produits'][0]
        modele = exemple['produits'][0]
        self.assertEqual(set(ligne), set(modele))
        for cle, valeur in modele.items():
            if cle != 'series':
                self.assertEqual(_nature(ligne[cle]), _nature(valeur), cle)
        self.assertEqual(set(ligne['series'][0]), set(modele['series'][0]))
        self.assertNotIn('prix', json.dumps(r.data))

    def test_comptes_doublons_parc_et_designation(self):
        # Même n° relevé deux fois (donnée héritée) : compté une seule fois.
        self._serial(self.iv, 'P-1', produit=self.panneau)
        self._serial(self.iv2, 'p-1', produit=self.panneau)
        self._serial(self.iv, '', produit=self.panneau)  # vide : ignoré
        # Parc déjà sérié : P-2 compte, P-1 n'est pas compté deux fois.
        Equipement.objects.create(company=self.company, produit=self.panneau,
                                  installation=self.inst, numero_serie='P-2')
        Equipement.objects.create(company=self.company, produit=self.panneau,
                                  installation=self.inst, numero_serie='P-1')
        # Relevé sans produit : rattaché par désignation (casse ignorée).
        self._serial(self.iv2, 'O-1', designation='onduleur terrain 10KW')
        r = self.api.get(f'{self.url}/serials-attendus/')
        self.assertEqual(r.status_code, 200, r.data)
        lignes = {p['produit_id']: p for p in r.data['produits']}
        self.assertNotIn(self.structure.id, lignes)  # hors parc
        pan = lignes[self.panneau.id]
        self.assertEqual((pan['attendu'], pan['releve'], pan['manquant']),
                         (3, 2, 1))
        self.assertEqual({s['source'] for s in pan['series']},
                         {'intervention', 'parc'})
        ond = lignes[self.onduleur.id]
        self.assertEqual((ond['attendu'], ond['releve'], ond['manquant']),
                         (1, 1, 0))
        self.assertEqual(r.data['nb_attendus'], 4)
        self.assertEqual(r.data['nb_releves'], 3)
        self.assertFalse(r.data['complet'])

    def test_chantier_sans_produit_porteur_exemple_vide(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        inst = make_chantier(self.company, self.user, [(self.structure, 4)])
        iv = make_intervention(inst, self.company, self.user)
        r = self.api.get(f'{BASE}/interventions/{iv.id}/serials-attendus/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data), set(contrat['exemple_vide']))
        self.assertEqual(r.data['produits'], [])
        self.assertTrue(r.data['complet'])

    def test_isolation_societe(self):
        autre = make_company('terrain-autre', 'Autre')
        intrus = User.objects.create_user(
            username='terrain_intrus', password='x',
            role_legacy='responsable', company=autre)
        r = auth(intrus).get(f'{self.url}/serials-attendus/')
        self.assertEqual(r.status_code, 404)


class AjouterSerialTests(_Base):
    def test_produit_caracteristiques_et_source(self):
        corps = {
            'produit': self.panneau.id, 'numero_serie': 'CS-0001',
            'capture_source': 'scan',
            'caracteristiques': {'modele': 'CS7N', 'puissance_wc': 710,
                                 'fabricant': 'Canadian Solar'}}
        r = self.api.post(f'{self.url}/ajouter-serial/', corps, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['designation'], self.panneau.nom)
        self.assertEqual(r.data['capture_source'], 'scan')
        self.assertEqual(r.data['caracteristiques']['puissance_wc'], 710)
        serial = ComponentSerial.objects.get(pk=r.data['id'])
        self.assertEqual(serial.caracteristiques['modele'], 'CS7N')

    def test_sans_produit_ni_designation_409(self):
        # api-fuzz-full 27/10 (ENF11) : « l'un OU l'autre » de deux champs
        # facultatifs, règle que le schéma du corps ne porte pas → 409 (400).
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'numero_serie': 'X-1'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('designation', r.data)
        self.assertFalse(ComponentSerial.objects.filter(
            numero_serie='X-1').exists())

    def test_caracteristiques_imbriquees_400(self):
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': self.panneau.id, 'numero_serie': 'X-2',
            'caracteristiques': {'modele': {'a': 1}}}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('caracteristiques', r.data)

    def test_produit_autre_societe_400(self):
        autre = make_company('terrain-autre2', 'Autre 2')
        etranger = make_produit(autre, 'Panneau étranger', 1)
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': etranger.id, 'numero_serie': 'X-3'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_validation_caracteristiques(self):
        ok, err = field_capture.valider_caracteristiques(
            {f'k{i}': 'v' for i in range(11)})
        self.assertIsNone(ok)
        self.assertTrue(err)
        ok, err = field_capture.valider_caracteristiques('{"modele": "A"}')
        self.assertEqual(ok, {'modele': 'A'})
        self.assertIsNone(err)

    def test_caracteristiques_non_finies_refusees(self):
        # NaN / Infinity / 1e400 (→ inf) feraient une DataError jsonb (500).
        for brut in ('{"puissance_wc": NaN}', '{"puissance_wc": Infinity}',
                     '{"puissance_wc": -Infinity}', '{"puissance_wc": 1e400}'):
            ok, err = field_capture.valider_caracteristiques(brut)
            self.assertIsNone(ok, brut)
            self.assertTrue(err, brut)
        ok, err = field_capture.valider_caracteristiques(
            {'puissance_wc': float('inf')})
        self.assertIsNone(ok)
        self.assertTrue(err)
        ok, err = field_capture.valider_caracteristiques('{"puissance_wc": 710.5}')
        self.assertEqual(ok, {'puissance_wc': 710.5})

    def test_caracteristiques_publiees_egal_acceptation(self):
        """api-fuzz-full 27/10 (ENF11) : le schéma publie un objet plat de
        valeurs texte/nombre ; une liste est refusée par le schéma ET le
        serveur, une clé blanche/longue (inexprimable) est nettoyée."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.installations import urls as installations_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/installations/', include(installations_urls)),
        ]).get_schema(request=None, public=True)
        champ = schema['components']['schemas']['AjouterSerialRequeteRequest'][
            'properties']['caracteristiques']
        self.assertEqual(champ['maxProperties'], 10)
        self.assertEqual({t['type'] for t in
                          champ['additionalProperties']['oneOf']},
                         {'string', 'number'})
        ok, err = field_capture.valider_caracteristiques(
            {'  ': 'x', 'k' * 50: 'v', 'mo\x00dele': 'A'})
        self.assertEqual(ok, {'k' * 40: 'v', 'modele': 'A'})
        for brut in ({'a': []}, {'a': 'b\x00c'}):
            ok, err = field_capture.valider_caracteristiques(brut)
            self.assertIsNone(ok, brut)
            self.assertTrue(err, brut)

    def test_caracteristiques_multipart_nan_400(self):
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': self.panneau.id, 'numero_serie': 'X-NAN',
            'caracteristiques': '{"puissance_wc": NaN}'}, format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('caracteristiques', r.data)


class PousseeParcTests(_Base):
    def test_designation_rattachee_puis_poussee(self):
        rattache = self._serial(self.iv, 'PAN-77',
                                designation='PANNEAU terrain 710w')
        orphelin = self._serial(self.iv, 'ZZ-1', designation='Truc inconnu')
        resultat = field_capture.push_serials_to_parc(self.iv, self.user)
        rattache.refresh_from_db()
        orphelin.refresh_from_db()
        self.assertEqual(rattache.produit_id, self.panneau.id)
        self.assertTrue(rattache.pousse_parc)
        self.assertTrue(Equipement.objects.filter(
            company=self.company, numero_serie='PAN-77').exists())
        self.assertIsNone(orphelin.produit_id)
        self.assertFalse(orphelin.pousse_parc)
        self.assertEqual(resultat.non_rattaches, 1)

    def test_note_sans_composant_non_repetee(self):
        from apps.installations.models import InterventionActivity
        self._serial(self.iv, 'ZZ-2', designation='Truc inconnu')
        field_capture.push_serials_to_parc(self.iv, self.user)
        field_capture.push_serials_to_parc(self.iv, self.user)
        self.assertEqual(InterventionActivity.objects.filter(
            intervention=self.iv, body__contains='sans composant catalogue',
        ).count(), 1)
        # Un orphelin de plus change le compte : nouvelle note.
        self._serial(self.iv, 'ZZ-3', designation='Autre inconnu')
        field_capture.push_serials_to_parc(self.iv, self.user)
        self.assertEqual(InterventionActivity.objects.filter(
            intervention=self.iv, body__contains='sans composant catalogue',
        ).count(), 2)

    def test_equipement_remplace_non_compte(self):
        from apps.sav.selectors import equipements_series_du_chantier
        Equipement.objects.create(
            company=self.company, produit=self.panneau, installation=self.inst,
            numero_serie='OLD-1', statut=Equipement.Statut.REMPLACE)
        Equipement.objects.create(
            company=self.company, produit=self.panneau, installation=self.inst,
            numero_serie='NEW-1')
        releve = [e['numero_serie'] for e in equipements_series_du_chantier(
            self.company, self.inst.id)]
        self.assertEqual(releve, ['NEW-1'])


class AvertissementSeriesTests(_Base):
    def test_avertissement_consultatif_a_cote_du_refus(self):
        with self.assertRaises(TransitionRefusee) as ctx:
            changer_statut_intervention(self.iv, 'terminee', self.user)
        self.assertEqual(ctx.exception.avertissements,
                         ['Séries manquantes : 3 panneaux, 1 onduleur'])
        r = self.api.patch(f'{self.url}/', {'statut': 'terminee'},
                           format='json')
        # api-fuzz-full 27/10 (ENF11) : refus d'ÉTAT = 409, mêmes clés de corps.
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('statut', r.data)
        self.assertEqual([str(a) for a in r.data['avertissements']],
                         ['Séries manquantes : 3 panneaux, 1 onduleur'])

    def test_series_manquantes_sur_la_fiche(self):
        self._serial(self.iv, 'P-9', produit=self.panneau)
        r = self.api.get(f'{self.url}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['series_manquantes'], 3)
        self.assertEqual(
            field_services.avertissements_terminee(self.iv, 'en_cours'), [])


@mock.patch('apps.records.storage.get_minio_client')
class PhotoMetaInterventionTests(_Base):
    def setUp(self):
        super().setUp()
        field_services.seed_shotlist_slots(self.company)

    def test_geoloc_et_horodatage_client_stockes(self, _minio):
        r = self.api.post(f'{self.url}/ajouter-photo/', {
            'file': png_file(), 'slot': 'toiture_avant',
            'lat': '33.573110', 'lng': '-7.589843', 'accuracy_m': '12.5',
            'client_ts': '2026-10-26T09:15:00+01:00'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        meta = PhotoChecklistMeta.objects.get(attachment_id=r.data['id'])
        self.assertEqual(meta.intervention_id, self.iv.id)
        self.assertIsNone(meta.checklist_item_id)
        self.assertAlmostEqual(float(meta.latitude), 33.57311, places=5)
        self.assertEqual(meta.precision_m, 12.5)
        self.assertIsNotNone(meta.horodatage_client)
        g = self.api.get(f'{self.url}/photos/')
        toiture = next(s for s in g.data['groupes']['avant']
                       if s['cle'] == 'toiture_avant')
        photo = toiture['photos'][0]
        self.assertAlmostEqual(photo['lat'], 33.57311, places=5)
        self.assertEqual(photo['accuracy_m'], 12.5)
        self.assertIsNotNone(photo['horodatage_serveur'])

    def test_sans_gps_ou_gps_illisible_jamais_bloquant(self, _minio):
        r = self.api.post(f'{self.url}/ajouter-photo/', {
            'file': png_file(), 'slot': 'toiture_avant',
            'lat': 'abc', 'lng': '999'}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['lat'])
        meta = PhotoChecklistMeta.objects.get(attachment_id=r.data['id'])
        self.assertIsNone(meta.latitude)
        self.assertIsNone(meta.longitude)

    def test_meta_jamais_deux_cibles(self, _minio):
        item = ensure_checklist_items(self.inst)[0]
        meta = PhotoChecklistMeta(
            company=self.company, intervention=self.iv, checklist_item=item)
        with self.assertRaises(ValidationError):
            meta.clean()


class ChecklistPhotoObligatoireTests(_Base):
    def setUp(self):
        super().setUp()
        self.item = ensure_checklist_items(self.inst)[0]
        self.item.photo_obligatoire = True
        self.item.save(update_fields=['photo_obligatoire'])
        self.cocher = f'{BASE}/chantiers/{self.inst.id}/cocher-checklist/'

    def _photo_etape(self):
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.create(
            company=self.company, content_type=ct, object_id=self.inst.id,
            file_key=f'attachments/{self.company.id}/etape.jpg',
            filename='etape.jpg', size=10, mime='image/jpeg', phase='pendant')
        PhotoChecklistMeta.objects.create(
            company=self.company, attachment=att, checklist_item=self.item)

    def test_vue_409_sans_photo_puis_200(self):
        r = self.api.post(self.cocher, {'cle': self.item.cle, 'fait': True},
                          format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(self.item.libelle, r.data['detail'])
        self.item.refresh_from_db()
        self.assertFalse(self.item.fait)
        # Décocher reste toujours permis.
        r = self.api.post(self.cocher, {'cle': self.item.cle, 'fait': False},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._photo_etape()
        r = self.api.post(self.cocher, {'cle': self.item.cle, 'fait': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.item.refresh_from_db()
        self.assertTrue(self.item.fait)

    def test_synchro_meme_regle(self):
        op = {'client_op_id': 'terrain-chk-1',
              'op_type': 'chantier.cocher_checklist',
              'payload': {'chantier': self.inst.id, 'cle': self.item.cle,
                          'fait': True}}
        r = self.api.post(f'{BASE}/sync/', {'ops': [op]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        res = r.data['results'][0]
        self.assertEqual(res['status'], 'error', res)
        self.assertIn('Photo requise', res['error'])
        self.item.refresh_from_db()
        self.assertFalse(self.item.fait)
        self._photo_etape()
        r = self.api.post(f'{BASE}/sync/', {'ops': [op]}, format='json')
        self.assertEqual(r.data['results'][0]['status'], 'applied')
