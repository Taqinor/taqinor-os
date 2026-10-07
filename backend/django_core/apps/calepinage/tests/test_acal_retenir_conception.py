"""ACAL107 (D-ACAL-2, D-ACAL-23) — retenir une variante l'ÉCRIT comme
conception courante ; le chantier et l'as-built lisent l'instantané figé de
la version ACCEPTÉE en vigueur, sinon la conception courante.

Ce qui est prouvé ici (catalogue tarifé réel, HTTP réel, aucun mock) :

* POST variantes/<A>/retenir/ : Calepinage.roof_layout == A.roof_layout, une
  version « Variante « A » retenue », A.retenue ; retenir A une seconde fois
  ⇒ aucune nouvelle version ;
* « Générer le devis » puis « Resynchroniser » chiffrent la RETENUE ;
* l'as-built lit la conception (plus la variante en parallèle) ;
* le chantier lit l'instantané V1 tant que V2 n'est pas acceptée, puis V2 ;
* l'import d'un projet restaure la retenue SANS réécrire la conception ;
* la bascule est journalisée AVEC son auteur.

Run :
    python manage.py test apps.calepinage.tests.test_acal_retenir_conception -v2
"""

from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.selectors import calepinage_retenu_pour_devis
from apps.calepinage.services import asbuilt
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import creer_variante
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def _toit(panneaux):
    return {
        'areas': [{
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'flat', 'pitch': 10,
            'azimuth': 180,
        }],
        'scenario': 'reseau',
        'result': {'panels': panneaux, 'kwc': round(panneaux * 0.55, 2),
                   'annualKwh': 10800, 'savings': 9200},
    }


def _panneaux_du_devis(devis_id):
    devis = Devis.objects.get(pk=devis_id)
    return sum(int(li.quantite) for li in devis.lignes.all()
               if 'panneau' in (li.designation or '').lower())


class RetenirConceptionTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-VAR')
        enregistrer_layout(self.calepinage, _toit(10), user=self.user)
        self.a = creer_variante(self.calepinage, nom='A',
                                roof_layout=_toit(14), user=self.user)

    def _retenir(self, variante):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}variantes/{variante.pk}/'
            'retenir/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        return reponse

    def test_retenir_ecrit_la_conception_et_versionne(self):
        self._retenir(self.a)
        self.a.refresh_from_db()
        self.assertTrue(self.a.retenue)
        self.assertEqual(self.calepinage.roof_layout, self.a.roof_layout)
        versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage, libelle='Variante « A » retenue')
        self.assertEqual(versions.count(), 1)
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        self._retenir(self.a)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), avant)
        # Rouvrir l'atelier : le document EST la variante.
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}layout/')
        self.assertEqual(reponse.data['roof_layout'], self.a.roof_layout)

    def test_generer_chiffre_la_retenue(self):
        self._retenir(self.a)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}generer-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(_panneaux_du_devis(reponse.data['devis']), 14)

    def test_resynchroniser_chiffre_la_retenue(self):
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}generer-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis_id = reponse.data['devis']
        self.assertEqual(_panneaux_du_devis(devis_id), 10)
        self._retenir(self.a)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}sync-devis/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(_panneaux_du_devis(devis_id), 14)

    def test_asbuilt_lit_la_conception(self):
        self._retenir(self.a)
        # Un enregistrement ultérieur de l'atelier ne touche pas la variante,
        # et l'as-built lit la CONCEPTION, plus la variante en parallèle.
        plus_tard = {'version': 2, 'zones': [
            {'id': 'z1', 'label': 'Pan Sud',
             'geometry': {'count': 9, 'azimuthDeg': 180, 'tiltDeg': 15}}]}
        enregistrer_layout(self.calepinage, plus_tard, user=self.user)
        self.a.refresh_from_db()
        self.assertEqual(self.a.roof_layout, _toit(14))
        prevus, source = asbuilt.pans_prevus(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_CALEPINAGE)
        self.assertEqual(sum(p['modules'] for p in prevus), 9)

    def _chaine_v1_v2(self):
        v1 = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL107-V1', statut=Devis.Statut.ACCEPTE,
            roof_layout=_toit(10), is_active=False)
        v2 = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL107-V2', statut=Devis.Statut.BROUILLON,
            roof_layout=_toit(14))
        Devis.objects.filter(pk=v1.pk).update(superseded_by=v2)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=v2)
        self.calepinage.refresh_from_db()
        return v1, v2

    def test_chantier_lit_l_instantane_v1_tant_que_v2_non_acceptee(self):
        self._retenir(self.a)
        _v1, v2 = self._chaine_v1_v2()
        document, source = asbuilt.conception_du_chantier(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_DEVIS_ACCEPTE)
        self.assertEqual(document['result']['panels'], 10)
        bloc = calepinage_retenu_pour_devis(v2.pk, self.company)
        self.assertEqual(bloc['nb_modules'], 10)

    def test_chantier_bascule_sur_v2_a_son_acceptation(self):
        self._retenir(self.a)
        _v1, v2 = self._chaine_v1_v2()
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        document, source = asbuilt.conception_du_chantier(self.calepinage)
        self.assertEqual(source, asbuilt.SOURCE_DEVIS_ACCEPTE)
        self.assertEqual(document['result']['panels'], 14)
        bloc = calepinage_retenu_pour_devis(v2.pk, self.company)
        self.assertEqual(bloc['nb_modules'], 14)

    def test_import_restaure_sans_reecrire(self):
        from apps.calepinage.services.export_projet import importer_projet

        from .test_calx370_projet_json import fichier

        document = fichier()
        self.assertIn('outline', document['roof_layout'])
        resume = importer_projet(document, self.company,
                                 client_id=self.client_a.pk)
        copie = Calepinage.objects.get(pk=resume['calepinage'])
        retenue = CalepinageVariante.objects.get(calepinage=copie,
                                                 retenue=True)
        self.assertNotIn('outline', retenue.roof_layout)
        # La conception importée reste LE document (jamais la variante).
        self.assertIn('outline', copie.roof_layout)

    def test_retenue_journalisee_avec_auteur(self):
        self._retenir(self.a)
        entree = (Activity.objects
                  .filter(content_type=ContentType.objects.get_for_model(
                      Calepinage), object_id=self.calepinage.pk,
                      field='variante')
                  .order_by('-id').first())
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, 'A')
        self.assertEqual(entree.created_by_id, self.user.pk)
