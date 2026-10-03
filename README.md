# research-workbench

Claude Code plugin ที่ให้ AI ช่วยทำงานวิจัยอย่างเป็นระบบ: **literature review → ความเห็นผู้เชี่ยวชาญ/อาจารย์ → hypothesis → การทดลอง ML → รายงานที่ทุก claim ไล่ย้อนไปหาหลักฐานได้**

หลักการ: agents ส่งงานกันผ่านไฟล์ที่มี schema ไม่ใช่บทสนทนา, งานที่ต้องได้ผลเหมือนเดิมทุกครั้งเป็น Python scripts, gate สำคัญอนุมัติโดยคุณเท่านั้น, และห้ามแต่งหลักฐาน

## ติดตั้ง

1. Python ≥ 3.10 ที่คำสั่ง `python3` ใช้ต้องมี `pyyaml` และ `jsonschema`
   ```bash
   python3 -m pip install --user pyyaml jsonschema   # Homebrew Python อาจต้องเติม --break-system-packages
   ```
   `/rw-init` จะเช็กให้อีกครั้ง ถ้าไม่มี package สองตัวนี้ hook ตรวจ artifact จะถูกข้ามแบบเงียบ ๆ
2. ติดตั้ง plugin ใน Claude Code
   ```
   /plugin marketplace add <github-user>/research-workbench
   /plugin install research-workbench@research-workbench
   ```
   หรือใช้จากโฟลเดอร์ในเครื่อง: `claude --plugin-dir /path/to/research-workbench`
3. (ไม่บังคับ) `export RW_MAILTO=you@example.com` เพื่อเข้า polite pool ของ OpenAlex/Crossref และ `export S2_API_KEY=…` สำหรับ Semantic Scholar

## เริ่มใช้งาน

```
/rw-init . --title "Stroke outcome prediction"   # ในโฟลเดอร์งานวิจัย (โฟลเดอร์ใหม่หรือที่มีอยู่แล้วก็ได้)
/rw-orchestrate                                   # ดูว่าอยู่ตรงไหนและต้องทำอะไรต่อ
```

| คำสั่ง | ใช้เมื่อ |
|---|---|
| `/rw-orchestrate` | ไม่แน่ใจว่าต้องทำอะไรต่อ หรือต้องการเดินงานต่อ |
| `/rw-protocol` | ตั้ง RQ, scope, criteria (หรือ amendment หลัง G1) |
| `/rw-search` | ค้น paper แบบ scoping หรือ literature check ของ hypothesis |
| `/rw-evidence` | screen paper + ดึงหลักฐานพร้อมหน้า/ตาราง + verify |
| `/rw-meeting` | `new` / `prep` / `log` การปรึกษาหมอหรือ review กับอาจารย์ |
| `/rw-progress` | สร้างเอกสาร progress review สำหรับอาจารย์ |
| `/rw-synthesize` | สังเคราะห์หลักฐาน + เสนอ hypothesis |
| `/rw-experiment` | `design` (spec ก่อนรัน) / `record` (run + result) |
| `/rw-audit` | ตรวจ DOI, สายหลักฐาน, comments, claims ก่อน release |
| `/rw-approve` | **คุณเท่านั้น:** `G1` `G2 [H-…]` `G3 X-…` `G4` `amend <file> --note …` |

## สายหลักฐาน

```
       E (paper) ─┐
O (หมอ/อาจารย์) ──┼─► H ─► X ─► R ─► C (claim ในรายงาน)
R (ผลเดิม/EDA) ───┘    ▲
                       └── K (comment) สั่งแก้ H, X, R หรือ C
```

| ID | ความหมาย | ID | ความหมาย |
|---|---|---|---|
| `RQ-n` | research question | `H-nnn` | hypothesis (origin: literature/expert/advisor/data-exploration) |
| `Q-nnn` | search query ที่รันจริง | `X-nnn` | experiment spec |
| `S-nnn` | paper/record | `RUN-nnn` | run ของ experiment (รวมที่ fail) |
| `E-nnn` | evidence พร้อม anchor | `R-nnn` | result |
| `M-nnn` | meeting | `C-nnn` | claim ในรายงาน |
| `O-nnn` | observation จากคน | `K-nnn` | comment / action item |

Gates: **G1** protocol → **G2** hypotheses (ต้องผ่าน literature check) → **G3** experiment spec (ก่อนรัน) → **G4** release (ต้องไม่มี comment `must` ค้าง และ audit ต้องสะอาด)

## ความเป็นส่วนตัว
- ข้อมูลผู้ป่วยอยู่ใน `data/` ของ workspace เท่านั้น และถูก gitignore
- PDF (`literature/fulltext/`), outputs ของ experiment และ transcript ก็ถูก gitignore
- repo นี้ (ตัว tool) ไม่มีข้อมูลวิจัยใด ๆ

## พัฒนา
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```
Spec: `docs/spec/` · แผน: `docs/plan/`

## License
MIT ได้แนวคิดจาก academic-research-skills, PRISMA 2020 และ Anthropic multi-agent research system แต่ไม่ได้คัดลอกโค้ดหรือเนื้อหามา
