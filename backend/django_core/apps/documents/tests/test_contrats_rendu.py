"""Dossier contractuel — rendu des cinq contenus du contrat d'API et
références de loi des textes par défaut (sans base de données).

- ``html_de`` rend chaque contenu d'exemple (contract_samples/acte_contractuel
  .json), sans accolade restée ni prix d'achat ;
- les corrections d'impression de la revue 1 (docs/contrats/revue-1.md,
  lane R) que le HTML garantit : aucun double échappement (R9), réserves et
  part retenue (R1), CIN sous le nom (R5), insécables (R3), renvoi vers la
  signature (R11) ;
- palier « pdf » : pagination de référence en français ET en arabe (contrat
  ≤ 7 pages, procès-verbaux 2, clôture 3), référence en tête des pages 2 et
  suivantes (R7), dates longues seulement (R6), part retenue imprimée (R1),
  nom à apostrophe (R9), et PDF signé portant le nom du signataire ;
- toute référence de loi que PRODUISENT les fabriques de ``textes.py``
  (« article », « loi n° »), toutes options, figure dans
  docs/contrats/juridique.md § 2 (critère K9).

Run :
    powershell -File scripts/test-backend.ps1 \
        -Modules "apps.documents.tests.test_contrats_rendu"
"""
import copy
import itertools
import json
import re
import unittest
from pathlib import Path

import fitz
from django.test import tag

from apps.documents.contrats.rendu import html_de, pdf_de

ECHANTILLON = (Path(__file__).resolve().parents[1] / 'contract_samples'
               / 'acte_contractuel.json')


def juridique():
    """docs/contrats/juridique.md, cherché en remontant depuis ce fichier
    (.../backend/django_core/apps/documents/tests/ → racine du dépôt)."""
    for dossier in Path(__file__).resolve().parents:
        chemin = dossier / 'docs' / 'contrats' / 'juridique.md'
        if chemin.exists():
            return chemin
    raise AssertionError('docs/contrats/juridique.md introuvable')


# Pagination tenue sur les exemples, en français ET en arabe (revue 1) :
# (au moins, au plus) pages.
PAGES = {'contrat_installation': (1, 7), 'pv_livraison': (2, 2),
         'pv_reception': (2, 2), 'cloture_garanties': (3, 3)}
DATE_COURTE = re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b')
SIG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
       'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


def exemples():
    donnees = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
    return [(cle, v['contenu']) for cle, v in donnees.items()
            if (cle == 'exemple' or cle.startswith('exemple_'))
            and isinstance(v, dict) and isinstance(v.get('contenu'), dict)]


def texte_pdf(octets):
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return doc.page_count, '\n'.join(p.get_text() for p in doc)
    finally:
        doc.close()


# L'en-tête courant s'imprime dans la marge haute (17 mm = 48 pt).
HAUT_DE_PAGE_PT = 48


def pages_pdf(octets):
    """(texte de la page, texte de son en-tête courant) pour chaque page."""
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return [(p.get_text(), ' '.join(
            b[4] for b in p.get_text('blocks') if b[3] <= HAUT_DE_PAGE_PT))
            for p in doc]
    finally:
        doc.close()


def exemples_deux_langues():
    """(clé, langue, contenu) : chaque exemple en français puis en arabe (le
    contenu arabe que construit le test de la traduction)."""
    from apps.documents.tests.test_contrats_arabe import _arabiser
    for cle, contenu in exemples():
        yield cle, 'fr', contenu
        yield cle, 'ar', _arabiser(contenu)


def exemple(type_acte, variante=''):
    for _cle, contenu in exemples():
        if contenu['type'] == type_acte and (
                not variante or contenu.get('variante') == variante):
            return copy.deepcopy(contenu)
    raise AssertionError(f'exemple {type_acte} introuvable')


