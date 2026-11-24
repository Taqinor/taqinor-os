"""Les quatre actes : un ``contenu`` → une page HTML complète.

L'ordre suit ce qui se lit le mieux (docs/contrats/conception.md) : l'essentiel
d'abord (quoi, combien, quand), le détail ensuite, les clauses de risque à la
fin, la signature en dernier.

``contenu['langue'] == 'ar'`` rend la traduction arabe : mêmes briques, mots
lus dans ``libelles``, page de droite à gauche (``<html dir="rtl">`` et la
feuille arabe de ``style``), fragments latins isolés. Sans ``langue`` (ou
``'fr'``), le rendu est le français historique, inchangé.
"""
from . import composants as c
from . import style
from .libelles import libelle

TYPES = tuple(t for t, _, _ in c.PARCOURS)


def _page(contenu, corps, *, paraphes=True, classe=''):
    langue = c.langue_de(contenu)
    titre_doc = c.esc(contenu.get('titre') or libelle('acte', langue))
    racine = ('<html lang="ar" dir="rtl">' if langue == 'ar'
              else '<html lang="fr">')
    page = (
        f'<!DOCTYPE html>{racine}<head><meta charset="utf-8">'
        f'<title>{titre_doc} — {c.esc(contenu.get("reference"))}</title>'
        f'<style>{style.css(langue)}</style></head><body class="{classe}">'
        f'{c.pied(contenu, paraphes=paraphes)}'
        f'{c.bandeau(contenu)}{c.parcours(contenu["type"], langue)}'
        f'<div class="corps">{corps}</div></body></html>')
    return c.isoler_latin(page) if langue == 'ar' else page


def _resume_systeme(systeme, langue='fr'):
    kwc = systeme.get('puissance_kwc')
    valeur = (f'{c.nombre(kwc, 2).rstrip("0").rstrip(",")}{c.INSECABLE}'
              f'{libelle("kwc", langue)}'
              if kwc else libelle('installation_solaire', langue))
    return valeur, c.esc(systeme.get('resume') or '')


def _garantie_la_plus_longue(garanties, langue='fr'):
    mois = max([int(g.get('duree_mois') or 0) for g in garanties or []] or [0])
    return c.duree_mois(mois, langue)


def _conditions_particulieres(contenu):
    langue = c.langue_de(contenu)
    texte = (contenu.get('conditions_particulieres') or '').strip()
    if not texte:
        return ''
    return (c.h2(libelle('conditions_particulieres', langue),
                 libelle('conditions_particulieres_intro', langue))
            + c.encadre(libelle('convenu_entre_nous', langue),
                        c.paragraphes([texte]), 'net'))


def _titre_paiement(nombre_tranches, langue):
    if langue == 'ar':
        return libelle('paiement_en_n', langue,
                       n=c.nombre_de_dfaat(nombre_tranches))
    cle = 'paiement_en_n' if nombre_tranches > 1 else 'paiement_en_1'
    return libelle(cle, langue, n=nombre_tranches)


# ── Acte 1 — Contrat d'installation ─────────────────────────────────────────

