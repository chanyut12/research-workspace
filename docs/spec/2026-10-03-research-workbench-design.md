# Research Workbench — Design Spec (v0.1)

- **วันที่:** 2026-10-03
- **สถานะ:** Draft รอ review (rev 2: เพิ่ม meetings, observations, advisor comments)
- **ที่มา:** `Research Agent Stack สำหรับ Claude Code.md`, `การออกแบบทีม Multi-Agent สำหรับงานวิจัยอย่างเป็นระบบ.md` และ use case จริงของผู้ใช้

## 1. เป้าหมาย

สร้าง Claude Code plugin ส่วนตัวที่ push ขึ้น GitHub แล้วติดตั้งใช้ได้ทันที ให้ AI ช่วยทำงานวิจัยหนึ่งชิ้นแบบเป็นระบบ โดยความรู้มาจาก **สองแหล่ง** คือ **literature** และ **คน** (การปรึกษาแพทย์ผู้เชี่ยวชาญ, progress review กับอาจารย์ และข้อสังเกตของผู้วิจัยเอง) จากนั้นต่อไปที่ hypothesis → การทดลอง ML → รายงาน ทุกขั้นเชื่อมกันด้วย ID และ claim ทุกข้อในรายงานไล่ย้อนกลับไปหาที่มาได้

**งานนำร่อง:** งานวิจัย stroke (มี dataset อยู่แล้ว ปรึกษาแพทย์ และ review progress กับอาจารย์เป็นระยะ)

**Use cases หลัก**
1. ทำ literature review อย่างมี protocol
2. บันทึกการปรึกษาแพทย์ แล้วแปลงข้อสังเกตเป็น hypothesis ที่ทดสอบได้
3. เตรียม progress review ให้อาจารย์ บันทึก comments และตามว่าแต่ละข้อจัดการแล้วหรือยัง
4. ออกแบบ บันทึก และ link การทดลอง ML กลับไปหา hypothesis
5. เขียนรายงานที่ทุก claim มีหลักฐาน

**เกณฑ์ความสำเร็จของ v0.1**
1. ติดตั้งด้วย `/plugin marketplace add <owner>/research-workbench` แล้วใช้ skills ได้
2. `/rw-init` สร้าง workspace ใหม่ได้ และ workspace นั้นผ่าน `validate.py`
3. Scripts ทุกตัวมี pytest และผ่านโดยไม่ต้องใช้ network
4. รันงาน stroke ได้อย่างน้อยหนึ่งรอบ ครอบคลุม: บันทึก meeting กับแพทย์ 1 ครั้ง → hypothesis ที่ origin = expert พร้อม literature check → experiment → progress review กับอาจารย์ → comments ถูก address → audit ผ่าน

## 2. หลักการ

1. **Tool แยกจากข้อมูล** — repo นี้ไม่มีข้อมูลวิจัยเลย ข้อมูลอยู่ใน workspace ของแต่ละงาน และ `data/` ถูก gitignore เสมอ (ข้อมูลผู้ป่วยต้องไม่หลุดขึ้น GitHub)
2. **Artifacts คือ shared state** — agents ส่งงานต่อกันผ่านไฟล์ที่มี schema ไม่ใช่ผ่านบทสนทนา
3. **งาน deterministic เป็น script** — ได้แก่ state transition, schema validation, dedupe, DOI check และ trace ส่วน LLM ใช้กับงานที่ต้องใช้ judgment เท่านั้น
4. **ห้ามแต่งหลักฐาน** — ห้ามสร้าง paper, DOI, ตัวเลข, ผลการทดลอง หรือ **คำพูดของคนจริง** จาก memory ของโมเดล
5. **ความรู้จากคนเป็นหลักฐานชั้นหนึ่ง แต่ติดป้ายชัดเจน** — ข้อสังเกตจากแพทย์/อาจารย์ใช้เป็นที่มาของ hypothesis ได้ แต่ในรายงานต้องแสดงเป็น expert opinion ไม่ใช่ข้อเท็จจริงที่พิสูจน์แล้ว
6. **มนุษย์เป็น PI** — gate สำคัญอนุมัติได้โดยผู้ใช้เท่านั้น
7. **License** — ใช้ MIT และเขียนเนื้อหาเองทั้งหมด ไม่ copy ไฟล์จาก `academic-research-skills` (CC BY-NC 4.0) เอามาเฉพาะแนวคิด

