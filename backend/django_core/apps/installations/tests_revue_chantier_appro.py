"""Nouveau fichier car : lanes parallèles file-disjointes de la revue chantier du 26/10/2026
(aucun module de test existant ne couvre à la fois l'approvisionnement,
`commander-besoin` multi-fournisseur, le gate matériel et la liste de
préparation F5).

Revue chantier 26/10/2026 (fondateur : « après l'acceptation, je dois savoir
ce qui manque, l'acheter, voir ce qui arrive ») :

  (a) `GET chantiers/<pk>/approvisionnement/` sert les clés EXACTES du contrat
      `contract_samples/chantier_approvisionnement.json` et ses chiffres
      (manque net de l'ENVOYÉ seulement, brouillon à part, reçu) ;
  (b) `serie_attendue` : faux pour un câble, vrai pour un panneau ;
  (c) `commander-besoin` : un BCF PAR FOURNISSEUR, surcharges honorées,
      chantier « Signé » → « Matériel commandé », second appel = 409 ;
  (d) gate matériel : un BCF brouillon ne lève pas le manque, un envoyé oui ;
  (e) isolation société : chantier d'une autre société → 404 ;
  (f) préparation F5 : un produit commandé (BCF envoyé) n'est plus
      « Manquant », il l'est toujours sur un simple brouillon.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_revue_chantier_appro"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import field_services
from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, Installation, Intervention,
    StockReservation,
)
from apps.installations.services import (
    _gate_check_materiel, consume_reservations, seed_stages,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    BonCommandeFournisseur, Categorie, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)

User = get_user_model()
BASE = '/api/django/installations/chantiers'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'chantier_approvisionnement.json')


class ApproBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Revue appro', slug='revue-appro-co')
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.admin = User.objects.create_user(
            username='admin-revue-appro', password='x', company=self.company,
            role=role_admin)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.four_a = Fournisseur.objects.create(
            company=self.company, nom='SunPro Appro')
        self.four_b = Fournisseur.objects.create(
            company=self.company, nom='Electra Appro')
        cat_panneau = Categorie.objects.create(
            company=self.company, nom='Panneaux',
            type_equipement=Categorie.TypeEquipement.PANNEAU)
        cat_cable = Categorie.objects.create(
            company=self.company, nom='Câbles',
            type_equipement=Categorie.TypeEquipement.CABLE)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 710W', sku='PAN-APPRO',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=0, categorie=cat_panneau,
            fournisseur=self.four_a)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', sku='BAT-APPRO',
            prix_vente=Decimal('9000'), prix_achat=Decimal('6000'),
            quantite_stock=0, fournisseur=self.four_b)
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble 6 mm²', sku='CAB-APPRO',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'),
            quantite_stock=100, categorie=cat_cable,
            fournisseur=self.four_a)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-APPRO-1',
            statut=Installation.Statut.SIGNE,
            bom=[
                {'produit_id': self.panneau.id, 'designation': 'Panneau',
                 'quantite': 10.0},
                {'produit_id': self.batterie.id, 'designation': 'Batterie',
                 'quantite': 2.0},
                {'produit_id': self.cable.id, 'designation': 'Câble',
                 'quantite': 60.0},
            ])

    def _bcf(self, fournisseur, statut, lignes):
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-APPRO-{statut}-{fournisseur.pk}',
            fournisseur=fournisseur, statut=statut,
            chantier_origine=self.chantier)
        for produit, qte, recue in lignes:
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bon, produit=produit, quantite=qte,
                quantite_recue=recue, prix_achat_unitaire=produit.prix_achat)
        return bon

    def _lignes(self, data):
        return {li['produit_id']: li for li in data['lignes']}


class ApprovisionnementEndpointTests(ApproBase):
    def _scenario(self):
        StockReservation.objects.create(
            company=self.company, installation=self.chantier,
            produit=self.cable, quantite=60)
        self.brouillon = self._bcf(
            self.four_a, BonCommandeFournisseur.Statut.BROUILLON,
            [(self.panneau, 4, 0)])
        self.envoye = self._bcf(
            self.four_b, BonCommandeFournisseur.Statut.ENVOYE,
            [(self.batterie, 2, 1)])
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-APPRO-1', objet='Coffret',
            chantier=self.chantier, created_by=self.admin,
            statut=DemandeAchat.Statut.SOUMISE)
        DemandeAchatLigne.objects.create(
            demande=self.da, designation='Coffret AC/DC',
            quantite=Decimal('1'), prix_estime=Decimal('500'))

    def test_cles_exactes_du_contrat(self):
        self._scenario()
        r = self.api.get(f'{BASE}/{self.chantier.id}/approvisionnement/')
        self.assertEqual(r.status_code, 200, r.content)
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        data = r.json()
        self.assertEqual(set(data), set(exemple))
        self.assertEqual(set(data['resume']), set(exemple['resume']))
        self.assertEqual(set(data['lignes'][0]), set(exemple['lignes'][0]))
        self.assertEqual(set(data['bons_commande'][0]),
                         set(exemple['bons_commande'][0]))
        self.assertEqual(set(data['bons_commande'][0]['lignes'][0]),
                         set(exemple['bons_commande'][0]['lignes'][0]))
        self.assertEqual(set(data['demandes_achat'][0]),
                         set(exemple['demandes_achat'][0]))
        self.assertEqual(set(data['reservations'][0]),
                         set(exemple['reservations'][0]))
        # Aucun prix d'achat (D-ASTK-2).
        self.assertNotIn('prix_achat', json.dumps(data))

    def test_chiffres_manque_en_commande_recu(self):
        self._scenario()
        data = self.api.get(
            f'{BASE}/{self.chantier.id}/approvisionnement/').json()
        lignes = self._lignes(data)
        pan = lignes[self.panneau.id]
        # Brouillon de 4 : jamais retranché du manque, servi à part.
        self.assertEqual(pan['requis'], 10)
        self.assertEqual(pan['en_commande_brouillon'], 4)
        self.assertEqual(pan['en_commande_envoye'], 0)
        self.assertEqual(pan['manque'], 10)
        bat = lignes[self.batterie.id]
        # Envoyé 2, reçu 1 : 1 encore en route ; manque 2 − 1 = 1.
        self.assertEqual(bat['en_commande_envoye'], 1)
        self.assertEqual(bat['recu'], 1)
        self.assertEqual(bat['manque'], 1)
        self.assertEqual(bat['fournisseur_id'], self.four_b.id)
        cab = lignes[self.cable.id]
        self.assertEqual(cab['reserve_chantier'], 60)
        self.assertEqual(cab['reserve_autres'], 0)
        self.assertEqual(cab['stock_total'], 100)
        self.assertEqual(cab['disponible'], 100)
        self.assertEqual(cab['manque'], 0)
        resume = data['resume']
        self.assertEqual(resume['nb_lignes'], 3)
        self.assertEqual(resume['nb_manques'], 2)
        self.assertEqual(resume['nb_en_commande'], 1)
        self.assertEqual(resume['nb_recues'], 1)
        self.assertFalse(resume['pret_a_poser'])
        self.assertIn('2 articles en manque', resume['raisons'])
        self.assertIn('Date de pose non fixée', resume['raisons'])
        self.assertEqual(len(data['bons_commande']), 2)
        envoye = next(b for b in data['bons_commande']
                      if b['id'] == self.envoye.id)
        self.assertEqual(envoye['quantite_commandee'], 2)
        self.assertEqual(envoye['quantite_recue'], 1)
        self.assertEqual(data['demandes_achat'][0]['id'], self.da.id)
        self.assertEqual(data['demandes_achat'][0]['nb_lignes'], 1)
        self.assertEqual(
            [(r['produit_id'], r['quantite']) for r in data['reservations']],
            [(self.cable.id, 60)])

    def test_serie_attendue_cable_faux_panneau_vrai(self):
        data = self.api.get(
            f'{BASE}/{self.chantier.id}/approvisionnement/').json()
        lignes = self._lignes(data)
        self.assertTrue(lignes[self.panneau.id]['serie_attendue'])
        self.assertFalse(lignes[self.cable.id]['serie_attendue'])

    def test_nomenclature_vide(self):
        vide = Installation.objects.create(
            company=self.company, reference='CH-APPRO-VIDE')
        data = self.api.get(f'{BASE}/{vide.id}/approvisionnement/').json()
        self.assertEqual(data['lignes'], [])
        self.assertFalse(data['resume']['pret_a_poser'])
        self.assertIn('Nomenclature vide', data['resume']['raisons'])

    def test_autre_societe_404(self):
        autre = Company.objects.create(nom='Autre appro', slug='autre-appro')
        chantier_autre = Installation.objects.create(
            company=autre, reference='CH-APPRO-AUTRE')
        r = self.api.get(f'{BASE}/{chantier_autre.id}/approvisionnement/')
        self.assertEqual(r.status_code, 404, r.content)
        r = self.api.post(f'{BASE}/{chantier_autre.id}/commander-besoin/',
                          {}, format='json')
        self.assertEqual(r.status_code, 404, r.content)

    def test_installe_consomme_n14_compte_comme_deja_sorti(self):
        # F1 — la sortie N14 de « Installé » (réservation consommée) compte
        # comme déjà sortie : la nomenclature ne repasse pas en manque.
        Installation.objects.filter(pk=self.chantier.pk).update(bom=[
            {'produit_id': self.panneau.id, 'designation': 'Panneau',
             'quantite': 10.0}])
        Produit.objects.filter(pk=self.panneau.pk).update(quantite_stock=10)
        self.chantier.refresh_from_db()
        StockReservation.objects.create(
            company=self.company, installation=self.chantier,
            produit=self.panneau, quantite=10)
        self.assertEqual(consume_reservations(self.chantier, self.admin), 1)
        Installation.objects.filter(pk=self.chantier.pk).update(
            statut=Installation.Statut.INSTALLE)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 0)
        data = self.api.get(
            f'{BASE}/{self.chantier.id}/approvisionnement/').json()
        pan = self._lignes(data)[self.panneau.id]
        self.assertEqual(pan['deja_sorti'], 10)
        self.assertEqual(pan['reserve_chantier'], 0)
        self.assertEqual(pan['manque'], 0)
        self.assertEqual(data['resume']['nb_manques'], 0)


class CommanderBesoinTests(ApproBase):
    def test_un_bcf_par_fournisseur_et_avance_statut(self):
        r = self.api.post(f'{BASE}/{self.chantier.id}/commander-besoin/',
                          {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        bons = r.data['bons_commande']
        self.assertEqual(len(bons), 2)
        par_fournisseur = {b['fournisseur']: b for b in bons}
        self.assertEqual(set(par_fournisseur),
                         {self.four_a.id, self.four_b.id})
        lignes_a = [(li['produit'], li['quantite'])
                    for li in par_fournisseur[self.four_a.id]['lignes']]
        self.assertEqual(lignes_a, [(self.panneau.id, 10)])
        lignes_b = [(li['produit'], li['quantite'])
                    for li in par_fournisseur[self.four_b.id]['lignes']]
        self.assertEqual(lignes_b, [(self.batterie.id, 2)])
        for b in bons:
            self.assertEqual(b['statut'], 'brouillon')
            self.assertEqual(b['chantier_origine'], self.chantier.id)
            self.assertEqual(b['chantier_origine_reference'], 'CH-APPRO-1')
        self.assertEqual(r.data['sans_fournisseur'], [])
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.statut,
                         Installation.Statut.MATERIEL_COMMANDE)
        self.assertEqual(r.data['statut_chantier'],
                         Installation.Statut.MATERIEL_COMMANDE)
        self.assertIsNone(r.data['statut_raison'])
        # Idempotent : les brouillons couvrent déjà tout → 409, rien de neuf.
        r2 = self.api.post(f'{BASE}/{self.chantier.id}/commander-besoin/',
                           {}, format='json')
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertEqual(BonCommandeFournisseur.objects.filter(
            company=self.company, chantier_origine=self.chantier).count(), 2)

    def test_surcharge_fournisseur_et_sous_ensemble(self):
        r = self.api.post(
            f'{BASE}/{self.chantier.id}/commander-besoin/',
            {'fournisseurs': {str(self.batterie.id): self.four_a.id},
             'produits': [self.batterie.id]},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        bons = r.data['bons_commande']
        self.assertEqual(len(bons), 1)
        self.assertEqual(bons[0]['fournisseur'], self.four_a.id)
        self.assertEqual([li['produit'] for li in bons[0]['lignes']],
                         [self.batterie.id])

    def test_surcharge_fournisseur_inconnu_404(self):
        autre = Company.objects.create(nom='Autre f', slug='autre-f-appro')
        four_autre = Fournisseur.objects.create(company=autre, nom='X')
        r = self.api.post(
            f'{BASE}/{self.chantier.id}/commander-besoin/',
            {'fournisseurs': {str(self.panneau.id): four_autre.id}},
            format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.assertFalse(BonCommandeFournisseur.objects.filter(
            chantier_origine=self.chantier).exists())

    def test_sans_fournisseur_signale(self):
        Produit.objects.filter(pk=self.batterie.pk).update(fournisseur=None)
        r = self.api.post(f'{BASE}/{self.chantier.id}/commander-besoin/',
                          {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.data['bons_commande']), 1)
        self.assertEqual(
            [s['produit_id'] for s in r.data['sans_fournisseur']],
            [self.batterie.id])

    def test_brouillon_ne_securise_pas_le_gate(self):
        self._bcf(self.four_a, BonCommandeFournisseur.Statut.BROUILLON,
                  [(self.panneau, 10, 0)])
        self._bcf(self.four_b, BonCommandeFournisseur.Statut.BROUILLON,
                  [(self.batterie, 2, 0)])
        raison = _gate_check_materiel(self.chantier)
        self.assertIsNotNone(raison)
        self.assertIn('Panneau 710W', raison)
        BonCommandeFournisseur.objects.filter(
            chantier_origine=self.chantier).update(
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.assertIsNone(_gate_check_materiel(self.chantier))

    def test_etapes_amorcees_materiel_commande_a_l_envoi(self):
        # F2 — étape bloquante « approvisionnement » : les brouillons ne
        # font pas avancer, l'ENVOI des BCF qui couvrent tout le manque oui.
        seed_stages(self.company)
        r = self.api.post(f'{BASE}/{self.chantier.id}/commander-besoin/',
                          {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['statut_chantier'], Installation.Statut.SIGNE)
        self.assertIn('Matériel en pénurie', r.data['statut_raison'])
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.statut, Installation.Statut.SIGNE)
        bons = {b['fournisseur']: b['id'] for b in r.data['bons_commande']}
        url = '/api/django/stock/bons-commande-fournisseur/{}/envoyer/'
        r = self.api.post(url.format(bons[self.four_a.id]))
        self.assertEqual(r.status_code, 200, r.content)
        self.chantier.refresh_from_db()
        # La batterie (fournisseur B) manque encore : pas d'avancée.
        self.assertEqual(self.chantier.statut, Installation.Statut.SIGNE)
        r = self.api.post(url.format(bons[self.four_b.id]))
        self.assertEqual(r.status_code, 200, r.content)
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.statut,
                         Installation.Statut.MATERIEL_COMMANDE)


class PreparationAccordTests(ApproBase):
    def _ligne_prep(self, produit):
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.admin)
        prep = field_services.ensure_preparation(interv)
        return prep.materiel.get(produit=produit)

    def test_bcf_envoye_leve_le_manquant_brouillon_non(self):
        bon = self._bcf(self.four_b, BonCommandeFournisseur.Statut.BROUILLON,
                        [(self.batterie, 2, 0)])
        ligne = self._ligne_prep(self.batterie)
        self.assertTrue(ligne.manquant)
        self.assertEqual(ligne.quantite_manquante, 2)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        ligne = self._ligne_prep(self.batterie)
        self.assertFalse(ligne.manquant)
        self.assertEqual(ligne.quantite_manquante, 0)

    def test_arrondi_plafond_comme_le_besoin(self):
        Installation.objects.filter(pk=self.chantier.pk).update(bom=[
            {'produit_id': self.panneau.id, 'designation': 'Panneau',
             'quantite': 2.4}])
        self.chantier.refresh_from_db()
        ligne = self._ligne_prep(self.panneau)
        self.assertEqual(ligne.quantite_requise, 3)
        self.assertEqual(ligne.quantite_manquante, 3)

    def test_deux_lignes_meme_produit_couverture_partagee(self):
        # F3 — deux lignes P × 5, stock 0, un BCF envoyé de 5 : la commande
        # couvre UNE ligne ; la somme des manques = le manque produit (5).
        Installation.objects.filter(pk=self.chantier.pk).update(bom=[
            {'produit_id': self.batterie.id, 'designation': 'Batterie A',
             'quantite': 5.0},
            {'produit_id': self.batterie.id, 'designation': 'Batterie B',
             'quantite': 5.0}])
        self.chantier.refresh_from_db()
        self._bcf(self.four_b, BonCommandeFournisseur.Statut.ENVOYE,
                  [(self.batterie, 5, 0)])
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.admin)
        prep = field_services.ensure_preparation(interv)
        lignes = list(prep.materiel.filter(produit=self.batterie))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(
            [(li.designation, li.quantite_manquante)
             for li in lignes if li.manquant],
            [('Batterie B', 5)])
        data = self.api.get(
            f'{BASE}/{self.chantier.id}/approvisionnement/').json()
        self.assertEqual(self._lignes(data)[self.batterie.id]['manque'], 5)
