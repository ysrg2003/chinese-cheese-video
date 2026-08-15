# Chinese Cheese Video

نظام إنتاج آلي لفيديوهات قصيرة عن **الشطرنج الصيني Xiangqi**. النظام ينتج الفيديوهات باللغة **الإنجليزية افتراضياً**، ويدعم **الصينية** كخيار ثانٍ. لا توجد العربية ضمن صوت الفيديو أو الكابشن أو العناوين أو نصوص المخرج أو الترجمة.

يستخدم النظام Remotion للرندر، وEdge-TTS للتعليق الصوتي الرجالي المجاني، ومخرجاً اختيارياً عبر Gemini أو Ollama، وقاعدة بيانات SQLite محلية تعمل مباشرة دون Supabase. يبقى Supabase مساراً اختيارياً فقط، ويعود النظام تلقائياً إلى SQLite إذا كان Supabase غير متاح أو غير مهيأ.

> الفكرة التشغيلية: يقرأ النظام لغزاً محلياً، يبني شرحاً وتوقيتات للنقلات، يولّد صوتاً رجاليّاً إنجليزياً أو صينياً، يقيس طول الصوت والنص وعدد النقلات، يحدد مدة الفيديو المناسبة للمحتوى، يرندر MP4 عمودياً بمقاس 1080×1920، ثم يحفظ الفيديو وحالة الطلب داخل التخزين المحلي.

## السياسة اللغوية

| الإعداد | القيمة |
| --- | --- |
| اللغة الافتراضية | `en` — English |
| اللغة الثانية | `zh` — Simplified Chinese |
| العربية | غير مدعومة وممنوعة من النصوص المولدة |
| صوت الإنجليزية الرجالي | `en-US-GuyNeural` |
| صوت الصينية الرجالي | `zh-CN-YunjianNeural` |
| الكابشن | بنفس لغة الفيديو، من توقيتات الكلمات أو الكابشنات المولدة |

إذا وصل للنظام نص عربي من لغز قديم أو من استجابة نموذج، يرفضه منطق التحقق ويستخدم النص الاحتياطي باللغة المحددة بدلاً منه.

## Sentence-Level Visual Supervision

Every non-foundation narration sentence receives a stable `sentenceId`, a `visualIntent`, and a renderer-safe storyboard scene before rendering. Known Xiangqi concepts use verified treatments such as `horse_leg`, `elephant_eye`, `cannon_screen`, river and palace overlays, and legal paths. New concepts receive the flexible `concept_focus` treatment instead of being dropped or assigned an invented move. See [`docs/sentence_level_visual_supervision_en.md`](docs/sentence_level_visual_supervision_en.md) for the data contract, validation gates, fallback behavior, and test commands.

## مكونات النظام

| المكوّن | الوظيفة | مكان الإعداد |
| --- | --- | --- |
| Remotion | رسم الرقعة والقطع وحركة النقلات وإخراج MP4 | `src/Composition.tsx` |
| Edge-TTS | توليد الصوت وتوقيتات الكلمات بصيغة JSON وVTT | `python/tts.py` |
| المخرج الذكي | كتابة العنوان والنص والنقلات والتوقيتات بالإنجليزية أو الصينية | `python/director.py` |
| SQLite المحلي | تخزين الألغاز وطلبات الإنتاج والنتائج دون خدمة خارجية | `python/local_store.py` |
| Supabase الاختياري | مسار بعيد بديل عند تشغيل `--storage supabase` أو `--storage auto` | `python/supabase_store.py` |
| GitHub Actions | تشغيل مجدول أو يدوي للرندر | `.github/workflows/render-video.yml` |
| أصول Xiangqi | قطع SVG مرخّصة مع ملفات النسبة والترخيص | `public/assets/pieces/` |

## قاعدة البيانات المحلية

يستخدم التشغيل العادي الملف التالي:

```text
data/chinese_cheese_video.db
```

ينشئ النظام الملف والجداول تلقائياً عند أول تشغيل. الجداول الرئيسية هي `xiangqi_puzzles` للألغاز و`video_jobs` لطلبات الرندر. يضيف النظام لغزاً إنجليزياً تجريبياً تلقائياً عند كون القاعدة جديدة.

