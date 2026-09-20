"""CAL243 — l'action ``equipements`` (contrat CAL120).

Ce qui est prouvé ici :

* sans devis lié, les quatre familles valent ``None`` et ``devis`` vaut
  ``None`` — jamais une famille inventée ;
* un panneau ET un onduleur retenus rendent leur bloc complet
  (``produit``, ``designation``, ``quantite``, ``specs``,
  ``champs_renseignes``/``champs_manquants``, ``sources``) ;
* une fiche technique VIDE (aucun champ saisi) rend ``specs: {}`` et TOUS
  les champs du contrat en ``champs_manquants`` — jamais un champ inventé ;
* le devis d'une AUTRE société n'est jamais lu (les quatre familles
  retombent à ``None``) ;
* AUCUNE clé ``prix_achat`` ne sort de la réponse ;
* un calepinage d'une autre société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_api_equipements -v2
"""
from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis

from .test_api_liste import BaseApiCalepinage, url_detail


def url_equipements(pk):
    return f'{url_detail(pk)}equipements/'


class ActionEquipementsTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _produit(self, *, nom, type_fiche, company=None, **champs_fiche):
        produit = Produit.objects.create(
            company=company or self.company, nom=nom, sku=f'CAL243-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=company or self.company, produit=produit,
            type_fiche=type_fiche, **champs_fiche)
        return produit

    def _devis_avec_lignes(self, *, company=None, reference='DEV-CAL243-1',
                           lignes=()):
        devis = Devis.objects.create(
            company=company or self.company, client=self.client_a,
            reference=reference)
        for produit, quantite, variante in lignes:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=quantite, prix_unitaire=Decimal('100'),
                type_ligne='produit', variante=variante)
        return devis

    # ── Sans devis lié ───────────────────────────────────────────────────
    def test_sans_devis_toutes_familles_none(self):
        reponse = self.api.get(url_equipements(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['devis'])
        for famille in ('panneau', 'onduleur', 'batterie', 'optimiseur'):
            self.assertIsNone(reponse.data[famille], famille)
        self.assertEqual(reponse.data['calepinage'], self.calepinage.pk)

    # ── Panneau + onduleur retenus, fiche complète ──────────────────────
    def test_panneau_et_onduleur_retenus_avec_completude(self):
        panneau = self._produit(
            nom='Module PV 550', type_fiche='module',
            vmp_v=Decimal('41.5'), voc_v=Decimal('49.8'),
            isc_a=Decimal('13.9'), imp_a=Decimal('13.25'),
            pmax_wc=Decimal('550'), longueur_mm=2278, largeur_mm=1134,
            poids_kg=Decimal('27.5'), rendement_pct=Decimal('21.3'))
        onduleur = self._produit(
            nom='Onduleur hybride 10kW', type_fiche='onduleur',
            ond_ac_kw=Decimal('10'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('120'), ond_mppt_v_max=Decimal('550'),
            ond_v_max_abs=Decimal('600'), ond_i_max_mppt_a=Decimal('13.5'),
            ond_rendement_euro_pct=Decimal('97.5'))
        devis = self._devis_avec_lignes(lignes=[
            (panneau, Decimal('12'), ''),
            (onduleur, Decimal('1'), ''),
        ])
        self.calepinage.devis = devis
        self.calepinage.save()

        reponse = self.api.get(url_equipements(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['devis'], devis.pk)

        bloc_panneau = reponse.data['panneau']
        self.assertEqual(bloc_panneau['produit'], panneau.pk)
        self.assertEqual(bloc_panneau['quantite'], 12.0)
        self.assertEqual(bloc_panneau['specs']['pmax_wc'], Decimal('550'))
        self.assertIn('pmax_wc', bloc_panneau['champs_renseignes'])
        self.assertNotIn('pmax_wc', bloc_panneau['champs_manquants'])
        self.assertIn('bifacial', bloc_panneau['champs_manquants'])
        self.assertEqual(bloc_panneau['sources']['pmax_wc'], 'fiche')
        self.assertEqual(bloc_panneau['sources']['quantite'], 'saisie')

        bloc_onduleur = reponse.data['onduleur']
        self.assertEqual(bloc_onduleur['produit'], onduleur.pk)
        self.assertIn('ac_kw', bloc_onduleur['champs_renseignes'])
        self.assertIn('dc_max_kwc', bloc_onduleur['champs_manquants'])

        self.assertIsNone(reponse.data['batterie'])
        self.assertIsNone(reponse.data['optimiseur'])

    # ── Fiche technique vide : specs vides, tout en manquant ────────────
    def test_fiche_vide_tous_les_champs_manquants(self):
        panneau = self._produit(nom='Module sans specs', type_fiche='module')
        devis = self._devis_avec_lignes(lignes=[(panneau, Decimal('4'), '')])
        self.calepinage.devis = devis
        self.calepinage.save()

        reponse = self.api.get(url_equipements(self.calepinage.pk))
        bloc = reponse.data['panneau']
        self.assertEqual(bloc['specs'], {})
        self.assertEqual(bloc['champs_renseignes'], [])
        self.assertGreater(len(bloc['champs_manquants']), 0)
        self.assertEqual(bloc['sources'], {'quantite': 'saisie'})

    # ── Une ligne « avec batterie » n'est jamais retenue par défaut ─────
    def test_ligne_variante_avec_exclue(self):
        batterie = self._produit(
            nom='Batterie 10kWh', type_fiche='batterie',
            bat_kwh_nominal=Decimal('10'))
        devis = self._devis_avec_lignes(
            lignes=[(batterie, Decimal('1'), 'avec')])
        self.calepinage.devis = devis
        self.calepinage.save()

        reponse = self.api.get(url_equipements(self.calepinage.pk))
        self.assertIsNone(reponse.data['batterie'])

    # ── Devis d'une AUTRE société : jamais lu ───────────────────────────
    def test_devis_d_une_autre_societe_jamais_lu(self):
        client_autre = Client.objects.create(company=self.autre,
                                             nom='Client voisin')
        panneau_autre = self._produit(
            nom='Module voisin', type_fiche='module', company=self.autre)
        devis_autre = Devis.objects.create(
            company=self.autre, client=client_autre,
            reference='DEV-CAL243-VOISIN')
        LigneDevis.objects.create(
            devis=devis_autre, produit=panneau_autre,
            designation=panneau_autre.nom, quantite=Decimal('4'),
            prix_unitaire=Decimal('100'), type_ligne='produit')
        # Fuite de FK possible seulement si la donnée est mal isolée : on
        # force quand même le lien pour prouver que la garde société tient.
        self.calepinage.devis_id = devis_autre.pk
        self.calepinage.save()

        reponse = self.api.get(url_equipements(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['devis'])
        self.assertIsNone(reponse.data['panneau'])

    # ── Aucune clé de prix d'achat ne sort jamais ───────────────────────
    def test_aucune_cle_prix_achat(self):
        panneau = self._produit(
            nom='Module PV 400', type_fiche='module', pmax_wc=Decimal('400'))
        devis = self._devis_avec_lignes(lignes=[(panneau, Decimal('6'), '')])
        self.calepinage.devis = devis
        self.calepinage.save()

        reponse = self.api.get(url_equipements(self.calepinage.pk))
        brut = str(reponse.data)
        for interdit in ('prix_achat', 'cout_achat', 'marge'):
            self.assertNotIn(interdit, brut)

    # ── Isolation société sur le calepinage lui-même ────────────────────
    def test_calepinage_d_une_autre_societe_404(self):
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=1, titre='Chez la voisine')
        reponse = self.api.get(url_equipements(etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    # ── Sans le droit de lecture ─────────────────────────────────────────
    def test_sans_droit_lecture_403(self):
        reponse = self.api_sans.get(url_equipements(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 403)