class RenduHtmlTests(unittest.TestCase):

    def test_cinq_exemples(self):
        liste = exemples()
        self.assertEqual(len(liste), 5)
        for cle, contenu in liste:
            with self.subTest(exemple=cle):
                html = html_de(contenu)
                self.assertIn(contenu['reference'], html)
                self.assertNotIn('{', re.sub(r'<style>.*?</style>', '', html,
                                             flags=re.S))
                self.assertNotIn('prix_achat', html)

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            html_de({'type': 'inconnu'})

    def test_logo_des_devis_dans_l_en_tete_sinon_le_nom(self):
        """Décision de Reda (24/11/2026) : le logo des actes est CELUI DES
        DEVIS, partout — la balise que le moteur de devis imprime dans une
        bande d'en-tête bleu nuit (variante sombre, rôle « onepage »), octet
        pour octet ; le fichier téléversé n'est jamais imprimé tel quel, et la
        pastille claire n'existe plus. Sans logo exploitable : le nom."""
        import base64

        from apps.ventes.quote_engine import logo as moteur
        brut = ('data:image/png;base64,'
                + base64.b64encode(moteur.CHEMIN_LOGO.read_bytes()).decode())
        for cle, contenu in exemples():
            with self.subTest(exemple=cle):
                contenu['societe']['logo_uri'] = brut
                html = html_de(contenu)
                attendu = moteur.img_html(
                    moteur.pour_role(moteur.societe_b64(brut, 'sombre'),
                                     'onepage'),
                    'onepage', alt=contenu['societe']['nom'])
                self.assertTrue(attendu)
                self.assertIn(f'<div class="marque">{attendu}</div>', html)
                # Le logo officiel téléversé = l'asset du devis, au même bloc.
                self.assertIn(moteur.taqinor_b64('sombre', 'lockup'), html)
                self.assertNotIn(brut, html)
                self.assertNotIn('class="puce"', html)
                self.assertNotIn('.puce', html)
                self.assertIn("font-family:'DM Sans'", html)
                for inexploitable in ('', 'data:image/svg+xml;base64,PHN2Zz4=',
                                      'data:image/png;base64,iVBORw0KGgo='):
                    contenu['societe']['logo_uri'] = inexploitable
                    html = html_de(contenu)
                    self.assertIn(
                        f'<div class="marque">{contenu["societe"]["nom"]}'
                        '</div>', html)
                    self.assertNotIn('<img', html.split('class="ref"')[0])
        # Même logo dans la traduction arabe (une seule brique d'en-tête).
        for cle, langue, contenu in exemples_deux_langues():
            with self.subTest(exemple=cle, langue=langue):
                contenu['societe']['logo_uri'] = brut
                html = html_de(contenu)
                self.assertIn(moteur.taqinor_b64('sombre', 'lockup'), html)
                self.assertNotIn(brut, html)

    def test_aucun_double_echappement(self):
        """R9 — un nom à apostrophe ne s'imprime jamais « &amp;#x27; »."""
        for cle, langue, contenu in exemples_deux_langues():
            contenu = copy.deepcopy(contenu)
            contenu['societe']['nom'] = contenu['societe']['nom_court'] = (
                "L'Atelier & Fils")
            with self.subTest(exemple=cle, langue=langue):
                html = html_de(contenu)
                self.assertNotIn('&amp;#', html)
                self.assertNotIn('&amp;amp;', html)

    def test_reception_reserves_et_part_retenue(self):
        """R1 — quatre lignes de réserves et la ligne de la part retenue."""
        html = html_de(exemple('pv_reception'))
        self.assertIn('<div class="lignes">' + '<i></i>' * 4 + '</div>', html)
        self.assertIn('class="part-retenue"', html)
        self.assertIn('class="a-remplir"', html)

    def test_cin_sous_le_nom_du_client(self):
        """R5 — la CIN du client particulier, ou la ligne à remplir."""
        contenu = exemple('pv_reception')
        contenu['client']['cin'] = 'BK123456'
        self.assertIn('<div class="ident">CIN\u00a0BK123456</div>',
                      html_de(contenu))
        contenu['client']['cin'] = ''
        self.assertIn('<div class="ident">CIN : ', html_de(contenu))

    @staticmethod
    def _societe(type_acte, **champs):
        contenu = exemple(type_acte)
        contenu['client'].update({
            'type': 'entreprise', 'nom_complet': 'K and L building',
            'cin': '', 'ice': '003456789000021',
            'representant': 'Khalid Lachraf, Gérant', **champs})
        return contenu

    def test_client_societe_ice_partout_personne_a_la_signature(self):
        """Fondateur, 24/11/2026 — pour un client société, « le Client » est
        la raison sociale, son ICE figure sur les actes, et la personne
        (gérant, responsable) n'est nommée qu'au cadre de signature."""
        ice = 'ICE 003456789000021'
        boite = ('<div class="qui">K and L building</div>'
                 f'<div class="ident">{ice}</div>'
                 '<div class="ident">Représentée par Khalid Lachraf, '
                 'Gérant</div>')
        for type_acte, nb_ice in (('contrat_installation', 2),
                                  ('pv_livraison', 1), ('pv_reception', 1)):
            with self.subTest(type_acte):
                html = html_de(self._societe(type_acte))
                self.assertIn(boite, html)
                # Parties du contrat + signature ; signature seule ailleurs.
                self.assertEqual(html.count(ice), nb_ice)
                self.assertEqual(html.count('Khalid Lachraf'), 1)
                self.assertNotIn('CIN : ', html)
        # Les parties du contrat : la société, jamais « représentée par ».
        parties = html_de(self._societe('contrat_installation')).split(
            'class="parties"')[1].split('<h2>')[0]
        self.assertIn('<div class="nom">K and L building</div>', parties)
        self.assertNotIn('Khalid', parties)

    def test_client_societe_sans_ice_ni_signataire_lignes_a_remplir(self):
        html = html_de(self._societe('pv_livraison', ice='', representant=''))
        self.assertIn('<div class="ident">ICE : ……', html)
        self.assertIn('<div class="ident">Représentée par : ……', html)

    def test_client_societe_au_contenu(self):
        """Le contenu d'un client société : sa raison sociale seule (jamais
        « prénom + raison sociale »), le signataire « nom, qualité », et le
        quitus du dernier acte qui le nomme avec son ICE."""
        from types import SimpleNamespace

        from apps.documents.contrats.contenu import (
            _bloc_client, _client_nomme)
        fiche = SimpleNamespace(
            type_client='entreprise', nom='K and L building', prenom='Khalid',
            contact_nom='Khalid Lachraf', contact_fonction='Gérant',
            ice='003456789000021', rc='', if_fiscal='', cin='', email='',
            telephone='', adresse='', adresse_siege='12, bd Exemple')
        bloc = _bloc_client(SimpleNamespace(client=fiche))
        self.assertEqual(bloc['nom_complet'], 'K and L building')
        self.assertEqual(bloc['representant'], 'Khalid Lachraf, Gérant')
        self.assertEqual(bloc['adresse'], '12, bd Exemple')
        self.assertEqual(_client_nomme(bloc),
                         'K and L building (ICE 003456789000021)')
        self.assertEqual(_client_nomme(dict(bloc, ice='')), 'K and L building')
        fiche.type_client, fiche.nom = 'particulier', 'Lachraf'
        particulier = _bloc_client(SimpleNamespace(client=fiche))
        self.assertEqual(particulier['nom_complet'], 'Khalid Lachraf')
        self.assertEqual(particulier['representant'], '')
        self.assertEqual(_client_nomme(particulier), 'Khalid Lachraf')

    def test_insecables_sans_nowrap_dans_les_phrases(self):
        """R3 — « n° 31-08 » et le RIB ne se coupent pas ; le RIB passe à la
        ligne ; aucun span nowrap dans une phrase (WeasyPrint recule alors la
        coupure au premier mot)."""
        from apps.documents.contrats.rendu import composants as c
        sortie = c.texte_libre(
            "Virement à l'ordre de X. RIB : 000 000 0000 00 — Banque.")
        self.assertIn('<br>RIB\u00a0:\u00a0000\u00a0000\u00a00000\u00a000',
                      sortie)
        self.assertIn('loi n°\u00a031-08', c.texte_libre('la loi n° 31-08'))
        self.assertIn('رقم\u00a031.08', c.texte_libre('القانون رقم 31.08'))
        self.assertNotIn('class="nb"', html_de(exemple('contrat_installation')))

    def test_signature_en_fin_sous_la_frise(self):
        """R11 — le renvoi vers la signature suit la frise du contrat."""
        html = html_de(exemple('contrat_installation'))
        self.assertLess(html.index('class="frise"'), html.index('class="renvoi"'))
        self.assertLess(html.index('class="renvoi"'),
                        html.index('class="parties"'))


