"""VT4 — Tests de la visite technique terrain (groupe VT).

Ce qui est prouvé ici, et pourquoi :

* **Isolation multi-société** — deux VRAIS locataires distincts (deux
  ``Company``, deux utilisateurs, deux leads) : une société ne voit ni ne
  touche la visite de l'autre.
* **La porte de complétude est SERVEUR** — ``terminer`` est refusé tant qu'un
  slot requis ou une mesure obligatoire manque, et la réponse porte la LISTE
  exacte des manquants (le front l'affiche, il ne l'invente pas).
* **La boucle du renvoi** — renvoyer → la photo redevient « à refaire » et la
  visite n'est plus terminable → re-upload → re-terminer.
* **Le feu vert est une permission à part** — un commercial qui remplit la
  visite ne peut pas se la valider à lui-même.
* **Aucune fuite de prix d'achat** — le RENDU de l'agrégat est scanné.
* **Un slot photo inconnu est refusé** (la checklist code est la seule
  autorité) et **le chatter du lead** garde la trace des transitions.

Aucune horloge vive n'est asservie : rien n'affirme une date « d'aujourd'hui ».
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity, VisiteTerrain
from apps.roles.models import Role
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

# Octets magiques PNG — suffisants pour la détection de type de records.storage.
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64

# Les slots REQUIS de la checklist, avec le nombre de photos exigé.
SLOTS_REQUIS = [
    ('toiture_vue_generale', 2),
    ('toiture_obstacles', 1),
    ('tableau_ouvert', 1),
    ('onduleur_mur', 1),
    ('general_facade', 1),
]

MESURES_COMPLETES = {
    'toiture': {
        'longueur_m': 12.5, 'largeur_m': 8, 'pente_deg': 15,
        'toit_plat': False, 'orientation': 'sud', 'type_couverture': 'tuile',
        'etat_couverture': 'bon',
    },
    'tableau': {
        'calibre_disjoncteur_a': 63, 'type_alimentation': 'mono',
        'emplacements_libres': 4,
    },
    'local_onduleur': {
        'largeur_mur_cm': 200, 'hauteur_mur_cm': 250,
        'profondeur_degagement_cm': 80, 'distance_tableau_m': 5,
        'local_abrite': True, 'local_ventile': True,
    },
}


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_role(company, nom, permissions):
    return Role.objects.create(company=company, nom=nom,
                               permissions=list(permissions))


def make_user(company, username, permissions):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal',
        role=make_role(company, f'role-{username}', permissions))


TERRAIN = ['crm_voir', 'crm_visite_voir', 'crm_visite_creer',
           'crm_visite_modifier']
BUREAU = TERRAIN + ['crm_visite_valider']


class VisiteTerrainBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VT4 Solaire', slug='vt4-a')
        self.autre = Company.objects.create(nom='VT4 Concurrent', slug='vt4-b')
        self.commercial = make_user(self.company, 'vt4-commercial', TERRAIN)
        self.bureau = make_user(self.company, 'vt4-bureau', BUREAU)
        self.etranger = make_user(self.autre, 'vt4-etranger', BUREAU)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            telephone='+212600000001', ville='Bouskoura',
            adresse='Lotissement Démo')
        self.lead_etranger = Lead.objects.create(
            company=self.autre, nom='Autre Client')
        self.api = auth(self.commercial)

    def creer_visite(self):
        resp = self.api.post('/api/django/crm/visites/',
                             {'lead': self.lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def poster_photo(self, visite_id, slot_code, nom='p.png', **extra):
        upload = SimpleUploadedFile(nom, PNG, content_type='image/png')
        corps = {'slot_code': slot_code, 'fichier': upload}
        corps.update(extra)
        return self.api.post(
            f'/api/django/crm/visites/{visite_id}/photos/', corps,
            format='multipart')

    def remplir(self, visite_id):
        """Amène la visite à la complétude serveur."""
        for slot, combien in SLOTS_REQUIS:
            for index in range(combien):
                resp = self.poster_photo(visite_id, slot,
                                         nom=f'{slot}-{index}.png')
                self.assertEqual(resp.status_code, 200, resp.data)
        for categorie, valeurs in MESURES_COMPLETES.items():
            resp = self.api.patch(
                f'/api/django/crm/visites/{visite_id}/mesures/',
                {'categorie': categorie, 'valeurs': valeurs}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)


class ScopingSocieteTests(VisiteTerrainBase):
    def test_une_societe_ne_voit_pas_la_visite_de_lautre(self):
        visite_id = self.creer_visite()
        intrus = auth(self.etranger)

        detail = intrus.get(f'/api/django/crm/visites/{visite_id}/')
        self.assertEqual(detail.status_code, 404)

        liste = intrus.get('/api/django/crm/visites/')
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(
            [ligne['id'] for ligne in liste.data], [])

    def test_creer_une_visite_sur_le_lead_dune_autre_societe_est_refuse(self):
        resp = self.api.post('/api/django/crm/visites/',
                             {'lead': self.lead_etranger.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_la_societe_est_forcee_cote_serveur(self):
        visite_id = self.creer_visite()
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.company_id, self.company.id)
        self.assertEqual(visite.commercial_id, self.commercial.id)


class CompletudeTests(VisiteTerrainBase):
    def test_terminer_est_refuse_avec_la_liste_des_manquants(self):
        visite_id = self.creer_visite()
        resp = self.api.post(
            f'/api/django/crm/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        manquants = resp.data['manquants']
        self.assertTrue(manquants)
        codes = {item['code'] for item in manquants}
        for slot, _ in SLOTS_REQUIS:
            self.assertIn(slot, codes, slot)
        self.assertIn('largeur_mur_cm', codes)
        # Le cheminement est OPTIONNEL : il ne bloque jamais.
        self.assertNotIn('cheminement_parcours', codes)
        # Un refus ne fait avancer AUCUN statut.
        self.assertEqual(
            VisiteTerrain.objects.get(pk=visite_id).statut,
            VisiteTerrain.Statut.BROUILLON)

    def test_un_slot_a_moitie_servi_reste_manquant(self):
        visite_id = self.creer_visite()
        # Le slot « vue générale » exige DEUX photos : une seule ne suffit pas.
        self.assertEqual(
            self.poster_photo(visite_id, 'toiture_vue_generale').status_code,
            200)
        detail = self.api.get(f'/api/django/crm/visites/{visite_id}/')
        toiture = detail.data['checklist'][0]
        self.assertEqual(toiture['slots'][0]['etat'], 'manquant')

    def test_terminer_est_accepte_quand_tout_y_est(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        detail = self.api.get(f'/api/django/crm/visites/{visite_id}/')
        self.assertTrue(detail.data['completude']['complet'],
                        detail.data['completude']['manquants'])
        resp = self.api.post(
            f'/api/django/crm/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.TERMINEE)
        self.assertIsNotNone(
            VisiteTerrain.objects.get(pk=visite_id).date_realisee)

    def test_slot_inconnu_refuse_en_nommant_le_champ(self):
        visite_id = self.creer_visite()
        resp = self.poster_photo(visite_id, 'toiture_drone_360')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('slot_code', resp.data['erreurs'])

    def test_mesure_invalide_nomme_le_champ_fautif(self):
        visite_id = self.creer_visite()
        resp = self.api.patch(
            f'/api/django/crm/visites/{visite_id}/mesures/',
            {'categorie': 'tableau',
             'valeurs': {'type_alimentation': 'quadri'}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('type_alimentation', resp.data['erreurs'])

    def test_un_toit_plat_dispense_de_la_pente(self):
        visite_id = self.creer_visite()
        valeurs = dict(MESURES_COMPLETES['toiture'])
        valeurs.pop('pente_deg')
        valeurs['toit_plat'] = True
        resp = self.api.patch(
            f'/api/django/crm/visites/{visite_id}/mesures/',
            {'categorie': 'toiture', 'valeurs': valeurs}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        codes = {item['code']
                 for item in resp.data['completude']['manquants']}
        self.assertNotIn('pente_deg', codes)


class BoucleDeRenvoiTests(VisiteTerrainBase):
    def test_renvoyer_puis_reupload_puis_reterminer(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        self.assertEqual(
            self.api.post(f'/api/django/crm/visites/{visite_id}/terminer/',
                          {}, format='json').status_code, 200)

        detail = self.api.get(f'/api/django/crm/visites/{visite_id}/')
        slot = detail.data['checklist'][1]['slots'][0]
        self.assertEqual(slot['code'], 'toiture_obstacles')
        media_id = slot['photos'][0]['id']

        bureau = auth(self.bureau)
        renvoi = bureau.post(
            f'/api/django/crm/visites/{visite_id}/renvoyer/',
            {'photos': [media_id], 'mesures': [], 'motif': 'Photo floue.'},
            format='json')
        self.assertEqual(renvoi.status_code, 200, renvoi.data)
        self.assertEqual(renvoi.data['statut'], VisiteTerrain.Statut.A_REFAIRE)
        renvoye = renvoi.data['checklist'][1]['slots'][0]
        self.assertEqual(renvoye['etat'], 'a_refaire')
        self.assertEqual(renvoye['photos'][0]['motif_refaire'], 'Photo floue.')

        # Tant que la photo n'est pas reprise, la visite n'est PAS terminable.
        refus = self.api.post(
            f'/api/django/crm/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(refus.status_code, 400, refus.data)

        supprime = self.api.delete(
            f'/api/django/crm/visites/{visite_id}/photos/{media_id}/')
        self.assertEqual(supprime.status_code, 200, supprime.data)
        self.assertEqual(
            self.poster_photo(visite_id, 'toiture_obstacles',
                              nom='reprise.png').status_code, 200)

        fini = self.api.post(
            f'/api/django/crm/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fini.status_code, 200, fini.data)

    def test_le_motif_est_obligatoire(self):
        visite_id = self.creer_visite()
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/crm/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': '   '}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif', resp.data['erreurs'])

    def test_une_mesure_renvoyee_est_redemandee(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/crm/visites/{visite_id}/renvoyer/',
            {'photos': [],
             'mesures': [{'categorie': 'tableau',
                          'code': 'calibre_disjoncteur_a'}],
             'motif': 'Calibre illisible sur la photo.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        codes = {item['code']
                 for item in resp.data['completude']['manquants']}
        self.assertIn('calibre_disjoncteur_a', codes)


class FeuVertTests(VisiteTerrainBase):
    def test_valider_est_refuse_sans_le_code_dedie(self):
        visite_id = self.creer_visite()
        resp = self.api.post(
            f'/api/django/crm/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertNotEqual(
            VisiteTerrain.objects.get(pk=visite_id).statut,
            VisiteTerrain.Statut.VALIDEE)

    def test_valider_gele_la_visite_en_lecture_seule(self):
        visite_id = self.creer_visite()
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/crm/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.VALIDEE)
        self.assertFalse(resp.data['modifiable'])
        self.assertTrue(resp.data['raison_lecture_seule'])

        # Plus aucune contribution n'est acceptée après le feu vert.
        bloque = self.poster_photo(visite_id, 'general_facade')
        self.assertEqual(bloque.status_code, 400, bloque.data)


class PanneauClientDevisTests(VisiteTerrainBase):
    def _devis(self):
        client = Client.objects.create(
            company=self.company, nom='Bennani Karim',
            email='vt4@example.com', telephone='+212600000001')
        self.lead.client = client
        self.lead.save(update_fields=['client'])
        devis = Devis.objects.create(
            company=self.company, reference='DEV-VT4-0001', client=client,
            lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', sku='VT4-PV-550',
            prix_vente=Decimal('1850'), prix_achat=Decimal('987.65'),
            quantite_stock=50, tva=Decimal('10.00'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 550 Wc',
            quantite=Decimal('12'), prix_unitaire=Decimal('1850'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'))
        return devis

    def test_le_panneau_porte_le_client_et_son_devis(self):
        devis = self._devis()
        visite_id = self.creer_visite()
        detail = self.api.get(f'/api/django/crm/visites/{visite_id}/')
        self.assertEqual(detail.status_code, 200)
        panneau = detail.data['client_panel']
        self.assertEqual(panneau['ville'], 'Bouskoura')
        self.assertEqual(panneau['telephone'], '+212600000001')
        dossiers = detail.data['devis']
        self.assertEqual(len(dossiers), 1)
        self.assertEqual(dossiers[0]['numero'], devis.reference)
        self.assertEqual(dossiers[0]['statut'], Devis.Statut.ENVOYE)
        self.assertEqual(len(dossiers[0]['lignes']), 1)
        self.assertEqual(dossiers[0]['lignes'][0]['designation'],
                         'Panneau 550 Wc')

    def test_aucun_prix_dachat_dans_le_rendu(self):
        """Le RENDU est scanné — pas seulement les clés du dictionnaire."""
        import json

        self._devis()
        visite_id = self.creer_visite()
        detail = self.api.get(f'/api/django/crm/visites/{visite_id}/')
        rendu = json.dumps(detail.data, default=str)
        for interdit in ('prix_achat', 'marge', '987.65', '987,65'):
            self.assertNotIn(interdit, rendu, interdit)


class ChatterTests(VisiteTerrainBase):
    def _notes(self):
        return list(
            LeadActivity.objects
            .filter(lead=self.lead, kind=LeadActivity.Kind.NOTE)
            .values_list('body', flat=True))

    def test_creation_terminaison_et_feu_vert_sont_journalises(self):
        visite_id = self.creer_visite()
        self.assertTrue(
            any('Visite technique créée' in note for note in self._notes()))

        self.remplir(visite_id)
        self.api.post(f'/api/django/crm/visites/{visite_id}/terminer/', {},
                      format='json')
        self.assertTrue(
            any('terminée' in note for note in self._notes()))

        bureau = auth(self.bureau)
        bureau.post(f'/api/django/crm/visites/{visite_id}/valider/', {},
                    format='json')
        notes = self._notes()
        self.assertTrue(any('feu vert' in note for note in notes), notes)
        # L'auteur est TOUJOURS résolu côté serveur.
        derniere = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).order_by('-id').first()
        self.assertEqual(derniere.company_id, self.company.id)
        self.assertEqual(derniere.user_id, self.bureau.id)

    def test_le_renvoi_journalise_son_motif(self):
        visite_id = self.creer_visite()
        bureau = auth(self.bureau)
        bureau.post(
            f'/api/django/crm/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': 'Tableau non photographié.'},
            format='json')
        self.assertTrue(
            any('Tableau non photographié.' in note
                for note in self._notes()))
