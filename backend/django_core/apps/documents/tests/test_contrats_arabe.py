"""Dossier contractuel — la traduction ARABE des quatre actes (loi n° 31-08,
art. 206).

Vérifie, sans base de données (``unittest.TestCase``) :
  - ``textes_ar`` est le jumeau exact de ``textes`` : mêmes ``cle``
    d'article, même nombre de paragraphes, de puces et de ``**gras**`` pour
    chaque acte, variante et combinaison d'options ; mêmes repères ``{…}``
    (sauf les deux montants en lettres, non imprimés en arabe) ; aucune
    accolade ni « à préciser » quand le ``ctx`` est complet ;
  - ``html_de`` d'un contenu arabe est en ``dir="rtl"`` et n'imprime aucun
    libellé français de ``rendu/libelles.py`` ; sans ``langue``, il reste
    français ;
  - le PDF arabe de chaque exemple fait au plus une page de plus que le
    français, contient de l'arabe, la référence et le montant inchangés.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_contrats_arabe -v 2
(ou ``python -m unittest apps.documents.tests.test_contrats_arabe`` : aucun
réglage Django requis).
"""
import copy
import itertools
import json
import re
import string
import unittest
from pathlib import Path

from django.test import tag

from apps.documents.contrats import textes, textes_ar
from apps.documents.contrats.rendu import composants
from apps.documents.contrats.rendu.documents import html_de
from apps.documents.contrats.rendu.libelles import LIBELLES, libelle

ECHANTILLON = (Path(__file__).resolve().parents[1] / 'contract_samples'
               / 'acte_contractuel.json')
EXEMPLES = ('exemple', 'exemple_pv_livraison_reste_a_regler',
            'exemple_pv_livraison_tranche_reglee', 'exemple_pv_reception',
            'exemple_cloture_garanties')
EN_LETTRES = {'total_lettres', 'exigible_lettres'}
ARABE = re.compile('[؀-ۿ]')
CAS = (('contrat_installation', ''), ('pv_livraison', 'reste_a_regler'),
       ('pv_livraison', 'tranche_reglee'), ('pv_reception', ''),
       ('cloture_garanties', ''))


def _toutes_options():
    """Toutes les combinaisons des options qui changent la liste française."""
    for conso, reserve, reseau, penalite in itertools.product(
            (True, False), (True, False), (True, False), (None, 10)):
        yield {'consommateur': conso, 'reserve_propriete': reserve,
               'raccorde_reseau': reseau, 'penalite_retard_pct': penalite}


def _reperes(module, fonction, args):
    """Les repères ``{…}`` qu'une fabrique de textes utilise : chaque repère
    connu reçoit un marqueur, on relève les marqueurs imprimés. ``args(ctx)``
    rend les arguments de la fabrique."""
    cles = set(textes_ar.FORMES_CTX) | EN_LETTRES
    ctx = {k: f'§{k}§' for k in cles}
    sortie = json.dumps(getattr(module, fonction)(*args(ctx)),
                        ensure_ascii=False)
    return set(re.findall('§([a-z_]+)§', sortie)), sortie


def _structure(articles):
    return [(a['cle'], len(a['paragraphes']),
             [p.count('\n- ') + p.startswith('- ') for p in a['paragraphes']],
             [p.count('**') for p in a['paragraphes']]) for a in articles]


