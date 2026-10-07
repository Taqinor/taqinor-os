// SPL212 — dialogues « Journal comptable » et « Export comptable » de la liste
// des factures, déplacés tels quels (move only) depuis FactureList.jsx ; leur
// état et leurs gestes viennent de useFactureCompta.js.
import {
  Button, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

export default function ComptaDialogs({ compta }) {
  const {
    journalOpen, setJournalOpen,
    journalMode, setJournalMode,
    journalMois, setJournalMois,
    journalAnnee, setJournalAnnee,
    journalTrimestre, setJournalTrimestre,
    journalBusy,
    exportComptableOpen, setExportComptableOpen,
    exportStart, setExportStart,
    exportEnd, setExportEnd,
    exportComptableBusy,
    handleExportComptable,
    handleJournalComptable,
  } = compta
  return (
    <>
      {/* VX142(a) — Journal comptable : Dialog mois/trimestre (remplace le
          window.prompt() texte libre). */}
      <Dialog open={journalOpen} onOpenChange={setJournalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Journal comptable</DialogTitle>
            <DialogDescription>
              Journal des ventes + résumé TVA (comptable), par mois ou par trimestre.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div role="group" aria-label="Période" className="inline-flex gap-1">
              {[['mois', 'Mois'], ['trimestre', 'Trimestre']].map(([val, label]) => (
                <Button key={val} type="button" size="sm"
                        variant={journalMode === val ? 'default' : 'outline'}
                        aria-pressed={journalMode === val}
                        onClick={() => setJournalMode(val)}>
                  {label}
                </Button>
              ))}
            </div>
            {journalMode === 'mois' ? (
              <Input type="month" value={journalMois}
                     onChange={e => setJournalMois(e.target.value)}
                     aria-label="Mois du journal" />
            ) : (
              <div className="flex gap-2">
                <Input type="number" className="w-28" value={journalAnnee}
                       onChange={e => setJournalAnnee(e.target.value)}
                       aria-label="Année du trimestre" />
                <Select value={journalTrimestre} onValueChange={setJournalTrimestre}>
                  <SelectTrigger className="w-32" aria-label="Trimestre">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {['1', '2', '3', '4'].map(q => (
                      <SelectItem key={q} value={q}>{`T${q}`}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJournalOpen(false)}>Annuler</Button>
            <Button loading={journalBusy} onClick={handleJournalComptable}>Télécharger</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* VX142(a) — Export comptable : Dialog plage de dates (remplace les
          deux window.prompt() successifs). */}
      <Dialog open={exportComptableOpen} onOpenChange={setExportComptableOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Export comptable</DialogTitle>
            <DialogDescription>
              Factures validées d'une plage de dates, en Excel + CSV (ventilation TVA, ICE, totaux).
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2">
            <Input type="date" value={exportStart} required
                   onChange={e => setExportStart(e.target.value)}
                   aria-label="Date de début" />
            <Input type="date" value={exportEnd} required
                   onChange={e => setExportEnd(e.target.value)}
                   aria-label="Date de fin" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExportComptableOpen(false)}>Annuler</Button>
            <Button loading={exportComptableBusy} onClick={handleExportComptable}>Télécharger</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
