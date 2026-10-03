<!-- research-workbench -->
# {{TITLE}} — Research Workspace

สร้างเมื่อ {{DATE}} ด้วย research-workbench · ถ้าไม่แน่ใจว่าต้องทำอะไรต่อ ให้ใช้ `/rw-orchestrate`

## กฎที่ห้ามละเมิด
1. ห้ามสร้าง paper, DOI, ตัวเลข, ผลการทดลอง หรือคำพูดของคนจริงจาก memory ทุกอย่างต้องมาจาก artifact ใน workspace หรือ API จริง
2. ทุก artifact มี ID (`RQ S E M O K H X R C`, `Q` = search, `RUN` = run) ออก ID ด้วย scripts เสมอ ห้ามตั้งเอง
3. Gate G1–G4 และ protocol amendment อนุมัติโดยผู้ใช้ผ่าน `/rw-approve` เท่านั้น
4. ห้ามแก้ `protocol/protocol.yaml` หลัง G1 ให้เขียน amendment ใน `protocol/amendments/` แทน
5. Observation และ comment จาก meeting บันทึกได้หลังผู้ใช้ยืนยันทีละรายการเท่านั้น
6. Claim ที่อ้าง O อย่างเดียวคือ expert opinion ห้ามเขียนเหมือนข้อเท็จจริงที่พิสูจน์แล้ว
7. ห้ามลบ run ที่ fail และห้ามเปลี่ยน metric หรือ split หลัง G3
8. งานสำรวจ (`kind: exploratory`) ใช้ตั้ง hypothesis ได้แต่ใช้ยืนยันไม่ได้ และ hypothesis ทุกข้อที่ทดลองแล้วต้องมี verdict แม้ผลจะเป็นลบ
9. ข้อมูลผู้ป่วยอยู่ใน `data/` เท่านั้น ห้ามคัดลอกข้อมูลที่ระบุตัวบุคคลได้ลง artifact อื่น

## โครงสร้าง
- `rw/` state + decision log (เขียนผ่าน `rw_state.py` เท่านั้น)
- `protocol/` RQ, criteria, amendments
- `literature/` search log, records (S), screening, evidence (E); วาง PDF ที่ download มาใน `literature/inbox/` แล้วใช้ `/rw-search import` (full text gitignored)
- `meetings/` M-xxx (notes), observations (O), comments (K)
- `synthesis/` synthesis.md, hypotheses (H)
- `experiments/X-xxx/` spec, runs, results (R)
- `progress/` เอกสาร progress review
- `report/` claims (C), report.md, audit.json
- `data/` dataset (gitignored)
