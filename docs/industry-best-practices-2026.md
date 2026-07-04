# Production-ready agent rendszer — 2026 nyári ipari best practice-k

Ez a dokumentum a beszélgetésben kért kérdésre ("hogyan kell egy igazi product-ready agensrendszernek nekiállni") ad egy forrásokkal alátámasztott, gyakorlati választ, és a végén visszaköti a konkrét repódhoz.

---

## 0. A helyzet 2026 közepén — miért ez most a fő iparági kérdés

- Deloitte *State of AI in 2026*: a cégek 74%-a tervez agentic AI-t bevezetni két éven belül, de csak 21%-uknak van érett governance modellje autonóm agentekre. ([forrás](https://www.clustox.com/blog/ai-agent-architecture-blueprint/))
- Okta kutatása: a szervezetek 91%-a már használ AI agenteket, de csak 10%-uknál van hozzá governance. ([forrás](https://builtin.com/articles/enterprise-identity-access-management))
- Gartner: 2026-ra a vállalati alkalmazások 40%-a beágyazott, feladat-specifikus AI agenteket fog tartalmazni (2025-ben ez <5% volt).
- A non-human identitások (szolgáltatásfiókok, API kulcsok, agentek) 25-50x, egyes források szerint akár 100x annyian vannak, mint az emberi felhasználók egy modern vállalatnál.

**A lényeg:** ma nem a "tudunk-e agentet hívni" a kérdés, hanem hogy a *governance* (identitás, audit, költség, biztonság) lépést tud-e tartani a bevezetés sebességével. A legtöbb szervezet ma pont ebben a résben van — ez az a rés, amit a te repód is demonstrált.

---

## 1. Architektúra-döntés: workflow vagy agent? Egy vagy több agent?

Anthropic saját, gyakorlatban validált ajánlása ("Building Effective AI Agents", frissítve 2026-ban):

- **Workflow** (prompt chaining, routing, parallelization, orchestrator-worker, evaluator-optimizer): akkor válaszd, ha a feladat jól dekomponálható fix lépésekre, és kiszámíthatóságra van szükséged. Determinisztikus "gate"-eket tehetsz a lépések közé programozott ellenőrzésre.
- **Agent**: nyílt végű feladatokra, ahol nem lehet előre megjósolni a lépésszámot, és a modell döntéseiben kell megbízni. Ez drágább és hibalánc-érzékenyebb.
- **Multi-agent**: csak akkor, ha a feladat tényleg megköveteli — Anthropic mérése szerint a multi-agent rendszerek **10-15x annyi tokent** használnak, mint egyetlen agent. "Ne over-engineer-elj": sok éles rendszernek elég egyetlen jól megtervezett agent + tool-készlet.
- Ökölszabály production autonómiára: egy 20 lépéses agent 5%-os lépésenkénti hibaarány mellett gyakorlatilag használhatatlan lesz guardrailek nélkül — a valóban autonóm, sok lépéses agenteknek jellemzően **jóval 1% alatti** végpontok közötti hibaarány kell.

Források: [Anthropic — Building Effective AI Agents](https://www.anthropic.com/research/building-effective-agents), [Anthropic Architecture Patterns PDF](https://resources.anthropic.com/building-effective-ai-agents), [Redis — AI Agent Architecture](https://redis.io/blog/ai-agent-architecture/)

---

## 2. Identitás és jogosultságkezelés — ez a 2026-os "nagy téma"

Ez ma az iparág legaktívabb frontja, és pontosan ez volt a te repód #1 hiányossága is.

**A konszenzus (EIC 2026, OWASP NHI Top 10, Microsoft/Okta/Google agent-identitás termékek):**

- Minden agentnek **saját, első osztályú, visszavonható identitása** legyen ("agent passport") — ne osztott service-account kulcsot használjon.
- **Runtime authorization minden egyes akcióra**, nem csak regisztrációkor egyszer. Ez a kulcskülönbség "fejlesztői szintű" és "enterprise-grade" megoldás között.
- Konvergáló szabványok: **OAuth 2.1**, **MCP**, **A2A** (Agent-to-Agent protokoll) mint alapkövek; **OpenID AuthZEN** mint runtime-authorization primitív.
- **"Human Custodian" elv**: minden gépi identitásnak legyen egy felelős ember hozzárendelve, aki tudja, még aktív-e és szükséges-e.
- **JIT (just-in-time) hozzáférés** hosszú élettartamú kulcsok helyett; azonnali "kill switch" minden agentre.
- Magas kockázatú akcióknál (pl. pénzügyi tranzakció, refund) hardware-alapú, emberi jóváhagyáshoz kötött engedélyezés jelenik meg éles enterprise megoldásokban (pl. Yubico + Delinea RSAC 2026 demo: minden magas kockázatú agent-akció visszavezethető egy ellenőrzött emberi döntésre).

Források: [Corbado — Agentic & NHI at EIC 2026](https://www.corbado.com/blog/agentic-non-human-identity-eic-2026), [Built In — Enterprise IAM for agents](https://builtin.com/articles/enterprise-identity-access-management), [SailPoint — Agentic AI and IAM](https://www.sailpoint.com/blog/agentic-ai-and-the-future-of-iam), [Cloud Security Alliance — NHI Governance Vacuum](https://labs.cloudsecurityalliance.org/research/csa-whitepaper-nonhuman-identity-agentic-ai-governance-v1-cs/)

---

## 3. Biztonsági fenyegetésmodell: van már agent-specifikus szabvány

- **OWASP Top 10 for Agentic Applications (2026)** — 100+ szakértő közreműködésével, kifejezetten autonóm/agentic rendszerekre (nem ugyanaz, mint a régi OWASP LLM Top 10). Kategóriák többek közt: Agent Goal Hijack (ASI01), Tool Misuse & Exploitation (ASI02), Agent Identity & Privilege Abuse (ASI03), Agentic Supply Chain Compromise (ASI04), egészen a "Rogue Agent" (viselkedésében eltért, de még hitelesített) kategóriáig.
- **MITRE ATLAS v5.1.0** — 16 taktika, 84 technika, AI-rendszerek elleni támadásokra.
- **"Lethal trifecta"** (Simon Willison formulája) — jó gyors mentális modell: ha egy agent-konfigurációban egyszerre jelen van (1) privát/bizalmas adat, (2) nem megbízható, külső tartalom (pl. retrieved dokumentum, weboldal), és (3) kifelé irányuló kommunikációs csatorna — az architekturálisan garantáltan kihasználható prompt injection-re. Ha ezt a hármat a tervezés fázisában külön tartod, sok támadási felületet kizársz eleve.
- **OWASP Agentic Skills Top 10** (2026, inkubátor projekt) — az agent-"skill"/plugin-ökoszisztémák supply-chain kockázataira (analóg az npm/pip lánc-támadásokkal, csak agent-képességekre).
- Nagy szállítói válaszok már léteznek: Microsoft Agent 365, Google Agent Governance Stack, AWS Bedrock Guardrails — de egyik sem helyettesíti a saját fenyegetésmodellezésedet.

Források: [OWASP GenAI — Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), [DeepTeam — OWASP ASI Top 10 kategóriák](https://www.trydeepteam.com/docs/frameworks-owasp-top-10-for-agentic-applications), [arXiv — lethal trifecta hivatkozás](https://arxiv.org/pdf/2605.18784)

---

## 4. MCP és tool-integráció — a de facto szabvány, és ahogy biztonságosan kell

A Model Context Protocol mára a tool-integráció széles körben elfogadott szabványa lett. A hivatalos és iparági guidance kulcspontjai:

- **Per-operation authorization, nem per-session.** Idézve: *"A session-level authorization check verifies that the AI is permitted to connect to the system. A per-operation authorization check verifies that the specific user, requesting this specific action on this specific data, is permitted to proceed — for every individual MCP operation. Only per-operation authorization enforces least privilege in practice."* Ez pontosan az a különbség, ami a te request_router / tool-handler szétválásodnál hiányzott.
- **A hitelesítő adatot soha nem adod át a modell kontextusán keresztül** — OAuth token nem kerülhet promptba, env varba, amit a modell "lát". Ugyanaz a minta, mint a Bedrock sessionAttributes vs. parameters különbség, amit a repód reviewjában találtam.
- **Enterprise MCP Gateway minta**: központi proxy, ami minden szerverre egységes policy-t, allowlistet, monitorozást kényszerít ki — ne hagyatkozz arra, hogy minden egyes fejlesztő helyesen konfigurálja a sajátját.
- **Alapértelmezett least privilege**: read-only alapból, write/edit csak explicit szerepkör mögött; magas kockázatú műveletekhez jóváhagyási lépés.
- **Single-tenant / explicit tenant-határok** még MCP-szerver szinten is: külön adatútvonalak, kulcsok, logok tenantonként.
- Gyakorlati riasztás: kutatók ~2000, publikusan elérhető MCP szervert vizsgálva azt találták, hogy mindegyik hitelesítés nélkül adott hozzáférést a belső tool-listákhoz — az ökoszisztéma ma még gyerekcipőben jár biztonsági érettség terén, ezért ez most versenyelőny, ha jól csinálod.

Források: [MCP hivatalos Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices), [Kiteworks — MCP enterprise security](https://www.kiteworks.com/cybersecurity-risk-management/model-context-protocol-enterprise-security/), [Descope — MCP server security](https://www.descope.com/blog/post/mcp-server-security-best-practices), [MCP Best Practice checklist](https://mcp-best-practice.github.io/mcp-best-practice/best-practice/)

---

## 5. Context engineering (Anthropic aktuális irányelvei)

- A "prompt engineering" helyett ma inkább "context engineering" a releváns keret: a cél a legkisebb, legmagasabb jel/zaj arányú token-készlet megtalálása, ami maximalizálja a kívánt kimenetet — a kontextusablak véges és drága erőforrás.
- **Compaction**: hosszan futó agenteknél a beszélgetés összefoglalása és új kontextusablakban való folytatása, kritikus döntések/hibák megőrzésével, redundáns tool-output eldobásával.
- **Tool-tervezés**: a tool leírását úgy írd meg, mintha egy új kollégának magyaráznád — egyértelmű paraméternevek (`user_id`, ne `user`), szigorú séma, hasznos, akcióra ösztönző hibaüzenetek nyers tracebackek helyett.
- A rendszer determinisztikus/valószínűségi határ elve (amit a repód pitch-e is használ) nem csak marketing-frázis — ez szó szerint Anthropic saját mérnöki filozófiája is: "As agents grow more capable, so does their potential blast radius. The engineering question is how to cap it."

Források: [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), [Anthropic — Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents), [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

---

## 6. Observability és eval-driven fejlesztés

2026-ra az "agent observability" önálló diszciplínává vált, elkülönülve a hagyományos APM-től és az egyszerű LLM-hívás-logolástól:

- A releváns kérdés nem az, hogy *mit* válaszolt az agent, hanem hogy *miért* döntött úgy, hogy ezt a tool-t hívja ebben a sorrendben — a teljes döntési láncot kell trace-elni, nem csak a végeredményt.
- **OpenTelemetry GenAI szemantikai konvenciók** (jelenleg kb. v1.41) — ma ez a vendor-semleges szabvány a trace-ekhez, érdemes erre építeni, nem egyedi log-formátumra.
- **Trace-to-dataset loop**: a production hibákat automatikusan eval/regressziós teszt-esetté kell alakítani — ez ma "table stakes", nem extra.
- Piaci szereplők tájékozódásra: Langfuse (ClickHouse alatt), Braintrust, Arize Phoenix, Fiddler — érdemes olyan stacket választani, ami OTel-kompatibilis, hogy ne kelljen egy év múlva lecserélni.

Források: [Digital Applied — AI Agent Observability 2026](https://www.digitalapplied.com/blog/ai-agent-observability-2026-tracing-monitoring-stack-guide), [Confident AI — Agent observability platformok](https://www.confident-ai.com/knowledge-base/compare/best-ai-agent-observability-tools-2026)

---

## 7. Cost governance (AI FinOps)

- Valós, **modellenkénti és tokenenkénti** követés, nem fix "becslés kérésenként" (pont ez volt a repód egyik hibája).
- **Model routing**: olcsó modell triage-re/egyszerű lépésekre, drágább modell csak ott, ahol tényleg kell.
- Multi-agent architektúránál számolj a 10-15x token-szorzóval (lásd 1. pont) — ez direkt költségvetési tétel, nem mellékes technikai részlet.
- A circuit breaker / kill-switch állapotát **megosztott, perzisztens tárban** kezeld (nem egy szolgáltatás-instance memóriájában) — szerverless/Lambda környezetben ez különösen fontos, mert minden konkurens végrehajtási környezet saját memóriát kap.

---

## 8. Human-in-the-loop magas kockázatú akciókra

- Az **EU AI Act 14. cikke** kötelezővé teszi az emberi felügyeleti interfészt és a megerősítési lépéseket magas kockázatú rendszereknél — ez uniós piacra szánt rendszereknél már ma jogi elvárás, nem csak jó gyakorlat.
- Iparági minta: minden visszafordíthatatlan vagy magas hatású akció (refund, adat-törlés, szerződés-módosítás) mögött legyen explicit jóváhagyási lépés, és legyen azonnali "kill switch" az agent-flottára.
- A jóváhagyás ne csak szoftveres legyen — komoly enterprise megoldásokban már hardware-alapú (hardverkulcs) emberi jóváhagyás jelenik meg kifejezetten agent-akciókra.

---

## 9. Összesített "production-ready" checklist

- [ ] Minden agentnek saját, első osztályú, visszavonható identitása van (nem megosztott kulcs)
- [ ] Az azonosítás forrása kizárólag authentikált csatorna (JWT/OIDC/sessionAttributes) — soha nem modell-generált paraméter
- [ ] Minden egyes akció (nem csak a kezdeti kérés) átmegy egy policy-ellenőrzésen — defense in depth minden tool-handlerben
- [ ] IAM/least privilege: nincs wildcard resource, nincs "majd a policy engine úgyis megfogja"
- [ ] Audit trail: tényleges, tamper-evident, append-only tár — nem stdout print
- [ ] Guardrails minden lépésre (nemcsak a kezdeti promptra) — ha van rá agent-specifikus API, azt használd
- [ ] Valós, tokenenkénti/modellenkénti cost tracking, élő budget-frissítéssel
- [ ] Circuit breaker/kill switch megosztott, perzisztens állapottal, automatikus recovery-vel
- [ ] Teljes döntési lánc trace-elve (OTel GenAI), production hibák → eval-dataset
- [ ] Adversarial/red-team tesztek: impersonation, tool-misuse, goal-hijack szimuláció — nem csak happy-path unit tesztek
- [ ] Magas kockázatú akciókhoz explicit human-in-the-loop jóváhagyás

---

## 10. Ami mindebből a te repódra vonatkozik

A jó hír: az architektúra-elveid (determinisztikus policy-réteg, strict schema, allowlist, audit-koncepció) pontosan lefedik a fenti keret vázát. A hiányok is pontosan a ma legforróbb iparági pontokra esnek — vagyis ha bezárod őket, nem egy elavult mintát követsz, hanem a *jelenlegi* frontvonalat:

1. Identitás → sessionAttributes/JWT-alapú kötés (1. és 2. pont fent) — a legnagyobb hatású javítás.
2. Per-operation authorization minden tool-handlerben, nem csak a kezdeti kérésben (2. és 4. pont).
3. Valódi, megosztott audit trail és circuit breaker state (9. pont checklist).
4. Adversarial tesztek hozzáadása a jelenlegi happy-path suite mellé (9. pont).
5. Fontold meg az OWASP ASI Top 10-et explicit checklistként a threat-model.md-be — ez azonnal hitelesebbé teszi a dokumentációt egy interjúban vagy risk review-n.