## 3. โครงสร้าง Tool Repo

```
research-workbench/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   ├── rw-init/           สร้าง workspace จาก templates/
│   ├── rw-orchestrate/    orchestrator: อ่าน state → บอกขั้นถัดไป → เรียก agent
│   ├── rw-approve/        อนุมัติ gate (ผู้ใช้เรียกเองเท่านั้น)
│   ├── rw-protocol/       RQ, scope, eligibility criteria, sources
│   ├── rw-search/         query strategy + ค้นจริง (รวม literature check ของ hypothesis)
│   ├── rw-evidence/       screening + extraction → evidence.jsonl
│   ├── rw-meeting/        prep / log การปรึกษาแพทย์และ review กับอาจารย์ → O, K
│   ├── rw-progress/       สร้างเอกสาร progress review
│   ├── rw-synthesize/     synthesis + hypotheses ที่อ้าง E / O / R
│   ├── rw-experiment/     experiment spec → run log → results
│   └── rw-audit/          ตรวจ citation + ตรวจสายหลักฐาน + สถานะ comments
├── agents/
│   ├── protocol-designer.md
│   ├── discovery-agent.md
│   ├── evidence-analyst.md
│   ├── synthesis-agent.md
│   ├── experiment-agent.md
│   └── verification-agent.md
├── scripts/
│   ├── rw_state.py        state machine + gates
│   ├── validate.py        ตรวจ artifact ตาม schemas/
│   ├── ids.py             ออก ID ถัดไปของแต่ละ prefix (ป้องกัน ID ชน)
│   ├── dedupe.py          DOI → arXiv/PMID → normalized title+year
│   ├── verify_doi.py      ตรวจ DOI กับ Crossref/OpenAlex
│   ├── trace.py           ตรวจสายหลักฐาน (ดูข้อ 5)
│   ├── comments.py        สรุปสถานะ comments (open/addressed/declined/deferred)
│   ├── search_openalex.py
│   ├── search_crossref.py
│   └── search_s2.py       Semantic Scholar (ใช้ API key ถ้ามี)
├── schemas/               JSON Schema หนึ่งไฟล์ต่อหนึ่ง artifact type
├── hooks/hooks.json
├── templates/
│   ├── workspace/         ไฟล์ตั้งต้นของ workspace
│   ├── meeting-prep.md    แม่แบบคำถามก่อนประชุม (consult / review)
│   └── progress-review.md แม่แบบเอกสาร progress
├── tests/                 pytest + fixtures (มี recorded API responses)
├── docs/spec/
├── README.md
└── LICENSE                MIT
```

**Runtime:** Python ≥ 3.10 และ dependencies มีเพียง `pyyaml` กับ `jsonschema` (HTTP ใช้ `urllib` จาก stdlib) Skills เรียก script ผ่าน `${CLAUDE_PLUGIN_ROOT}/scripts/...`

**หมายเหตุ:** skills จาก plugin จะถูก namespace เป็น `/research-workbench:rw-init` เป็นต้น ในเอกสารนี้เขียนย่อเป็น `/rw-init`

## 4. โครงสร้าง Workspace (สร้างโดย `/rw-init`)