@tag('pdf')
class RenduPdfTests(unittest.TestCase):
    """Rendu WeasyPrint réel (palier « pdf », hors gate rapide)."""

    def test_pagination_de_reference(self):
        """Contrat ≤ 7 pages, procès-verbaux 2, clôture 3 — français et arabe ;
        la référence en tête de chaque page à partir de la 2e (R7) ; aucune
        date courte jj/mm/aaaa (R6)."""
        for cle, langue, contenu in exemples_deux_langues():
            with self.subTest(exemple=cle, langue=langue):
                pages = pages_pdf(pdf_de(contenu))
                mini, maxi = PAGES[contenu['type']]
                self.assertGreaterEqual(len(pages), mini)
                self.assertLessEqual(len(pages), maxi)
                self.assertIn(contenu['reference'], pages[0][0])
                for numero, (_texte, tete) in enumerate(pages[1:], start=2):
                    self.assertIn(contenu['reference'], tete,
                                  f'référence absente en tête de la page '
                                  f'{numero}')
                self.assertIsNone(DATE_COURTE.search(
                    '\n'.join(texte for texte, _tete in pages)))

    def test_reception_part_retenue_imprimee(self):
        """R1 — la ligne de la part retenue est dans le PDF de la réception."""
        from apps.documents.contrats.rendu.libelles import libelle
        _pages, texte = texte_pdf(pdf_de(exemple('pv_reception')))
        debut = libelle('part_retenue').split('…')[0].strip()
        self.assertIn(debut, re.sub(r'\s+', ' ', texte))

    def test_livraison_nom_a_apostrophe(self):
        """R9 — un nom de société à apostrophe s'imprime tel quel dans la
        livraison ; le titre des articles est « Ce que nous convenons
        ensemble », sans entité HTML."""
        from apps.documents.contrats.rendu.libelles import libelle
        contenu = exemple('pv_livraison')
        contenu['societe']['nom'] = contenu['societe']['nom_court'] = (
            "L'Atelier Solaire")
        _pages, texte = texte_pdf(pdf_de(contenu))
        self.assertIn(libelle('ce_que_vous_convenez'), texte)
        self.assertIn("L'Atelier Solaire", texte.replace('’', "'"))
        self.assertNotIn('&#x27;', texte)
        self.assertNotIn('&amp;', texte)

    def test_brouillon_marque_chaque_page_meme_pagination(self):
        """C2 : chaque page d'un brouillon porte « PROJET — document non
        émis », sans page de plus ; un acte émis n'en porte aucune."""
        for cle, contenu in exemples():
            with self.subTest(exemple=cle):
                contenu = copy.deepcopy(contenu)
                contenu['brouillon'] = True
                pages = pages_pdf(pdf_de(contenu))
                mini, maxi = PAGES[contenu['type']]
                self.assertTrue(mini <= len(pages) <= maxi, len(pages))
                for numero, (texte, _tete) in enumerate(pages, start=1):
                    self.assertIn('PROJET', texte, f'page {numero}')
                contenu['brouillon'] = False
                _n, texte = texte_pdf(pdf_de(contenu))
                self.assertNotIn('PROJET', texte)

    def test_cloture_non_soldee_trois_pages(self):
        for langue in ('fr', 'ar'):
            with self.subTest(langue=langue):
                pages = pages_pdf(pdf_de(cloture_non_soldee(langue)))
                self.assertEqual(len(pages), 3)
                if langue == 'fr':
                    # S1 : le PDF lu ne dit aucun paiement (l'extraction
                    # du texte arabe d'un PDF n'est pas fiable : l'arabe est
                    # vérifié sur le HTML).
                    texte = re.sub(r'\s+', ' ', ' '.join(
                        t for t, _tete in pages))
                    for phrase in PAIEMENT_AFFIRME['fr']:
                        self.assertNotIn(phrase, texte)

    def test_pdf_signe_porte_le_nom(self):
        contenu = copy.deepcopy(exemples()[0][1])
        contenu['signatures']['client'] = {
            'image': SIG, 'nom': 'Youssef EL EXEMPLE',
            'signe_le': '2026-11-24', 'preuve': ' · empreinte 0123456789abcdef'}
        _pages, texte = texte_pdf(pdf_de(contenu))
        self.assertIn('Youssef EL EXEMPLE', texte)
        self.assertIn('24 novembre 2026', texte)


