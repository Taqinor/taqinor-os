"""L-PCMP (fondateur, 24/08/2026) — les TROIS silhouettes d'occupation,
calculées CÔTÉ SERVEUR, servies à la page publique de proposition.

Ce que ces tests PROUVENT — et pourquoi c'est la seule preuve qui compte ici :
les chiffres affichés au client sortent du MOTEUR, pas d'une constante. Chaque
assertion sur un nombre le compare à une PASSE DIRECTE du moteur
(``etude_horaire_pour_devis`` / ``dimensionnement.recommander_taille``) sur le
même devis — jamais à une valeur écrite à la main dans le test, qui ne prouve
rien d'autre que sa propre existence (règle « zéro chiffre inventé »).

Fixtures calquées sur ``test_t5_dimensionnement_devis`` (Casablanca, table de
référence PVGIS, aucun accès réseau)."""
import copy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.courbes_journalieres import (
    OCCUPATION_ABSENCE, OCCUPATION_PARTIELLE, OCCUPATION_PRESENCE)
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.profils_comparatifs import (
    OCCUPATIONS_COMPAREES, calculer_profils_comparatifs,
    rafraichir_profils_comparatifs_devis)

User = get_user_model()


class _PcmpBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, mode='residentiel', avec_lead=True,
               facture_hiver=1800, avec_catalogue=True):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = None
        if avec_lead:
            lead = Lead.objects.create(
                company=company, nom='Lead', prenom=slug,
                telephone='+212600000000', ville='Casablanca',
                facture_hiver=facture_hiver, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={})
        if avec_catalogue:
            produit = Produit.objects.create(
                company=company, nom='Panneau Canadien Solar 710W',
                prix_vente='1166.67', quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation='Panneau Canadien Solar 710W',
                quantite=Decimal('14'), prix_unitaire=Decimal('1166.67'),
                remise=Decimal('0'))
        return devis


class GateTests(_PcmpBase):
    def test_devis_non_residentiel_renvoie_none(self):
        devis = self._devis('pcmp-nonres', mode='industriel')
        self.assertIsNone(calculer_profils_comparatifs(devis))

    def test_sans_panneau_lisible_renvoie_none(self):
        """Pas de kWc ⇒ AUCUN bloc : on ne simule pas trois comportements sur
        une installation dont on ne connaît pas la puissance."""
        devis = self._devis('pcmp-sanskwc', avec_catalogue=False)
        self.assertIsNone(calculer_profils_comparatifs(devis))

    def test_sans_facture_renvoie_none(self):
        devis = self._devis('pcmp-sansfact', facture_hiver=None)
        self.assertIsNone(calculer_profils_comparatifs(devis))

    def test_ne_leve_jamais(self):
        devis = self._devis('pcmp-nolev')
        devis.company = None
        self.assertIsNone(calculer_profils_comparatifs(devis))