class JumeauDesTextesTests(unittest.TestCase):

    def test_memes_articles_pour_chaque_acte_et_option(self):
        for (type_acte, variante), options in itertools.product(
                CAS, list(_toutes_options())):
            with self.subTest(type=type_acte, variante=variante, **options):
                fr = textes.articles_par_defaut(type_acte, variante, {},
                                                options)
                ar = textes_ar.articles_par_defaut(type_acte, variante, {},
                                                   options)
                self.assertEqual([a['cle'] for a in ar],
                                 [a['cle'] for a in fr])
                self.assertEqual(_structure(ar), _structure(fr))
                if type_acte in ('contrat_installation', 'pv_livraison'):
                    # T8 bis : la garde a son article, avec ou sans
                    # réserve de propriété.
                    self.assertIn('garde', [a['cle'] for a in fr])

    def test_memes_reperes_que_le_francais(self):
        for (type_acte, variante), options in itertools.product(
                CAS, list(_toutes_options())):
            with self.subTest(type=type_acte, variante=variante, **options):
                def args(ctx):
                    return (type_acte, variante, ctx, options)
                rep_fr, sortie_fr = _reperes(textes, 'articles_par_defaut',
                                             args)
                rep_ar, sortie_ar = _reperes(textes_ar, 'articles_par_defaut',
                                             args)
                self.assertEqual(rep_ar - rep_fr, set(), 'repère inventé')
                self.assertLessEqual(rep_fr - rep_ar, EN_LETTRES,
                                     'repère perdu')
                # Aucun repère hors du ctx connu (il s'imprimerait « à
                # préciser »).
                self.assertNotIn(textes.A_PRECISER, sortie_fr)
                self.assertNotIn(textes_ar.A_PRECISER, sortie_ar)
        rep_fr, _ = _reperes(textes, 'quitus_par_defaut', lambda c: (c,))
        rep_ar, _ = _reperes(textes_ar, 'quitus_par_defaut', lambda c: (c,))
        self.assertEqual(rep_ar, rep_fr - EN_LETTRES)

    def test_aucune_accolade_avec_un_ctx_complet(self):
        ctx = textes_ar.FORMES_CTX
        for (type_acte, variante), options in itertools.product(
                CAS, list(_toutes_options())):
            arts = textes_ar.articles_par_defaut(type_acte, variante, ctx,
                                                 options)
            for texte in itertools.chain.from_iterable(
                    [a['titre']] + a['paragraphes'] for a in arts):
                self.assertNotRegex(texte, '[{}]')
                self.assertNotIn(textes_ar.A_PRECISER, texte)
                self.assertNotIn('()', texte)
        for texte in textes_ar.quitus_par_defaut(ctx):
            self.assertNotRegex(texte, '[{}]')
            self.assertNotIn('()', texte)

    def test_autres_fabriques_jumelles(self):
        for type_acte in ('pv_livraison', 'pv_reception', 'autre'):
            fr = textes.constats_par_defaut(type_acte)
            ar = textes_ar.constats_par_defaut(type_acte)
            self.assertEqual([(c['cochee'], c['texte'].count('**'))
                              for c in ar],
                             [(c['cochee'], c['texte'].count('**'))
                              for c in fr])
        for batterie in (True, False):
            fr, ar = (textes.journee_solaire(batterie),
                      textes_ar.journee_solaire(batterie))
            self.assertEqual([(p['sorte'], p['part']) for p in ar['plages']],
                             [(p['sorte'], p['part']) for p in fr['plages']])
            fr = textes.conseils_par_defaut(batterie)[1]
            intro_ar, ar = textes_ar.conseils_par_defaut(batterie)
            self.assertTrue(ARABE.search(intro_ar))
            self.assertEqual(len(ar), len(fr))
            self.assertEqual([sorted(k) for k in ar], [sorted(k) for k in fr])
        self.assertEqual(
            [p.count('\n- ') for p in textes_ar.entretien_par_defaut()],
            [p.count('\n- ') for p in textes.entretien_par_defaut()])

    def test_consommateur_ou_entreprise_dans_les_deux_langues(self):
        """Revue 1, T13 et T14 : le tribunal du certificat de garantie et la
        clause « traduction arabe » suivent ``consommateur``, en français
        comme en arabe."""
        ctx_ar = textes_ar.FORMES_CTX
        ctx_fr = dict(ctx_ar, societe='TAQINOR')
        siege = {'fr': 'tribunal compétent du siège de TAQINOR',
                 'ar': 'مقر Société Exemple'}
        domicile = {'fr': 'tribunal de votre domicile', 'ar': 'محكمة موطنكم'}
        traduction = {'fr': 'traduction en arabe', 'ar': 'بترجمته إلى اللغة'}
        for langue, module, ctx in (('fr', textes, ctx_fr),
                                    ('ar', textes_ar, ctx_ar)):
            for conso in (True, False):
                with self.subTest(langue=langue, consommateur=conso):
                    options = {'consommateur': conso}
                    cloture = {a['cle']: a for a in module.articles_par_defaut(
                        'cloture_garanties', '', ctx, options)}
                    tribunal = cloture['garantie_legale']['paragraphes'][1]
                    self.assertEqual(domicile[langue] in tribunal, conso)
                    self.assertEqual(siege[langue] in tribunal, not conso)
                    contrat = {a['cle']: a for a in module.articles_par_defaut(
                        'contrat_installation', '', ctx, options)}
                    finales = contrat['dispositions_finales']['paragraphes']
                    self.assertEqual(len(finales), 2 if conso else 1)
                    self.assertEqual(
                        any(traduction[langue] in p for p in finales), conso)

    def test_a_preciser_identique_au_rendu(self):
        self.assertEqual(textes_ar.A_PRECISER, composants.A_PRECISER['ar'])


