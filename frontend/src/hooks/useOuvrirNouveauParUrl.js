import { useEffect } from 'react'

/* Raccourci « c c » (CommandPalette) : /crm?new=1 ou /crm/leads?new=1 ouvre
   directement le formulaire de création, une seule fois. Le paramètre `new`
   est retiré une fois lu pour ne pas rouvrir le formulaire à chaque rendu. */
export function useOuvrirNouveauParUrl(searchParams, setSearchParams, ouvrir) {
  useEffect(() => {
    if (searchParams.get('new') !== '1') return
    ouvrir()
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('new')
      return next
    }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps -- ouverture one-shot pilotée par ?new=1; ni `ouvrir` ni setSearchParams ne doivent la rejouer (D-ENF22)
  }, [searchParams])
}
