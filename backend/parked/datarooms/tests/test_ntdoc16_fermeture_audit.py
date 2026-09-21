"""NTDOC16 — Fermeture d'une salle de données et export d'audit.

Couvre :
  * fermer une salle révoque TOUS les accès actifs d'un coup → chaque lien
    viewer répond 404 IMMÉDIATEMENT ;
  * la fermeture est idempotente et trace qui/quand ;
  * une salle fermée n'accepte plus ni document ni nouvel invité ;
  * la réouverture est réservée à un administrateur et n'exhume aucun lien ;
  * l'export d'audit liste l'INTÉGRALITÉ de l'activité (documents, viewers,
    journal) et se rend en PDF via le service partagé (jamais WeasyPrint en
    direct) ;
  * isolation société.
"""
from unittest import mock

from django.test import TestCase

from apps.datarooms import services
from apps.datarooms.models import AccesSalleDonnees, SalleDeDonnees

from ._base import auth, make_admin, make_company, make_document, make_user


PDF = b'%PDF-1.4 contenu'


class NtDoc16Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc16-a', 'Ntdoc16 A')
        self.co_b = make_company('ntdoc16-b', 'Ntdoc16 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc16-admin-a')
        self.admin_b = make_admin(self.co_b, 'ntdoc16-admin-b')
        self.api = auth(self.admin_a)
        self.salle = services.creer_salle(
            company=self.co_a, nom='Due diligence 2026',
            deal_type='due diligence', created_by=self.admin_a)
        self.doc = make_document(self.co_a, 'Pacte d’associés')
        services.ajouter_documents(self.salle, [self.doc])
        self.viewer_a = services.inviter_viewer(
            self.salle, nom='Alice', email='alice@example.com')
        self.viewer_b = services.inviter_viewer(self.salle, nom='Bob')

    def _url_public(self, acces):
        return f'/api/django/datarooms/public/{acces.token}/'


class FermetureTests(NtDoc16Base):
    def test_fermer_revoque_tous_les_acces_et_404_immediat(self):
        # Avant : les deux liens répondent.
        self.assertEqual(
            self.client.get(self._url_public(self.viewer_a)).status_code, 200)
        self.assertEqual(
            self.client.get(self._url_public(self.viewer_b)).status_code, 200)

        reponse = self.api.post(
            f'/api/django/datarooms/salles/{self.salle.pk}/fermer/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['acces_revoques'], 2)

        self.assertEqual(
            self.client.get(self._url_public(self.viewer_a)).status_code, 404)
        self.assertEqual(
            self.client.get(self._url_public(self.viewer_b)).status_code, 404)
        self.assertEqual(
            AccesSalleDonnees.objects.filter(
                salle=self.salle, revoque=False).count(), 0)

    def test_fermeture_trace_qui_et_quand(self):
        services.fermer_salle(self.salle, fermee_par=self.admin_a)
        self.salle.refresh_from_db()
        self.assertEqual(self.salle.statut, SalleDeDonnees.Statut.FERMEE)
        self.assertIsNotNone(self.salle.fermee_le)
        self.assertEqual(self.salle.fermee_par_id, self.admin_a.pk)

    def test_fermeture_idempotente(self):
        self.assertEqual(services.fermer_salle(self.salle), 2)
        self.assertEqual(services.fermer_salle(self.salle), 0)

    def test_salle_fermee_refuse_document_et_invitation(self):
        services.fermer_salle(self.salle)
        autre = make_document(self.co_a, 'Annexe tardive')
        with self.assertRaises(services.SalleFermee):
            services.ajouter_documents(self.salle, [autre])
        with self.assertRaises(services.SalleFermee):
            services.inviter_viewer(self.salle, nom='Retardataire')
        with self.assertRaises(services.SalleFermee):
            services.retirer_document(self.salle, self.doc)

    def test_reouverture_reservee_a_un_admin(self):
        services.fermer_salle(self.salle)
        simple = make_user(self.co_a, 'ntdoc16-simple-a')
        reponse = auth(simple).post(
            f'/api/django/datarooms/salles/{self.salle.pk}/rouvrir/', {},
            format='json')
        self.assertIn(reponse.status_code, (403, 404))
        self.salle.refresh_from_db()
        self.assertEqual(self.salle.statut, SalleDeDonnees.Statut.FERMEE)

    def test_reouverture_admin_n_exhume_aucun_lien(self):
        services.fermer_salle(self.salle)
        reponse = self.api.post(
            f'/api/django/datarooms/salles/{self.salle.pk}/rouvrir/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.salle.refresh_from_db()
        self.assertEqual(self.salle.statut, SalleDeDonnees.Statut.OUVERTE)
        self.assertIsNone(self.salle.fermee_le)
        # Les liens révoqués restent morts : il faut réinviter.
        self.assertEqual(
            self.client.get(self._url_public(self.viewer_a)).status_code, 404)


class ExportAuditTests(NtDoc16Base):
    def _consulter(self, acces, document):
        url = (f'/api/django/datarooms/public/{acces.token}/documents/'
               f'{document.pk}/')
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(PDF, None)), \
                mock.patch('apps.ged.services.apply_watermark',
                           return_value=(PDF, True)):
            return self.client.get(url)

    def test_rapport_liste_toute_l_activite(self):
        self._consulter(self.viewer_a, self.doc)
        html = services.rapport_audit_html(self.salle)
        self.assertIn('Due diligence 2026', html)
        self.assertIn('Pacte', html)
        self.assertIn('Alice', html)
        self.assertIn('alice@example.com', html)
        self.assertIn('Bob', html)
        self.assertIn('Journal de consultation', html)
        self.assertIn('Synthèse par document', html)

    def test_rapport_sans_activite_reste_valide(self):
        html = services.rapport_audit_html(self.salle)
        self.assertIn('Aucune consultation enregistrée', html)

    def test_rapport_mentionne_la_fermeture(self):
        services.fermer_salle(self.salle, fermee_par=self.admin_a)
        self.salle.refresh_from_db()
        html = services.rapport_audit_html(self.salle)
        self.assertIn('Fermée', html)
        self.assertIn('Révoqué', html)

    def test_export_pdf_passe_par_le_service_partage(self):
        with mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = self.api.get(
                f'/api/django/datarooms/salles/{self.salle.pk}/export-audit/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'application/pdf')
        self.assertIn('attachment', reponse['Content-Disposition'])
        self.assertEqual(reponse.content, PDF)
        rendu.assert_called_once()

    def test_export_d_une_salle_voisine_inaccessible(self):
        salle_b = services.creer_salle(
            company=self.co_b, nom='Salle voisine', created_by=self.admin_b)
        reponse = self.api.get(
            f'/api/django/datarooms/salles/{salle_b.pk}/export-audit/')
        self.assertEqual(reponse.status_code, 404)