def _arabiser(contenu):
    """Le contenu arabe d'un exemple : mêmes clés, textes arabes (ce que la
    lane du contenu sert avec ``?langue=ar``)."""
    ar = copy.deepcopy(contenu)
    ar['langue'] = 'ar'
    # Le vrai nom de la société et du client, comme le serveur les pose
    # (jamais les exemples de ``FORMES_CTX``, dont « Société » est aussi un
    # libellé français).
    ctx = dict(textes_ar.FORMES_CTX,
               societe=ar['societe'].get('nom_court') or ar['societe']['nom'],
               client=ar['client'].get('nom_complet') or '')
    options = ar.get('options') or {}
    ar['articles'] = textes_ar.articles_par_defaut(
        ar['type'], ar.get('variante', ''), ctx, options)
    if 'constats' in ar:
        ar['constats'] = [dict(c, cochee=ancien.get('cochee', False))
                          for c, ancien in zip(
                              textes_ar.constats_par_defaut(ar['type']),
                              ar['constats'])]
    if 'quitus' in ar:
        batterie = (ar.get('systeme') or {}).get('avec_batterie')
        ar['quitus'] = textes_ar.quitus_par_defaut(ctx)
        ar['conseils_intro'], ar['conseils'] = (
            textes_ar.conseils_par_defaut(batterie))
        ar['journee'] = textes_ar.journee_solaire(batterie)
        ar['entretien'] = textes_ar.entretien_par_defaut()
    ar['societe']['capital_social'] = '100 000 درهم'
    ar['systeme']['resume'] = '10 ألواح 590 Wc · عاكس هجين 6 kW'
    ar['prix']['total_en_lettres'] = ''
    mots = {'acompte': ('تسبيق', 'عند التوقيع'),
            'materiel': ('تسليم المعدات', 'عند التسليم'),
            'solde': ('باقي الثمن', 'عند تسلُّم الأشغال')}
    for tranche in ar.get('echeancier') or []:
        tranche['libelle'], tranche['exigibilite'] = mots[tranche['cle']]
    for garantie in ar.get('garanties') or []:
        garantie.update(designation='الألواح', garant='ضمان الصانع',
                        detail='عيوب الصنع.')
    if ar.get('delais'):
        ar['delais'].update(resume='في أجل أقصاه 23 يناير 2027',
                            detail='يشمل التسليم والتركيب والتشغيل.')
    paiement = ar.get('paiement') or {}
    paiement.pop('exigible_en_lettres', None)
    for cle in ('modalites', 'engagement'):
        if paiement.get(cle):
            paiement[cle] = 'يتم الأداء بتحويل بنكي لأمر TAQINOR.'
    if ar.get('livraison'):
        ar['livraison'].update(suite='التركيب يوم 18 دجنبر',
                               suite_detail='3 أيام عمل.')
    if (ar.get('reception') or {}).get('delai_levee_reserves'):
        ar['reception']['delai_levee_reserves'] = '15 يومًا'
    if ar.get('conditions_particulieres'):
        ar['conditions_particulieres'] = 'يوفّر الزبون الولوج إلى السطح.'
    for p in ar.get('paiements') or []:
        p.update(libelle='دفعة', mode='تحويل بنكي')
    if ar.get('sav'):
        ar['sav']['horaires'] = 'من الإثنين إلى السبت.'
    return ar


def _exemples():
    donnees = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
    return [donnees[cle]['contenu'] for cle in EXEMPLES]


def _corps_texte(html):
    corps = html.split('<body', 1)[1]
    return re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', corps))


