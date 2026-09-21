"""NTCON30 — export CSV/XLSX des réserves et RFI (reporting externe MOE/client).

Ce que le test PROUVE :
  * les colonnes sont CELLES DU CONTRAT (numéro, lot, description, gravité/
    priorité, statut, responsable, date limite, date de levée) ;
  * AUCUN coût interne n'apparaît dans l'export — ni déboursé, ni prix d'achat,
    ni exposition aux pénalités (ce fichier part chez le MOE/client) ;
  * les filtres de l'export sont ceux de la liste (l'export contient ce que
    l'écran affiche) ;
  * XLSX et CSV servent le MÊME contenu ;
  * cross-tenant : l'export d'une société ne contient jamais la ligne d'une
    autre.
"""
import csv
import io

from django.test import TestCase
from django.utils import timezone

from apps.btp_chantier import services
from apps.btp_chantier.models import ReserveChantier

from .helpers import auth, make_chantier, make_company, make_user

URL_RESERVES = '/api/django/btp-chantier/reserves-chantier/export/'
URL_RFI = '/api/django/btp-chantier/rfi/export/'

#: Tout terme qui trahirait une donnée de coût interne dans un export client.
TERMES_INTERDITS = (
    'prix_achat', "prix d'achat", 'debourse', 'déboursé', 'marge',
    'penalite', 'pénalité', 'cout interne', 'coût interne',
)


def _lignes_csv(reponse):
    texte = reponse.content.decode('utf-8-sig')
    return list(csv.reader(io.StringIO(texte), delimiter=';'))


class ExportReservesRfiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.api = auth(self.user)

    def _reserve(self, **kwargs):
        kwargs.setdefault('lot', 'électricité')
        kwargs.setdefault('description', 'Tableau non conforme')
        kwargs.setdefault('gravite', ReserveChantier.Gravite.BLOQUANTE)
        return ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier,
            localisation_plan={'document_ged_id': 1, 'x': 0.1, 'y': 0.1},
            created_by=self.user, **kwargs)

    def _rfi(self, **kwargs):
        kwargs.setdefault('question', 'Quelle section de câble ?')
        return services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.user,
            **kwargs)

    # ── réserves ───────────────────────────────────────────────────────────
    def test_colonnes_export_reserves(self):
        self._reserve(responsable_leve=self.user,
                      date_limite=timezone.localdate())
        lignes = _lignes_csv(self.api.get(URL_RESERVES))
        self.assertEqual(
            lignes[0],
            ['Numéro', 'Chantier', 'Lot', 'Description', 'Gravité', 'Statut',
             'Responsable', 'Date limite', 'Date de levée'])
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1][2], 'électricité')
        self.assertEqual(lignes[1][4], 'Bloquante')
        self.assertEqual(lignes[1][5], 'Ouverte')

    def test_date_de_levee_renseignee(self):
        reserve = self._reserve()
        reserve.statut = ReserveChantier.Statut.LEVEE
        reserve.date_levee = timezone.now()
        reserve.save(update_fields=['statut', 'date_levee'])
        lignes = _lignes_csv(self.api.get(URL_RESERVES))
        self.assertEqual(lignes[1][5], 'Levée')
        self.assertEqual(
            lignes[1][8], reserve.date_levee.date().isoformat())

    def test_aucun_cout_interne_dans_l_export(self):
        self._reserve()
        texte = self.api.get(URL_RESERVES).content.decode('utf-8-sig').lower()
        for terme in TERMES_INTERDITS:
            with self.subTest(terme=terme):
                self.assertNotIn(terme, texte)

    def test_filtres_de_l_export(self):
        self._reserve(gravite=ReserveChantier.Gravite.BLOQUANTE,
                      description='Bloquante A')
        self._reserve(gravite=ReserveChantier.Gravite.MINEURE,
                      description='Mineure B')
        lignes = _lignes_csv(
            self.api.get(URL_RESERVES, {'gravite': 'bloquante'}))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1][3], 'Bloquante A')

    def test_filtre_chantier(self):
        autre_chantier = make_chantier(self.co)
        self._reserve(description='Chantier A')
        ReserveChantier.objects.create(
            company=self.co, chantier=autre_chantier, lot='CVC',
            localisation_plan={}, description='Chantier B',
            gravite=ReserveChantier.Gravite.MINEURE, created_by=self.user)
        lignes = _lignes_csv(
            self.api.get(URL_RESERVES, {'chantier': self.chantier.id}))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1][3], 'Chantier A')

    def test_format_xlsx(self):
        self._reserve()
        resp = self.api.get(URL_RESERVES, {'format': 'xlsx'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])
        self.assertIn('reserves-chantier.xlsx', resp['Content-Disposition'])
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        entetes = [c.value for c in ws[1]]
        self.assertEqual(entetes[0], 'Numéro')
        self.assertEqual(ws.max_row, 2)

    # ── RFI ────────────────────────────────────────────────────────────────
    def test_colonnes_export_rfi(self):
        self._rfi(destinataire_texte='Bureau d\'études')
        lignes = _lignes_csv(self.api.get(URL_RFI))
        self.assertEqual(
            lignes[0],
            ['Numéro', 'Chantier', 'Question', 'Priorité', 'Statut',
             'Destinataire', 'Date limite de réponse', 'Date de réponse'])
        self.assertEqual(lignes[1][3], 'Normale')
        self.assertEqual(lignes[1][4], 'Ouvert')
        self.assertEqual(lignes[1][5], "Bureau d'études")

    def test_priorite_derivee_des_impacts_declares(self):
        """Jamais un niveau inventé : le libellé vient des impacts du RFI."""
        self._rfi(impact_cout=True, impact_delai_jours=5)
        lignes = _lignes_csv(self.api.get(URL_RFI))
        self.assertIn('coût', lignes[1][3])
        self.assertIn('délai 5 j', lignes[1][3])

    def test_date_de_reponse_rfi(self):
        rfi = self._rfi()
        services.repondre_rfi(rfi, auteur=self.user, texte='3G2,5')
        lignes = _lignes_csv(self.api.get(URL_RFI))
        self.assertEqual(lignes[1][4], 'Répondu')
        self.assertNotEqual(lignes[1][7], '')

    def test_filtre_statut_rfi(self):
        ouvert = self._rfi(question='Toujours ouvert')
        repondu = self._rfi(question='Déjà répondu')
        services.repondre_rfi(repondu, auteur=self.user, texte='ok')
        lignes = _lignes_csv(self.api.get(URL_RFI, {'statut': 'ouvert'}))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(int(lignes[1][0]), ouvert.numero)

    def test_aucun_cout_interne_dans_l_export_rfi(self):
        self._rfi(impact_cout=True)
        texte = self.api.get(URL_RFI).content.decode('utf-8-sig').lower()
        for terme in ('prix_achat', "prix d'achat", 'déboursé', 'marge'):
            with self.subTest(terme=terme):
                self.assertNotIn(terme, texte)

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_cross_tenant_isole(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        autre_user = make_user(autre, role='responsable')
        ReserveChantier.objects.create(
            company=autre, chantier=autre_chantier, lot='SECRET',
            localisation_plan={}, description='Réserve voisine',
            gravite=ReserveChantier.Gravite.MINEURE, created_by=autre_user)
        self._reserve(description='La mienne')
        texte = self.api.get(URL_RESERVES).content.decode('utf-8-sig')
        self.assertIn('La mienne', texte)
        self.assertNotIn('Réserve voisine', texte)
        self.assertNotIn('SECRET', texte)
