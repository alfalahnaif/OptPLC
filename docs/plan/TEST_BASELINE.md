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
  - بصمة `backend/plcforge.db` متطابقة قبل التشغيل وبعده: `161230E8…29EE`.
  - ملفات النتائج الـ 14 متطابقة في بصمتها المجمعة.
  - `E:\app\rag_db` لم يُنشأ.
  - المجلد المؤقت للاختبارات حُذف بعد الانتهاء.
- **هل سبّب العزل أيًّا من حالات الفشل؟** لا، بحسب رسائل الفشل. لا توجد حالة فشل تعتمد على رد LLM حقيقي، والاختبارات التي تستدعي الـ LLM كانت ستفشل بالرد الحقيقي أيضًا. لم أتحقق بتشغيل الإعداد القديم، لأنه يحذف الجداول ويتصل بمزود مدفوع.

## تصنيف حالات الفشل الـ 43

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

### ب. اختبارات قديمة لم تُحدَّث بعد تغيّر الكود: 16 اختبارًا، تُصلح في `P0-11`

بعض هذه الحالات يحتاج قرارًا منك قبل التحديث: هل الصحيح هو ما يتوقعه الاختبار، أم ما يفعله الكود الآن؟

| الملف | الاختبار | السبب |
| --- | --- | --- |
| `test_code_generation_agent` | `test_motor_plan_generates_structured_text_program`، `test_different_domains_produce_different_code` | يتوقعان قالبًا قديمًا يحوي `Run_Cmd` و`Safety_OK` |
| `test_code_generation_agent` | `test_batch_generation_includes_step_logic` | يتوقع `Step_State = 10`، والقالب الحالي يستخدم 1 إلى 3 |
| `test_code_generation_agent` | `test_llm_mode_is_placeholder_only` | يتوقع `NotImplementedError`، ووضع LLM صار منفذًا |
| `test_projects` | `test_get_requirements_returns_404_when_no_requirement_submitted` | الخدمة صارت تعيد متطلبًا افتراضيًا بدل 404. **يحتاج قرارًا** |
| `test_projects` | `test_different_project_domains_generate_different_code` | يتوقع القالب القديم (`Run_Cmd`) |
| `test_health` | `test_health_endpoint` | يتوقع `"healthy"`، والكود يعيد `"ok"`. **يحتاج قرارًا** |
| `test_optimization_agent` | `test_optimization_metrics_improve_or_stay_equal`، `test_rollback_occurs_if_optimization_pass_breaks_validation` | يستدعيان `optimize()` دون `await` بعد أن صارت async |
| `test_optimization_agent` | `test_llm_mode_raises_not_implemented` | وضع LLM صار منفذًا |
| `test_planning_agent` | `test_llm_mode_is_placeholder_only` | وضع LLM صار منفذًا |
| `test_validation_agent` | `test_formal_mode_is_placeholder_only` | الوضع الصوري لم يعد placeholder |
| `test_validation_agent` | `test_matiec_success_path_keeps_static_validation`، `test_matiec_syntax_failure_returns_syntax_error`، `test_matiec_unavailable_falls_back_to_static_validation`، `test_matiec_timeout_falls_back_to_static_validation` | تستبدل دالة `_is_matiec_available` التي حُذفت من الكود |

### ج. خطأ وظيفي حقيقي جديد، C-10: اختباران، يُصلح في `P1-22`

**قالب المحرك يعكس قطبية زر الإيقاف المغلق عادةً (`Stop_PB`)، فالمحرك لا يمكن أن يعمل أبدًا.**

- **في الكود** (`code_generation_agent.py:435-441`): الإعلان يقول `Stop_PB: TRUE = healthy, FALSE = pressed`.
- **شرط التعشيق** `Run_Latch := TRUE` يتطلب `NOT Stop_PB`، أي أن الزر مضغوط.
- **شرط الفصل** يعمل على `NOT Stop_PB` نفسها، في المسح نفسه وبعد التعشيق.
- **النتيجة:**
  - إذا كان الزر سليمًا، لا يتحقق شرط التعشيق.
  - إذا كان مضغوطًا، يُعشَّق المحرك ثم يُفصل فورًا في المسح نفسه.
  - في الحالتين يبقى `Run_Latch` وبالتالي `Motor_Run` على `FALSE` دائمًا.
- **الاختباران اللذان يكشفانه، وهما صحيحان:** `test_code_generation_agent::test_motor_template_uses_normally_closed_stop_pb_semantics` و`test_projects::test_generate_code_persists_artifact`.
- **الدلالة العلمية:**
  - هذا القالب نفسه يحصل على `VERIFIED` من القواعد الساكنة، كما في تجربة التدقيق مع محاكاة MATIEC.
  - الكود المحفوظ في نتيجة benchmark B001 فيه الخطأ نفسه.
  - هذا دليل مباشر على أن القواعد الساكنة لا ترى السلوك، وسيكشفه المحاكي (L3) والتحقق الصوري (L4) تلقائيًا.

## ملاحظات أخرى من التشغيل

- `pytest-asyncio 1.3.0` مثبت في `.venv` لكنه غير مذكور في `requirements-dev.txt`، ويُضاف في `P0-05`.
- `test_optimization_agent.py` يضع علامة asyncio على اختبارات متزامنة، مما يسبب تحذيرات، ويُنظَّف في `P0-11`.

## سجل الحصيلة

| التاريخ | البند | نجح | فشل | ملاحظة |
| --- | --- | --- | --- | --- |
| 2026-09-14 | P0-04 | 96 | 43 | أول تشغيل آمن ومعزول |