def _fragments_francais():
    """Les morceaux fixes (hors repères ``{…}``) de chaque libellé français
    qui diffère de sa traduction."""
    for cle, francais in LIBELLES['fr'].items():
        if LIBELLES['ar'].get(cle) == francais:
            continue
        sans_balises = re.sub('<[^>]+>|\\*\\*', '', francais)
        for morceau in re.split(r'\{[a-z_]+\}', sans_balises):
            morceau = morceau.strip(string.punctuation + ' «»·—…')
            if sum(ch.isalpha() for ch in morceau) >= 4:
                yield cle, morceau


class RenduArabeTests(unittest.TestCase):

    def test_toutes_les_cles_sont_traduites(self):
        self.assertEqual(set(LIBELLES['ar']), set(LIBELLES['fr']))
        self.assertEqual(libelle('article', 'ar', n=3), 'البند 3')
        self.assertEqual(libelle('article', 'xx', n=3), 'Article 3')

    def test_sans_langue_le_rendu_reste_francais(self):
        contenu = _exemples()[0]
        contenu.pop('langue', None)
        html = html_de(contenu)
        self.assertIn('<html lang="fr">', html)
        self.assertNotIn('dir="rtl"', html)
        self.assertNotIn('class="ltr"', html)

    def test_html_arabe_en_rtl_sans_libelle_francais(self):
        fragments = list(_fragments_francais())
        self.assertTrue(fragments)
        variantes = [_arabiser(c) for c in _exemples()]
        # Les deux cases de réception et l'encadré « payé » aussi.
        reception = copy.deepcopy(variantes[3])
        reception['reception']['prononcee'] = True
        reception['reserves'] = ['جزء من الحاجز ناقص.']
        reception['paiement']['exigible_maintenant'] = '0.00'
        variantes.append(reception)
        signe = copy.deepcopy(variantes[0])
        signe['signatures']['client'] = {
            'image': '', 'nom': 'M. Youssef EL EXEMPLE',
            'signe_le': '2026-11-25', 'preuve': ''}
        signe['systeme']['puissance_kwc'] = ''
        variantes.append(signe)
        for contenu in variantes:
            with self.subTest(type=contenu['type'],
                              variante=contenu.get('variante')):
                html = html_de(contenu)
                self.assertIn('<html lang="ar" dir="rtl">', html)
                texte = _corps_texte(html)
                self.assertRegex(texte, ARABE)
                for cle, morceau in fragments:
                    self.assertNotIn(morceau, texte,
                                     f'libellé français {cle!r} imprimé')

    def test_fragments_latins_isoles_sans_deplacer_l_arabe(self):
        html = composants.isoler_latin(
            '<head><title>x</title></head><body><p>المبلغ 98 500,00'
            ' درهم (الفصول 618-21) &amp; +212 6 00 00 00 00</p></body>')
        self.assertIn('<span class="ltr">98 500,00</span> درهم',
                      html)
        self.assertIn('(الفصول <span class="ltr">618-21</span>)', html)
        self.assertIn('<span class="ltr">+212 6 00 00 00 00</span>', html)
        self.assertIn('&amp;', html)
        self.assertIn('<title>x</title>', html)


@tag('pdf')
class PdfArabeTests(unittest.TestCase):
    """Rendu WeasyPrint réel (lourd : palier « pdf », hors gate rapide)."""

    def test_pdf_arabe_rendu_et_lisible(self):
        import pymupdf
        from weasyprint import HTML

        montants = ('total_ttc', 'exigible_maintenant', 'total_regle',
                    'exigible_maintenant', 'total_regle')
        for contenu, cle_montant in zip(_exemples(), montants):
            arabe = _arabiser(contenu)
            with self.subTest(type=contenu['type'],
                              variante=contenu.get('variante')):
                pages_fr = len(HTML(string=html_de(contenu)).render().pages)
                pdf = HTML(string=html_de(arabe)).write_pdf()
                doc = pymupdf.open(stream=pdf, filetype='pdf')
                self.assertLessEqual(doc.page_count, pages_fr + 1)
                texte = ''.join(page.get_text() for page in doc)
                self.assertRegex(texte, ARABE)
                self.assertIn(contenu['reference'], texte)
                source = (contenu.get('prix') if cle_montant == 'total_ttc'
                          else contenu.get('paiement'))
                chiffres = composants.nombre(source[cle_montant], 2)
                compact = re.sub('[\\s  ]', '', texte)
                self.assertIn(re.sub(' ', '', chiffres), compact)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
