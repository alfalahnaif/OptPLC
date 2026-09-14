# خط أساس اختبارات الخلفية

ملف حي: يُحدَّث كلما أُصلح اختبار أو تغيّرت الحصيلة. الهدف أن تصل الحصيلة إلى نجاح كل الاختبارات، أو أن يُوثَّق كل استثناء بسبب مقبول.

- **الإخفاقات المعروفة المسموح بها** مسجلة آليًا في `backend/app/tests/known_failures.txt`.
- **`scripts/check.ps1`** يفشل على أي إخفاق غير مدرج هناك.

## الحصيلة الحالية · 2026-09-14 · بعد P0-11

**141 اختبارًا: 107 نجح، و34 فشل كلها معروفة.** الفئة أ فيها 28 (C-01)، والفئة ج فيها 6 (القوالب).

الأمر، من داخل `backend/`:

```
.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

أو الفحص الكامل:

```
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

## القياس الأول · 2026-09-14 · بعد P0-04

- **الحصيلة:** 139 اختبارًا. **96 نجح و43 فشل**، في 33 ثانية، دون شبكة.
- **التحقق من العزل:**
  - بصمة `backend/plcforge.db` متطابقة قبل التشغيل وبعده.
  - ملفات النتائج الـ 14 متطابقة.
  - `E:\app\rag_db` لم يُنشأ.
- **هل سبّب العزل أيًّا من حالات الفشل؟** لا، بحسب رسائل الفشل. لم أتحقق بتشغيل الإعداد القديم لأنه غير آمن.

## تصنيف الإخفاقات

### أ. نتيجة للخطأ C-01: 28 اختبارًا، تُصلح في `P1-01`

مدقق regex الاحتياطي يرفض كل برنامج فيه `VAR_INPUT` و`VAR_OUTPUT` بخطأ `Mismatched VAR/END_VAR (1 VAR vs 3 END_VAR)`. النتيجة سلسلة من الأعطال: التحقق يعطي `SYNTAX_ERROR`، فيعطي وكيل التصحيح `invalid_variable_block`، ولا تصل حلقة الإصلاح إلى `VERIFIED`، ويرفض المحسِّن العمل.

| الملف | الاختبارات |
| --- | --- |
| `test_validation_agent` | `test_valid_motor_structured_text_returns_verified`، `test_motor_missing_emergency_stop_handling_returns_formal_violation`، `test_motor_stop_pb_open_circuit_behavior_returns_formal_violation`، `test_undeclared_assigned_variable_returns_syntax_error`، `test_traffic_conflicting_greens_return_formal_violation`، `test_tank_level_with_real_variables_and_safety_logic_returns_verified`، `test_matiec_unavailable_falls_back_to_static_validation` (انتقل من ب في P0-11) |
| `test_debugging_agent` | `test_verified_validation_returns_not_required`، `test_undeclared_variable_error_returns_targeted_advice`، `test_motor_formal_violation_returns_shutdown_patch_advice`، `test_traffic_formal_violation_returns_conflicting_green_advice`، `test_tank_formal_violation_returns_high_low_safety_advice`، `test_llm_mode_falls_back_to_rule_based` |
| `test_repair_loop` | `test_repair_loop_returns_immediately_when_code_is_verified`، `test_motor_missing_emergency_stop_is_repaired_and_verified`، `test_traffic_light_conflict_is_repaired`، `test_invalid_syntax_triggers_debugging_and_regeneration`، `test_repair_loop_report_is_stored_in_repository` |
| `test_optimization_agent` | `test_verified_motor_code_optimizes_and_remains_verified`، `test_optimization_report_is_stored_in_memory`، و`test_optimization_metrics_improve_or_stay_equal` و`test_rollback_occurs_if_optimization_pass_breaks_validation` (انتقلا من ب في P0-11) |
| `test_metrics_endpoint` | `test_metrics_after_optimization_uses_optimized_code_as_after_metrics` |
| `test_projects` | `test_debug_after_verified_validation_returns_not_required`، `test_optimize_persists_optimization_report`، `test_get_optimization_returns_same_persisted_report`، و`test_artifact_get_endpoints_return_persisted_values` (مرجّح) |
| `test_report_endpoint` | `test_report_includes_optimization_and_metrics_after_pipeline` |

**متوقع بعد إصلاح C-01:** قد تظهر أخطاء كانت مختفية خلفه، ومنها اثنان معروفان:

- `test_traffic_conflicting_greens_return_formal_violation` يتوقع المعرّف اليتيم `TL-1` (C-09).
- `test_undeclared_assigned_variable_returns_syntax_error` يتوقع كشف المتغيرات غير المعلنة، وهو ما يجب أن يضيفه فحص المحلل في P1-01.

