# إعادة التشغيل · ElCon-EE 2027 pilot

> **قاعدة:** لا شيء في `results/` يُكتب فوقه. كل إعادة تشغيل تُخرِج إلى مسار آخر، ثم تُقارن يدويًا.

## 1. ما يمكن إعادته اليوم

| البوابة | قابلة للإعادة؟ | الأمر |
| --- | --- | --- |
| **G2** | ✅ نعم، بلا Docker | §2 |
| **G3** | ⚠️ تحتاج بناء صورة nuXmv و`Dockerfile` فقط (الأرشيف يُنزَّل) | §4 |
| **G1** | ❌ لا، تحتاج الصورة المرجعية وMATIEC مع Docker مشغَّل | §5 |
| أداة التمييز لـ `M-M3` | ✅ نعم، Python خالص | §3 |

## 2. G2 · مدققات المجال الساكنة

من جذر المستودع، وببيئة الخلفية الافتراضية:

```powershell
$env:OPENAI_API_KEY = "dummy-not-used"   # لأن app.config تتحقق من الإعدادات عند الاستيراد
backend\.venv\Scripts\python.exe research\elcon2027\scripts\rerun_g2.py `
    --out "$env:TEMP\elcon_g2_rerun.json"
```

المتوقع (أُعيد في 2026-11-05): `E27-M01` 0/6، و`E27-I01` 0/6، و`E27-B01` 4/6 بالقواعد `BT-6` و`BT-7` و`BT-5` و`BT-7`. المجموع **4 من 18 = 22.22 %**، والمراجع الثلاثة `PASS`.

السكربت يقرأ فقط، ويرفض الكتابة داخل `research/elcon2027/results/`.

## 3. أداة التمييز لـ `M-M3`

```powershell
cd research\elcon2027\cases\E27-M01-motor
..\..\..\..\backend\.venv\Scripts\python.exe simulate_witness.py
```

تُقارن بـ `traces/M-M3_ground_truth_trace.csv`. **أداة تطوير، لا دليل:** منطقها كُتب يدويًا بـ Python ولم يُشتق من `reference.st`.

## 4. G3 · nuXmv

الأرشيف **غير مخزَّن في git** (الرخصة الأكاديمية لـ nuXmv لا تسمح بإعادة التوزيع، والحجم 24 MB). نزّله من <https://nuxmv.fbk.eu> وضعه في `research/tools/nuxmv/`:

| الملف | SHA256 | الحجم |
| --- | --- | --- |
| `nuXmv-2.2.0-linux64.tar.xz` | `d31709895ae2d7737e1e3c59eec9442c76527d2273380eaff6f3aea8cce9f946` | 24,790,208 بايت |

إصدار الأداة في التشغيل الأصلي، من ترويسة السجلات: `nuXmv 2.2.0 (compiled on Fri May 29 11:00:56 2026)`، مرتبط بـ NuSMV 2.7.0، وCUDD 2.4.1، وMiniSat، وMathSAT.

```bash
docker build -t optplc-nuxmv:2.2.0 research/tools/nuxmv
docker run --rm -v "$PWD/research/elcon2027:/work" optplc-nuxmv:2.2.0 \
    -dcx /work/cases/E27-M01-motor/formal/M-M3_reset_bypass.smv
```

> ⚠️ **لم يُعَد تشغيل G3 في 2026-11-05** لأن Docker Desktop لم يكن يعمل. ما تحقق هو تحليل السجلات المخزَّنة. والأمر أعلاه **أُعيد بناؤه من `Dockerfile` ومن ترويسة السجلات، ولم يكن مسجلًا في التشغيل الأصلي** (عيب 2.3 في `AUDIT_2026-11-05.md`). تحقق منه قبل الاعتماد عليه.

## 5. G1 · ترجمة MATIEC

الصورة المرجعية مطلوبة:

```powershell
docker build -f docker/app.Dockerfile -t optplc-backend:p0-05 .
powershell -ExecutionPolicy Bypass -File scripts\st-compile.ps1 `
    -Path research\elcon2027\cases\E27-M01-motor\mutants\M-M3_reset_bypass.st
```

يجب أن يُنفَّذ على 21 ملفًا (3 مراجع + 18 طفرة)، **وتُحفظ أكواد الخروج والمخرجات الخام** هذه المرة. المصنوع الأصلي معطوب (عيب 2.1 في `AUDIT_2026-11-05.md`)، فالنتيجة G1 = 0/18 **غير متحقَّق منها**. البند: `R1-A6`.

## 6. البصمات

```bash
sha256sum -c   # قارن بـ results/E27-I01/baseline_hashes.csv و results/E27-B01/baseline_hashes.csv
```

7 من 7 بصمات مطابقة في 2026-11-05. لا بصمات مخزَّنة لـ `E27-M01` (عيب 2.4).
