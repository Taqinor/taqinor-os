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
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity
from apps.visites.models import VisiteMedia, VisiteTerrain
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


TERRAIN = ['crm_voir', 'visites_voir', 'visites_creer',
           'visites_modifier']
BUREAU = TERRAIN + ['visites_valider']


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
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': self.lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def poster_photo(self, visite_id, slot_code, nom='p.png', **extra):
        upload = SimpleUploadedFile(nom, PNG, content_type='image/png')
        corps = {'slot_code': slot_code, 'fichier': upload}
        corps.update(extra)
        return self.api.post(
            f'/api/django/visites/visites/{visite_id}/photos/', corps,
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
                f'/api/django/visites/visites/{visite_id}/mesures/',
                {'categorie': categorie, 'valeurs': valeurs}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)


class ScopingSocieteTests(VisiteTerrainBase):
    def test_une_societe_ne_voit_pas_la_visite_de_lautre(self):
        visite_id = self.creer_visite()
        intrus = auth(self.etranger)

        detail = intrus.get(f'/api/django/visites/visites/{visite_id}/')
        self.assertEqual(detail.status_code, 404)

        liste = intrus.get('/api/django/visites/visites/')
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(
            [ligne['id'] for ligne in liste.data], [])

    def test_creer_une_visite_sur_le_lead_dune_autre_societe_est_refuse(self):
        # ENF11 (nocturne 15/10) — lead borné à la société : celui d'une autre
        # société est « inconnu », 404 de même corps qu'un lead absent.
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': self.lead_etranger.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(resp.data['lead'][0].code, 'does_not_exist', resp.data)
        absent = self.api.post('/api/django/visites/visites/',
                               {'lead': 99999999}, format='json')
        self.assertEqual(absent.status_code, 404, absent.data)
        self.assertEqual(str(resp.data['lead']).replace(str(self.lead_etranger.id), 'N'),
                         str(absent.data['lead']).replace('99999999', 'N'))
        self.assertFalse(VisiteTerrain.objects.filter(lead=self.lead_etranger).exists())

    def test_la_societe_est_forcee_cote_serveur(self):
        visite_id = self.creer_visite()
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.company_id, self.company.id)
        self.assertEqual(visite.commercial_id, self.commercial.id)