### ب. اختبارات قديمة: 0، أُغلقت في `P0-11`

كانت 12 اختبارًا:

- 9 منها صارت تنجح بعد تحديثها لتطابق السلوك المقصود.
- 3 انتقلت إلى الفئة أ لأنها صارت تفشل بسبب C-01 وحده.

التفاصيل في `CHANGELOG.md`، في قيد P0-11.

### ج. اختبارات قوالب تكشف أخطاء حقيقية: 6 اختبارات، تُصلح في `P1-22`

**ما يقوله سجل git:** ملف `code_generation_agent.py` له ثلاثة commits فقط.

- **الأول (`6ea4a27`، مايو):** قالب المحرك يستخدم `Run_Cmd` و`Safety_OK` بمنطق متسق لزر إيقاف مفتوح عادةً. الـ commit التالي `0576978` لم يغيّر هذه الأسطر.
- **الثالث (`c2f05b2`، يوليو):** أعاد كتابة القالب إلى `Run_Latch`، وأعلن الزر مغلقًا عادةً.
- **الاختبارات:** تتوقع تصميمًا ثالثًا مغلقًا عادةً مع `Safety_OK`، **لا يوجد في أي commit**.

**C-10:** شرط التعشيق `Run_Latch := TRUE` وشرط الفصل كلاهما يحتوي `NOT Stop_PB` (`code_generation_agent.py:435-441`). حين يتحقق شرط التعشيق، يتحقق شرط الفصل أيضًا في المسح نفسه فيُلغيه. **فالمحرك لا يعمل أبدًا، أيًّا كان اصطلاح توصيل الزر.**

**C-11:** يُحسب `Batch_Complete := (Step_State = 3) AND Low_Level AND NOT Fault_State` بعد `CASE`. والـ `CASE` نفسه يعيد `Step_State` إلى 0 عندما يكون `Low_Level` صحيحًا، فتصبح `Batch_Complete` خطأً دائمًا. القالب الأول كان يستخدم خطوة إنهاء مستقلة (`Step = 50`).

| الملف | الاختبار |
| --- | --- |
| `test_code_generation_agent` | `test_motor_plan_generates_structured_text_program`، `test_different_domains_produce_different_code`، `test_motor_template_uses_normally_closed_stop_pb_semantics`، `test_batch_generation_includes_step_logic` |
| `test_projects` | `test_different_project_domains_generate_different_code`، `test_generate_code_persists_artifact` |

**الإصلاح (P1-22):**

- إعادة تصميم القالبين عمدًا.
- استبدال اختبارات النصوص الحرفية باختبارات سلوك عبر عدة مسوحات.

**الدلالة العلمية:** القواعد الساكنة أعطت قالب المحرك `VERIFIED` مع أنه لا يعمل، وهذا دليل مباشر على الحاجة إلى L3 وL4.

## أخطاء كشفتها الاختبارات وأُصلحت

| المعرّف | الخطأ | كيف اكتُشف | الإصلاح |
| --- | --- | --- | --- |
| C-12 | توليد الكود بوضع LLM ينهار دائمًا (`ValidationError: ragSources`) كلما نجح النموذج والـ RAG معطّل، وهذا المسار الافتراضي لـ `/generate` | اختبار جديد برد مبرمج في P0-11 | P0-11: `ragSources=rag_sources` |

## أخطاء كشفها التحقق ولم تُصلح بعد

| المعرّف | الخطأ | كيف اكتُشف | الإصلاح |
| --- | --- | --- | --- |
| C-13 | مجال `"Safety Interlock"` (مفرد) يُنتج خطة تعشيق صحيحة، لكن توليد الكود لا يقبل إلا `"safety interlocks"` (جمع)، فيستخدم القالب العام بمتغيرات غير معلنة، ولا يُترجم الكود | ترجمة القوالب الخمسة بـ MATIEC الحقيقي في الصورة المرجعية (P0-05) | `P1-22`، ومعه كشف المتغيرات غير المعلنة في `P1-01` |

**ملاحظة:** لا يوجد اختبار في الحزمة يغطي C-13 حاليًا، ولذلك لا يظهر في حصيلة pytest. سيُضاف له اختبار في P1-22.

## سجل الحصيلة

| التاريخ | البند | الاختبارات | نجح | فشل | ملاحظة |
| --- | --- | --- | --- | --- | --- |
| 2026-09-14 | P0-04 | 139 | 96 | 43 | أول تشغيل آمن ومعزول: 25 أ، و12 ب، و6 ج |
| 2026-09-14 | P0-11 | 141 | 107 | 34 | 28 أ، و0 ب، و6 ج. وكُشف C-12 وأُصلح |