```
stroke-study/
├── CLAUDE.md                   กฎประจำงาน (non-fabrication, ID rules, privacy)
├── .gitignore                  data/, experiments/*/outputs/, meetings/**/transcript.*
├── rw/
│   ├── state.json              stage ปัจจุบัน, gates, protocol_version
│   └── decision-log.jsonl      ทุก transition / approval / amendment
├── protocol/
│   ├── protocol.yaml           RQ, criteria, sources, date range
│   └── amendments/             การแก้ protocol หลัง G1
├── literature/
│   ├── search-log.csv          query_id, purpose, source, exact query, filters, timestamp, count
│   ├── raw/                    raw API responses
│   ├── records.jsonl           normalized + deduped (S-xxx)
│   ├── screening.csv           S-id, stage, decision, reason_code, confidence
│   ├── evidence.jsonl          E-xxx
│   └── references.bib
├── meetings/
│   ├── M-001-2026-10-05-consult/
│   │   ├── meeting.yaml        type, date, participants (role), agenda, prep questions
│   │   ├── notes.md            notes ที่ผู้ใช้จด (รูปแบบหลัก)
│   │   └── transcript.txt      ถ้ามี (gitignored โดย default)
│   ├── observations.jsonl      O-xxx
│   └── comments.jsonl          K-xxx
├── synthesis/
│   ├── synthesis.md
│   └── hypotheses.yaml         H-xxx
├── experiments/X-001/
│   ├── spec.yaml               hypothesis, dataset version, metrics, seeds, analysis plan
│   ├── runs.jsonl              ทุก run รวม run ที่ fail (code commit, env, params)
│   └── results.jsonl           R-xxx
├── progress/
│   └── 2026-10-10-review.md    เอกสารที่ใช้คุยกับอาจารย์
├── data/                       (gitignored)
└── report/
    ├── claims.jsonl            C-xxx
    ├── report.md
    └── audit.json
```

## 5. ระบบ ID และสายหลักฐาน

| Prefix | สิ่งที่แทน | ต้องอ้างถึง / field บังคับ |
|---|---|---|
| `RQ-n` | Research question | — |
| `S-nnn` | Study/record จาก database | source + identifier (DOI/arXiv/PMID) จาก API จริง |
| `E-nnn` | Evidence จาก paper | `S-id` + anchor (page/section/table) + `RQ-id` |
| `M-nnn` | Meeting | `type` (`expert-consult` / `advisor-review` / `self-note`), `date`, `participants` (role; ชื่อใส่หรือไม่ก็ได้) |
| `O-nnn` | Observation จากคน | `M-id` + `speaker_role` + `statement` + `form` (`verbatim` / `paraphrase`) + `basis` (`clinical-experience` / `domain-rule` / `anecdote` / `data-impression`) |
| `K-nnn` | Comment / action item | `M-id` + `target` (ID ของ H/X/R/C หรือ `general`) + `severity` (`must` / `should` / `consider`) + `status` + `resolution` |
| `H-nnn` | Hypothesis | `origin` (`literature` / `expert` / `advisor` / `data-exploration`) + อ้าง `E`, `O` หรือ `R` อย่างน้อย 1 รายการ + `literature_checks` (query_id ใน search-log) |
| `X-nnn` | Experiment | `H-id` |
| `R-nnn` | Result | `X-id` + run id ใน `runs.jsonl` |
| `C-nnn` | Claim ในรายงาน | อ้าง `E`, `O` และ/หรือ `R` อย่างน้อย 1 รายการ + `support_level` คำนวณจากที่มา |

**สายหลักฐาน**

```
       E (paper) ─┐
O (แพทย์/อาจารย์) ─┼─► H ─► X ─► R ─► C
R (ผลเดิม/EDA) ───┘    ▲
                       └── K (comment) สั่งแก้ H, X, R หรือ C ได้
```

**กฎของ `trace.py`** (ถ้าผิดข้อใดข้อหนึ่ง = fail)
- ทุก ID ที่ถูกอ้างต้องมีอยู่จริง (ไม่มี dangling reference)
- `S` ที่มี evidence ต้องมี `screening.decision = include`
- `E` ต้องมี anchor และ `verification_status` ไม่ใช่ `rejected`
- `O` ต้องชี้ไปยัง `M` ที่มีอยู่จริง และ `confirmed_by_user = true`
- `H` ต้องอ้าง `E`, `O` หรือ `R` อย่างน้อยหนึ่งรายการ
- `H` ทุกตัวต้องมี `literature_checks` อย่างน้อย 1 รายการ ซึ่งเป็น search ที่ตั้งใจหาทั้งงานที่สนับสนุนและงานที่ขัดแย้ง (ผล 0 รายการถือว่าผ่าน และบันทึกเป็น potential gap) สำหรับ origin = `literature` ต้องมี search ที่ตั้งใจหางานที่ขัดแย้งอย่างน้อย 1 รายการ (`purpose = contradicting`) ส่วน query ที่ทำให้ได้ E นั้นมานับเป็นฝั่งสนับสนุนได้
- `R` ต้องชี้ไปยัง run ที่มีอยู่จริงใน `runs.jsonl`
- `C` ต้องอ้าง `E`, `O` หรือ `R` และในรายงานทุก `[C-xxx]` ต้องอยู่ใน `claims.jsonl`
- `C` ที่อ้างเพียง `O` ต้องมี `support_level = expert-opinion` (ห้ามเขียนเป็นข้อเท็จจริงที่พิสูจน์แล้ว)