def contrat_installation(contenu):
    langue = c.langue_de(contenu)
    societe = contenu.get('societe') or {}
    systeme = contenu.get('systeme') or {}
    prix = contenu.get('prix') or {}
    delais = contenu.get('delais') or {}
    garanties = contenu.get('garanties') or []
    echeancier = contenu.get('echeancier') or []
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))
    valeur_sys, detail_sys = _resume_systeme(systeme, langue)

    detail_prix = libelle('ttc_long', langue)
    if prix.get('total_ht') and prix.get('tva'):
        detail_prix = libelle(
            'ttc_detail', langue,
            ht=c.esc(c.montant(prix['total_ht'], langue=langue)),
            tva=c.esc(c.montant(prix['tva'], langue=langue)))
    plus_longue = _garantie_la_plus_longue(garanties, langue)
    apercu_garanties = ' · '.join(
        f'{c.esc(g.get("designation"))} <b>'
        f'{c.esc(g.get("duree_libelle") or c.duree_mois(g.get("duree_mois"), langue))}'
        f'</b>' for g in garanties[:5])

    corps = c.titre(
        'contrat_installation', contenu.get('titre') or
        libelle('h1_contrat', langue),
        libelle('chapeau_contrat', langue, nom=nom),
        contenu.get('reference'), langue)
    corps += c.h2(libelle('lessentiel', langue))
    corps += c.cartes(
        c.carte(libelle('votre_installation', langue), valeur_sys, detail_sys),
        c.carte(libelle('prix_convenu', langue),
                c.esc(c.montant(prix.get('total_ttc'), langue=langue)),
                detail_prix, forte=True),
        c.carte(libelle('termine_au_plus_tard', langue),
                c.esc(c.date_longue(delais.get('date_limite'), langue)
                      or delais.get('resume')
                      or libelle('a_preciser_maj', langue)),
                c.esc(delais.get('detail') or '')),
        c.carte(libelle('vos_garanties', langue),
                (libelle('jusqua', langue, duree=c.esc(plus_longue))
                 if plus_longue else libelle('garanties_fabricant', langue)),
                apercu_garanties),
    )
    corps += c.h2(_titre_paiement(len(echeancier), langue),
                  libelle('paiement_intro', langue))
    corps += c.frise(echeancier, langue=langue)
    if contenu.get('paiement', {}).get('modalites'):
        corps += f'<p class="petit">{c.texte_libre(contenu["paiement"]["modalites"])}</p>'
    # Page 1 : qui la lit seule sait que la signature est à la fin (R11).
    corps += f'<p class="renvoi">{c.esc(libelle("signature_en_fin", langue))}</p>'

    corps += c.h2(libelle('entre_soussignes', langue))
    corps += c.parties(contenu)

    devis = c.texte_libre((contenu.get('chantier') or {}).get('devis_reference'))
    corps += c.h2(libelle('ce_que_nous_installons', langue),
                  libelle('ce_que_nous_installons_intro', langue, devis=devis))
    corps += c.tableau_materiel(systeme.get('lignes'), langue=langue)

    corps += c.h2(libelle('vos_garanties', langue),
                  libelle('garanties_intro', langue))
    corps += c.tableau_garanties(garanties, langue=langue)

    corps += c.h2(libelle('conditions_du_contrat', langue))
    corps += c.articles(contenu.get('articles'), langue)
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu, mention_client=libelle('mention_contrat', langue))
    return _page(contenu, corps, classe='contrat')


# ── Acte 2 — Procès-verbal de livraison du matériel ─────────────────────────

def _montant_du(montant, en_lettres, langue):
    """La colonne du chiffre d'un encadré de montant : le montant en grand,
    puis en lettres s'il est connu."""
    html = f'<div class="grand">{c.esc(c.montant(montant, langue=langue))}</div>'
    if en_lettres:
        html += f'<p class="lettres">{c.esc(en_lettres)}</p>'
    return html


def _encadre_paiement_livraison(contenu):
    langue = c.langue_de(contenu)
    paiement = contenu.get('paiement') or {}
    regle = paiement.get('total_regle')
    if contenu.get('variante') == 'tranche_reglee':
        part = c.pourcent(paiement.get('pourcentage_regle'))
        quoi = (libelle('part_du_prix', langue, part=c.esc(part)) if part
                else libelle('sommes_dues', langue))
        explication = f'<p>{libelle("vous_avez_regle", langue, quoi=quoi)}</p>'
        reste = paiement.get('reste_a_regler')
        if reste not in (None, '', 0, '0', '0.00'):
            explication += (f'<p>{libelle("il_restera", langue, montant=c.esc(c.montant(reste, langue=langue)))}'
                            f'</p>')
        return c.encadre_montant(libelle('regle_a_ce_jour', langue),
                                 _montant_du(regle, '', langue), explication,
                                 'ok')
    explication = ''
    if regle not in (None, ''):
        explication += '<p>' + libelle(
            'deja_regle', langue,
            montant=c.esc(c.montant(regle, langue=langue))) + '</p>'
    if paiement.get('restera_ensuite') not in (None, ''):
        explication += '<p>' + libelle(
            'restera_reception', langue,
            montant=c.esc(c.montant(paiement['restera_ensuite'],
                                    langue=langue))) + '</p>'
    if paiement.get('modalites'):
        explication += (f'<p class="petit">'
                        f'{c.texte_libre(paiement["modalites"])}</p>')
    return c.encadre_montant(
        libelle('a_regler_livraison', langue),
        _montant_du(paiement.get('exigible_maintenant'),
                    paiement.get('exigible_en_lettres'), langue),
        explication)


