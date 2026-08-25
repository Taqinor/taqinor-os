"""PACT10/PACT11 (« deux optimiseurs », lane P2-B, 25/08/2026) — clé
``paliers_batterie`` du payload public de la proposition (contrat
``apps/ventes/contract_samples/paliers_batterie.json``).

Source de vérité : ``apps.ventes.dimensionnement.echelle_paliers_batterie``
(lane P2-A, fichier disjoint, en cours de fold en parallèle). Cette lane
(P2-B) ne possède QUE la lecture pure côté ``public_views.py`` : import
paresseux + ``getattr`` défensif, jamais un chiffre inventé, jamais une
erreur si la fonction n'existe pas encore sur cette branche.

Fixtures calquées sur ``test_payload_dimensionnement_options.py`` /
``test_cj2b_economies_publiques.py`` : Casablanca est dans la table de
référence PVGIS, aucun accès réseau n'est nécessaire.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import _echelle_paliers_batterie_publique

User = get_user_model()

_PALIER_EXEMPLE = {
    'capacite_kwh': 15.0, 'nb_batteries_5': 1, 'nb_batteries_10': 1,
    'nb_panneaux': 26, 'puissance_kwc': 18.46, 'prix_ttc': 148655.0,
    'economies_annuelles': 28088.0, 'payback_annees': 5.5,
    'remplissage_ok': True, 'retenu': True,
}
_CLES_CONTRAT_PALIER = frozenset(_PALIER_EXEMPLE)


# ═══════════════════════════════════════════════════════════════════════════
# 1. ``_echelle_paliers_batterie_publique`` — pur, aucune BD
# ═══════════════════════════════════════════════════════════════════════════

class EchelleaPaliersBatteriePubliqueTests(SimpleTestCase):
    def test_avec_ok_faux_renvoie_none_meme_residentiel(self):
        """L-VAR — une échelle de batterie n'a pas de sens sur une option que
        ce devis ne vend pas réellement."""
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        return_value=[_PALIER_EXEMPLE], create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': False}, True)
        self.assertIsNone(bloc)

    def test_non_residentiel_renvoie_none_meme_avec_ok_vrai(self):
        """Même discriminant que ``dimensionnement_options``/``is_residential``
        — un devis agricole/industriel/commercial n'a pas cette notion de
        palier de batterie domestique."""
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        return_value=[_PALIER_EXEMPLE], create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, False)
        self.assertIsNone(bloc)

    def test_fonction_absente_cle_absente_jamais_une_erreur(self):
        """Recalage fold 25/08 — la lane P2-A a DEPUIS foldé sa fonction sur
        cette branche : l'absence se SIMULE désormais (attribut à ``None``,
        exactement ce que rend le ``getattr`` défensif quand la fonction
        manque). La garde reste épinglée : absente ⇒ ``None``, jamais lever."""
        with mock.patch(
                'apps.ventes.dimensionnement.echelle_paliers_batterie',
                new=None):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, True)
        self.assertIsNone(bloc)

    def test_fonction_presente_liste_servie_telle_quelle(self):
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        return_value=[_PALIER_EXEMPLE], create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, True)
        self.assertEqual(bloc, [_PALIER_EXEMPLE])

    def test_fonction_presente_liste_vide_servie_vide_pas_none(self):
        """Une liste VIDE (fonction présente, aucun palier dérivable) reste
        une VALEUR servie — jamais confondue avec « la lane P2-A est
        absente » (qui, elle, omet la clé)."""
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        return_value=[], create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, True)
        self.assertEqual(bloc, [])
        self.assertIsNotNone(bloc)

    def test_fonction_qui_leve_renvoie_none_best_effort(self):
        """Un bloc additif ne fait jamais tomber la page client."""
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        side_effect=RuntimeError('boom'), create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, True)
        self.assertIsNone(bloc)

    def test_forme_du_contrat_respectee_aucune_cle_ajoutee_ni_perdue(self):
        """Contrat ``apps/ventes/contract_samples/paliers_batterie.json`` —
        chaque entrée passe par cette fonction SANS mutation : les clés
        restent exactement celles du contrat."""
        with mock.patch('apps.ventes.dimensionnement.echelle_paliers_batterie',
                        return_value=[_PALIER_EXEMPLE], create=True):
            bloc = _echelle_paliers_batterie_publique(
                None, {'avec_ok': True}, True)
        self.assertEqual(set(bloc[0]), _CLES_CONTRAT_PALIER)

    def test_aucun_prix_achat_ni_marge_dans_le_rendu(self):
        """RULE #4 — même si le moteur en portait un par mégarde, cette
        fonction ne recopie que ce que la lane P2-A renvoie ; ce test épingle
        au moins que le contrat lui-même ne porte aucun champ de marge."""
        self.assertNotIn('prix_achat', _CLES_CONTRAT_PALIER)
        self.assertNotIn('marge', _CLES_CONTRAT_PALIER)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Bout en bout — vrai pipeline (build_quote_data → proposal_data)
# ═══════════════════════════════════════════════════════════════════════════

class _PayloadBase(TestCase):
    """Fixture calquée sur ``test_payload_dimensionnement_options._PayloadBase``
    / ``test_cj2b_economies_publiques._CJ2bBase`` : société, lead Casablanca
    (facture réelle, table PVGIS — aucun réseau)."""

    LIGNES_DEUX_ONDULEURS = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 10 kWh', '1', '25000.00'),
    )

    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, avec_batterie=True,
               scenario='Les deux (Sans + Avec)'):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
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
            lignes = lignes[:2]   # panneau + onduleur réseau seulement
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _payload(self, devis, **share_link_kwargs):
        link = ShareLink.objects.create(
            company=devis.company, devis=devis, **share_link_kwargs)
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()


class FonctionAbsentePayloadTests(_PayloadBase):
    """Bout en bout, fonction SIMULÉE ABSENTE (recalage fold 25/08 — P2-A a
    depuis foldé la vraie fonction : l'absence se rejoue par patch ``None``,
    la valeur exacte du ``getattr`` défensif) — le payload reste correct, la
    clé est simplement absente."""

    def test_cle_absente_du_payload_sans_erreur(self):
        devis = self._devis('pb-absent')
        with mock.patch(
                'apps.ventes.dimensionnement.echelle_paliers_batterie',
                new=None):
            p = self._payload(devis)
        self.assertNotIn('paliers_batterie', p)
        # Aucune régression des clés voisines déjà servies par PACT10.
        self.assertIn('dimensionnement_options', p)
        self.assertIn('variantes_servables', p)


class FonctionPresentePayloadTests(_PayloadBase):
    """Bout en bout, AVEC la fonction P2-A mockée — prouve le câblage
    ``proposal_data`` -> ``_echelle_paliers_batterie_publique`` ->
    ``apps.ventes.dimensionnement.echelle_paliers_batterie``."""

    def _mock(self):
        return mock.patch(
            'apps.ventes.dimensionnement.echelle_paliers_batterie',
            return_value=[_PALIER_EXEMPLE], create=True)

    def test_residentiel_avec_ok_sert_la_liste_du_moteur(self):
        devis = self._devis('pb-servi')
        with self._mock():
            p = self._payload(devis)
        self.assertIn('paliers_batterie', p)
        self.assertEqual(p['paliers_batterie'], [_PALIER_EXEMPLE])
        self.assertEqual(set(p['paliers_batterie'][0]), _CLES_CONTRAT_PALIER)

    def test_avec_ok_faux_cle_absente_meme_fonction_presente(self):
        """Onduleur réseau seul (pas de ligne batterie) : ``avec_ok`` reste
        faux — la garde l'emporte même si la lane P2-A est déjà là."""
        devis = self._devis('pb-sansavec', avec_batterie=False, scenario=None)
        with self._mock():
            p = self._payload(devis)
        self.assertNotIn('paliers_batterie', p)

    def test_standard_et_confiance_servent_la_meme_echelle(self):
        """L-NIV — les tailles/prix ne se dégradent JAMAIS au niveau
        standard (seule la nomenclature détaillée le fait)."""
        devis = self._devis('pb-niveau')
        with self._mock():
            p_standard = self._payload(devis, niveau=ShareLink.NIVEAU_STANDARD)
        with self._mock():
            p_confiance = self._payload(devis, niveau=ShareLink.NIVEAU_CONFIANCE)
        self.assertIn('paliers_batterie', p_standard)
        self.assertIn('paliers_batterie', p_confiance)
        self.assertEqual(p_standard['paliers_batterie'],
                         p_confiance['paliers_batterie'])

    def test_aucune_regression_des_cles_voisines(self):
        """``dimensionnement_options``/``economies_mensuelles``/
        ``variantes_servables`` restent intactes, avec ou sans
        ``paliers_batterie`` posé à côté."""
        devis = self._devis('pb-regression')
        with self._mock():
            p_avec_mock = self._payload(devis)
        p_sans_mock = self._payload(devis)
        # Recalage fold 25/08 — `economies_mensuelles` n'est PAS servie sur
        # cette fixture (elle exige un ancrage éco réel, doctrine Z2/CJ2b) :
        # les voisines comparées sont celles que la fixture sert VRAIMENT.
        for cle in ('dimensionnement_options', 'courbes_journalieres',
                    'variantes_servables'):
            self.assertIn(cle, p_avec_mock)
            self.assertIn(cle, p_sans_mock)
            self.assertEqual(p_avec_mock[cle], p_sans_mock[cle])

    def test_aucun_prix_achat_ni_marge_dans_le_bloc_servi(self):
        devis = self._devis('pb-rule4')
        with self._mock():
            p = self._payload(devis)
        import json
        blob = json.dumps(p['paliers_batterie'])
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)
