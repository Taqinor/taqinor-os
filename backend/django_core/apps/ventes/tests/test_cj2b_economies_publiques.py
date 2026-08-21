"""CJ2b (fondateur, 21/08/2026) — « we cannot see the real calculated saving
neither the pvgis data ». La proposition en ligne sert désormais :

  1. ``courbes_journalieres.consommation[<saison>].forme`` — la silhouette
     d'occupation SERVEUR (voir ``test_courbes_journalieres.py`` pour cette
     moitié, pure et sans BD) ;
  2. ``economies_mensuelles`` — 12 valeurs MAD/mois sans/avec batterie, la
     même série que le graphe mensuel du PDF, jamais un second calcul.

Ce module épingle la moitié API du payload public (``economies_mensuelles``) :
présence des 8 clés du contrat quand la couche économique est servable,
absence quand elle ne l'est pas (Z2/aucun ancrage), ``avec``/``total_avec`` à
``None`` quand la batterie n'est pas RÉELLEMENT vendable sur ce devis (sans
qu'aucun chiffre « avec batterie » ne fuie ailleurs dans le payload — bug
class #69), et la mention « estimation » quand la source de consommation
n'est qu'un point réel répété (facture d'hiver).

Fixtures calquées sur ``test_pvcov_synthese_servie.py`` / ``test_etude_horaire.
PhysiqueDuMoteurTest`` : Casablanca est dans la table de référence PVGIS,
aucun accès réseau n'est nécessaire.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.services import rafraichir_etude_horaire_devis

User = get_user_model()

CLES_CONTRAT = ('sans', 'avec', 'total_sans', 'total_avec', 'devise',
                'modele', 'estimation', 'note')


def _tous_les_nombres(obj):
    """Parcourt récursivement un JSON déjà décodé et rend TOUS les nombres
    (feuilles), jamais des sous-chaînes de texte — bug class #69 : on scanne
    la valeur RENDUE, pas un grep sur du texte brut."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _tous_les_nombres(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _tous_les_nombres(v)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield obj


class _CJ2bBase(TestCase):
    """Fixture commune : société, utilisateur, client, lead avec facture
    d'hiver réelle (Casablanca, aucune donnée GPS — la chaîne PVGIS passe par
    la table de référence de la ville, aucun réseau)."""

    LIGNES_DEUX_ONDULEURS = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 10 kWh', '1', '25000.00'),
    )

    def _devis(self, slug, *, scenario=None, avec_batterie=True,
               avec_lead=True, prix_achat_panneau=None):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = None
        if avec_lead:
            lead = Lead.objects.create(
                company=company, nom='Lead', prenom=slug,
                telephone='+212600000000', ville='Casablanca',
                facture_hiver=1800, ete_differente=False)
        etude_params = {'scenario': scenario} if scenario else {}
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params=etude_params)
        lignes = list(self.LIGNES_DEUX_ONDULEURS)
        if not avec_batterie:
            lignes = lignes[:2]  # panneau + onduleur réseau seulement
        for nom, qte, pu in lignes:
            kwargs = dict(company=company, nom=nom, prix_vente=pu,
                          quantite_stock=50)
            if prix_achat_panneau and 'Panneau' in nom:
                # ``prix_achat`` n'est PAS nullable (défaut 0) : on ne le
                # passe QUE quand un montant à épingler est explicitement
                # demandé, sinon le défaut du modèle s'applique.
                kwargs['prix_achat'] = prix_achat_panneau
            produit = Produit.objects.create(**kwargs)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(company=company, devis=devis)
        return devis, link

    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user', defaults={'password': 'x', 'company': company})
        return company

    def _payload(self, link):
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()


class BlocServiQuandAncreTests(_CJ2bBase):
    """Le devis porte deux VRAIES options (déclarées via ``scenario``) et un
    ancrage réel (facture d'hiver du lead + bloc horaire rafraîchi) — le bloc
    ``economies_mensuelles`` doit porter ses huit clés."""

    def test_les_huit_cles_du_contrat_sont_servies(self):
        devis, link = self._devis(
            'cj2b-deux', scenario='Les deux (Sans + Avec)')
        rafraichir_etude_horaire_devis(devis)

        payload = self._payload(link)
        self.assertIn('economies_mensuelles', payload)
        em = payload['economies_mensuelles']
        for cle in CLES_CONTRAT:
            self.assertIn(cle, em, cle)

        self.assertEqual(len(em['sans']), 12)
        self.assertEqual(len(em['avec']), 12)
        self.assertIsInstance(em['total_sans'], (int, float))
        self.assertIsInstance(em['total_avec'], (int, float))
        self.assertEqual(em['devise'], 'MAD')
        self.assertIn(em['modele'], ('horaire', 'factures', 'estimation'))
        self.assertIsInstance(em['estimation'], bool)
        self.assertTrue(em['note'].strip())

    def test_sans_et_avec_sont_bien_les_series_du_moteur(self):
        """Aucun second calcul : ``sans``/``avec`` sont EXACTEMENT
        ``eco_s_monthly``/``eco_a_monthly`` du builder, arrondis."""
        devis, link = self._devis(
            'cj2b-miroir', scenario='Les deux (Sans + Avec)')
        rafraichir_etude_horaire_devis(devis)

        from apps.ventes.quote_engine.builder import build_quote_data
        brut = build_quote_data(devis, {'pdf_mode': 'full'})

        payload = self._payload(link)
        em = payload['economies_mensuelles']
        self.assertEqual(em['sans'], [round(v) for v in brut['eco_s_monthly']])
        self.assertEqual(em['avec'], [round(v) for v in brut['eco_a_monthly']])


