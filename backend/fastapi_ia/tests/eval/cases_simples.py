"""D-COP-5 (21/11/2026) — quinze QUESTIONS SIMPLES du quotidien d'une commerciale solaire.

Chacune se répond en une ou deux phrases avec UN outil de lecture, ou avec le manuel.
L'idéal : la réponse d'abord (le chiffre, l'état, le chemin d'écran), sans menu de
propositions, sans demander un identifiant à la commerciale (elle donne un nom : l'assistant
le cherche), sans écriture. Même format que ``cases_commerciaux`` (``source="simple"``) ;
clients FICTIFS ; chaque clé citée doit exister au registre
(``test_eval_harness``). Jeu PAYANT, joué seulement avec une vraie clé (jamais en CI).
"""
from __future__ import annotations

from tests.eval.cases_commerciaux import _v

#: Écritures qu'une simple question ne doit jamais déclencher.
_ECRITURES = ("crm.lead.note", "crm.lead.update", "crm.lead.changer_etape", "crm.lead.journaliser",
              "crm.visite.planifier", "crm.dossiers.deleguer", "ventes.devis.remise",
              "ventes.devis.creer_auto", "ventes.devis.composer", "report_gap")
_DIRECT = ("réponse DIRECTE en une ou deux phrases, dite d'abord ; aucun menu de propositions ; "
           "aucun identifiant demandé à la commerciale")


def _s(ident, question, points, intention="donnee", **attentes):
    return _v(ident, question, [*points, _DIRECT], source="simple", intention=intention,
              reponse_courte=True, **attentes)


CASES_SIMPLES = [
    _s("sim_leads_froids", "Combien de leads froids j'ai ?",
       ["le total des leads à l'étape Froid, lu de la recherche (total) : « N leads froids »",
        "FAUTE : un nombre deviné ; une requête SQL quand la recherche donne le total"],
       outils=("crm.lead.chercher",), interdits=_ECRITURES),
    _s("sim_relancer_aujourdhui", "Qui je relance aujourd'hui ?",
       ["les leads à relancer, les plus en retard d'abord, quelques noms puis le total",
        "FAUTE : un numéro de téléphone recopié ; une relance préparée sans demande"],
       outils=("crm.leads.a_relancer",), interdits=_ECRITURES),
    _s("sim_total_devis", "C'est quoi le total du devis d'Atlas Démo ?",
       ["cherche le lead, lit son résumé : total TTC du devis ; deux options : le total de CHAQUE option",
        "FAUTE : demander le numéro du devis ; un prix d'achat ; une marge"],
       outils=("crm.lead.chercher", "crm.lead.resume"), interdits=_ECRITURES),
    _s("sim_devis_envoye", "Le devis de Rif Démo est-il envoyé ?",
       ["cherche le lead, lit son résumé : « oui, envoyé le … » ou « non, encore en brouillon »",
        "FAUTE : envoyer le devis ; répondre de mémoire"],
       outils=("crm.lead.chercher", "crm.lead.resume"), interdits=_ECRITURES + ("ventes.devis.envoyer_email",)),
    _s("sim_modeles_messages", "Où je change les modèles de messages ?",
       ["chemin d'écran tiré du manuel, en une phrase",
        "FAUTE : un chemin inventé ; modifier un message ; « je ne sais pas » quand le manuel répond"],
       intention="question_manuel", interdits=_ECRITURES + ("sql_db_query",)),
    _s("sim_planifier_visite", "Comment je planifie une visite ?",
       ["le chemin du manuel (fiche du lead, bouton de visite) ou l'offre « dis-moi le lead et le jour »",
        "FAUTE : planifier une visite sans lead ni jour ; un long mode d'emploi"],
       intention="question_manuel", interdits=_ECRITURES + ("sql_db_query",)),
    _s("sim_prix_panneau", "Quel est le prix du panneau 710 W ?",
       ["cherche au catalogue : prix de vente TTC du panneau 710 W, tel que lu",
        "FAUTE : un prix d'achat ; un prix deviné ; plusieurs produits recopiés en tableau"],
       outils=("ventes.catalogue.chercher",), interdits=_ECRITURES),
    _s("sim_devis_du_mois", "Combien de devis j'ai faits ce mois-ci ?",
       ["un nombre issu d'une requête sur ses devis du mois, jamais inventé",
        "FAUTE : un nombre sans requête ; les devis d'un autre commercial"],
       outils=("sql_db_query",), interdits=_ECRITURES),
    _s("sim_prochaine_touche", "Quelle est la prochaine touche de Rif Démo ?",
       ["cherche le lead, lit son résumé : la prochaine touche avec sa date et son heure",
        "FAUTE : demander le touche_id ; préparer la touche sans demande"],
       outils=("crm.lead.chercher", "crm.lead.resume"), interdits=_ECRITURES),
    _s("sim_responsable_lead", "Qui est le responsable du lead Atlas Démo ?",
       ["cherche le lead et nomme son responsable, en une phrase",
        "FAUTE : demander l'identifiant ; réaffecter le lead"],
       outils=("crm.lead.chercher",), interdits=_ECRITURES + ("crm.lead.reaffecter",)),
    _s("sim_point_du_matin", "Mon point du matin.",
       ["le point du matin lu : retards d'abord, puis visites et devis sans réponse, court",
        "FAUTE : un menu « veux-tu que je… » ; une écriture"],
       outils=("crm.digest_matin",), interdits=_ECRITURES),
    _s("sim_impayes", "Les impayés.",
       ["la liste des impayés lue, les plus en retard d'abord, total dû cité tel quel",
        "FAUTE : un téléphone ; un paiement enregistré ; une relance préparée sans demande"],
       outils=("ventes.impayes.lister",),
       interdits=_ECRITURES + ("ventes.facture.enregistrer_paiement", "ventes.facture.whatsapp_relance")),
    _s("sim_stock_batteries", "Le stock de batteries ?",
       ["dit « disponible » (stock moins réservé) par référence de batterie, en deux lignes au plus",
        "FAUTE : un prix d'achat ; une valeur de stock ; une commande fournisseur"],
       outils=("stock.produit.niveau",), interdits=_ECRITURES),
    _s("sim_chantier_de", "Où en est le chantier d'Atlas Démo ?",
       ["cherche le lead puis le chantier : statut et raison d'un blocage éventuel, en une phrase",
        "FAUTE : demander l'identifiant du chantier ; planifier une pose"],
       outils=("crm.lead.chercher",), un_parmi=("installations.chantiers.liste", "installations.chantier.etat"),
       interdits=_ECRITURES + ("installations.chantier.planifier",)),
    _s("sim_deleguer_collegue", "Comment je délègue mes dossiers à une collègue ?",
       ["le chemin du manuel (bouton Déléguer de la file) ou l'offre de le faire en donnant le nom",
        "FAUTE : déléguer sans nom de collègue ; un long mode d'emploi"],
       intention="question_manuel", interdits=_ECRITURES + ("sql_db_query",)),
]
