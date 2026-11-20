"""Contre-visite AERR (VER5-500, lead, témoin d'AERR189) : pages/crm/leads/LeadsPage.jsx::LeadsPage,
pages/crm/leads/views/LeadCard.jsx::LeadCard, features/crm/CallLogPopover.jsx::CallLogPopover.
AERR189 garde montée la fenêtre « Planifier la relance » de la liste des leads (ouverture pilotée par `relanceOuverte`) ;
le rejeu en direct a ajouté `onCloseAutoFocus` au menu « ⋯ » de la carte. Le détecteur vérifie dans le source :
(1) le bloc <CallLogPopover mode="planification"> de LeadsPage garde `key={relanceLead.id}` (autre lead ⇒ fenêtre neuve),
`open={relanceOuverte}`, un `onOpenChange` qui ne remet PAS `relanceLead` à null, un `onLogged` qui ferme et relit ;
(2) LeadCard n'empêche le retour de focus du menu que si l'item « Planifier une relance » l'a demandé (drapeau remis à
faux dans le même gestionnaire) ; (3) CallLogPopover ne pose `appelJournalise` que hors planification (pas de succès
faux VER2-200 possible depuis la liste) et ne remet la saisie à zéro à la fermeture que si l'appel est journalisé.
repro = un de ces points manque (régression d'AERR189 ou de son correctif de rejeu)."""
SONDE = {"constat": "C-AERR-VER5-500", "sha": "decf0330bd",
         "attendu": "fenêtre gardée montée par lead, fermeture sans démontage, retour de focus coupé pour le seul item relance"}
import json, pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def lire(rel):
    return (SRC / rel).read_text(encoding="utf-8")


obs = {}
page = lire("pages/crm/leads/LeadsPage.jsx")
i = page.find('mode="planification"')
debut = page.rfind("<CallLogPopover", 0, i)
bloc = page[debut:page.find("/>", i)] if i > 0 and debut > 0 else ""
obs["bloc_trouve"] = bool(bloc)
obs["key_par_lead"] = "key={relanceLead.id}" in bloc
obs["open_pilote"] = "open={relanceOuverte}" in bloc
m = re.search(r"onOpenChange=\{([^\n]*)\}", bloc)
obs["onOpenChange_ne_demonte_pas"] = bool(m) and "setRelanceLead(null)" not in m.group(1)
m = re.search(r"onLogged=\{([^\n]*)\}", bloc)
obs["onLogged_ferme_et_relit"] = bool(m) and all(t in m.group(1) for t in ("setRelanceLead(null)", "setRelanceOuverte(false)", "refetch()"))
obs["ouverture_pose_lead_et_ouvre"] = bool(re.search(r"setRelanceLead\(lead\)\s*\n\s*setRelanceOuverte\(true\)", page))

carte = lire("pages/crm/leads/views/LeadCard.jsx")
obs["item_relance_pose_drapeau"] = bool(re.search(r"onSelect=\{\(\) => \{ relanceChoisie\.current = true; onPlanifierRelance\(lead\) \}\}", carte))
obs["retour_focus_coupe_sous_drapeau"] = bool(re.search(
    r"onCloseAutoFocus=\{\(e\) => \{\s*if \(relanceChoisie\.current\) \{ relanceChoisie\.current = false; e\.preventDefault\(\) \}", carte))
obs["drapeau_pose_une_seule_fois"] = carte.count("relanceChoisie.current = true") == 1

pop = lire("features/crm/CallLogPopover.jsx")
obs["appelJournalise_hors_planification"] = bool(re.search(
    r"if \(!planificationSeule && !reprise\) \{\s*await crmApi\.logInteraction\(.{0,200}?\}\)\s*setAppelJournalise\(true\)", pop, re.S)) \
    and pop.count("setAppelJournalise(true)") == 1
obs["fermeture_reset_si_journalise_seul"] = bool(re.search(
    r"else if \(ouvertVu !== isOpen\) \{ setOuvertVu\(isOpen\); if \(appelJournalise\) reset\(\) \}", pop))
obs["autre_lead_reset"] = bool(re.search(r"if \(leadVu !== leadId\) \{[^}]*reset\(\)", pop))

print(json.dumps({"repro": not all(obs.values()), "observe": obs, "methode": "lecture écran"}, ensure_ascii=False, indent=1))