def pv_livraison(contenu):
    langue = c.langue_de(contenu)
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    livraison = contenu.get('livraison') or {}

    corps = c.titre(
        'pv_livraison', contenu.get('titre') or libelle('h1_livraison', langue),
        libelle('chapeau_livraison', langue), contenu.get('reference'), langue)
    corps += c.cartes(
        c.carte(libelle('livre_le', langue),
                c.esc(c.date_longue(livraison.get('date'), langue)
                      or libelle('date_a_porter', langue)),
                c.esc(chantier.get('adresse') or '')),
        c.carte(libelle('etape_suivante', langue),
                c.esc(livraison.get('suite') or libelle('la_pose', langue)),
                c.esc(livraison.get('suite_detail') or '')),
    )
    corps += c.h2(libelle('materiel_livre', langue),
                  libelle('conformement_devis', langue,
                          devis=c.texte_libre(chantier.get('devis_reference'))))
    corps += c.tableau_materiel(systeme.get('lignes'), avec_series=bool(
        livraison.get('avec_series')), langue=langue)

    corps += c.h2(libelle('vos_constatations', langue))
    corps += c.cases(contenu.get('constats'))
    corps += c.encadre(
        libelle('reserves_eventuelles', langue),
        f'<p class="petit">{libelle("reserves_eventuelles_aide", langue)}</p>'
        + (c.paragraphes(contenu.get('reserves'))
           if contenu.get('reserves') else c.lignes_a_ecrire(3)), 'net')

    corps += c.bloc_insecable(
        c.h2(libelle('paiement_cette_etape', langue))
        + c.frise(contenu.get('echeancier'), avec_etats=True, langue=langue)
        + _encadre_paiement_livraison(contenu))

    # Le titre ne porte plus le nom de la société (revue 1, R9 : il était
    # échappé deux fois, « L&amp;#x27;… » à l'impression).
    corps += c.h2(libelle('ce_que_vous_convenez', langue))
    corps += c.articles(contenu.get('articles'), langue)
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu, mention_client=libelle('mention_livraison', langue))
    return _page(contenu, corps, classe='proces')


# ── Acte 3 — Procès-verbal de réception des travaux ─────────────────────────

