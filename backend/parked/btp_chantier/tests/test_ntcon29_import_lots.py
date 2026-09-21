"""NTCON29 — import CSV/XLSX en masse des lots et jalons contractuels.

Ce que le test PROUVE :
  * UNE LIGNE INVALIDE NE BLOQUE PAS LES AUTRES — le critère d'acceptation
    textuel (« 50 lots avec 3 lignes erronées → 47 créés + rapport précis ») ;
  * chaque motif d'erreur NOMME la cause (sous-traitant introuvable, dates
    incohérentes, nom manquant, doublon) — jamais un refus générique ;
  * l'import réutilise ``apps.dataimport`` : un ``ImportJob`` +
    ``ImportJobRow`` par ligne sont écrits, pas un 2ᵉ journal maison ;
  * cross-tenant : on n'importe jamais dans le chantier d'une autre société,
    et un sous-traitant d'une autre société ne résout pas.
"""
import io

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import Lot
from apps.dataimport.models import ImportJob, ImportJobRow

from .helpers import auth, make_chantier, make_company, make_user

URL = '/api/django/btp-chantier/lots/import/'

ENTETE = ('nom;entreprise;date debut;date fin;jalon;montant;'
          'taux penalite;plafond\n')


def _fournisseur(company, nom):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def _csv(lignes, entete=ENTETE):
    contenu = entete + ''.join(lignes)
    fichier = io.BytesIO(contenu.encode('utf-8'))
    fichier.name = 'lots.csv'
    return fichier


class ImportLotsTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.batix = _fournisseur(self.co, 'SARL BATIX')

    # ── service ────────────────────────────────────────────────────────────
    def test_import_nominal(self):
        octets = (ENTETE
                  + 'Gros œuvre;SARL BATIX;01/02/2026;30/06/2026;oui;250000;1,5;5\n'
                  + 'Électricité;;01/07/2026;30/09/2026;non;80000;;\n'
                  ).encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)

        self.assertEqual(resultat['total_lignes'], 2)
        self.assertEqual(resultat['crees'], 2)
        self.assertEqual(resultat['erreurs'], 0)

        gros = Lot.objects.get(chantier=self.chantier, nom='Gros œuvre')
        self.assertEqual(gros.company_id, self.co.id)
        self.assertEqual(gros.sous_traitant_id, self.batix.id)
        self.assertFalse(gros.interne)
        self.assertTrue(gros.jalon_contractuel)
        self.assertEqual(str(gros.date_fin_prevue), '2026-06-30')
        self.assertEqual(str(gros.montant_ht), '250000.00')
        self.assertEqual(str(gros.taux_penalite_retard_pmil), '1.500')

        elec = Lot.objects.get(chantier=self.chantier, nom='Électricité')
        self.assertIsNone(elec.sous_traitant_id)
        self.assertTrue(elec.interne)
        self.assertFalse(elec.jalon_contractuel)

    def test_les_lignes_valides_passent_malgre_les_erreurs(self):
        """Critère d'acceptation : 50 lignes dont 3 erronées → 47 créés."""
        lignes = []
        for i in range(1, 51):
            if i == 7:   # sous-traitant introuvable
                lignes.append(f'Lot {i};ENTREPRISE FANTOME;;;;;\n')
            elif i == 19:  # dates incohérentes
                lignes.append(f'Lot {i};;10/05/2026;01/03/2026;;;\n')
            elif i == 33:  # nom manquant
                lignes.append(';;;;;;\n')
            else:
                lignes.append(f'Lot {i};;;;;1000;\n')
        octets = (ENTETE + ''.join(lignes)).encode('utf-8')

        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)

        self.assertEqual(resultat['crees'], 47)
        self.assertEqual(resultat['erreurs'], 3)
        self.assertEqual(
            Lot.objects.filter(chantier=self.chantier).count(), 47)
        motifs = {e['ligne']: e['motif'] for e in resultat['lignes']}
        # Les numéros de ligne sont ceux du FICHIER (1 = en-tête).
        self.assertIn('sous-traitant introuvable', motifs[8])
        self.assertIn('ENTREPRISE FANTOME', motifs[8])
        self.assertIn('dates incohérentes', motifs[20])
        self.assertIn('nom du lot manquant', motifs[34])

    def test_doublon_rejete_sans_casser_les_suivants(self):
        Lot.objects.create(
            company=self.co, chantier=self.chantier, nom='Gros œuvre')
        octets = (ENTETE
                  + 'Gros œuvre;;;;;;\n'
                  + 'Charpente;;;;;;\n').encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)
        self.assertEqual(resultat['crees'], 1)
        self.assertEqual(resultat['erreurs'], 1)
        self.assertIn('déjà présent', resultat['lignes'][0]['motif'])
        self.assertTrue(
            Lot.objects.filter(chantier=self.chantier,
                               nom='Charpente').exists())

    def test_montant_illisible_nomme_le_champ(self):
        octets = (ENTETE + 'Lot A;;;;;abc;\n').encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)
        self.assertEqual(resultat['erreurs'], 1)
        self.assertIn('montant HT', resultat['lignes'][0]['motif'])

    def test_plafond_hors_bornes(self):
        octets = (ENTETE + 'Lot A;;;;;1000;1;250\n').encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)
        self.assertEqual(resultat['erreurs'], 1)
        self.assertIn('plafond', resultat['lignes'][0]['motif'])

    def test_colonne_nom_absente_refuse_tout_le_fichier(self):
        octets = b'colonneA;colonneB\n1;2\n'
        with self.assertRaises(ValueError) as ctx:
            services.importer_lots(
                company=self.co, chantier=self.chantier,
                fichier_octets=octets, nom_fichier='lots.csv',
                user=self.user)
        self.assertIn('nom du lot', str(ctx.exception))

    # ── journal dataimport RÉUTILISÉ ───────────────────────────────────────
    def test_journal_import_dataimport(self):
        octets = (ENTETE
                  + 'Lot A;;;;;1000;\n'
                  + ';;;;;;\n').encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='planning.csv',
            user=self.user)
        job = ImportJob.objects.get(pk=resultat['job_id'])
        self.assertEqual(job.company_id, self.co.id)
        self.assertEqual(job.target, 'btp_lots')
        self.assertEqual(job.fichier_nom, 'planning.csv')
        self.assertEqual(job.created_by_id, self.user.id)
        self.assertEqual(job.statut, ImportJob.Statut.PARTIEL)
        self.assertEqual(job.total_lignes, 2)
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.error_count, 1)
        self.assertEqual(job.rows.count(), 2)
        ok = job.rows.get(statut=ImportJobRow.Statut.OK)
        self.assertEqual(ok.cible_type, 'btp_chantier.Lot')
        self.assertIsNotNone(ok.cible_id)

    # ── endpoint ───────────────────────────────────────────────────────────
    def test_endpoint_import(self):
        fichier = _csv(['Lot API;SARL BATIX;;;oui;5000;1;\n'])
        resp = auth(self.user).post(
            URL, {'file': fichier, 'chantier': self.chantier.id},
            format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.data['crees'], 1)
        self.assertEqual(resp.data['erreurs'], 0)
        self.assertEqual(resp.data['lignes'], [])
        self.assertTrue(
            Lot.objects.filter(chantier=self.chantier, nom='Lot API').exists())

    def test_endpoint_sans_fichier(self):
        resp = auth(self.user).post(
            URL, {'chantier': self.chantier.id}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', resp.data['detail'])

    def test_endpoint_sans_chantier(self):
        resp = auth(self.user).post(
            URL, {'file': _csv(['Lot X;;;;;;\n'])}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('chantier', resp.data['detail'])

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_chantier_d_une_autre_societe_404(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = auth(self.user).post(
            URL, {'file': _csv(['Lot X;;;;;;\n']),
                  'chantier': chantier_autre.id},
            format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Lot.objects.filter(chantier=chantier_autre).count(), 0)

    def test_sous_traitant_d_une_autre_societe_ne_resout_pas(self):
        autre = make_company()
        _fournisseur(autre, 'ENTREPRISE AILLEURS')
        octets = (ENTETE
                  + 'Lot X;ENTREPRISE AILLEURS;;;;;\n').encode('utf-8')
        resultat = services.importer_lots(
            company=self.co, chantier=self.chantier,
            fichier_octets=octets, nom_fichier='lots.csv', user=self.user)
        self.assertEqual(resultat['erreurs'], 1)
        self.assertIn('introuvable', resultat['lignes'][0]['motif'])
