# خط أساس اختبارات الخلفية

ملف حي: يُحدَّث كلما أُصلح اختبار أو تغيّرت الحصيلة. الهدف أن تصل الحصيلة إلى نجاح كل الاختبارات، أو أن يُوثَّق كل استثناء بسبب مقبول.

## القياس الأول · 2026-09-14 · بعد P0-04

- **الفرع:** `p0/P0-04-hermetic-backend-tests`، من `staging @ b3acb5a`.
- **الأمر:** من داخل `backend/`:

  ```
  .venv\Scripts\python -m pytest -q -p no:cacheprovider
  ```

- **الحصيلة:** 139 اختبارًا. **96 نجح و43 فشل**، في 33 ثانية، دون أي اتصال بالشبكة.
- **التحقق من العزل:**
  - بصمة `backend/plcforge.db` متطابقة قبل التشغيل وبعده.
  - ملفات النتائج الـ 14 متطابقة في بصمتها المجمعة.
  - `E:\app\rag_db` لم يُنشأ.
  - المجلد المؤقت للاختبارات حُذف بعد الانتهاء.
- **هل سبّب العزل أيًّا من حالات الفشل؟** لا، بحسب رسائل الفشل. لا توجد حالة فشل تعتمد على رد LLM حقيقي. لم أتحقق بتشغيل الإعداد القديم لأنه غير آمن.

## تصنيف حالات الفشل الـ 43

**التصنيف مُراجَع في 2026-09-14** بعد مقارنة القوالب في سجل git. نُقلت 4 اختبارات من ب إلى ج.

### أ. نتيجة للخطأ C-01: 25 اختبارًا، تُصلح في `P1-01`

مدقق regex الاحتياطي يرفض كل برنامج فيه `VAR_INPUT` و`VAR_OUTPUT` بخطأ `Mismatched VAR/END_VAR (1 VAR vs 3 END_VAR)`. النتيجة سلسلة من الأعطال: التحقق يعطي `SYNTAX_ERROR`، فيعطي وكيل التصحيح `invalid_variable_block`، ولا تصل حلقة الإصلاح إلى `VERIFIED`، ويرفض المحسِّن العمل (HTTP 400).

| الملف | الاختبارات |
| --- | --- |
| `test_validation_agent` | `test_valid_motor_structured_text_returns_verified`، `test_motor_missing_emergency_stop_handling_returns_formal_violation`، `test_motor_stop_pb_open_circuit_behavior_returns_formal_violation`، `test_undeclared_assigned_variable_returns_syntax_error`، `test_traffic_conflicting_greens_return_formal_violation`، `test_tank_level_with_real_variables_and_safety_logic_returns_verified` |
| `test_debugging_agent` | `test_verified_validation_returns_not_required`، `test_undeclared_variable_error_returns_targeted_advice`، `test_motor_formal_violation_returns_shutdown_patch_advice`، `test_traffic_formal_violation_returns_conflicting_green_advice`، `test_tank_formal_violation_returns_high_low_safety_advice`، `test_llm_mode_falls_back_to_rule_based` |
| `test_repair_loop` | `test_repair_loop_returns_immediately_when_code_is_verified`، `test_motor_missing_emergency_stop_is_repaired_and_verified`، `test_traffic_light_conflict_is_repaired`، `test_invalid_syntax_triggers_debugging_and_regeneration`، `test_repair_loop_report_is_stored_in_repository` |
| `test_optimization_agent` | `test_verified_motor_code_optimizes_and_remains_verified`، `test_optimization_report_is_stored_in_memory` |
| `test_metrics_endpoint` | `test_metrics_after_optimization_uses_optimized_code_as_after_metrics` |
| `test_projects` | `test_debug_after_verified_validation_returns_not_required`، `test_optimize_persists_optimization_report`، `test_get_optimization_returns_same_persisted_report`، و`test_artifact_get_endpoints_return_persisted_values` (مرجّح) |
| `test_report_endpoint` | `test_report_includes_optimization_and_metrics_after_pipeline` |

**تنبيه:** قد يكشف إصلاح C-01 أخطاء أخرى كانت مختفية خلفه، وستُسجَّل عندها كما هي.

### ب. اختبارات قديمة فعلًا: 12 اختبارًا، تُصلح في `P0-11`

تغيّر الكود عمدًا ولم تُحدَّث هذه الاختبارات.