def pv_reception(contenu):
    langue = c.langue_de(contenu)
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    reception = contenu.get('reception') or {}
    paiement = contenu.get('paiement') or {}
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))
    valeur_sys, detail_sys = _resume_systeme(systeme, langue)

    corps = c.titre(
        'pv_reception', contenu.get('titre') or libelle('h1_reception', langue),
        libelle('chapeau_reception', langue, nom=nom),
        contenu.get('reference'), langue)
    corps += c.cartes(
        c.carte(libelle('votre_installation', langue), valeur_sys, detail_sys),
        c.carte(libelle('mise_en_service', langue),
                c.esc(c.date_longue(reception.get('date_mise_en_service'),
                                    langue)
                      or libelle('date_a_porter', langue)),
                c.esc(chantier.get('adresse') or '')),
    )
    corps += c.h2(libelle('verifie_ensemble', langue))
    corps += c.cases(contenu.get('constats'))

    corps += c.h2(libelle('la_reception', langue),
                  libelle('une_seule_case', langue))
    sans = not contenu.get('reserves')
    corps += c.cases([
        {'texte': libelle('sans_reserve', langue),
         'cochee': bool(reception.get('prononcee')) and sans},
        {'texte': libelle('avec_reserves', langue,
                          nom=(societe.get('nom_court')
                               or societe.get('nom') or '')),
         'cochee': bool(reception.get('prononcee')) and not sans},
    ])
    delai = reception.get('delai_levee_reserves')
    # Quatre lignes pour écrire les réserves, puis la part du solde retenue
    # jusqu'à leur levée, chiffrée à la main (revue 1, R1 ; texte T2).
    corps += c.encadre(
        libelle('reserves', langue)
        + (libelle('a_lever_sous', langue, delai=delai) if delai else ''),
        (c.paragraphes(contenu.get('reserves')) if contenu.get('reserves')
         else c.lignes_a_ecrire(4))
        + f'<p class="part-retenue">'
        f'{c.a_remplir(libelle("part_retenue", langue))}</p>', 'net')

    # Titre, frise et encadré du montant dû : un seul bloc insécable — en
    # arabe, le titre et la frise restaient en bas de page 1, l'encadré
    # partait seul en page 2 (revue 1, R10).
    solde = c.h2(libelle('solde_installation', langue))
    solde += c.frise(contenu.get('echeancier'), avec_etats=True, langue=langue)
    du = paiement.get('exigible_maintenant')
    if du in (None, '', 0, '0', '0.00'):
        solde += c.encadre_montant(
            libelle('paye_integralement', langue),
            _montant_du(paiement.get('total_regle'), '', langue),
            f'<p>{libelle("regle_totalite", langue)}</p>', 'ok')
    else:
        explication = (
            f'<p>{c.texte_libre(paiement.get("engagement") or "")}</p>'
            if paiement.get('engagement') else '')
        if paiement.get('modalites'):
            explication += (f'<p class="petit">'
                            f'{c.texte_libre(paiement["modalites"])}</p>')
        solde += c.encadre_montant(
            libelle('solde_a_regler', langue),
            _montant_du(du, paiement.get('exigible_en_lettres'), langue),
            explication)
    corps += c.bloc_insecable(solde)

    corps += c.h2(libelle('ce_que_reception_change', langue))
    corps += c.articles(contenu.get('articles'), langue)
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu, mention_client=libelle('mention_reception', langue))
    return _page(contenu, corps, classe='proces')


# ── Acte 4 — Clôture : quitus, certificat de garantie, conseils ─────────────

def _journee(journee):
    """La journée type, du lever au coucher du soleil. Les largeurs suivent les
    parts du ``contenu`` : elles situent les moments, elles ne chiffrent rien."""
    plages = journee.get('plages') or []
    total = sum(float(p.get('part') or 0) for p in plages) or 1

    def largeur(p):
        return f'{100 * float(p.get("part") or 0) / total:.2f}%'

    rail = ''.join(
        f'<div class="{c.esc(p.get("sorte"))}" style="width:{largeur(p)}">'
        f'{c.esc(p.get("libelle") or "")}</div>' for p in plages)
    sous = ''.join(
        f'<div class="{c.esc(p.get("sorte"))}" style="width:{largeur(p)}">'
        f'{c.esc(p.get("sous") or "")}</div>' for p in plages)
    legende = (f'<p class="petit">{c.esc(journee["legende"])}</p>'
               if journee.get('legende') else '')
    return (f'<div class="journee"><div class="rail">{rail}</div>'
            f'<div class="sous">{sous}</div>{legende}</div>')


