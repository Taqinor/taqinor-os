"""CAL14 — créer, retenir, dupliquer : le chemin d'écriture atomique.

Ce qui est prouvé ici :

* la bascule ne laisse JAMAIS deux variantes retenues ni ZÉRO — l'ancienne
  repasse à faux dans la MÊME transaction ;
* re-retenir la variante déjà retenue est neutre (elle reste la seule) ;
* une duplication ne porte AUCUN ``devis`` ni ``appel_offre_id`` : dupliquer
  une conception ne réquisitionne pas le devis de l'original ;
* la duplication reste dans la MÊME société, garde le rattachement
  lead/client (sans quoi elle violerait la contrainte « lead ou client ») et
  recopie les variantes, y compris LAQUELLE est retenue ;
* les refus nomment le champ fautif, en français ;
* le titre de la copie est DÉRIVÉ de l'original — aucun nom figé.

Run :
    python manage.py test apps.calepinage.tests.test_services_variantes -v2
"""
from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import (
    VarianteRefusee,
    creer_variante,
    dupliquer,
    retenir_variante,
)
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company

LAYOUT = {'zones': [{'id': 'z1', 'panels': 10}], 'result': {'kwc': 5.75}}


class BaseVariantes(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Variantes Co',
                                              slug='variantes-co-14')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.lead_a = Lead.objects.create(company=self.company,
                                          nom='Toiture Anfa')
        self.pivot = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            lead_id=self.lead_a.pk, titre='Toiture Atlas',
            roof_layout=LAYOUT)


class CreerTest(BaseVariantes):
    def test_creation_simple(self):
        variante = creer_variante(self.pivot, nom='Option A',
                                  roof_layout=LAYOUT)
        self.assertEqual(variante.calepinage_id, self.pivot.pk)
        self.assertEqual(variante.company_id, self.company.pk)
        self.assertFalse(variante.retenue)
        self.assertEqual(len(variante.layout_hash), 64)

    def test_creation_retenue_immediate(self):
        variante = creer_variante(self.pivot, nom='Option A', retenir=True)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)

    def test_nom_obligatoire(self):
        with self.assertRaises(VarianteRefusee) as capture:
            creer_variante(self.pivot, nom='   ')
        self.assertEqual(capture.exception.champ, 'nom')

    def test_conception_qui_n_est_pas_un_objet(self):
        with self.assertRaises(VarianteRefusee) as capture:
            creer_variante(self.pivot, nom='A', roof_layout=['zones'])
        self.assertEqual(capture.exception.champ, 'roof_layout')

    def test_calepinage_non_enregistre(self):
        with self.assertRaises(VarianteRefusee) as capture:
            creer_variante(Calepinage(company=self.company, lead_id=1),
                           nom='A')
        self.assertEqual(capture.exception.champ, 'calepinage')


class RetenirTest(BaseVariantes):
    def setUp(self):
        super().setUp()
        self.a = creer_variante(self.pivot, nom='Option A')
        self.b = creer_variante(self.pivot, nom='Option B')

    def _retenues(self):
        return list(CalepinageVariante.objects
                    .filter(calepinage=self.pivot, retenue=True)
                    .values_list('pk', flat=True))

    def test_bascule_laisse_exactement_une_retenue(self):
        retenir_variante(self.a)
        self.assertEqual(self._retenues(), [self.a.pk])
        retenir_variante(self.b)
        self.assertEqual(self._retenues(), [self.b.pk])

    def test_jamais_zero_apres_bascule(self):
        retenir_variante(self.a)
        retenir_variante(self.b)
        self.assertEqual(len(self._retenues()), 1)

    def test_re_retenir_est_neutre(self):
        retenir_variante(self.a)
        retenir_variante(self.a)
        self.assertEqual(self._retenues(), [self.a.pk])

    def test_variante_non_enregistree_refusee(self):
        with self.assertRaises(VarianteRefusee) as capture:
            retenir_variante(CalepinageVariante(company=self.company,
                                                calepinage=self.pivot,
                                                nom='fantôme'))
        self.assertEqual(capture.exception.champ, 'variante')

    def test_bascule_bornee_au_calepinage(self):
        """Retenir ici ne détrône pas la retenue d'un AUTRE calepinage."""
        autre = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        ailleurs = creer_variante(autre, nom='Ailleurs', retenir=True)
        retenir_variante(self.a)
        ailleurs.refresh_from_db()
        self.assertTrue(ailleurs.retenue)


class DupliquerTest(BaseVariantes):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(company=self.company,
                                          client=self.client_a,
                                          reference='DEV-202609-0030')
        self.pivot.devis = self.devis
        self.pivot.appel_offre_id = 55
        self.pivot.save()
        self.a = creer_variante(self.pivot, nom='Option A')
        self.b = creer_variante(self.pivot, nom='Option B', retenir=True)

    def test_la_copie_ne_porte_ni_devis_ni_affaire(self):
        copie = dupliquer(self.pivot)
        self.assertIsNone(copie.devis_id)
        self.assertIsNone(copie.appel_offre_id)

    def test_la_copie_reste_dans_la_societe(self):
        copie = dupliquer(self.pivot)
        self.assertEqual(copie.company_id, self.company.pk)

    def test_la_copie_garde_le_rattachement(self):
        copie = dupliquer(self.pivot)
        self.assertEqual(copie.client_id, self.client_a.pk)
        self.assertEqual(copie.lead_id, self.lead_a.pk)

    def test_la_copie_reprend_le_layout(self):
        copie = dupliquer(self.pivot)
        self.assertEqual(copie.roof_layout, LAYOUT)
        self.assertEqual(copie.layout_hash, self.pivot.layout_hash)

    def test_la_copie_repart_en_brouillon(self):
        self.pivot.statut = Calepinage.Statut.VALIDE
        self.pivot.save()
        copie = dupliquer(self.pivot)
        self.assertEqual(copie.statut, Calepinage.Statut.BROUILLON)

    def test_les_variantes_sont_recopiees_avec_leur_retenue(self):
        copie = dupliquer(self.pivot)
        noms = list(copie.variantes.order_by('id')
                    .values_list('nom', flat=True))
        self.assertEqual(noms, ['Option A', 'Option B'])
        retenues = list(copie.variantes.filter(retenue=True)
                        .values_list('nom', flat=True))
        self.assertEqual(retenues, ['Option B'])

    def test_l_original_garde_ses_variantes(self):
        dupliquer(self.pivot)
        self.assertEqual(self.pivot.variantes.count(), 2)

    def test_titre_derive_de_l_original(self):
        copie = dupliquer(self.pivot)
        self.assertEqual(copie.titre, 'Toiture Atlas (copie)')

    def test_titre_explicite_respecte(self):
        copie = dupliquer(self.pivot, titre='Scénario batterie')
        self.assertEqual(copie.titre, 'Scénario batterie')

    def test_calepinage_non_enregistre_refuse(self):
        with self.assertRaises(VarianteRefusee) as capture:
            dupliquer(Calepinage(company=self.company, lead_id=1))
        self.assertEqual(capture.exception.champ, 'calepinage')
