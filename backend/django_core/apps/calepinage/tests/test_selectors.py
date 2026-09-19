"""CAL10 — toutes les lectures du module, bornées société.

Les autres apps liront ``apps.calepinage`` UNIQUEMENT par ``selectors.py``.
Ce qui est prouvé ici :

* un calepinage d'une AUTRE société est invisible de CHAQUE fonction —
  introuvable (``None`` / queryset vide), jamais « interdit » ;
* une société ``None`` ne se mue jamais en « pas de filtre » : le résultat
  est vide, pas l'annuaire entier ;
* chaque filtre (lead, client, statut, date, recherche) restreint réellement ;
* les variantes sortent la RETENUE en tête, les versions du plus récent au
  plus ancien ;
* AUCUNE fonction n'écrit : le nombre de lignes en base est identique avant
  et après un balayage complet des sélecteurs.

Run :
    python manage.py test apps.calepinage.tests.test_selectors -v2
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.calepinage import selectors
from apps.calepinage.models import (
    Calepinage,
    CalepinageVariante,
    CalepinageVersion,
)
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from authentication.models import Company


class BaseLecture(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Lecture Co',
                                              slug='lecture-co')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-10')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.client_b = Client.objects.create(company=self.autre,
                                              nom='Bâtiment Rif')
        self.mien = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Toiture Atlas', statut=Calepinage.Statut.BROUILLON)
        self.sur_lead = Calepinage.objects.create(
            company=self.company, lead_id=4242, titre='Toiture Lead',
            statut=Calepinage.Statut.VALIDE, appel_offre_id=7)
        self.etranger = Calepinage.objects.create(
            company=self.autre, client=self.client_b, titre='Toiture Rif')


class IsolationTest(BaseLecture):
    def test_liste_ne_voit_pas_l_autre_societe(self):
        ids = set(selectors.liste_calepinages(self.company)
                  .values_list('pk', flat=True))
        self.assertNotIn(self.etranger.pk, ids)
        self.assertEqual(ids, {self.mien.pk, self.sur_lead.pk})

    def test_detail_d_une_autre_societe_est_introuvable(self):
        self.assertIsNone(
            selectors.calepinage_detail(self.etranger.pk, self.company))

    def test_societe_none_ne_rend_rien(self):
        self.assertEqual(selectors.liste_calepinages(None).count(), 0)
        self.assertIsNone(selectors.calepinage_detail(self.mien.pk, None))
        self.assertIsNone(selectors.calepinage_du_devis(1, None))
        self.assertIsNone(selectors.calepinage_de_l_affaire(7, None))

    def test_affaire_d_une_autre_societe_invisible(self):
        Calepinage.objects.create(company=self.autre, client=self.client_b,
                                  appel_offre_id=99)
        self.assertIsNone(
            selectors.calepinage_de_l_affaire(99, self.company))


class FiltresTest(BaseLecture):
    def test_filtre_lead(self):
        lignes = selectors.liste_calepinages(self.company, lead_id=4242)
        self.assertEqual([c.pk for c in lignes], [self.sur_lead.pk])

    def test_filtre_client(self):
        lignes = selectors.liste_calepinages(self.company,
                                             client_id=self.client_a.pk)
        self.assertEqual([c.pk for c in lignes], [self.mien.pk])

    def test_filtre_statut(self):
        lignes = selectors.liste_calepinages(
            self.company, statut=Calepinage.Statut.VALIDE)
        self.assertEqual([c.pk for c in lignes], [self.sur_lead.pk])

    def test_filtre_depuis(self):
        demain = timezone.now() + timedelta(days=1)
        self.assertEqual(
            selectors.liste_calepinages(self.company, depuis=demain).count(),
            0)
        hier = timezone.now() - timedelta(days=1)
        self.assertEqual(
            selectors.liste_calepinages(self.company, depuis=hier).count(), 2)

    def test_recherche_sur_le_titre(self):
        lignes = selectors.liste_calepinages(self.company, q='atlas')
        self.assertEqual([c.pk for c in lignes], [self.mien.pk])

    def test_recherche_vide_ne_filtre_pas(self):
        self.assertEqual(
            selectors.liste_calepinages(self.company, q='   ').count(), 2)

    def test_plus_recent_en_tete(self):
        lignes = list(selectors.liste_calepinages(self.company))
        self.assertEqual(lignes[0].pk, self.sur_lead.pk)


class SousRessourcesTest(BaseLecture):
    def test_versions_du_plus_recent_au_plus_ancien(self):
        for graine in ('a', 'b', 'c'):
            CalepinageVersion.objects.create(
                company=self.company, calepinage=self.mien,
                layout_hash=(graine * 64)[:64])
        lignes = list(selectors.versions(self.mien))
        self.assertEqual(len(lignes), 3)
        self.assertEqual(lignes[0].layout_hash, ('c' * 64))

    def test_variantes_retenue_en_tete(self):
        CalepinageVariante.objects.create(company=self.company,
                                          calepinage=self.mien, nom='A')
        with bascule_autorisee():
            retenue = CalepinageVariante.objects.create(
                company=self.company, calepinage=self.mien,
                nom='B', retenue=True)
        lignes = list(selectors.variantes(self.mien))
        self.assertEqual(lignes[0].pk, retenue.pk)

    def test_sous_ressources_d_un_objet_non_enregistre(self):
        vierge = Calepinage(company=self.company, lead_id=1)
        self.assertEqual(selectors.versions(vierge).count(), 0)
        self.assertEqual(selectors.variantes(vierge).count(), 0)
        self.assertEqual(selectors.versions(None).count(), 0)


class AucuneEcritureTest(BaseLecture):
    def test_les_selecteurs_n_ecrivent_jamais(self):
        avant = (Calepinage.objects.count(),
                 CalepinageVersion.objects.count(),
                 CalepinageVariante.objects.count())
        list(selectors.liste_calepinages(self.company))
        selectors.calepinage_detail(self.mien.pk, self.company)
        list(selectors.versions(self.mien))
        list(selectors.variantes(self.mien))
        selectors.calepinage_du_devis(1, self.company)
        selectors.calepinage_de_l_affaire(7, self.company)
        selectors.parametres_de_societe(self.company)
        apres = (Calepinage.objects.count(),
                 CalepinageVersion.objects.count(),
                 CalepinageVariante.objects.count())
        self.assertEqual(avant, apres)


class AffaireTest(BaseLecture):
    def test_calepinage_de_l_affaire(self):
        trouve = selectors.calepinage_de_l_affaire(7, self.company)
        self.assertEqual(trouve.pk, self.sur_lead.pk)

    def test_affaire_inconnue(self):
        self.assertIsNone(
            selectors.calepinage_de_l_affaire(999, self.company))

    def test_devis_sans_calepinage(self):
        self.assertIsNone(selectors.calepinage_du_devis(999, self.company))
