# Research Workbench v0.1 — Implementation Plan (แบบสั้น)

**Spec:** `docs/spec/2026-10-03-research-workbench-design.md`
**Stack:** Python ≥ 3.10 · `pyyaml` · `jsonschema` · `pytest` · venv แยกที่ `research-workbench/.venv`
**กติกา:** ทุก task เขียน test ก่อน → ทำให้ผ่าน → commit · tests ห้ามใช้ network · ไฟล์ทั้งหมด UTF-8

## ส่วนที่ต่างจาก spec เล็กน้อย
- รวม search ทั้ง 3 แหล่งไว้ใน `scripts/search.py` ไฟล์เดียว
- เพิ่ม ID `Q-nnn` สำหรับ search query และ `RUN-nnn` สำหรับ run
- เพิ่มไฟล์ `literature/candidates.jsonl`, `dedupe-log.csv`, `doi-verification.jsonl` และ `literature/fulltext/` (gitignored)
- Hook guard เพิ่ม 3 อย่าง:
  1. บล็อกไม่ให้โมเดลรัน `rw_state.py approve` เอง
  2. บล็อกการแก้ `spec.yaml` ของ experiment ที่ผ่าน G3 แล้ว
  3. บล็อกการแก้ `rw/state.json` ตรง ๆ
- Verification-agent แก้ไฟล์เองไม่ได้ (ไม่มี Write/Edit) ต้องบันทึกผลผ่าน `audit.py` เท่านั้น

## Tasks

| # | สร้างอะไร | Test ที่ต้องผ่าน |
|---|---|---|
| 1 | **Scaffold:** git init, `.venv`, `requirements.txt`, `pytest.ini`, LICENSE (MIT), `.gitignore`, `plugin.json`, `marketplace.json`, `scripts/rw_io.py` (หา workspace, อ่าน/เขียน json/jsonl/yaml/csv), `check_deps.py` | ภาษาไทยไม่ถูก escape, CSV ที่มี BOM/CRLF จาก Excel, path ที่มีเว้นวรรค, รันนอก workspace แล้วได้ error ที่อ่านเข้าใจ |
| 2 | **Schemas + validate:** `schemas/*.schema.json` (15 ชนิด), `validate.py`, `tests/wsfactory.py` (golden workspace ครบทุก ID) | golden workspace ผ่าน, evidence ไม่มี anchor, ID ซ้ำ, comment `addressed` ไม่มี `changed_ids`, error บอกเลขบรรทัด |
| 3 | **`ids.py`:** ออก ID ถัดไปของทุก prefix | ID ต่อจากของเดิม, workspace ว่าง, ID เกิน 999 |
| 4 | **`comments.py`:** summary / resolve / ตาราง markdown | กฎของแต่ละ status, มีบันทึกลง decision-log |
| 5 | **`trace.py`:** ตรวจสายหลักฐานตามกฎข้อ 5 ใน spec + `check_hypotheses` | golden ผ่าน + mutation tests 11 กรณี (dangling ID, support_level ผิด, ไม่มี literature check, O ที่ยังไม่ confirm, ผลจาก run ที่ fail, รันก่อนผ่าน G3, …) |
| 6 | **`audit.py`:** run / review / set-evidence-status / status | DOI ยังไม่ verify, comment `must` ที่ยังเปิดอยู่, verdict WEAKEN ต้อง block |
| 7 | **`rw_state.py`:** stage, advance, approve G1–G4, amend | ข้าม stage ไม่ได้, gate ไม่ผ่านต้องบอกเหตุผล, ถอยกลับต้องมี reason, G4 ถูก block ถ้ายังมี comment `must` เปิดอยู่ |
| 8 | **`init_workspace.py`** + `templates/workspace/` (CLAUDE.md, gitignore, protocol.example.yaml) | workspace ใหม่ผ่าน validate, ไม่เขียนทับ CLAUDE.md หรือ .gitignore เดิม (append แทน), init ซ้ำไม่ได้ |
| 9 | **`net.py`** (retry/backoff) + **`dedupe.py`** | retry เมื่อเจอ 503, 404 ไม่ retry, merge ด้วย DOI/title, ไม่ merge ถ้า DOI ต่างกัน |
| 10 | **`search.py`:** OpenAlex / Crossref / Semantic Scholar | parse fixture ทั้ง 3 แหล่ง, บันทึก search-log, ถ้าค้นล้มเหลวต้องบันทึก error และไม่มีผลปลอม |
| 11 | **`verify_doi.py`** (Crossref) | verified / mismatch / not-found / retracted |
| 12 | **`meeting.py`:** new / prep / add-observation / add-comment / attach-transcript / logged | `verbatim` ต้องมีข้อความอยู่ใน notes จริง, role ต้องเป็นผู้เข้าร่วม meeting, target ต้องมีอยู่จริง |
| 13 | **`experiment.py`** + **`claims.py`** | log run ได้หลังผ่าน G3 เท่านั้น, result ใช้ได้เฉพาะ metric ที่ประกาศไว้ใน spec, `support_level` คำนวณอัตโนมัติ |
| 14 | **`progress.py`:** สร้าง progress review จาก artifacts | ตัดรายการตามวันที่ review ครั้งก่อน, มีตารางผลและสถานะ comments, ไม่เขียนทับไฟล์เดิม |
| 15 | **Hooks:** `hook_validate.py`, `hook_guard.py`, `hooks/hooks.json` | artifact เสียได้ exit 2, ไม่มี deps ต้องไม่ block, approve ผ่าน Bash ถูกบล็อก, protocol หลัง G1 ถูกบล็อก |
| 16 | **Agents 6 ตัว** + test ตรวจ frontmatter | name ตรงกับชื่อไฟล์, มี tools ครบ, verification-agent ไม่มี Write |
| 17 | **Skills ชุด 1:** rw-init, rw-orchestrate, rw-approve, rw-protocol, rw-search, rw-evidence | frontmatter ถูก, script ที่อ้างถึงมีอยู่จริง, rw-approve มี `disable-model-invocation` |
| 18 | **Skills ชุด 2:** rw-meeting (+ คลังคำถามสำหรับหมอ/อาจารย์), rw-progress, rw-synthesize, rw-experiment, rw-audit | เหมือน task 17 |
| 19 | **README + smoke test จริงใน Claude Code** | `claude --plugin-dir` → `/rw-init` → `/rw-meeting` → `/rw-approve G1` ใช้ได้, pytest ผ่านทั้งหมด |

## จุดเสี่ยงที่ต้องเช็กตอน smoke test (task 19)
1. `${CLAUDE_SKILL_DIR}` ถูกแทนค่าใน SKILL.md จริงไหม
2. `` !`command` `` ใน rw-approve รันได้จริงไหม ถ้าไม่ได้ ให้ผู้ใช้รันเองด้วย `! python3 …/rw_state.py approve …`
3. `python3` ที่ hook ใช้มี `pyyaml`/`jsonschema` ไหม (ตอนนี้ `python3` ใน shell ชี้ไป venv ของ project อื่นที่ไม่มี yaml) ซึ่ง rw-init จะเช็กและบอกคำสั่งติดตั้งให้