لإضافة لغز محلي يمكن استخدام Python أو SQLite، أو تمرير ملف JSON واحد إلى خط الإنتاج. شكل اللغز:

```json
{
  "id": "fork-001",
  "title": "The Hidden Fork",
  "language": "en",
  "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
  "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
  "theme": "wood"
}
```

القيمة `language` تقبل `en` أو `zh` فقط. عند عدم وجودها يستخدم النظام الإنجليزية. حقل `durationInSeconds` اختياري؛ إذا غاب، يحسب النظام المدة تلقائياً من طول السرد، مدة الصوت الفعلية، عدد النقلات، والكابشن. يمكن استخدامه كحد أدنى تحريري عندما تكون حلقة معينة بحاجة إلى مساحة زمنية أطول.

## التثبيت والتشغيل المحلي

ثبّت اعتماديات Node وPython ثم متصفح Remotion:

```bash
npm install
sudo pip3 install -r python/requirements.txt
npx remotion browser ensure
```

يمكن تشغيل تجربة كاملة باللغة الإنجليزية من قاعدة SQLite المحلية:

```bash
python3 python/run_pipeline.py --language en --storage local
```

ويمكن تشغيل فيديو صيني من نفس القاعدة:

```bash
python3 python/run_pipeline.py --language zh --storage local
```

لتجربة ملف JSON محدد دون الحاجة إلى حفظه في قاعدة البيانات:

```bash
python3 python/run_pipeline.py \
  --input python/sample_job.json \
  --language en \
  --storage local
```

لتشغيل البيانات والمخرج دون رندر، استخدم:

```bash
python3 python/run_pipeline.py \
  --input python/sample_job.json \
  --language en \
  --storage local \
  --skip-render
```

ولتجربة الفحص دون حفظ أو اتصال أو رندر:

```bash
python3 python/run_pipeline.py \
  --input python/sample_job.json \
  --language en \
  --dry-run \
  --skip-tts \
  --skip-render
```

لتشغيل استوديو Remotion:

```bash
npm run dev
```

ولتجربة الرندر اليدوي:

```bash
npm run render:sample
```

## اختيار التخزين

التخزين المحلي هو الافتراضي ولا يحتاج إلى أي متغيرات سرية:

```bash
python3 python/run_pipeline.py --storage local --language en
```

وضع `auto` يحاول الاتصال بـ Supabase فقط إذا كانت متغيراته موجودة، ثم ينتقل إلى SQLite عند فشل الشبكة أو غياب الجداول أو عدم تهيئة المشروع:

```bash
python3 python/run_pipeline.py --storage auto --language zh
```

وضع `supabase` يجبر استخدام Supabase، وهو مفيد فقط بعد تنفيذ مخطط SQL وتهيئة المفتاح:

```bash
python3 python/run_pipeline.py --storage supabase --language en
```

## Gemini وOllama

إذا لم تُضبط أي خدمة ذكاء اصطناعي، يعمل المخرج الاحتياطي الحتمي باللغة المطلوبة. عند ضبط أسرار Gemini يستخدم النظام `gemini-2.5-flash` ثم `gemini-2.5-flash-lite` عبر مدير المزودات ويطلب مخرجات باللغة الإنجليزية أو الصينية فقط. يمكن استخدام Ollama عبر `OLLAMA_BASE_URL` و`OLLAMA_MODEL` إذا كان خادمه متاحاً.

انسخ `.env.example` إلى `.env` عند الحاجة، ولا تضع أي مفتاح سري داخل ملفات TypeScript أو داخل مستودع GitHub. الأصوات الافتراضية رجالية فقط: `en-US-GuyNeural` و`zh-CN-YunjianNeural`. يمكن تغييرها عبر `TTS_VOICE_EN` و`TTS_VOICE_ZH`، لكن يجب اختيار صوت رجالي موثق من قائمة Edge-TTS.

## مشروع الذكاء الاصطناعي المستقل