class TroisBlocsIssusDuMoteurTests(_PcmpBase):
    """LE test central : trois blocs, et chaque chiffre = une sortie moteur."""

    def test_les_trois_silhouettes_sont_servies_et_etiquetees(self):
        devis = self._devis('pcmp-trois')
        bloc = calculer_profils_comparatifs(devis)
        self.assertIsNotNone(bloc)
        self.assertEqual(
            [p['occupation'] for p in bloc['profils']],
            list(OCCUPATIONS_COMPAREES))
        self.assertEqual(
            set(OCCUPATIONS_COMPAREES),
            {OCCUPATION_PRESENCE, OCCUPATION_ABSENCE, OCCUPATION_PARTIELLE})
        # UN SEUL profil est « celui du client », et c'est bien celui que
        # ``occupation_du_devis`` résout — pas un défaut réinventé ici.
        reels = [p['occupation'] for p in bloc['profils']
                 if p['est_profil_reel']]
        self.assertEqual(reels, [bloc['profil_reel']])

    def test_chaque_economie_egale_une_passe_directe_du_moteur(self):
        """Aucune constante magique : la valeur servie pour CHAQUE silhouette
        est comparée au résultat d'un appel DIRECT au moteur horaire avec cette
        même silhouette."""
        from apps.ventes.etude_horaire import etude_horaire_pour_devis

        devis = self._devis('pcmp-moteur')
        bloc = calculer_profils_comparatifs(devis)
        self.assertIsNotNone(bloc)
        kwc = bloc['kwc_devis']
        self.assertGreater(kwc, 0)

        for entree in bloc['profils']:
            with self.subTest(occupation=entree['occupation']):
                direct = etude_horaire_pour_devis(
                    devis, kwc=kwc, occupation=entree['occupation'])
                self.assertIsNotNone(direct)
                annuel = direct['annuel']
                self.assertAlmostEqual(
                    entree['economie_sans_mad'],
                    annuel['economie_sans_mad'], places=6)
                self.assertAlmostEqual(
                    entree['taux_autoconso_sans'],
                    annuel['taux_autoconso_sans'], places=6)
                self.assertAlmostEqual(
                    entree['couverture_sans'],
                    annuel['couverture_sans'], places=6)

    def test_les_silhouettes_ne_donnent_pas_toutes_le_meme_chiffre(self):
        """Garde-fou anti-« trois fois la même colonne » : si le paramètre
        ``occupation`` n'était pas réellement transmis au moteur, les trois
        blocs seraient identiques et la fonctionnalité mentirait au client."""
        devis = self._devis('pcmp-distinct')
        bloc = calculer_profils_comparatifs(devis)
        economies = {p['occupation']: p['economie_sans_mad']
                     for p in bloc['profils']}
        self.assertEqual(len(set(economies.values())), len(economies))

    def test_optimal_egale_la_recommandation_du_balayage_pour_ce_profil(self):
        """L'« installation optimale » d'une silhouette est le palier retenu
        par le balayage EXISTANT lancé avec cette silhouette — comparé ici à
        une passe directe, jamais à un nombre écrit dans le test."""
        from apps.ventes.profils_comparatifs import _dimensionnement_variante

        devis = self._devis('pcmp-optimal')
        bloc = calculer_profils_comparatifs(devis)
        cible = OCCUPATION_ABSENCE
        entree = next(p for p in bloc['profils']
                      if p['occupation'] == cible)
        direct = _dimensionnement_variante(devis, cible)
        self.assertIsNotNone(direct)
        reco = direct.get('recommandation_avec' if bloc['avec_batterie']
                          else 'recommandation')
        if reco is None:
            # Catalogue trop pauvre pour recommander quoi que ce soit : le
            # moteur ne recommande RIEN et le bloc n'invente rien non plus.
            self.assertIsNone(entree['optimal'])
        else:
            self.assertIsNotNone(entree['optimal'])
            self.assertAlmostEqual(
                entree['optimal']['kwc'], round(reco['kwc'], 2), places=6)


class BlocPrincipalIntactTests(_PcmpBase):
    def test_le_reste_d_etude_params_est_byte_identique(self):
        """Le profil DÉCLARÉ reste le bloc principal : poser les variantes
        n'ajoute QUE ``profils_comparatifs`` — aucune autre clé d'
        ``etude_params`` ne bouge d'un octet."""
        devis = self._devis('pcmp-intact')
        from apps.ventes.services import (
            rafraichir_dimensionnement_devis, rafraichir_etude_horaire_devis)
        rafraichir_etude_horaire_devis(devis, force=True)
        rafraichir_dimensionnement_devis(devis, force=True)
        devis.refresh_from_db()
        avant = copy.deepcopy(devis.etude_params or {})

        rafraichir_profils_comparatifs_devis(devis, force=True)
        devis.refresh_from_db()
        apres = dict(devis.etude_params or {})
        self.assertIn('profils_comparatifs', apres)
        apres.pop('profils_comparatifs')
        self.assertEqual(apres, avant)

    def test_bloc_devenu_incalculable_est_retire(self):
        devis = self._devis('pcmp-retire')
        devis.etude_params = {'profils_comparatifs': {'sentinelle': True}}
        devis.save(update_fields=['etude_params'])
        devis.lead = None
        devis.save(update_fields=['lead'])
        self.assertIsNone(
            rafraichir_profils_comparatifs_devis(devis, force=True))
        devis.refresh_from_db()
        self.assertNotIn('profils_comparatifs', devis.etude_params or {})