**รายงานสรุปของ `trace.py`:** hypothesis แยกตาม origin, hypothesis ที่ยังไม่ได้ทดสอบ, observation ที่ยังไม่ได้ใช้, claim ที่ไม่มีหลักฐาน และ comments ที่ยัง open

## 6. Workflow และ Gates

```
INIT → SCOPED ─[G1]→ PROTOCOL_APPROVED → LITERATURE → SYNTHESIZED ─[G2]→ HYPOTHESES_APPROVED
     ─[G3]→ EXPERIMENTING → RESULTS_VALIDATED → WRITING → AUDITED ─[G4]→ RELEASED
```

| Gate | สิ่งที่ผู้ใช้อนุมัติ | เงื่อนไขที่ script ตรวจก่อน |
|---|---|---|
| G1 | Protocol (RQ, criteria, sources) | `protocol.yaml` ผ่าน validate |
| G2 | Hypotheses ที่จะทดสอบ | H ทุกตัวมีที่มาและ literature check |
| G3 | Experiment spec (metrics, split, analysis plan) ก่อนรัน | spec อ้าง H ที่อนุมัติแล้ว |
| G4 | Release รายงานสุดท้าย | `trace.py` ผ่าน, `audit.json` ไม่มี blocking issue, **ไม่มี comment `severity=must` ที่ยัง `open`** |

- `rw_state.py advance <stage>` ตรวจเงื่อนไขก่อนเปลี่ยน stage
- การอนุมัติ gate ทำผ่าน `/rw-approve G<n>` ซึ่งตั้ง `disable-model-invocation: true` ทำให้โมเดลเรียกเองไม่ได้ ทุกการอนุมัติถูกบันทึกลง `decision-log.jsonl`
- เดินย้อนได้ เช่น `EXPERIMENTING → LITERATURE` เมื่อพบ evidence gap หรือเมื่อ comment จากอาจารย์ต้องการให้กลับไปแก้ โดยต้องบันทึกเหตุผลและ `K-id` ที่เป็นต้นเหตุใน decision-log
- **Hypothesis ใหม่เพิ่มได้ทุกเวลา** (เช่นหลังคุยกับแพทย์ระหว่างทดลอง) แต่ต้องผ่าน G2 ของตัวเองก่อนสร้าง experiment
- **Meetings เป็น event ไม่ใช่ stage** บันทึกได้ทุก stage โดยไม่เปลี่ยน state

## 7. Meetings, Observations และ Comments

### `/rw-meeting prep <type>`
อ่าน state ปัจจุบันแล้วสร้างรายการคำถามลง `meeting.yaml` (field `prep_questions`)
- **expert-consult (แพทย์):** ความสมเหตุสมผลทางคลินิกของ hypothesis/feature, ความน่าเชื่อถือของ label และตัวแปร, confounder ที่ควรคุม, ผลที่ดูขัดกับประสบการณ์คลินิก
- **advisor-review (อาจารย์):** ใช้ร่วมกับ `/rw-progress` และระบุ decision ที่ต้องการให้อาจารย์ตัดสิน

### `/rw-meeting log <M-id>`
1. รับ input จาก `notes.md` (รูปแบบหลัก: ข้อความสั้นที่ผู้ใช้จดเอง) หรือ `transcript.txt` (บางครั้ง)
2. โมเดลเสนอรายการ O และ K ที่ดึงได้ แต่ละรายการแสดงข้อความต้นฉบับที่ใช้อ้าง
3. **ผู้ใช้ยืนยัน แก้ หรือทิ้งทีละรายการ** ก่อนบันทึก (`confirmed_by_user = true`) เพราะเป็นการระบุว่าคนจริงพูดอะไร
4. ถ้า O ใดดูทดสอบได้ ให้เสนอ draft hypothesis (origin = `expert`) ให้ผู้ใช้เลือกว่าจะสร้างหรือไม่

