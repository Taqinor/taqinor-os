"""NTDOC14 — Journal de consultation par salle et par viewer.

Couvre :
  * ouvrir 3 documents depuis un lien viewer produit 3 entrées `JournalAcces`
    ATTRIBUABLES à ce viewer précis (aucun nouveau modèle de journal) ;
  * un autre viewer de la même salle a ses propres entrées ;
  * l'endpoint de gestion liste qui a vu quoi et quand, et résume le temps
    estimé par document ;
  * l'export CSV reflète l'ORDRE CHRONOLOGIQUE et le même nombre de lignes ;
  * isolation société : le journal d'une salle voisine est inaccessible.

Horloge FIGÉE : les horodatages du journal sont réécrits explicitement avant
toute assertion de durée — aucune comparaison à un ``now()`` vivant.
"""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.datarooms import services

from ._base import auth, make_admin, make_company, make_document


REFERENCE = timezone.make_aware(datetime.datetime(2026, 6, 15, 10, 0, 0))
PDF = b'%PDF-1.4 contenu'


class NtDoc14Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc14-a', 'Ntdoc14 A')
        self.co_b = make_company('ntdoc14-b', 'Ntdoc14 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc14-admin-a')
        self.admin_b = make_admin(self.co_b, 'ntdoc14-admin-b')
        self.api = auth(self.admin_a)
        self.salle = services.creer_salle(
            company=self.co_a, nom='Due diligence', created_by=self.admin_a)
        self.docs = [make_document(self.co_a, f'Pièce {i}') for i in range(3)]
        services.ajouter_documents(self.salle, self.docs)
        self.viewer_a = services.inviter_viewer(
            self.salle, nom='Alice', email='alice@example.com')
        self.viewer_b = services.inviter_viewer(self.salle, nom='Bob')

    def _ouvrir(self, acces, document):
        url = (f'/api/django/datarooms/public/{acces.token}/documents/'
               f'{document.pk}/')
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(PDF, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(PDF, True)):
            return self.client.get(url)

    def _figer_horodatages(self, *ecarts_minutes):
        """Réécrit les `created_at` du journal (auto_now_add) pour rendre les
        durées déterministes."""
        from apps.ged.models import JournalAcces
        entrees = list(JournalAcces.objects.filter(
            company=self.co_a).order_by('id'))
        for entree, minutes in zip(entrees, ecarts_minutes):
            JournalAcces.objects.filter(pk=entree.pk).update(
                created_at=REFERENCE + datetime.timedelta(minutes=minutes))


class JournalisationTests(NtDoc14Base):
    def test_trois_ouvertures_trois_entrees_attribuables(self):
        from apps.ged.models import JournalAcces

        for doc in self.docs:
            self.assertEqual(self._ouvrir(self.viewer_a, doc).status_code, 200)
        entrees = JournalAcces.objects.filter(
            source_ref=services.reference_acces(self.viewer_a))
        self.assertEqual(entrees.count(), 3)
        self.assertEqual(
            set(entrees.values_list('document_id', flat=True)),
            {d.pk for d in self.docs})
        # Accès PUBLIC anonyme : aucun utilisateur interne n'est attribué.
        self.assertTrue(all(e.utilisateur_id is None for e in entrees))
        self.assertTrue(all(e.company_id == self.co_a.pk for e in entrees))

    def test_chaque_viewer_a_ses_propres_entrees(self):
        from apps.ged.models import JournalAcces

        self._ouvrir(self.viewer_a, self.docs[0])
        self._ouvrir(self.viewer_b, self.docs[1])
        self.assertEqual(JournalAcces.objects.filter(
            source_ref=services.reference_acces(self.viewer_a)).count(), 1)
        self.assertEqual(JournalAcces.objects.filter(
            source_ref=services.reference_acces(self.viewer_b)).count(), 1)

    def test_acces_ged_ordinaire_reste_sans_source(self):
        """Une consultation GED classique ne porte aucune source de salle."""
        from apps.ged import services as ged_services
        from apps.ged.models import JournalAcces

        ged_services.journaliser_acces(self.docs[0])
        self.assertEqual(
            JournalAcces.objects.filter(source_ref='').count(), 1)
        self.assertEqual(
            services.journal_de_salle(self.salle).count(), 0)


class RapportJournalTests(NtDoc14Base):
    def test_resume_du_temps_par_document(self):
        for doc in self.docs:
            self._ouvrir(self.viewer_a, doc)
        # 10 min entre le 1er et le 2e, 5 min entre le 2e et le 3e.
        self._figer_horodatages(0, 10, 15)

        lignes, resume = services.journal_detaille_salle(self.salle)
        self.assertEqual(len(lignes), 3)
        self.assertEqual([ligne['viewer_nom'] for ligne in lignes],
                         ['Alice'] * 3)
        durees = {ligne['document_nom']: ligne['duree_secondes']
                  for ligne in lignes}
        self.assertEqual(durees['Pièce 0'], 600)
        self.assertEqual(durees['Pièce 1'], 300)
        # Dernier document de la session : aucun accès suivant → 0, jamais une
        # durée inventée.
        self.assertEqual(durees['Pièce 2'], 0)
        self.assertEqual(len(resume), 3)
        self.assertTrue(all(r['consultations'] == 1 for r in resume))

    def test_ecart_trop_long_non_comptabilise(self):
        self._ouvrir(self.viewer_a, self.docs[0])
        self._ouvrir(self.viewer_a, self.docs[1])
        self._figer_horodatages(0, 24 * 60)  # onglet laissé ouvert une nuit
        lignes, _ = services.journal_detaille_salle(self.salle)
        self.assertEqual(lignes[0]['duree_secondes'], 0)

    def test_endpoint_journal(self):
        for doc in self.docs:
            self._ouvrir(self.viewer_a, doc)
        self._figer_horodatages(0, 10, 15)
        reponse = self.api.get(
            f'/api/django/datarooms/salles/{self.salle.pk}/journal/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(reponse.data['lignes']), 3)
        self.assertEqual(len(reponse.data['resume_par_document']), 3)

    def test_export_csv_chronologique(self):
        for doc in self.docs:
            self._ouvrir(self.viewer_a, doc)
        self._figer_horodatages(0, 10, 15)
        reponse = self.api.get(
            f'/api/django/datarooms/salles/{self.salle.pk}/journal/'
            f'?format=csv')
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('text/csv', reponse['Content-Type'])
        texte = reponse.content.decode('utf-8-sig')
        lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
        # 1 en-tête + 3 accès.
        self.assertEqual(len(lignes), 4)
        self.assertLess(lignes.index([ligne for ligne in lignes
                                      if 'Pièce 0' in ligne][0]),
                        lignes.index([ligne for ligne in lignes
                                      if 'Pièce 2' in ligne][0]))

    def test_journal_d_une_salle_voisine_inaccessible(self):
        salle_b = services.creer_salle(
            company=self.co_b, nom='Salle voisine', created_by=self.admin_b)
        reponse = self.api.get(
            f'/api/django/datarooms/salles/{salle_b.pk}/journal/')
        self.assertEqual(reponse.status_code, 404)