class BlocAbsentSansAncrageTests(_CJ2bBase):
    """Z2 (ORDRE FONDATEUR, 20/08/2026) — sans AUCUNE donnée réelle d'ancrage
    (ni facture, ni conso saisie, ni bloc horaire), la clé ne doit JAMAIS
    apparaître — même vide, même à ``null`` : elle est ABSENTE."""

    def test_aucun_ancrage_reel_la_cle_est_absente(self):
        devis, link = self._devis(
            'cj2b-z2', scenario='Les deux (Sans + Avec)', avec_lead=False)
        # AUCUN lead, AUCUNE facture, AUCUN bloc horaire : rien à ancrer.
        payload = self._payload(link)
        self.assertNotIn('economies_mensuelles', payload)


class AvecBatterieNonVendableTests(_CJ2bBase):
    """Le devis porte une VRAIE batterie en lignes (la physique la voit) mais
    le document est déclaré MONO-option « Sans batterie » — CJ2a a trouvé un
    vrai trou catalogue où l'option batterie n'est pas livrable en résidentiel
    monophasé ; le payload ne doit JAMAIS afficher un chiffre « avec
    batterie » qu'aucun document remis au client ne montre."""

    def test_avec_et_total_avec_sont_null_et_aucun_chiffre_ne_fuit(self):
        devis, link = self._devis('cj2b-monosans', scenario='Sans batterie')
        rafraichir_etude_horaire_devis(devis)

        from apps.ventes.quote_engine.builder import build_quote_data
        brut = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertFalse(brut.get('avec_ok'))
        self.assertFalse(brut.get('deux_options'))

        eco_avec_interdit = {round(v) for v in (brut.get('eco_a_monthly') or [])}
        eco_sans_permis = {round(v) for v in (brut.get('eco_s_monthly') or [])}
        # Fixture valide seulement si les deux séries se distinguent VRAIMENT
        # (la batterie réelle en ligne doit changer la physique) — sinon
        # l'absence de la valeur ne prouverait rien.
        propres_a_avec = eco_avec_interdit - eco_sans_permis
        self.assertTrue(
            propres_a_avec,
            'fixture invalide : sans/avec identiques, le test ne prouverait '
            'rien (aucune valeur propre à la série avec-batterie)')

        payload = self._payload(link)
        em = payload.get('economies_mensuelles')
        self.assertIsNotNone(em)
        self.assertIsNone(em['avec'])
        self.assertIsNone(em['total_avec'])
        # PV86 (garde déjà en place ailleurs) — même vérité côté totaux.
        self.assertIsNone(payload['option_totals']['avec_batterie'])

        presentes = set(_tous_les_nombres(payload))
        fuite = propres_a_avec & presentes
        self.assertFalse(
            fuite,
            f'chiffre "avec batterie" interdit trouvé dans le payload '
            f'public : {fuite}')


class EstimationDeclareeTests(_CJ2bBase):
    """La source de consommation du bloc horaire n'est qu'un point réel
    (facture d'hiver) répété sur les douze mois : la variation mensuelle est
    ESTIMÉE, et la note doit le dire — jamais un chiffre inventé dans le
    texte."""

    def test_estimation_vraie_et_note_le_dit(self):
        devis, link = self._devis(
            'cj2b-estim', scenario='Les deux (Sans + Avec)')
        bloc = rafraichir_etude_horaire_devis(devis)
        self.assertIsNotNone(bloc, 'fixture invalide : bloc horaire absent')
        self.assertEqual(bloc.get('source_consommation'), 'facture_hiver')

        payload = self._payload(link)
        em = payload['economies_mensuelles']
        self.assertEqual(em['modele'], 'horaire')
        self.assertTrue(em['estimation'])
        self.assertIn('estimation', em['note'].lower())
        # Le texte ne contient JAMAIS un montant : uniquement de la
        # provenance (RULE #4 — pas de chiffre inventé dans une phrase).
        self.assertFalse(any(c.isdigit() for c in em['note']))


class AucuneCleConfidentielleTests(_CJ2bBase):
    """RULE #4 — jamais de prix d'achat/marge/nom de revendeur sur le lien
    public, même dans le nouveau bloc (mirroir de test_qx49_proposal_payload).
    """

    def test_aucune_cle_confidentielle_ne_fuit(self):
        devis, link = self._devis(
            'cj2b-conf', scenario='Les deux (Sans + Avec)',
            prix_achat_panneau='7777.00')
        rafraichir_etude_horaire_devis(devis)

        payload = self._payload(link)
        self.assertIn('economies_mensuelles', payload)
        blob = json.dumps(payload)
        for interdit in ('prix_achat', 'marge', 'revendeur', '7777'):
            self.assertNotIn(interdit, blob, interdit)