**Notes:** รับข้อความที่สั้นและไม่เป็นทางการ (bullet, ภาษาไทยปนอังกฤษ) และไม่บังคับรูปแบบ
**Transcript:** ถ้ายาว ให้อ่านทีละช่วง O/K ทุกรายการต้องอ้างช่วงเวลาหรือบรรทัดใน transcript และ `form = verbatim` ใช้ได้เฉพาะข้อความที่ตรงกับ transcript จริง

### `/rw-progress`
สร้าง `progress/<date>-review.md` จาก artifacts (ห้ามเขียนจาก memory) ประกอบด้วย:
1. สิ่งที่ทำไปตั้งแต่ review ครั้งก่อน (จาก decision-log)
2. ผลการทดลองล่าสุด (อ้าง R พร้อมตัวเลขจาก `results.jsonl`)
3. สถานะ comments ทุกข้อจาก review ก่อน ๆ (จาก `comments.py`)
4. Hypotheses ใหม่และที่มา
5. คำถามหรือ decision ที่ต้องการจากอาจารย์

หลังประชุม ใช้ `/rw-meeting log` เพื่อบันทึก comments ใหม่

### วงจรชีวิตของ comment
`open` → `addressed` (ต้องระบุ artifact/ID ที่เปลี่ยน) / `declined` (ต้องมีเหตุผล) / `deferred` (ต้องระบุว่าเลื่อนไปเมื่อไร)

## 8. Orchestrator และ Agents

**Orchestrator เป็น skill ที่รันใน main session ไม่ใช่ subagent** เพราะ subagent ใน Claude Code สร้าง subagent ต่อไม่ได้ หน้าที่ของมันคือ อ่าน `state.json` → บอกผู้ใช้ว่าอยู่ขั้นไหน ขั้นถัดไปคืออะไร และมี comment หรือ observation ที่ค้างอยู่หรือไม่ → เรียก agent ที่เกี่ยวข้องพร้อม task packet → validate output → เสนอ transition

| Agent | ใช้เมื่อ | เขียน | ห้าม |
|---|---|---|---|
| protocol-designer | SCOPED | `protocol.yaml` | ค้นหา paper |
| discovery-agent | LITERATURE, literature check ของ H | `search-log.csv`, `raw/`, `records.jsonl` | screen, แก้ criteria |
| evidence-analyst | LITERATURE | `screening.csv`, `evidence.jsonl` | สังเคราะห์ข้าม paper |
| synthesis-agent | SYNTHESIZED | `synthesis.md`, `hypotheses.yaml` | ค้นเว็บเพิ่ม, เพิ่ม source ใหม่, สร้าง O เอง |
| experiment-agent | EXPERIMENTING | `spec.yaml`, `runs.jsonl`, `results.jsonl` | เปลี่ยน metric/split หลัง G3, ตัด run ที่ fail ทิ้ง |
| verification-agent | WRITING→AUDITED | `audit.json` | แก้รายงานหรือ artifact ของคนอื่น |

**Task packet** (orchestrator ส่งให้ agent ทุกครั้ง): `task_id`, `objective`, `inputs`, `required_outputs`, `prohibited_actions` และ `stop_conditions`

**งานที่ทำใน main session (ไม่แยก agent):** การดึง O/K จาก meeting และการเขียน progress review เพราะผู้ใช้ต้องยืนยันแบบโต้ตอบ รวมถึงการเขียนรายงาน (ขั้น WRITING) ซึ่งเขียนได้เฉพาะจาก `claims.jsonl` เท่านั้น

**Experiment agent** ไม่ได้เขียนโมเดลแทนผู้ใช้ทั้งหมด โค้ด ML อยู่ใน workspace หน้าที่ของ agent คือบันทึกและ link ให้ครบ และใช้ร่วมกับ skill `ml-model-advisor` และ `stroke-research-expert` ที่ผู้ใช้มีอยู่แล้วได้

## 9. Hooks (v0.1)

