"""APAR61 (C-APAR-013, D-APAR-4) — l'identité vendeur imprimée sur une
facture est FIGÉE à l'émission (``Facture.identite_vendeur``) et le PDF d'une
facture émise se rend depuis cet instantané : changer le RIB de la société ne
change pas le PDF d'une facture déjà émise ; une nouvelle facture prend le
nouveau RIB ; une facture sans instantané (antérieure) suit le profil vivant.

Rejoue la sonde VB p5 (`rendu2 (apres changement profil) contient nouveau
RIB: True` sur une facture émise). Rendu WeasyPrint réel ; seul l'upload
MinIO est neutralisé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_facture_apar61_identite_vendeur"
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

R1 = '011 780 0000111111111111 11'
R2 = '022 780 0000222222222222 22'


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class IdentiteVendeurFigeeTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from authentication.models import Company
        self.company = Company.objects.create(nom='APAR61', slug='apar61-co')
        self.profile = CompanyProfile.get(company=self.company)
        self.profile.rib = R1
        self.profile.banque = 'Banque Une'
        self.profile.save()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='APAR61',
            email='apar61@example.invalid')
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)

    def _facture(self, ref, statut='brouillon'):
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        produit, _ = Produit.objects.get_or_create(
            company=self.company, sku='APAR61-P',
            defaults={'nom': 'Centrale', 'prix_vente': Decimal('1000')})
        facture = Facture.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Centrale',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return facture

    def _emettre(self, facture):
        from apps.ventes.domain.facturation_ops import emettre_facture
        emettre_facture(facture, source='test_apar61')
        facture.refresh_from_db()
        return facture

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def _changer_rib(self, rib, banque):
        self.profile.rib = rib
        self.profile.banque = banque
        self.profile.save()

    def test_identite_acheteur_figee_a_l_emission(self):
        """AARG27 (C-AARG-021) — après PATCH du client, le PDF et l'UBL d'une
        facture émise gardent X / ICE A ; la suivante porte Y / ICE B."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.ventes.dgi.dgi_export import build_ubl_xml
        from apps.ventes.models import Facture
        ice_a, ice_b = '001234567000089', '002234567000089'
        type(self.client_obj).objects.filter(pk=self.client_obj.pk).update(
            nom='X SARL', prenom='', type_client='entreprise', ice=ice_a,
            if_fiscal='IF-1', rc='RC-1', adresse='Casablanca')
        self.client_obj.refresh_from_db()
        emise = self._emettre(self._facture('FAC-APAR61-0300'))
        self.assertEqual(emise.identite_acheteur['ice'], ice_a)
        user = get_user_model().objects.create_user(
            username='aarg27-resp', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.force_authenticate(user)
        r = api.patch(f'/api/django/crm/clients/{self.client_obj.pk}/',
                      {'nom': 'Y SARL', 'ice': ice_b}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.client_obj.refresh_from_db()
        emise = Facture.objects.get(pk=emise.pk)
        texte, ubl = self._pdf(emise), build_ubl_xml(emise)
        for sortie in (texte, ubl):
            self.assertIn('X SARL', sortie)
            self.assertIn(ice_a, sortie)
            self.assertNotIn(ice_b, sortie)
        self.assertEqual(Facture.objects.get(pk=emise.pk).identite_acheteur['nom'],
                         'X SARL')
        suivante = self._emettre(self._facture('FAC-APAR61-0301'))
        texte = self._pdf(suivante)
        self.assertIn('Y SARL', texte)
        self.assertIn(ice_b, texte)
        # Facture historique sans instantané : lecture du client (repli).
        Facture.objects.filter(pk=emise.pk).update(identite_acheteur=None)
        self.assertIn(ice_b, build_ubl_xml(Facture.objects.get(pk=emise.pk)))
        # Jamais envoyée, remise en brouillon : la réémission re-fige l'acheteur.
        r = api.post(
            f'/api/django/ventes/factures/{suivante.pk}/remettre-brouillon/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(
            Facture.objects.get(pk=suivante.pk).identite_acheteur)

    def test_commande_figer_identite_acheteur_dry_run_puis_appliquer(self):
        """ASUP1 (C-ASUP-001) — dry-run sans écriture, ``--appliquer`` fige
        les 4 non brouillon sans instantané ; brouillon, figée et client déjà
        anonymisé inchangés ; l'ICE survit à « Anonymiser (RGPD) »."""
        from io import StringIO

        from django.core.management import call_command

        from apps.crm.dsr_provider import anonymiser_client
        from apps.crm.models import Client
        from apps.ventes.domain.instantanes_facture import (
            acheteur_de_la_facture)
        from apps.ventes.models import Facture
        ice = '001234567000089'
        Client.objects.filter(pk=self.client_obj.pk).update(
            nom='X SARL', prenom='', type_client='entreprise', ice=ice,
            if_fiscal='IF-1', rc='RC-1', adresse='Casablanca')
        self.client_obj.refresh_from_db()
        cibles = [self._facture(f'FAC-ASUP1-{s}', statut=s)
                  for s in ('emise', 'payee', 'en_retard', 'annulee')]
        brouillon = self._facture('FAC-ASUP1-brouillon')
        figee = self._facture('FAC-ASUP1-figee', statut='emise')
        Facture.objects.filter(pk=figee.pk).update(
            identite_acheteur={'nom': 'Figé', 'ice': 'ICE-FIGE'})
        perdu = Client.objects.create(company=self.company, nom='Anonymisé',
                                      is_anonymized=True)
        perdue = Facture.objects.create(
            company=self.company, reference='FAC-ASUP1-perdue', client=perdu,
            statut='emise', taux_tva=Decimal('20'))

        def jouer(*args):
            out = StringIO()
            call_command('figer_identite_acheteur', *args, stdout=out)
            return out.getvalue()

        sortie = jouer()
        for f in cibles:
            self.assertIn(f'{f.reference} | X SARL | {f.statut}', sortie)
        avant, _, apres = sortie.partition('identité déjà perdue')
        self.assertIn('FAC-ASUP1-perdue', apres)
        self.assertNotIn('FAC-ASUP1-perdue', avant)
        for ref in ('FAC-ASUP1-brouillon', 'FAC-ASUP1-figee'):
            self.assertNotIn(ref, sortie)
        self.assertFalse(Facture.objects.filter(
            pk__in=[f.pk for f in cibles],
            identite_acheteur__isnull=False).exists())
        jouer('--appliquer')
        for f in cibles:
            self.assertEqual(Facture.objects.get(pk=f.pk)
                             .identite_acheteur['ice'], ice)
        self.assertIsNone(Facture.objects.get(pk=brouillon.pk).identite_acheteur)
        self.assertIsNone(Facture.objects.get(pk=perdue.pk).identite_acheteur)
        self.assertEqual(Facture.objects.get(pk=figee.pk).identite_acheteur,
                         {'nom': 'Figé', 'ice': 'ICE-FIGE'})
        anonymiser_client(self.company, self.client_obj, motif='t')
        for f in cibles:
            acheteur = acheteur_de_la_facture(Facture.objects.get(pk=f.pk))
            self.assertEqual((acheteur.nom, acheteur.ice, acheteur.if_fiscal,
                              acheteur.rc, acheteur.adresse),
                             ('X SARL', ice, 'IF-1', 'RC-1', 'Casablanca'))
        rejeu = jouer()
        for f in cibles:
            self.assertNotIn(f.reference, rejeu)

    def test_avoir_et_note_debit_impriment_l_acheteur_fige_apres_anonymisation(self):
        """ASUP57 (C-ASUP-VER2-101) — après « Anonymiser (RGPD) » du client,
        l'avoir créé, l'avoir annulé (re-rendu) et la note de débit impriment
        le nom, l'ICE, l'IF, le RC et l'adresse FIGÉS de la facture d'origine,
        jamais « Client anonymisé ». Mutant : relire ``avoir.client`` dans
        ``avoir.html`` ⇒ échec."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.crm.models import Client
        from apps.ventes.models import Avoir, NoteDebit
        from apps.ventes.utils.pdf import generate_avoir_pdf, generate_note_debit_pdf
        ice = '001234567000089'
        Client.objects.filter(pk=self.client_obj.pk).update(
            nom='X SARL', prenom='', type_client='entreprise', ice=ice,
            if_fiscal='IF-57', rc='RC-57', adresse='Casablanca Anfa')
        self.client_obj.refresh_from_db()
        facture = self._facture('FAC-ASUP57-0001')
        facture.lignes.update(quantite=Decimal('2'))
        facture = self._emettre(facture)
        admin = get_user_model().objects.create_user(
            username='asup57-admin', password='x', role_legacy='admin',
            company=self.company)
        api = APIClient()
        api.force_authenticate(admin)
        url_avoir = f'/api/django/ventes/factures/{facture.pk}/creer-avoir/'
        ligne = {'produit': facture.lignes.get().produit_id, 'designation': 'Centrale',
                 'quantite': '1', 'prix_unitaire': '100', 'taux_tva': '20'}
        existant = api.post(url_avoir, {'motif': 'geste', 'lignes': [ligne]}, format='json')
        self.assertEqual(existant.status_code, 201, existant.data)
        r = api.post(f'/api/django/crm/clients/{self.client_obj.pk}/anonymize/')
        self.assertEqual(r.status_code, 200, r.data)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)
        nouveau = api.post(url_avoir, {'motif': 'geste 2', 'lignes': [ligne]}, format='json')
        self.assertEqual(nouveau.status_code, 201, nouveau.data)
        r = api.post(f'/api/django/ventes/avoirs/{existant.data["id"]}/annuler/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        note = api.post(f'/api/django/ventes/factures/{facture.pk}/creer-note-debit/',
                        {'motif': 'pénalité', 'montant': '50.00', 'taux_tva': '20'},
                        format='json')
        self.assertEqual(note.status_code, 201, note.data)
        pieces = ((Avoir, nouveau.data['id'], generate_avoir_pdf),
                  (Avoir, existant.data['id'], generate_avoir_pdf),
                  (NoteDebit, note.data['id'], generate_note_debit_pdf))
        for modele, pk, generer in pieces:
            # CLAUSE PERSISTANCE — le PDF stocké, puis un nouveau rendu
            # (re-téléchargement d'une pièce sans fichier) : même acheteur.
            for cle in (modele.objects.get(pk=pk).fichier_pdf, generer(pk)):
                texte = _texte(self.objets[cle])
                with self.subTest(piece=modele.__name__, pk=pk):
                    for attendu in ('X SARL', ice, 'IF-57', 'RC-57', 'Casablanca Anfa'):
                        self.assertIn(attendu, texte)
                    self.assertNotIn('Client anonymisé', texte)

    def test_effacement_refuse_tant_qu_une_facture_emise_n_a_pas_d_identite_figee(self):
        """ASUP3 (C-ASUP-001) — ``traiter`` d'une demande d'effacement rend
        409 nommant la facture et la commande, client intact ; après
        ``figer_identite_acheteur --appliquer`` l'effacement s'exécute."""
        from io import StringIO

        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from rest_framework.test import APIClient

        from apps.crm.models import Client
        from apps.roles.models import Role
        from core import dsr
        from core.models import DataSubjectRequest
        self.assertIn('pieces_legales_sans_identite_figee',
                      dsr.list_erasure_guards())
        ice = '001234567000089'
        Client.objects.filter(pk=self.client_obj.pk).update(
            nom='X SARL', prenom='', type_client='entreprise', ice=ice)
        facture = self._facture('FAC-ASUP3-0001', statut='emise')
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='apar61@example.invalid',
            kind=DataSubjectRequest.KIND_ERASURE)
        call_command('init_roles', verbosity=0)
        user = get_user_model().objects.create_user(
            username='asup3-directeur', password='x', company=self.company,
            role=Role.objects.get(company=self.company, nom='Directeur'))
        api = APIClient()
        api.force_authenticate(user)
        url = f'/api/django/core/dsr-requests/{demande.pk}/traiter/'
        r = api.post(url)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('FAC-ASUP3-0001', r.data['detail'])
        self.assertIn('figer_identite_acheteur', r.data['detail'])
        self.client_obj.refresh_from_db()
        self.assertFalse(self.client_obj.is_anonymized)
        self.assertEqual(self.client_obj.ice, ice)
        call_command('figer_identite_acheteur', '--appliquer', stdout=StringIO())
        r = api.post(url)
        self.assertEqual(r.status_code, 200, r.data)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)
        facture.refresh_from_db()
        self.assertEqual(facture.identite_acheteur['ice'], ice)

    def test_rib_fige_a_l_emission(self):
        f120 = self._emettre(self._facture('FAC-APAR61-0120'))
        self.assertIn(R1, self._pdf(f120))
        self._changer_rib(R2, 'Banque Deux')
        # CLAUSE PERSISTANCE : l'instantané relu est inchangé.
        f120.refresh_from_db()
        self.assertEqual(f120.identite_vendeur['rib'], R1)
        texte = self._pdf(f120)
        self.assertIn(R1, texte)
        self.assertNotIn(R2, texte)

    def test_nouvelle_facture_prend_le_nouveau_rib(self):
        self._emettre(self._facture('FAC-APAR61-0121'))
        self._changer_rib(R2, 'Banque Deux')
        nouvelle = self._emettre(self._facture('FAC-APAR61-0122'))
        self.assertIn(R2, self._pdf(nouvelle))

    def test_facture_sans_instantane_suit_le_profil(self):
        ancienne = self._facture('FAC-APAR61-0100', statut='emise')
        self.assertIsNone(ancienne.identite_vendeur)
        self._changer_rib(R2, 'Banque Deux')
        texte = self._pdf(ancienne)
        self.assertIn(R2, texte)

    def test_capital_et_forme_figes_a_l_emission(self):
        """VNT39 — « <raison sociale> <forme> au capital de <capital> » en
        tête de la bande légale : la facture émise APRÈS (instantané complet)
        et le brouillon l'impriment ; une émise AVANT (instantané sans ces
        clés) et une émise SANS instantané n'impriment JAMAIS le capital du
        jour ; ICE/IF/RC/Patente inchangés."""
        self.profile.nom = 'Soleil Atlas'
        self.profile.forme_juridique = 'SARLAU'
        self.profile.capital_social = '100 000,00 MAD'
        for champ, valeur in (('ice', '001122334455667'),
                              ('identifiant_fiscal', 'IF-39'),
                              ('rc', 'RC-39'), ('patente', 'PAT-39')):
            setattr(self.profile, champ, valeur)
        self.profile.save()
        avant = self._facture('FAC-APAR61-0390', statut='emise')
        avant.identite_vendeur = {'entreprise_nom': 'Soleil Atlas',
                                  'rib': R1, 'banque': 'Banque Une'}
        avant.save(update_fields=['identite_vendeur'])
        sans = self._facture('FAC-APAR61-0391', statut='emise')
        apres = self._emettre(self._facture('FAC-APAR61-0392'))
        brouillon = self._facture('FAC-APAR61-0393')
        phrase = 'Soleil Atlas SARLAU au capital de 100 000,00 MAD'
        self.assertEqual(apres.identite_vendeur['entreprise_capital_social'],
                         '100 000,00 MAD')
        self.profile.capital_social = '200 000,00 MAD'
        self.profile.save()
        textes = {nom: self._pdf(f) for nom, f in (
            ('avant', avant), ('sans', sans), ('apres', apres),
            ('brouillon', brouillon))}
        self.assertIn(phrase, textes['apres'])
        self.assertIn('Soleil Atlas SARLAU au capital de 200 000,00 MAD',
                      textes['brouillon'])
        for nom in ('avant', 'sans'):
            with self.subTest(facture=nom):
                self.assertNotIn('au capital de', textes[nom])
                self.assertNotIn('SARLAU', textes[nom])
        for nom, texte in textes.items():
            with self.subTest(identifiants=nom):
                for attendu in ('ICE : 001122334455667', 'IF : IF-39',
                                'RC : RC-39', 'Patente : PAT-39'):
                    self.assertIn(attendu, texte)