class PayloadPublicTests(_PcmpBase):
    """La projection publique : client-safe par construction, additive."""

    def _bloc_publie(self, niveau=None, slug='pcmp-public'):
        # ``slug`` distinct par appel dans un MÊME test : la référence du devis
        # est dérivée du slug et (company, reference) est unique — deux appels
        # avec le même slug violeraient la contrainte.
        from apps.ventes.models import ShareLink
        from apps.ventes.public_views import _profils_comparatifs_publique
        devis = self._devis(slug)
        rafraichir_profils_comparatifs_devis(devis, force=True)
        devis.refresh_from_db()
        return _profils_comparatifs_publique(
            devis.etude_params,
            niveau or ShareLink.NIVEAU_CONFIANCE), devis

    def test_absent_quand_rien_n_est_calculable(self):
        from apps.ventes.public_views import _profils_comparatifs_publique
        self.assertIsNone(_profils_comparatifs_publique({}))
        self.assertIsNone(_profils_comparatifs_publique(None))
        self.assertIsNone(
            _profils_comparatifs_publique({'profils_comparatifs': {}}))

    def test_les_taux_sortent_en_pourcentage_du_meme_bloc_moteur(self):
        publie, devis = self._bloc_publie()
        self.assertIsNotNone(publie)
        interne = devis.etude_params['profils_comparatifs']
        for pub, brut in zip(publie['profils'], interne['profils']):
            self.assertEqual(pub['occupation'], brut['occupation'])
            self.assertEqual(pub['economie_sans_mad'],
                             round(brut['economie_sans_mad']))
            if brut['taux_autoconso_sans'] is not None:
                self.assertAlmostEqual(
                    pub['taux_autoconso_sans_pct'],
                    round(brut['taux_autoconso_sans'] * 100, 1), places=6)

    def test_aucune_cle_de_prix_d_achat_ni_de_ligne_ne_fuite(self):
        """Whitelist stricte : on énumère RÉCURSIVEMENT ce qui sort et on
        refuse tout ce qui ressemble à un prix d'achat, une marge ou une
        composition."""
        publie, _devis = self._bloc_publie()
        interdits = ('prix_achat', 'marge', 'cout_achat', 'lignes',
                     'lignes_sans', 'lignes_avec', 'balayage_stockage',
                     'tableau')

        def _scan(noeud):
            if isinstance(noeud, dict):
                for cle, valeur in noeud.items():
                    self.assertNotIn(cle, interdits, f'clé interdite : {cle}')
                    _scan(valeur)
            elif isinstance(noeud, list):
                for element in noeud:
                    _scan(element)

        _scan(publie)

    def test_le_payload_a_exactement_les_cles_du_contrat_partage(self):
        """PACT10 — le fichier ``contract_samples/profils_comparatifs.json``
        est LE contrat que les deux moitiés lisent. S'il diverge de ce que la
        vue sert réellement, c'est ce test qui passe au rouge — pas l'écran du
        client en production."""
        import json
        from pathlib import Path

        publie, _devis = self._bloc_publie()
        chemin = (Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'profils_comparatifs.json')
        # L'échantillon porte l'enveloppe PACT10 {endpoint, pourquoi, exemple}
        # exigée par check_api_shapes ; le payload vit sous exemple.
        contrat = json.loads(chemin.read_text(
            encoding='utf-8'))['exemple']['profils_comparatifs']
        attendues = {c for c in contrat if not c.startswith('_')}
        self.assertEqual(set(publie), attendues)
        self.assertEqual(set(publie['profils'][0]),
                         set(contrat['profils'][0]))
        # ``optimal`` est légitimement ``None`` quand le moteur ne recommande
        # rien (catalogue incomplet) — on n'épingle ses clés que lorsqu'il en
        # a, jamais en inventant un bloc vide.
        optimal = publie['profils'][0]['optimal']
        if optimal is not None:
            self.assertEqual(set(optimal),
                             set(contrat['profils'][0]['optimal']))

    def test_le_niveau_standard_neutralise_le_texte_pas_les_chiffres(self):
        from apps.ventes.models import ShareLink
        confiance, _d1 = self._bloc_publie(
            ShareLink.NIVEAU_CONFIANCE, slug='pcmp-conf')
        standard, _d2 = self._bloc_publie(
            ShareLink.NIVEAU_STANDARD, slug='pcmp-std')
        self.assertNotEqual(confiance['note'], standard['note'])
        self.assertNotIn('heure par heure', standard['note'])
        self.assertEqual(confiance['profils'], standard['profils'])