1. **PostToolUse (Write|Edit)** — ถ้าไฟล์ที่เขียนเป็น artifact ที่มี schema ให้รัน `validate.py` กับไฟล์นั้น ถ้าไม่ผ่านให้ส่ง error กลับไปให้โมเดลแก้
2. **PreToolUse (Write|Edit)** — หลัง G1 ห้ามแก้ `protocol/protocol.yaml` ตรง ๆ ต้องเขียน amendment ใน `protocol/amendments/` แทน

Hooks ทำงานเฉพาะเมื่อ cwd เป็น workspace (มี `rw/state.json`) ถ้าไม่ใช่ให้ผ่านไปโดยไม่ทำอะไร

## 10. การจัดการข้อผิดพลาด

- **API ล่มหรือติด rate limit:** retry 3 ครั้งแบบ backoff แล้วเขียนลง `literature/retrieval-errors.jsonl` และหยุดขอการตัดสินใจจากผู้ใช้ ห้ามเติมผลจาก memory
- **DOI resolve ไม่ได้:** ให้สถานะ `not-found` และ claim ที่อ้างถึงจะถูก audit block
- **Full text เข้าถึงไม่ได้:** `screening.decision = awaiting-retrieval` ไม่ใช่ exclude
- **ความมั่นใจต่ำ:** ใช้สถานะ `needs-human` ห้ามบังคับให้เป็น include/exclude
- **Notes กำกวม:** ถ้าไม่แน่ใจว่าใครพูดหรือหมายถึงอะไร ให้ถามผู้ใช้ ห้ามเดา
- **Notes/transcript มีข้อมูลระบุตัวคนไข้:** เตือนผู้ใช้ และไม่คัดลอกข้อมูลนั้นลง O/K
- **Script พบ artifact เสีย:** exit code ≠ 0 พร้อมข้อความระบุไฟล์ บรรทัด และ field

## 11. Testing

- **Unit tests (pytest):** `rw_state` (transition ที่ถูก/ผิด, gate, G4 block เมื่อมี comment `must` ที่ open), `validate` (artifact ดี/เสีย), `ids`, `dedupe`, `trace`, `comments`, `verify_doi` และ search scripts โดยใช้ recorded responses ใน `tests/fixtures/` ไม่ต้องใช้ network
- **Fixture workspace:** mini workspace สมบูรณ์ 1 ชุด
  - 2 studies, 3 evidence
  - 2 meetings (consult 1, review 1), 2 observations, 2 comments
  - 2 hypotheses (origin `literature` 1, `expert` 1)
  - 1 experiment, 2 results, 4 claims (หนึ่งข้อเป็น expert-opinion)

  ใช้เป็น golden test ของ `trace.py`
- **Mutation tests:** ต้องให้ trace/validate จับได้ทุกกรณีต่อไปนี้
  - ลบ evidence ที่ถูกอ้าง
  - ใส่ DOI ผิด
  - ใส่ claim ที่ไม่มี source
  - H ที่ไม่มี literature check
  - O ที่ยังไม่ confirmed
  - claim ที่อ้าง O อย่างเดียวแต่ไม่ติดป้าย expert-opinion
- **Smoke test (manual):** `claude --plugin-dir ./research-workbench` → `/rw-init` → workspace ผ่าน validate → `/rw-meeting log` กับ notes ตัวอย่าง

## 12. นอกขอบเขต v0.1

- Adapter สำหรับ Codex/Cursor/IDE อื่น (v0.2: แยก core skills ที่ไม่ผูกกับ host ออกมา)
- ถอดเสียงจากไฟล์เสียงเอง (v0.1 รับเฉพาะ transcript ที่เป็นข้อความแล้ว)
- Zotero MCP, PaperQA2, ASReview
- Dual screening และ adversarial reviewer agent
- Dashboard / UI
- รันโมเดล ML ให้อัตโนมัติ

## 13. คำถามที่ยังเปิดอยู่ (ไม่ block v0.1)

- ปลายทางของงาน stroke คือ thesis, paper หรือรายงานภายใน ซึ่งมีผลต่อ template ของ `report.md` และ `progress-review.md` ใน v0.2
- GitHub owner/ชื่อ repo สุดท้าย (ตอนนี้ใช้ `research-workbench`)