| الملف | الاختبار | السبب | الإصلاح المخطط |
| --- | --- | --- | --- |
| `test_planning_agent` | `test_llm_mode_is_placeholder_only` | وضع LLM صار منفذًا | اختباران: رجوع إلى القواعد عند رد غير JSON، ونجاح برد مبرمج |
| `test_code_generation_agent` | `test_llm_mode_is_placeholder_only` | وضع LLM صار منفذًا | اختباران: رجوع إلى القالب عند رد بلا `PROGRAM`، ونجاح برد مبرمج |
| `test_optimization_agent` | `test_llm_mode_raises_not_implemented` | وضع LLM صار منفذًا | الرد غير الصالح يترك الكود بلا تغيير (`NO_CHANGES`) |
| `test_optimization_agent` | `test_optimization_metrics_improve_or_stay_equal`، `test_rollback_occurs_if_optimization_pass_breaks_validation` | `optimize()` صارت async ولا يوجد `await` | إضافة `await`. قد يبقيان فاشلين بسبب C-01 والقوالب، ويُسجَّل ذلك كما هو |
| `test_validation_agent` | `test_formal_mode_is_placeholder_only` | الوضع الصوري لم يعد placeholder | الوضع الصوري يفشل مغلقًا دون MATIEC |
| `test_validation_agent` | 4 اختبارات تستبدل `_is_matiec_available` | الدالة حُذفت، وصار المدقق يُحقن عبر الـ constructor | مدقق MATIEC وهمي بأربع حالات: نجاح، وفشل، وغير متوفر (يرجع إلى regex، ويفشل حتى P1-01)، ومهلة (فشل مغلق، ليس VERIFIED) |
| `test_health` | `test_health_endpoint` | يتوقع `"healthy"` ومفاتيح غير موجودة | مطابقة العقد الحالي (D-025) |
| `test_projects` | `test_get_requirements_returns_404_when_no_requirement_submitted` | الخدمة تعيد متطلبًا افتراضيًا | **تعديل الكود** ليعيد 404 (D-024)، والاختبار صحيح كما هو |

### ج. اختبارات قوالب تكشف أخطاء حقيقية: 6 اختبارات، تُصلح في `P1-22`

**ما يقوله سجل git:** ملف `code_generation_agent.py` له ثلاثة commits فقط.

- **الأول (`6ea4a27`، مايو):** قالب المحرك يستخدم `Run_Cmd` و`Safety_OK` بمنطق متسق لزر إيقاف مفتوح عادةً. الـ commit التالي `0576978` لم يغيّر هذه الأسطر.
- **الثالث (`c2f05b2`، يوليو):** أعاد كتابة القالب إلى `Run_Latch`، وأعلن الزر مغلقًا عادةً.
- **الاختبارات:** تتوقع تصميمًا ثالثًا مغلقًا عادةً مع `Safety_OK`، **لا يوجد في أي commit**.

**C-10، مصحَّح الوصف:** شرط التعشيق `Run_Latch := TRUE` وشرط الفصل كلاهما يحتوي `NOT Stop_PB` (`code_generation_agent.py:435-441`). والنتيجة:

- حين يتحقق شرط التعشيق، يتحقق شرط الفصل أيضًا في المسح نفسه، فيُلغي الفصل التعشيق.
- **المحرك لا يعمل أبدًا، أيًّا كان اصطلاح توصيل الزر.** كنتُ وصفته سابقًا بـ "عكس القطبية"، والوصف الأدق هو هذا.

**C-11، خطأ جديد:** في قالب الدفعات، يُحسب `Batch_Complete := (Step_State = 3) AND Low_Level AND NOT Fault_State` بعد `CASE`. والـ `CASE` نفسه يعيد `Step_State` إلى 0 عندما يكون `Low_Level` صحيحًا، فتصبح `Batch_Complete` خطأً دائمًا. القالب الأول كان يستخدم خطوة إنهاء مستقلة (`Step = 50`).

| الملف | الاختبار |
| --- | --- |
| `test_code_generation_agent` | `test_motor_plan_generates_structured_text_program`، `test_different_domains_produce_different_code`، `test_motor_template_uses_normally_closed_stop_pb_semantics`، `test_batch_generation_includes_step_logic` |
| `test_projects` | `test_different_project_domains_generate_different_code`، `test_generate_code_persists_artifact` |

**الإصلاح (P1-22):**

- إعادة تصميم قالبي المحرك والدفعات عمدًا: منطق صحيح للزر المغلق عادةً، وإنهاء دفعة قابل للوصول.
- استبدال اختبارات النصوص الحرفية باختبارات سلوك: أدخل كذا، فيجب أن يحدث كذا عبر عدة مسوحات.
- حتى وصول المحاكي (P2-04)، يُستخدم منفّذ صغير خاص بهذه القوالب في الاختبارات.

**الدلالة العلمية:** القواعد الساكنة أعطت قالب المحرك `VERIFIED` مع أنه لا يعمل. هذا دليل مباشر على الحاجة إلى المحاكاة (L3) والتحقق الصوري (L4).

## ملاحظات أخرى من التشغيل

- `pytest-asyncio 1.3.0` مثبت في `.venv` لكنه غير مذكور في `requirements-dev.txt`. أُضيف في `P0-05`.
- `test_optimization_agent.py` يضع علامة asyncio على اختبارات متزامنة، مما يسبب تحذيرات، ويُنظَّف في `P0-11`.

## سجل الحصيلة

| التاريخ | البند | نجح | فشل | ملاحظة |
| --- | --- | --- | --- | --- |
| 2026-09-14 | P0-04 | 96 | 43 | أول تشغيل آمن ومعزول. التصنيف: 25 من C-01، و12 قديمة، و6 تكشف C-10 وC-11 |
