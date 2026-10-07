# -*- coding: utf-8 -*-
"""ACAL300 (C-ACAL-016, D-ACAL-14) — le calepinage est fournisseur DSR (loi
09-08) et son titre par défaut ne recopie plus le nom d'une personne.

LE CONSTAT : ``creer_pour_lead`` titrait « Calepinage Dupont » ; aucun
fournisseur ``calepinage`` n'était enregistré auprès de ``core.dsr`` — un
effacement légal laissait le nom, les photos de la maison, l'épingle GPS et la
géométrie absolue du toit (qui localise la personne à elle seule).

Chaîne RÉELLE : ``core.dsr.exporter`` / ``effacer`` (registre réel), CRM réel
(``crm.selectors``), base réelle. Aucun mock du registre ni du CRM.
"""
from __future__ import annotations

import datetime
from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from apps.calepinage.dsr_provider import NOTE_ANONYMISATION
from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion, PhotoSite,
)
from apps.calepinage.services.creation import creer_pour_lead
from apps.calepinage.services.documents.gabarit_document import (
    identite_du_calepinage,
)
from apps.crm.models import Lead
from apps.records.models import Activity, Attachment
from core import dsr

from .test_api_liste import BaseApiCalepinage, url_detail

EMAIL = 'dupont.acal@example.ma'
DOCUMENT = {
    'version': 2,
    'pin': {'lat': 33.5, 'lng': -7.6},
    'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999]],
    'zones': [{'id': 'z1', 'label': 'Pan Sud',
               'vertices': [[-7.6, 33.5], [-7.5999, 33.5],
                            [-7.5999, 33.5001]],
               'geometry': {'count': 4, 'origin': [-7.6, 33.5]}}],
}


def _coordonnees_absolues(document):
    """Toute paire qui ressemble encore à [lng≈-7.6, lat≈33.5]."""
    trouvees = []

    def parcourir(noeud):
        if isinstance(noeud, dict):
            for valeur in noeud.values():
                parcourir(valeur)
        elif isinstance(noeud, list):
            if (len(noeud) >= 2 and all(isinstance(v, (int, float))
                                        for v in noeud[:2])
                    and {round(abs(noeud[0])), round(abs(noeud[1]))}
                    == {8, 34}):
                trouvees.append(noeud)
            for valeur in noeud:
                parcourir(valeur)

    parcourir(document)
    return trouvees


class DsrCalepinageTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.dupont = Lead.objects.create(company=self.company, nom='Dupont',
                                          email=EMAIL)

    def _calepinage_complet(self):
        calepinage = creer_pour_lead(self.dupont.pk, self.company,
                                     user=self.user)
        Calepinage.objects.filter(pk=calepinage.pk).update(
            titre='Maison Dupont', roof_layout=DOCUMENT)
        calepinage.refresh_from_db()
        CalepinageVersion.objects.create(
            company=self.company, calepinage=calepinage,
            libelle='V1', roof_layout=DOCUMENT)
        CalepinageVariante.objects.create(
            company=self.company, calepinage=calepinage, nom='Variante A',
            roof_layout=DOCUMENT)
        piece = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, file_key='roofs/acal300/photo.jpg',
            filename='photo.jpg', mime='image/jpeg')
        PhotoSite.objects.create(
            company=self.company, calepinage=calepinage, attachment=piece,
            prise_le=datetime.date(2026, 9, 1))
        return calepinage, piece

    def test_titre_par_defaut_sans_nom_de_personne(self):
        calepinage = creer_pour_lead(self.dupont.pk, self.company,
                                     user=self.user)

        self.assertEqual(calepinage.titre, '')
        self.assertEqual(str(calepinage), f'Calepinage #{calepinage.pk}')
        self.assertNotIn('Dupont', self.api.get(
            url_detail(calepinage.pk)).data['nom'])

    def test_titre_saisi_conserve(self):
        calepinage = creer_pour_lead(self.dupont.pk, self.company,
                                     user=self.user, titre='Ma toiture')

        self.assertEqual(calepinage.titre, 'Ma toiture')

    def test_export_liste_les_calepinages_du_sujet(self):
        calepinage, _piece = self._calepinage_complet()
        Calepinage.objects.create(company=self.company,
                                  lead_id=self.lead.pk, titre='Autre')

        export = dsr.exporter(self.company, EMAIL)['calepinage']

        self.assertEqual([c['id'] for c in export['calepinages']],
                         [calepinage.pk])
        ligne = export['calepinages'][0]
        self.assertEqual(sorted(ligne), ['client', 'id', 'lead', 'nb_photos',
                                         'pin', 'reference', 'titre'])
        self.assertEqual(ligne['nb_photos'], 1)
        self.assertEqual(ligne['pin'], {'lat': 33.5, 'lng': -7.6})

    def test_effacement_titre_photos_pin_versions_variantes(self):
        calepinage, piece = self._calepinage_complet()

        with self.captureOnCommitCallbacks() as rappels:
            rendu = dsr.effacer(self.company, EMAIL)

        self.assertEqual(rendu['calepinage'], {'anonymises': 1})
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, '')
        self.assertEqual(PhotoSite.objects.filter(
            calepinage=calepinage).count(), 0)
        self.assertFalse(Attachment.objects.filter(pk=piece.pk).exists())
        self.assertTrue(rappels)  # l'objet stocké part après validation
        documents = [calepinage.roof_layout] + [
            v.roof_layout for v in CalepinageVersion.objects.filter(
                calepinage=calepinage)] + [
            v.roof_layout for v in CalepinageVariante.objects.filter(
                calepinage=calepinage)]
        for document in documents:
            self.assertNotIn('pin', document)
            self.assertEqual(document['repere']['type'], 'local')
            self.assertEqual(_coordonnees_absolues(document), [])
        self.assertNotEqual(calepinage.layout_hash, '')
        # Le titre affiché et la page de garde ne nomment plus personne.
        self.assertEqual(identite_du_calepinage(calepinage)['projet'],
                         f'Calepinage #{calepinage.pk}')
        note = Activity.objects.filter(
            object_id=calepinage.pk, kind='note',
            body=NOTE_ANONYMISATION)
        self.assertEqual(note.count(), 1)

    def test_effacement_idempotent(self):
        calepinage, _piece = self._calepinage_complet()
        dsr.effacer(self.company, EMAIL)
        calepinage.refresh_from_db()
        avant = (calepinage.titre, calepinage.roof_layout,
                 calepinage.layout_hash)

        self.assertEqual(dsr.effacer(self.company, EMAIL)['calepinage'],
                         {'anonymises': 0})
        calepinage.refresh_from_db()
        self.assertEqual((calepinage.titre, calepinage.roof_layout,
                          calepinage.layout_hash), avant)
        self.assertEqual(Activity.objects.filter(
            object_id=calepinage.pk, kind='note',
            body=NOTE_ANONYMISATION).count(), 1)

    def test_geometrie_translatee_en_repere_local(self):
        calepinage, _piece = self._calepinage_complet()

        dsr.effacer(self.company, EMAIL)

        calepinage.refresh_from_db()
        sommets = calepinage.roof_layout['zones'][0]['vertices']
        self.assertEqual(sommets[0], [0.0, 0.0])  # l'ancienne épingle
        self.assertAlmostEqual(sommets[1][0], 9.3, delta=0.2)  # ≈ 0,0001° E
        self.assertAlmostEqual(sommets[2][1], 11.1, delta=0.2)  # ≈ 0,0001° N

    def test_ligne_de_creation_anonymisee(self):
        calepinage, _piece = self._calepinage_complet()
        creation = Activity.objects.get(object_id=calepinage.pk,
                                        kind='creation', field='calepinage')
        self.assertNotIn('Dupont', creation.new_value)  # titre vide à la création
        Activity.objects.filter(pk=creation.pk).update(
            new_value='Maison Dupont')

        dsr.effacer(self.company, EMAIL)

        creation.refresh_from_db()
        self.assertEqual(creation.new_value, 'Calepinage créé')

    def test_page_de_garde_projet_sans_nom(self):
        calepinage = creer_pour_lead(self.dupont.pk, self.company,
                                     user=self.user)

        identite = identite_du_calepinage(calepinage)

        self.assertEqual(identite['projet'], f'Calepinage #{calepinage.pk}')

    def test_commande_rattrapage_dry_run_puis_apply(self):
        calepinage, _piece = self._calepinage_complet()
        Lead.objects.filter(pk=self.dupont.pk).update(
            nom='Anonymisé', email=None, telephone=None)

        sortie = StringIO()
        call_command('anonymiser_calepinages_effaces', stdout=sortie)
        self.assertIn('%s / Maison Dupont / 1 photo(s)' % calepinage.pk,
                      sortie.getvalue())
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, 'Maison Dupont')  # dry-run

        call_command('anonymiser_calepinages_effaces', '--apply',
                     stdout=StringIO())
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, '')
        self.assertNotIn('pin', calepinage.roof_layout)
