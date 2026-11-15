# Context Proiect: CS Flip Helper v2
Acest fișier definește responsabilitățile agenților AI pentru generarea codului. Este strict interzisă încălcarea granițelor dintre domenii (Separation of Concerns).

## @front (Next.js & Tailwind)
- Responsabilitate: Dashboard "Sniper" UI.
- Tehnologii: Next.js (App router), Tailwind CSS, shadcn/ui.
- Reguli: Fără logică de business sau procesare de prețuri. Doar consumă datele de la @back via REST/WebSockets.

## @back (FastAPI)
- Responsabilitate: Core business logic, rate-limiting in-memory, gestionarea bazei de date.
- Tehnologii: Python 3.10+, FastAPI, asyncio, supabase-py.
- Structură: 
  - `app/api/`: Doar definiții de rute. Fără logică de bază de date aici.
  - `app/core/`: Singleton-uri (MemoryDB), config, setări de mediu.
  - `app/services/`: Logica de scraping și integrare externă.
- Reguli de Fier: 
  - Toată filtrarea float-urilor și prețurilor are loc EXCLUSIV în memoria RAM.
  - Interogările externe (Supabase) nu trebuie să blocheze Event Loop-ul asincron (folosiți asyncio.to_thread pentru clienți sincroni).

## @scraper (CSFloat Integration)
- Responsabilitate: Comunicarea HTTP cu API-ul CSFloat.
- Tehnologii: httpx (async).
- Reguli: Trebuie să citească și să respecte capetele (headers) X-RateLimit. Orice request trebuie să implementeze exponential backoff.