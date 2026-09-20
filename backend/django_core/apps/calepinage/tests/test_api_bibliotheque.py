"""CAL246 — la bibliothèque (presets, kits, modèles, favoris) en lecture.

Ce qui est prouvé ici :

* ``GET /api/django/calepinage/parametres/`` porte AUSSI ``kits`` (catalogue
  AO lu, jamais stocké) en plus des sept sections ;
* ``PUT`` refuse ``kits`` comme toute section inconnue (catalogue en
  LECTURE SEULE depuis cet endpoint) ;
* ``GET /api/django/calepinage/calepinages/modeles/`` rend UNIQUEMENT les
  calepinages marqués modèle de la société de l'appelant ;
* sans ``calepinage_voir``, les deux répondent 403 ; un calepinage/kit d'une
  autre société n'apparaît jamais.

Run :
    python manage.py test apps.calepinage.tests.test_api_bibliotheque -v2
"""
from decimal import Decimal

from apps.ao.models import KitCalepinage
from apps.calepinage.models import Calepinage
from apps.calepinage.services.modeles import marquer_modele

from .test_api_liste import URL, BaseApiCalepinage

URL_PARAMETRES = '/api/django/calepinage/parametres/'
URL_MODELES = f'{URL}modeles/'


class BibliothequeParametresTest(BaseApiCalepinage):
    def test_get_porte_les_kits_en_plus_des_sept_sections(self):
        KitCalepinage.objects.create(
            company=self.company, code='VILLA-720-EW', libelle='Chevron 720',
            modules_par_kit=2, pas_rangee_m=Decimal('1.134'),
            longueur_pente_m=Decimal('1.303'), puissance_module_w=720)
        reponse = self.api.get(URL_PARAMETRES)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('kits', reponse.data)
        self.assertEqual(len(reponse.data['kits']), 1)
        for section in ('imagerie', 'degagements', 'zones_types',
                        'gabarits_disposition', 'presets',
                        'favoris_materiel', 'gabarits_dossier'):
            self.assertIn(section, reponse.data)

    def test_get_sans_kit_rend_liste_vide(self):
        reponse = self.api.get(URL_PARAMETRES)
        self.assertEqual(reponse.data['kits'], [])

    def test_put_refuse_kits_comme_section_inconnue(self):
        reponse = self.api.put(URL_PARAMETRES, {'kits': []}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('kits', reponse.data)

    def test_kit_d_une_autre_societe_jamais_vu(self):
        KitCalepinage.objects.create(
            company=self.autre, code='AUTRE', libelle='Autre société',
            modules_par_kit=2, pas_rangee_m=Decimal('1.0'),
            longueur_pente_m=Decimal('1.0'), puissance_module_w=500)
        reponse = self.api.get(URL_PARAMETRES)
        self.assertEqual(reponse.data['kits'], [])

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(URL_PARAMETRES)
        self.assertEqual(reponse.status_code, 403)


class BibliothequeModelesTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa type')
        self.non_modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Autre')
        marquer_modele(self.modele)

    def test_liste_uniquement_les_modeles(self):
        reponse = self.api.get(URL_MODELES)
        self.assertEqual(reponse.status_code, 200)
        ids = {ligne['id'] for ligne in self._lignes(reponse)}
        self.assertEqual(ids, {self.modele.pk})

    def test_modele_d_une_autre_societe_jamais_vu(self):
        modele_autre = Calepinage.objects.create(
            company=self.autre, lead_id=9999, titre='Modèle voisin')
        marquer_modele(modele_autre)
        reponse = self.api.get(URL_MODELES)
        ids = {ligne['id'] for ligne in self._lignes(reponse)}
        self.assertNotIn(modele_autre.pk, ids)

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(URL_MODELES)
        self.assertEqual(reponse.status_code, 403)