def cloture_garanties(contenu):
    langue = c.langue_de(contenu)
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    prix = contenu.get('prix') or {}
    paiement = contenu.get('paiement') or {}
    sav = contenu.get('sav') or {}
    valeur_sys, detail_sys = _resume_systeme(systeme, langue)

    corps = c.titre(
        'cloture_garanties', contenu.get('titre') or
        libelle('h1_cloture', langue), libelle('chapeau_cloture', langue),
        contenu.get('reference'), langue)
    corps += c.cartes(
        c.carte(libelle('votre_installation', langue), valeur_sys, detail_sys),
        c.carte(libelle('paye_integralement', langue),
                c.esc(c.montant(paiement.get('total_regle')
                                or prix.get('total_ttc'), langue=langue)),
                libelle('solde_zero', langue,
                        zero=c.esc(c.montant(0, langue=langue))),
                forte=True),
    )
    corps += c.h2(libelle('attestation', langue))
    corps += c.encadre(libelle('quitus', langue),
                       c.paragraphes(contenu.get('quitus')), 'ok quitus')
    corps += c.tableau_paiements(contenu.get('paiements'),
                                 paiement.get('total_regle'), langue)
    corps += c.signatures(contenu, mention_client='', client_signe=False,
                          exemplaires=False)

    date_reception = c.date_longue(
        (contenu.get('reception') or {}).get('date'), langue)
    corps += c.h2(libelle('certificat', langue),
                  libelle('certificat_intro', langue,
                          date=c.esc(date_reception
                                     or libelle('date_inconnue', langue)),
                          adresse=c.esc(
                              chantier.get('adresse')
                              or libelle('adresse_du_chantier', langue))))
    corps += c.tableau_garanties(contenu.get('garanties'), avec_dates=True,
                                 langue=langue)
    # Le matériel n'est relisté que s'il porte ses numéros de série (preuve
    # de ce qui est couvert) ; sinon le tableau des garanties suffit.
    if any(lg.get('numeros_serie') for lg in systeme.get('lignes') or []):
        corps += c.h2(libelle('materiel_couvert', langue))
        corps += c.tableau_materiel(systeme['lignes'], avec_series=True,
                                    langue=langue)
    # La carte du service après-vente se lit juste sous « Qui appeler »
    # (revue 1, R2) ; sans cet article, elle suit les articles.
    articles = contenu.get('articles') or []
    contact = ' · '.join(c.insecable(c.esc(x)) for x in (
        sav.get('telephone'), sav.get('whatsapp'), sav.get('email')) if x)
    carte_sav = ''
    if contact:
        carte_sav = c.encadre(
            libelle('sav', langue,
                    nom=societe.get('nom_court') or societe.get('nom') or ''),
            f'<div class="grand sav">{contact}</div>'
            f'<p class="petit">{c.esc(sav.get("horaires") or "")}</p>', 'net')
    sous_contact = any(a.get('cle') == 'contact' for a in articles)
    corps += c.h2(libelle('si_probleme', langue))
    corps += c.articles(articles, langue,
                        annexes={'contact': carte_sav} if sous_contact else None)
    if not sous_contact:
        corps += carte_sav

    conseils = contenu.get('conseils') or []
    if conseils:
        # Plus de saut de page forcé : les conseils suivent, et ne passent à
        # la page suivante que si la place manque. Le titre, l'introduction
        # et la journée type restent ensemble (jamais un titre seul en bas).
        tete = c.h2(libelle('bien_consommer', langue),
                    c.esc(contenu.get('conseils_intro') or ''))
        if contenu.get('journee'):
            tete += _journee(contenu['journee'])
        corps += c.bloc_insecable(tete)
        corps += '<div class="conseils">' + ''.join(
            f'<div class="conseil"><div class="lbl">{c.esc(k.get("rubrique"))}'
            f'</div><h3>{c.esc(k.get("titre"))}</h3>'
            f'<p>{c.esc(k.get("texte"))}</p></div>' for k in conseils) + '</div>'
        if contenu.get('entretien'):
            # Court : son titre et ses lignes restent ensemble.
            corps += c.bloc_insecable(
                c.h2(libelle('entretien', langue))
                + '<div class="article plein"><div class="texte">'
                + c.paragraphes(contenu['entretien']) + '</div></div>')

    return _page(contenu, corps, paraphes=False, classe='cloture')


_RENDUS = {
    'contrat_installation': contrat_installation,
    'pv_livraison': pv_livraison,
    'pv_reception': pv_reception,
    'cloture_garanties': cloture_garanties,
}


def html_de(contenu):
    """HTML complet d'un acte. ``ValueError`` si le type est inconnu."""
    try:
        rendu = _RENDUS[contenu['type']]
    except KeyError:
        raise ValueError(f"Type d'acte inconnu : {contenu.get('type')!r}")
    return rendu(contenu)