تم فصل إدارة المزودات والنماذج والمفاتيح والتدوير إلى مستودع مستقل قابل لإعادة الاستخدام:

[github.com/ysrg2003/ai-provider-router](https://github.com/ysrg2003/ai-provider-router)

يستهلك هذا المشروع الطبقة عبر `python/ai_router_bridge.py`. محلياً اضبط `AI_ROUTER_PATH` و`AI_ROUTER_CONFIG_DIR`، وفي GitHub Actions يقوم workflow بعمل checkout للمستودع وتثبيته بـ `pip install -e ai-provider-router`. تغيير ترتيب Gemini أو إضافة مزود أو حذف نموذج يتم من ملفات `config/` في المستودع المستقل فقط.

## التشغيل المستقل عبر GitHub Actions

لم يعد النظام يحتاج إلى جلسة Manus مفتوحة. الملف `.github/workflows/render-video.yml` يشغل خط الإنتاج ثلاث مرات يومياً بتوقيت UTC، ويتيح تشغيله يدوياً. يمنع `concurrency` تشغيل جولتين متوازيتين حتى لا تتعارض قاعدة SQLite أو تستهلك المفاتيح في وقت واحد. بعد كل جولة يرفع الفيديوهات والسجل وقاعدة SQLite كـ artifacts، ثم يحفظ قاعدة البيانات في commit ليقرأها التشغيل التالي.

قبل تفعيل workflow، أضف الأسرار التالية في إعدادات المستودع:

| Secret / Variable | الاستخدام |
| --- | --- |
| `AI_ROUTER_REPO_TOKEN` | token بصلاحية قراءة مستودع `ysrg2003/ai-provider-router` الخاص من workflow الفيديو |
| `AI_ROUTER_GEMINI_KEYS_JSON` | مصفوفة مرتبة من مفاتيح Gemini، ويفضل أن تتضمن `id`, `key`, و`project` |
| `AI_ROUTER_HF_KEYS_JSON` | اختياري؛ مصفوفة مفاتيح Hugging Face الاحتياطية |
| `HF_TOKEN` | أبسط طريقة؛ Access Token واحد يفعّل سلسلة النماذج العشرة الافتراضية |
| `YOUTUBE_API_KEY` | اختياري؛ البحث عن فيديوهات Xiangqi الحديثة المرتبة بالمشاهدات |
| `SUPABASE_URL` و`SUPABASE_SERVICE_ROLE_KEY` | اختياريان فقط عند تفعيل التخزين البعيد |
| `HF_MODELS` | متغير اختياري لقائمة نماذج Hugging Face المرتبة |

ترتيب الاستدعاء يقرأه المشروع المستقل من `config/models.json`: `gemini-2.5-flash`، ثم `gemini-2.5-flash-lite`، ثم عشرة نماذج Hugging Face. إذا لم تضف Gemini وأضفت `HF_TOKEN` فقط، يبدأ النظام مباشرة بسلسلة Hugging Face الافتراضية. كل نجاح وفشل وتبريد يسجل في `data/ai_router.db`، ولا يضع النظام المفاتيح داخل الكود أو قاعدة البيانات.

لا يتوقف الإنتاج عند انتهاء خطة القناة. `python/automation_runner.py` يستدعي `content_discovery.py` في كل جولة؛ فيجمع إشارات RSS، ويستخدم YouTube Data API عند توفيره، وينشئ أفكاراً evergreen، ويولد كل الأزواج المرتبة بين مستويات المهارة، ويطلب فكرة جديدة من مزود الذكاء الاصطناعي عند توفره. كل مرشح يحصل على بصمة تمنع إعادة إنتاجه، والفشل يعيده إلى قائمة إعادة المحاولة.

عند استخدام التشغيل المحلي خارج GitHub Actions، يمكن تشغيل نفس المنسق:

```bash
python3 python/automation_runner.py --daily-count 1 --languages en,zh --discover-limit 20
```

يوجد شرح معماري أوسع في `docs/independent_automation.md`.

## النشر التلقائي إلى Xiangqi Lab

بعد إعداد OAuth مرة واحدة، يستطيع workflow نشر الفيديو مباشرة إلى [قناة Xiangqi Lab](https://www.youtube.com/@XiangqiLab) وإضافته إلى قائمة التشغيل المناسبة حسب `content_type` واللغة. الناشر المستقل موجود في `python/youtube_publisher.py`، وسياسة metadata في `config/youtube_metadata_policy.json`، وقوائم التشغيل في `config/youtube_playlists.json`.

اتبع الدليل الكامل في `docs/youtube_autopublish_setup.md`. أضف Secret باسم `YOUTUBE_OAUTH_TOKEN_JSON`، ثم فعّل `YOUTUBE_PUBLISH_ENABLED=1` مع `YOUTUBE_PUBLISH_MODE=public`؛ كل فيديو منشور سيكون عاماً مباشرة كما طلب مالك القناة. لا تضع `client_secret.json` أو `youtube-token.json` داخل المستودع؛ فهما محميان أيضاً في `.gitignore`.

حالات النشر تحفظ في جدول `youtube_publications` داخل SQLite. إذا نجح رفع MP4 وفشلت إضافة قائمة التشغيل، يحتفظ النظام بـ `video_id` ويعيد محاولة الإضافة دون إنشاء فيديو مكرر. إذا كانت الحالة `published`، يعيد التشغيل استخدام النتيجة المسجلة ولا يرندر أو يرفع نسخة ثانية.


## المخرجات

يحفظ كل طلب محلياً في:

```text
output/jobs/<job-id>/
```

ويضع ملفات Remotion القابلة للقراءة داخل:

```text
public/generated/<job-id>/
```

ويحفظ الفيديو المحلي في:

```text
data/local_storage/xiangqi-videos/jobs/<job-id>.mp4
```

كما يحفظ JSON الطلب وMP3 وتوقيتات الكلمات وVTT بجانب الفيديو. لا يوجد حد ثابت لمدة الفيديو؛ قد يكون Short قصيراً، أو درساً متوسطاً، أو مباراة كاملة أطول حسب البيانات الداخلة.

## خطة قناة يوتيوب كاملة

الوثيقة `docs/youtube_channel_plan.md` تحتوي خطة القناة من التعريف والرقعة والقطع، مروراً بأول مباراة والافتتاح والتكتيك والوسط والنهايات، وصولاً إلى الألغاز المتقدمة والمباريات الكاملة والمقارنات مع الشطرنج الغربي وShogi وJanggi وGo. كما تتضمن قوائم التشغيل الإنجليزية والصينية، قائمة أول 60 حلقة، برنامج إطلاق 12 أسبوعاً، قوالب العناوين والكابشن، ونظام قياس الأداء.

## Supabase الاختياري

إذا رغبت في إعادة استخدام Supabase مستقبلاً، نفّذ `sql/001_initial_schema.sql` في SQL Editor. المخطط محدث ليقبل الإنجليزية والصينية فقط. لا يضع النظام مفتاح الخدمة داخل الواجهة أو المستودع، ويستخدمه في طبقة Python فقط.

إذا كان Supabase لا يعمل، لا يوجد أي توقف للنظام: استخدم `--storage local`، أو اترك `--storage auto` ليعود إلى SQLite تلقائياً.

## الأمان

يوجد فحص يمنع النص العربي من الوصول إلى الفيديو حتى لو ظهر في ملف إدخال قديم أو في رد مزود الذكاء الاصطناعي. كما أن `.gitignore` يمنع ملفات البيئة وملفات النتائج المؤقتة من الرفع. وبما أن مفتاح `service_role` ظهر سابقاً في المحادثة، فمن الأفضل تدويره في لوحة Supabase قبل استخدامه في أي بيئة نشر.

## مصادر الأصول

الأصول الحالية مأخوذة من مجموعة `Kadagaden/chess-pieces`، وهي موثقة بترخيص **CC BY 4.0** داخل `public/assets/CHESS_PIECES_LICENSE.txt`، مع حفظ ملف README الخاص بالمصدر. يجب إبقاء النسبة عند إعادة توزيع الأصول.