class CompletudeTests(VisiteTerrainBase):
    def test_terminer_est_refuse_avec_la_liste_des_manquants(self):
        visite_id = self.creer_visite()
        resp = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
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
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        toiture = detail.data['checklist'][0]
        self.assertEqual(toiture['slots'][0]['etat'], 'manquant')

    def test_terminer_est_accepte_quand_tout_y_est(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        self.assertTrue(detail.data['completude']['complet'],
                        detail.data['completude']['manquants'])
        resp = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
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

    def test_slot_d_un_autre_gabarit_est_un_refus_d_etat(self):
        # ERR-ENF11-FUZZ-VISITES — « cellule_mt » est publié (gabarit
        # professionnel) mais étranger à une visite de toiture : 409.
        visite_id = self.creer_visite()
        resp = self.poster_photo(visite_id, 'cellule_mt')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('slot_code', resp.data['erreurs'])

    def test_coordonnee_hors_amplitude_refusee_avant_toute_ecriture(self):
        visite_id = self.creer_visite()
        resp = self.poster_photo(visite_id, 'general_facade', gps_lat='1000')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('gps_lat', resp.data['erreurs'])
        self.assertFalse(VisiteMedia.objects.filter(
            visite_id=visite_id).exists())

    def test_categorie_d_un_autre_gabarit_est_un_refus_d_etat(self):
        visite_id = self.creer_visite()
        resp = self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': 'site_commerce', 'valeurs': {}}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('categorie', resp.data['erreurs'])

    def test_un_champ_inconnu_de_la_categorie_est_un_refus_d_etat(self):
        visite_id = self.creer_visite()
        resp = self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': 'tableau', 'valeurs': {'champ_fantaisiste': 1}},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('champ_fantaisiste', resp.data['erreurs'])

    def test_mesure_invalide_nomme_le_champ_fautif(self):
        visite_id = self.creer_visite()
        resp = self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
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
            f'/api/django/visites/visites/{visite_id}/mesures/',
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
            self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/',
                          {}, format='json').status_code, 200)

        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        # Le slot se trouve par son CODE, jamais par position : l'ordre des
        # catégories vient de visite_checklist.py, pas de ce test.
        slot = next(s for cat in detail.data['checklist']
                    for s in cat['slots'] if s['code'] == 'toiture_obstacles')
        media_id = slot['photos'][0]['id']

        bureau = auth(self.bureau)
        renvoi = bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [media_id], 'mesures': [], 'motif': 'Photo floue.'},
            format='json')
        self.assertEqual(renvoi.status_code, 200, renvoi.data)
        self.assertEqual(renvoi.data['statut'], VisiteTerrain.Statut.A_REFAIRE)
        renvoye = next(s for cat in renvoi.data['checklist']
                       for s in cat['slots']
                       if s['code'] == 'toiture_obstacles')
        self.assertEqual(renvoye['etat'], 'a_refaire')
        self.assertEqual(renvoye['photos'][0]['motif_refaire'], 'Photo floue.')

        # Tant que la photo n'est pas reprise, la visite n'est PAS terminable.
        refus = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(refus.status_code, 409, refus.data)

        supprime = self.api.delete(
            f'/api/django/visites/visites/{visite_id}/photos/{media_id}/')
        self.assertEqual(supprime.status_code, 200, supprime.data)
        self.assertEqual(
            self.poster_photo(visite_id, 'toiture_obstacles',
                              nom='reprise.png').status_code, 200)

        fini = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(fini.status_code, 200, fini.data)

    def test_le_motif_est_obligatoire(self):
        visite_id = self.creer_visite()
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': '   '}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif', resp.data['erreurs'])

    def test_une_mesure_renvoyee_est_redemandee(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        # ALEA6 — seule une visite TERMINÉE (ou validée) se renvoie : le
        # renvoi d'une visite en cours sautait une étape du parcours.
        self.assertEqual(
            self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/',
                          {}, format='json').status_code, 200)
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
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
            f'/api/django/visites/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertNotEqual(
            VisiteTerrain.objects.get(pk=visite_id).statut,
            VisiteTerrain.Statut.VALIDEE)

    def test_valider_gele_la_visite_en_lecture_seule(self):
        visite_id = self.creer_visite()
        # ALEA6 — le feu vert ne se donne qu'à une visite TERMINÉE et
        # complète : ce test validait un brouillon vide (l'état sauté que la
        # table des transitions refuse désormais).
        self.remplir(visite_id)
        self.assertEqual(
            self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/',
                          {}, format='json').status_code, 200)
        bureau = auth(self.bureau)
        resp = bureau.post(
            f'/api/django/visites/visites/{visite_id}/valider/', {},
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
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
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
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
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
        self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/', {},
                      format='json')
        self.assertTrue(
            any('terminée' in note for note in self._notes()))

        bureau = auth(self.bureau)
        bureau.post(f'/api/django/visites/visites/{visite_id}/valider/', {},
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
        # ALEA6 — on ne renvoie qu'une visite terminée (ou validée).
        self.remplir(visite_id)
        self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/', {},
                      format='json')
        bureau = auth(self.bureau)
        bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': 'Tableau non photographié.'},
            format='json')
        self.assertTrue(
            any('Tableau non photographié.' in note
                for note in self._notes()))