def cloture_non_soldee(langue='fr'):
    """La clôture d'une vente dont 110 400 DH restent dus (recette C2)."""
    from apps.documents.tests.test_contrats_arabe import _arabiser
    contenu = exemple('cloture_garanties')
    contenu['paiement'].update(total_regle='0.00', pourcentage_regle='0',
                               exigible_maintenant='110400.00',
                               reste_a_regler='110400.00')
    return _arabiser(contenu) if langue == 'ar' else contenu


class BrouillonEtClotureHtmlTests(unittest.TestCase):
    """C2 (recette sur écran réel) : le brouillon se voit, la clôture d'une
    vente non soldée n'atteste rien."""

    def test_filigrane_sur_tout_brouillon_jamais_sur_un_acte_emis(self):
        """Défaut attrapé : le brouillon du quitus se téléchargeait sans
        aucune marque de projet."""
        from apps.documents.contrats.rendu.libelles import libelle
        for cle, langue, contenu in exemples_deux_langues():
            with self.subTest(exemple=cle, langue=langue):
                contenu = copy.deepcopy(contenu)
                contenu['brouillon'] = True
                html = html_de(contenu)
                self.assertIn('class="filigrane-projet"', html)
                self.assertIn(libelle('filigrane_projet', langue), html)
                for valeur in (False, None):
                    contenu['brouillon'] = valeur
                    self.assertNotIn('class="filigrane-projet"',
                                     html_de(contenu))

    def test_cloture_non_soldee_n_atteste_rien(self):
        """Défaut attrapé : avec 110 400 DH dus, le brouillon imprimait
        « Payé intégralement 0,00 DH », le quitus et « propriété
        définitivement acquise »."""
        from apps.documents.contrats.rendu.libelles import libelle
        for langue in ('fr', 'ar'):
            with self.subTest(langue=langue):
                html = html_de(cloture_non_soldee(langue))
                self.assertIn(libelle('reste_a_regler_carte', langue), html)
                self.assertIn(libelle('quitus_en_attente', langue,
                                      montant='')[:20], html)
                self.assertNotIn(libelle('paye_integralement', langue), html)
                self.assertNotIn('définitivement acquise', html)
                self.assertNotIn('class="encadre ok quitus"', html)

    def test_cloture_non_soldee_aucune_phrase_de_paiement(self):
        """Défaut attrapé (recette finale, S1) : avec un reste dû, le
        chapeau du brouillon disait encore « Votre installation est payée…
        il prouve votre paiement », le titre « Attestation de paiement
        intégral » et la société signait sous le quitus en attente. Payée,
        la clôture est inchangée."""
        from apps.documents.contrats.rendu import composants as c
        from apps.documents.contrats.rendu.libelles import libelle
        for langue in ('fr', 'ar'):
            with self.subTest(langue=langue):
                texte = texte_html(html_de(cloture_non_soldee(langue)))
                for phrase in PAIEMENT_AFFIRME[langue]:
                    self.assertNotIn(phrase, texte)
                reste = c.montant('110400.00', langue=langue)
                self.assertIn(texte_html(libelle(
                    'chapeau_cloture_du', langue, reste=reste)), texte)
                self.assertIn(libelle('attestation_du', langue), texte)
                self.assertNotIn('class="signatures"', html_de(
                    cloture_non_soldee(langue)))
        payee = exemple('cloture_garanties')
        html = html_de(payee)
        self.assertIn(libelle('chapeau_cloture'), html)
        self.assertIn(libelle('attestation'), html)
        self.assertIn('class="signatures"', html)
        self.assertIn('class="encadre ok quitus"', html)