class CablageRetourLeadTests(VisiteTerrainBase):
    """VT12 — ce que le feu vert REDESCEND sur la fiche lead, et la porte
    ``photo-toit`` par laquelle le reste de l'ERP lit le toit réaliste.

    Aucune horloge vive n'est asservie : la date du récap est comparée à la
    date que le SERVEUR a lui-même posée sur la visite, jamais à
    « aujourd'hui ».
    """

    URL = '/api/django/crm/leads/{}/photo-toit/'

    def _valider(self, visite_id):
        bureau = auth(self.bureau)
        resp = bureau.post(f'/api/django/visites/visites/{visite_id}/valider/',
                           {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _valider_par_le_service(self, visite_id):
        """Feu vert posé par le SERVICE (ce que la route appelle après la
        table des transitions) : ces tests portent sur ce que le feu vert
        REDESCEND au lead, y compris pour une visite sans mesure — un état
        que la route refuse depuis ALEA6 (visite non terminée/incomplète)."""
        from apps.visites import services

        services.valider_visite(VisiteTerrain.objects.get(pk=visite_id),
                                self.bureau)

    # ── L'écriture en retour sur le lead ─────────────────────────────────────

    def test_le_feu_vert_marque_la_visite_effectuee_sur_le_lead(self):
        self.assertFalse(self.lead.visite_effectuee)
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/', {},
                      format='json')
        self._valider(visite_id)

        self.lead.refresh_from_db()
        self.assertTrue(self.lead.visite_effectuee)

    def test_le_recap_ne_porte_que_des_mesures_reellement_saisies(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        self.api.post(f'/api/django/visites/visites/{visite_id}/terminer/', {},
                      format='json')
        self._valider(visite_id)

        self.lead.refresh_from_db()
        notes = self.lead.visite_notes or ''
        # Les valeurs saisies dans MESURES_COMPLETES, telles quelles.
        self.assertIn('12.5 × 8 m', notes)
        self.assertIn('pente 15°', notes)
        self.assertIn('orientation sud', notes)
        self.assertIn('disjoncteur 63 A', notes)
        # La date vient du SERVEUR (posée au « terminer »), pas d'une horloge
        # vive de test.
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertIn(visite.date_realisee.strftime('%d/%m/%Y'), notes)

    def test_une_mesure_absente_est_omise_jamais_remplacee(self):
        """Zéro chiffre inventé : sans mesure relevée, aucune n'est affirmée."""
        visite_id = self.creer_visite()
        self._valider_par_le_service(visite_id)

        self.lead.refresh_from_db()
        notes = self.lead.visite_notes or ''
        self.assertIn('Visite technique validée', notes)
        for interdit in ('zone utile', 'pente', 'orientation', 'disjoncteur'):
            self.assertNotIn(interdit, notes, interdit)

    def test_une_note_deja_ecrite_nest_pas_ecrasee_ni_dupliquee(self):
        self.lead.visite_notes = 'Chien méchant dans la cour.'
        self.lead.save(update_fields=['visite_notes'])
        visite_id = self.creer_visite()
        self._valider_par_le_service(visite_id)

        self.lead.refresh_from_db()
        premier = self.lead.visite_notes
        self.assertIn('Chien méchant dans la cour.', premier)
        self.assertIn('Visite technique validée', premier)

        # Une re-validation (deuxième visite du même lead, aucune mesure de
        # plus) ne duplique pas le même récap sur la fiche.
        autre = self.creer_visite()
        self._valider_par_le_service(autre)
        self.lead.refresh_from_db()
        self.assertEqual(
            self.lead.visite_notes.count('Visite technique validée'), 1)

    def test_le_chatter_du_feu_vert_nest_pas_double(self):
        visite_id = self.creer_visite()
        self._valider_par_le_service(visite_id)
        feux = [note for note in LeadActivity.objects
                .filter(lead=self.lead, kind=LeadActivity.Kind.NOTE)
                .values_list('body', flat=True)
                if 'feu vert' in note]
        self.assertEqual(len(feux), 1, feux)

    # ── La porte ``photo-toit`` du lead ──────────────────────────────────────

    def _visite_avec_toit(self, statut=VisiteTerrain.Statut.VALIDEE,
                          company=None, lead=None, key='toit-assemble.png'):
        return VisiteTerrain.objects.create(
            company=company or self.company, lead=lead or self.lead,
            commercial=self.commercial, statut=statut, photo_toit_key=key,
            texture_calage={'coins': [[33.57, -7.58], [33.57, -7.57],
                                      [33.56, -7.57], [33.56, -7.58]]})

    def test_sans_visite_validee_les_trois_cles_sortent_nulles(self):
        resp = self.api.get(self.URL.format(self.lead.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(dict(resp.data), {
            'visite_id': None, 'url': None, 'texture_calage': None})

    def test_une_visite_validee_avec_toit_sert_url_et_calage(self):
        visite = self._visite_avec_toit()
        resp = self.api.get(self.URL.format(self.lead.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['visite_id'], visite.id)
        self.assertEqual(resp.data['url'],
                         f'/api/django/visites/visites/{visite.id}/photo-toit/')
        self.assertEqual(len(resp.data['texture_calage']['coins']), 4)

    def test_une_visite_non_validee_ne_peint_jamais_de_toit(self):
        self._visite_avec_toit(statut=VisiteTerrain.Statut.TERMINEE)
        resp = self.api.get(self.URL.format(self.lead.id))
        self.assertIsNone(resp.data['visite_id'])
        self.assertIsNone(resp.data['url'])

    def test_une_visite_validee_sans_image_sort_nulle(self):
        self._visite_avec_toit(key='')
        resp = self.api.get(self.URL.format(self.lead.id))
        self.assertIsNone(resp.data['visite_id'])
        self.assertIsNone(resp.data['url'])

    def test_la_derniere_visite_validee_gagne(self):
        self._visite_avec_toit(key='ancien.png')
        recente = self._visite_avec_toit(key='recent.png')
        resp = self.api.get(self.URL.format(self.lead.id))
        self.assertEqual(resp.data['visite_id'], recente.id)

    def test_jamais_la_visite_dune_autre_societe(self):
        """Deux VRAIS locataires : la texture ne traverse pas la frontière."""
        self._visite_avec_toit(company=self.autre, lead=self.lead_etranger)
        self._visite_avec_toit()

        # (a) l'étranger ne voit pas le toit du lead de notre société — et
        #     n'apprend même pas que ce lead existe (200 à valeurs nulles,
        #     jamais un 404 distinctif).
        intrus = auth(self.etranger)
        resp = intrus.get(self.URL.format(self.lead.id))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(dict(resp.data), {
            'visite_id': None, 'url': None, 'texture_calage': None})

        # (b) et l'étranger voit bien SA propre texture (la porte fonctionne
        #     des deux côtés — ce n'est pas un refus global).
        sienne = intrus.get(self.URL.format(self.lead_etranger.id))
        self.assertIsNotNone(sienne.data['visite_id'])

    def test_un_lead_inexistant_ne_leve_jamais_404(self):
        resp = self.api.get(self.URL.format(999999))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['visite_id'])


# ENFP (D1) — ``?lead=`` est déclaré ET honoré sur la liste des visites.
class ListeFiltreLeadTests(VisiteTerrainBase):
    def test_filtre_lead(self):
        visite_id = self.creer_visite()
        autre = Lead.objects.create(company=self.company, nom='Autre dossier')
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': autre.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.api.get('/api/django/visites/visites/',
                            {'lead': self.lead.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['id'] for r in resp.data], [visite_id])

    def test_lead_non_entier_400(self):
        # CI #956 (api-fuzz « accepted schema-violating », ?lead=null → 200) :
        # `lead` est déclaré entier au schéma ; une valeur illisible est un
        # 400 nommé — plus un filtre ignoré (l'ancien test attendait 200).
        self.creer_visite()
        for brut in ('abc', 'null', '1.5'):
            resp = self.api.get('/api/django/visites/visites/', {'lead': brut})
            self.assertEqual(resp.status_code, 400, (brut, resp.data))
            self.assertIn('lead', resp.data)
        # Vide = pas de filtre ; un id inconnu = liste vide, jamais 404.
        resp = self.api.get('/api/django/visites/visites/', {'lead': ''})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        resp = self.api.get('/api/django/visites/visites/', {'lead': '0'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])


class ModificationSansLeadTests(VisiteTerrainBase):
    """ENF11 — le dossier (lead) d'une visite est figé : le PUT ne l'exige pas."""

    def test_put_sans_lead_met_a_jour_les_notes(self):
        visite_id = self.creer_visite()
        resp = self.api.put(f'/api/django/visites/visites/{visite_id}/',
                            {'notes': 'Portail vert'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['notes'], 'Portail vert')
        self.assertEqual(resp.data['lead'], self.lead.id)

    def test_put_avec_un_autre_lead_reste_refuse(self):
        visite_id = self.creer_visite()
        autre = Lead.objects.create(company=self.company, nom='Autre dossier')
        resp = self.api.put(f'/api/django/visites/visites/{visite_id}/',
                            {'lead': autre.id}, format='json')
        # ENF11 (nocturne 15/10) — la visite EN PLACE s'oppose (dossier figé) :
        # 409, même corps ``{lead: [message]}`` ; la visite garde son lead.
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('lead', resp.data)
        self.assertNotEqual(VisiteTerrain.objects.get(pk=visite_id).lead_id, autre.id)


class SchemaVisitesPublieTests(SimpleTestCase):
    """ERR-ENF11-FUZZ-VISITES — le schéma publié dit ce que la vue sert
    (api-fuzz du 13/10/2026 : liste publiée en tableau DE tableaux, PUT publié
    avec l'agrégat alors qu'il rend l'entête)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        generateur = SchemaGenerator(patterns=[path(
            'api/django/visites/', include('apps.visites.urls'))])
        cls.schema = generateur.get_schema(request=None, public=True)

    def _reponse(self, methode, chemin):
        operation = self.schema['paths'][
            '/api/django/visites/' + chemin][methode]
        return operation['responses']['200']['content'][
            'application/json']['schema']

    def _composant(self, noeud):
        return self.schema['components']['schemas'][
            noeud['$ref'].rsplit('/', 1)[-1]]

    def test_la_liste_est_un_tableau_de_lignes(self):
        schema = self._reponse('get', 'visites/')
        self.assertEqual(schema['type'], 'array')
        ligne = self._composant(schema['items'])
        self.assertEqual(ligne['type'], 'object')
        self.assertEqual(
            set(ligne['properties']),
            {'id', 'lead', 'lead_nom', 'ville', 'statut', 'date_prevue',
             'complet', 'manquants_count'})

    def test_le_put_publie_l_entete(self):
        entete = self._composant(self._reponse('put', 'visites/{id}/'))
        self.assertEqual(
            set(entete['properties']),
            {'id', 'lead', 'commercial', 'statut', 'date_prevue',
             'date_realisee', 'notes'})

    def test_le_motif_de_renvoi_publie_non_blanc_sans_nul(self):
        # api-fuzz-full 27/10 : « /@Bl\x00 » était publié conforme puis
        # refusé 400 — le corps publie désormais le motif « non blanc, sans
        # NUL » que la validation applique.
        from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL
        operation = self.schema['paths'][
            '/api/django/visites/visites/{id}/renvoyer/']['post']
        corps = self._composant(operation['requestBody']['content'][
            'application/json']['schema'])
        self.assertEqual(corps['properties']['motif']['pattern'],
                         MOTIF_NON_BLANC_SANS_NUL)