#: Ce qu'une clôture non soldée ne dit jamais (S1), français et arabe.
PAIEMENT_AFFIRME = {
    'fr': ('payée', 'Payé intégralement', 'prouve votre paiement',
           'plus rien à régler', 'acquise', 'paiement intégral'),
    'ar': ('مؤدّاة ومضمونة', 'تثبت أداءكم', 'لا شيء يُؤدّى بعد الآن',
           'بصفة نهائية', 'شهادة الأداء الكامل', 'مؤدّى بالكامل'),
}


def texte_html(html):
    """Le texte lu d'une page : sans feuille de style ni balises, espaces
    (insécables comprises) ramenées à une seule."""
    html = re.sub(r'<style>.*?</style>|<title>.*?</title>', '', html,
                  flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).replace(
        ' ', ' ')


class ReferencesDeLoiTests(unittest.TestCase):
    """K9 — chaque référence de loi des textes français est dans
    juridique.md § 2 (lue au niveau P)."""

    def _section_2(self):
        texte = juridique().read_text(encoding="utf-8")
        debut = texte.index('## 2.')
        fin = texte.index('## 3.', debut)
        return texte[debut:fin]

    @staticmethod
    def _textes_produits():
        """Tout le texte que les fabriques de ``textes.py`` PRODUISENT, toutes
        options allumées et éteintes (le code est exécuté, jamais lu)."""
        from apps.documents.contrats import textes
        morceaux = []
        for booleens in itertools.product((True, False), repeat=2):
            options = dict(zip(('consommateur', 'reserve_propriete'),
                               booleens),
                           penalite_retard_pct=5)
            for type_acte, variante in (
                    ('contrat_installation', ''),
                    ('pv_livraison', 'reste_a_regler'),
                    ('pv_livraison', 'tranche_reglee'),
                    ('pv_reception', ''), ('cloture_garanties', '')):
                for art in textes.articles_par_defaut(type_acte, variante, {},
                                                      options):
                    morceaux += [art['titre']] + art['paragraphes']
        morceaux += textes.quitus_par_defaut({})
        morceaux += textes.entretien_par_defaut()
        return '\n'.join(morceaux)

    def test_references_de_textes_dans_juridique(self):
        source = self._textes_produits()
        section = self._section_2()
        lois = set(re.findall(r'loi\s+n°\s*(\d{2}-\d{2})', source))
        self.assertTrue(lois)
        for loi in lois:
            with self.subTest(loi=loi):
                self.assertIn(loi, section)
        articles = re.findall(
            r'articles?\s+(\d+(?:-\d+)?)(?:\s+(?:à|et)\s+(\d+(?:-\d+)?))?',
            source)
        self.assertTrue(articles)
        for premier, second in articles:
            for numero in filter(None, (premier, second)):
                with self.subTest(article=numero):
                    self.assertRegex(section, rf'(?<![\d.]){re.escape(numero)}'
                                              rf'(?!\d)')


class ProfilLecturePureTests(unittest.TestCase):
    """Profil société — le bloc société d'un acte lit le profil par
    ``CompanyProfile.lire`` (jamais ``get``, qui crée la ligne : le dossier
    de contrats préparé à la création du chantier, donc à l'acceptation,
    écrivait un profil au fuseau par défaut qui périmait les simulations de
    calepinage). Sans base."""

    def test_lit_par_lire_jamais_par_get(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.documents.contrats.contenu import Lecture
        from apps.parametres.models import CompanyProfile
        company = SimpleNamespace(pk=7, id=7, nom='Sans Profil')
        defaut = CompanyProfile(nom='Sans Profil')
        lecture = Lecture(SimpleNamespace(company=company))
        with mock.patch.object(CompanyProfile, 'get',
                               side_effect=AssertionError('get')) as get, \
                mock.patch.object(CompanyProfile, 'lire',
                                  return_value=defaut) as lu:
            self.assertIs(lecture.profil(), defaut)
        get.assert_not_called()
        lu.assert_called_once_with(company=company)

    def test_logo_du_bloc_societe_lit_par_lire(self):
        """Revue — ``_bloc_societe`` lit aussi ``logo_uri()`` →
        ``utils/pdf._company_context`` : même règle, jamais ``get``."""
        from types import SimpleNamespace
        from unittest import mock

        from apps.documents.contrats.contenu import Lecture
        from apps.parametres.models import CompanyProfile
        company = SimpleNamespace(pk=7, id=7, nom='Sans Profil')
        defaut = CompanyProfile(nom='Sans Profil')
        lecture = Lecture(SimpleNamespace(company=company))
        with mock.patch.object(CompanyProfile, 'get',
                               side_effect=AssertionError('get')) as get, \
                mock.patch.object(CompanyProfile, 'lire',
                                  return_value=defaut) as lu:
            self.assertEqual(lecture.logo_uri(), '')
        get.assert_not_called()
        lu.assert_called_once_with(company=company)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
