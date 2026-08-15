# شرح نظام Chinese Cheese Video من الفكرة إلى النشر

## 1. الفكرة العامة

هذا المشروع ليس ملفاً واحداً يطلب من نموذج ذكاء اصطناعي أن يكتب نصاً ثم يرفع فيديو. هو خط إنتاج مؤتمت متعدد الطبقات. كل طبقة لها مسؤولية محددة، ولا تنتقل البيانات إلى الطبقة التالية إلا بعد اجتياز الشروط المطلوبة.

القاعدة الأساسية هي أن **الذكاء الاصطناعي يقترح ويشرح، لكن الكود الحتمي يملك القرار النهائي في قانونية Xiangqi، وصحة الادعاءات الميكانيكية، وسلامة الحالة المنشورة**. لذلك لا يكفي أن يكتب النموذج جملة تبدو مقنعة؛ يجب أن تكون مدعومة بمصادر، ثم يجب أن تطابق board state فعلياً، ثم يجب أن يظهر معناها في المشهد، ثم يجب أن ينجح الفيديو الناتج في الفحص قبل الرفع.

> المسؤول عن إنتاج النص هو director والـAI Router، والمسؤول عن إثبات أن النص صحيح هو `xiangqi_claims.py` و`xiangqi_rules.py`، والمسؤول عن تحويل النص إلى صورة متزامنة هو visual director وRemotion، والمسؤول عن النشر الآمن هو YouTube publisher وSQLite state machine.

اللغة الأساسية هي English، واللغة الصينية Simplified Chinese هي المسار الثاني. العربية ممنوعة من الصوت والنصوص والعناوين والكابشن. الأصوات الافتراضية ذكورية فقط: `en-US-GuyNeural` للإنجليزية و`zh-CN-YunjianNeural` للصينية.

## 2. من المسؤول عن ماذا؟

| المسؤول البرمجي | الملف أو الطبقة | المسؤولية العملية |
|---|---|---|
| مخطط القناة | `config/xiangqi_curriculum_en.json` و`python/curriculum.py` | ترتيب الدروس، المرحلة، الهدف، playlist، الصعوبة، القالب، القطعة المستهدفة، والمدة التقريبية. |
| مدير الحالة | `python/local_store.py` و`data/chinese_cheese_video.db` | حفظ المرشحين، الخطط، الوظائف، نتائج الرندر، النشر، الـplaylists، والمحاولات. |
| مولد الأفكار | `python/content_discovery.py` | RSS، YouTube Data API، أفكار evergreen، مباريات مستويات المهارة، وأفكار AI الجديدة بعد تغطية المنهج. |
| المنسق | `python/automation_runner.py` | اختيار المرشح، منع التكرار، تشغيل `run_pipeline.py`، تحديث حالات المرشح، والتعامل مع pending/retry. |
| البحث والـgrounding | `python/research_grounding.py` | جمع مصادر WXF وXiangqi.com وChess.com، وإضافة Google Search grounding وحفظ evidence وhash. |
| مدير الذكاء الاصطناعي | `python/ai_router_bridge.py` والمستودع المستقل `ai-provider-router` | اختيار النموذج والمفتاح، الدوران بين المفاتيح والنماذج، التسجيل في `data/ai_router.db`، والتعامل مع cooldown. |
| مخرج السيناريو | `python/director.py` | كتابة العنوان، المقدمة، narration، move purpose، opponent reply، effect، claims، والكابشن الأولي بصيغة JSON. |
| مدقق قواعد Xiangqi | `python/xiangqi_rules.py` و`python/xiangqi_claims.py` | إعادة تشغيل كل ply، التحقق من النقلات القانونية، وإثبات Horse Leg وElephant Eye وCannon Screen وRiver Limit وFlying General. |
| سياق التعليم | `python/curriculum.py` | تذكير سريع بالقطع المساعدة، الإحالة إلى درس سابق أو لاحق، وتطبيق ذلك في Piece Academy فقط. |
| مدير الصورة | `python/visual_director.py` | تحويل كل claim إلى primitive بصري صحيح، وبناء action/reply/effect/constraint beats. |
| الأصول الاختيارية | `python/visual_assets.py` و`CHATGPT_VISUAL_API_BASE` | توليد establishing shots اختيارية، مع بقاء الرقعة الحتمية هي المرجع الأساسي. فشل الصورة الاختيارية لا يغيّر قانونية الرقعة. |
| مدير الصوت | `python/tts.py` | Edge-TTS، الصوت الذكوري، word boundaries، وتوقيت الكلمات. |
| مدير التوقيت والكابشن | `python/timing.py` و`tts.py` و`run_pipeline.py` | حساب مدة الفيديو، مزامنة narration segments مع الصوت، وإنتاج captions من التوقيت الفعلي. |
| الناقد الإبداعي | `python/creative_critic.py` | فحص storyboard قبل الرندر، اقتراح إصلاحات آمنة محدودة، ثم فحص الـMP4 بعد الرندر. |
| الرندر | Remotion في `src/Composition.tsx` و`run_pipeline.py` | رسم الرقعة، القطع، النهر، القصور، الأسهم، التظليل، الكابشن، والصوت إلى MP4. |
| الفحص البصري | `python/visual_qa.py` | فحص frames من الفيديو، التزامن، وجود primitives المطلوبة، وعدم وجود أخطاء بصرية أو عربية. |
| الصورة المصغرة | `python/thumbnail.py` | توليد thumbnail، فحص المقاس والحجم، وتجهيزها قبل YouTube upload. |
| ناشر YouTube | `python/youtube_publisher.py` و`python/localization.py` | metadata، العنوان، الوصف، tags، hashtags، playlist، upload، localization، captions، thumbnail، وحالات الاستئناف. |
| التشغيل الآلي | `.github/workflows/render-video.yml` | تشغيل ثلاث مرات يومياً، تثبيت البيئة، تشغيل الاختبارات، تنفيذ production، رفع artifacts، وحفظ SQLite في GitHub. |

## 3. أين توجد الحقيقة الأساسية؟

يستخدم النظام SQLite كقاعدة افتراضية في `data/chinese_cheese_video.db`. Supabase اختياري؛ إذا كان غير مهيأ أو فشل الاتصال، يعود التشغيل إلى SQLite. هذا يعني أن قناة YouTube لا تعتمد على Supabase كي تعمل.

الجداول المهمة هي:

| الجدول | وظيفته |
|---|---|
| `curriculum_lessons` | تعريف خطة القناة وترتيب الدروس. |
| `content_candidates` | كل فكرة قابلة للإنتاج، سواء كانت curriculum أو RSS أو YouTube أو evergreen. |
| `curriculum_episode_plans` | حالة كل درس: planned، queued، processing، published، retry أو blocked. |
| `xiangqi_puzzles` | FEN والنقلات والموضوع واللغة. |
| `video_jobs` | job payload، الحالة، output path، ورسالة الخطأ. |
| `youtube_publications` | video ID، status، playlist، attempts، وmetadata الخاصة بالنشر. |
| `youtube_videos` | catalog مفصل للفيديو المحلي والهوية العامة. |
| `youtube_video_playlists` | علاقة الفيديو بقائمة التشغيل. |
| `publication_reset_history` | سجل الهويات العامة القديمة بعد deletion أو quarantine لمنع التكرار وضياع الأثر. |
| `ai_provider_calls` و`ai_provider_state` | سجل استدعاءات النماذج وحالات الفشل والتبريد. |

الحالة ليست مجرد نص واحد. المرشح والفيديو والـpublication والـcurriculum episode لها حالات مستقلة؛ وهذا يسمح للنظام بأن يعرف الفرق بين: لم يبدأ، قيد المعالجة، رندر جاهز، public upload نجح، playlist فشلت، localization معلقة، أو أن الفيديو محذوف ويحتاج regeneration.

## 4. التشغيل المجدول يبدأ من GitHub Actions

الملف `.github/workflows/render-video.yml` يعمل وفق cron ثلاث مرات يومياً: `08:15` و`14:15` و`20:15` UTC، وهو ما يعادل أوقات التشغيل المحددة في المشروع بتوقيت Arabia Standard Time. ويمكن تشغيله يدوياً من GitHub Actions.

عند بدء الجولة، يقوم GitHub Actions بالخطوات التالية:

1. يعمل checkout للمستودع الأساسي.
2. يعمل checkout لمستودع `ysrg2003/ai-provider-router` داخل مجلد `ai-provider-router`.
3. يثبت Node.js وPython وFFmpeg واعتماديات npm وPython.
4. يضمن وجود متصفح Remotion.
5. يقرأ secrets الخاصة بالمفاتيح وOAuth من GitHub، ولا يضعها في الكود.
6. يشغل `validate_ai_router_runtime.py` ليتأكد من أن key pools وترتيب المزودات صالحان.
7. يشغل TypeScript compile وPython tests و`py_compile` وفحوص العقود، لكن بيئة الاختبار تعطل live grounding عمداً وتستخدم fixtures deterministic.
8. يشغل reconciliation قبل الإنتاج العادي.
9. يشغل `automation_runner.py`.
10. يرفع artifacts تشمل job JSON وMP4 وvisual QA وSQLite وAI Router state.
11. يعمل commit لتغيرات SQLite حتى تقرأ الجولة التالية الحالة الحديثة.

يوجد `concurrency` يمنع تشغيل جولتين متوازيتين من خط الإنتاج. هذا مهم لأن جولتين قد تحاولان اختيار الدرس نفسه أو الكتابة في SQLite أو استهلاك المفتاح نفسه في الوقت نفسه.

## 5. المرحلة الأولى: reconciliation قبل إنتاج محتوى جديد

قبل أن ينشئ النظام فيديو جديداً، يستدعي `python/continuous_reconcile.py`. الغرض هو فحص الحالات العامة التي ربما نجح فيها upload، لكن فشلت خطوة لاحقة مثل playlist أو captions أو localization أو thumbnail.

مثلاً، قد يحدث الآتي:

> نجح رفع MP4 وأصبح له video ID عام، ثم فشلت إضافة الفيديو إلى playlist.

في هذه الحالة لا يعيد النظام الرندر ولا يرفع فيديو جديداً. بل يحتفظ بالـvideo ID ويعيد محاولة playlist فقط. إذا كانت الحالة `published_localization_pending`، يعيد محاولة localization. وإذا كانت `published_thumbnail_pending`، يعيد محاولة thumbnail. هذه الحماية هي التي تمنع duplicates.

الـreconciliation محدود بزمن ومحاولات. إذا ظهر quota cooldown أو فشل مؤقت، يسجل الحالة ويستطيع أن يطلب continuation run لاحقاً بدلاً من إبقاء runner عالقاً بلا نهاية.

## 6. المرحلة الثانية: اختيار ما هو الفيديو التالي

يوجد مساران للاختيار.

### 6.1 اختيار المنهج أولاً

طالما أن هناك درس curriculum لم يُنشر، فإن `LocalStore.get_next_curriculum_candidate()` يعطي الأولوية للمنهج. يتم ترتيب الدروس بواسطة `sequence_no` داخل `config/xiangqi_curriculum_en.json`.

هذا يعني أن النظام لا يختار موضوعاً عشوائياً من RSS قبل إكمال الأساسيات. مثلاً، بعد إعادة البدء اختار:

```text
curriculum_lesson_key: en-001-what-is-xiangqi
selection_mode: curriculum
```

وكان العنوان الأساسي:

```text
What Is Xiangqi?
```

بعد إكمال دروس البداية والرقعة والإعداد والقطع، ينتقل المنهج إلى opening، tactics، endgame، full_game، comparison، advanced puzzles وباقي المراحل المعرّفة.

### 6.2 اكتشاف أفكار إضافية

في كل جولة يستدعي المنسق `content_discovery.py`. هذه الطبقة لا تتجاوز الدرس curriculum عندما يكون هناك درس مستحق، لكنها تملأ المستقبل بأفكار جديدة. مصادرها هي:

| المصدر | ماذا يفعل؟ |
|---|---|
| RSS | يبحث عن أخبار وموضوعات Xiangqi حديثة حسب `DISCOVERY_RSS_QUERY`. |
| YouTube Data API | يبحث عن مواضيع فيديو أو مباريات ذات اهتمام، إذا توفر `YOUTUBE_API_KEY`. |
| Evergreen | ينشئ أفكاراً ثابتة مثل شرح القواعد، التكتيكات، النهايات، والمقارنات. |
| Skill match | ينشئ مباريات تعليمية بين مبتدئ ومبتدئ، مبتدئ ومتوسط، متوسط وخبير، وخيارات مشابهة. |
| AI candidate | يطلب فكرة جديدة من AI Router عند توفره. |

كل candidate يحصل على `topic_key` و`fingerprint` و`content_type` وpriority وpayload. لا يكفي اختلاف العنوان؛ فالنظام يستخدم SHA-256 وtopic key وتوقيع FEN/moves لمنع إعادة إنتاج الموضوع نفسه أو نفس الوضع.

## 7. ما الذي يحدد موضوع الفيديو وشكله؟

الموضوع لا يحدده النموذج وحده. توجد طبقات قرار مرتبة:

1. ترتيب المنهج يحدد الدرس المطلوب.
2. `lesson_key` يحدد هوية الحلقة المستقرة.
3. `content_type` يحدد نوع الحلقة: definition، rules، tactics، opening، full_game، comparison وغيرها.
4. `format` يحدد إن كانت الحلقة board introduction أو piece lesson أو puzzle أو full game.
5. `position_template` يحدد الوضع والنقلات المناسبة للتدريس.
6. `target_piece` أو `analysis_focus` يحدد ما يجب أن يتعلمه المشاهد.
7. FEN وmoves يحددان الحالة الميكانيكية الفعلية.
8. director يكتب التعبير البشري فوق هذه الحقائق، لكنه لا يستطيع تجاوزها.

في درس static مثل `en-001` لا توجد لعبة كاملة ولا سلسلة نقلات. الهدف هو تعريف اللعبة واللوحة والجيشين والقصر والنهر. وفي درس قطعة، توجد عادة حركة أو وضع قصير يشرح قاعدة القطعة. وفي full game، توجد قائمة نقلات أطول وتحليل مرحلي مختلف.

## 8. ما الذي يحدث قبل أن يكتب AI السيناريو؟ البحث والـgrounding

عندما تكون متغيرات production مفعلة، يستدعي `run_pipeline.py`:

```text
XIANGQI_RESEARCH_REQUIRED=1
GOOGLE_GROUNDING_ENABLED=1
GOOGLE_GROUNDING_REQUIRED=1
```

تقوم `research_grounding.py` بالآتي:

1. تقرأ موضوع الدرس والمصطلحات المطلوبة.
2. تجمع مرجع World Xiangqi Federation.
3. تجمع مرجع Xiangqi.com المتخصص في القطع والحركات.
4. تجمع مرجعاً ثانوياً مثل Chess.com.
5. تضيف مصادر lesson-specific إذا كان للموضوع رابط أو research URL.
6. تستدعي Gemini Grounding with Google Search وURL Context في production إذا كان مفعلاً.
7. تحفظ source URL وretrieval timestamp وshort excerpt وsource ID وhash في `researchBundle`.
8. ترفض الاستمرار إذا لم توجد evidence كافية أو تعذر hash أو كانت Google grounding مطلوبة وغير متاحة.

الـresearchBundle ليس بديلاً عن التحقق الميكانيكي. المصدر يشرح القاعدة العامة، أما تحديد ما إذا كان Pawn أغلق Horse Leg في موضع محدد فيحسمه board-state verifier.

هناك cache versioned للقواعد الثابتة يسمح بالاستمرار عند عطل HTTPS مؤقت، لكنه لا يستخدم كبديل قديم لأخبار أو مباراة حديثة. إذا كان topic حديثاً ويحتاج بحثاً حياً، يبقى fail-closed عند فشل البحث المطلوب.

## 9. كيف يكتب الذكاء الاصطناعي العنوان والسيناريو؟

يستدعي `director.py` AI Router، ويطلب JSON منظماً وليس نصاً حراً. الـsystem prompt يفرض English أو Chinese حسب language، ويمنع العربية، ويمنع Markdown خارج JSON.

الـdirector يطلب هذه العناصر:

| الحقل | وظيفته |
|---|---|
| `title` | عنوان الحلقة الأولي. يمر لاحقاً على YouTube metadata policy. |
| `narration` | المقدمة والجسر العام، وليس قائمة نقلات جافة. |
| `moves` | كل ply مع from/to/piece/side. |
| `purpose` | لماذا لعبنا النقلة. |
| `opponentReply` | ما الرد المتوقع أو التعليمي. |
| `effect` | ما الذي تغير بعد الرد. |
| `claims` | الادعاءات البنيوية التي تحتاج إثباتاً. |
| `captions` | كابشن أولي، لكنه ليس المصدر النهائي عند توفر TTS word cues. |
| `durationInSeconds` | اقتراح، وليس سقفاً ثابتاً؛ timing يعيد حساب المدة. |

كل نقلة تُحوّل إلى أربع beats تعليمية:

1. **Action:** ماذا تحرك ومن أين إلى أين.
2. **Reply:** ماذا يتوقع أن يفعل الخصم.
3. **Effect:** ماذا تغير في الوضع.
4. **Constraint:** ما القاعدة أو القيد الذي يجب تذكره.

هذا يمنع الفيديو من أن يكون مجرد صوت يقول أسماء النقلات بينما الحركة البصرية تحدث منفصلة عن الكلام.

## 10. كيف تُفهم القطع المساعدة في Piece Academy؟

في المرحلة التعليمية فقط، يستدعي director طبقة `piece_learning_intro()` من `curriculum.py`. هذه الطبقة تقرأ القطع الموجودة في template وتقارن ترتيبها بالمنهج.

إذا كانت القطعة المساعدة مشروحة سابقاً، يقول الفيديو تذكيراً سريعاً ويشير إلى الدرس السابق. وإذا لم تكن مشروحة، يشرح النظام آلية حركتها بجملة قصيرة ويقول إنها ستأتي في درس مستقل لاحقاً. بعدها ينتقل إلى القطعة الهدف.

مثلاً، إذا استخدم درس Horse قطعة Pawn للوصول إلى الوضع، لا يتظاهر النظام بأن المشاهد يعرف Pawn؛ بل يقول إن المثال يستخدم Pawn، يذكر حركته الأساسية بسرعة، ويشير إلى أن درس Pawn سيأتي لاحقاً. هذا السلوك محصور في Piece Academy ولا يُضاف تلقائياً إلى مباريات كاملة أو ألغاز متقدمة.

## 11. كيف يمنع النظام أخطاء Xiangqi؟

بعد استجابة director، لا يثق النظام بها مباشرة.

### 11.1 فحص المصطلحات

`director.py` يرفض العربية، ويمنع النص الصيني داخل English، وي canonicalize المصطلح القديم. المصطلحات الإلزامية هي:

| المفهوم | المصطلح الإنجليزي الصحيح |
|---|---|
| حاجز الحصان | Horse Leg |
| حاجز الفيل القطري | Elephant Eye |
| حاجز المدفع | Cannon Screen أو mount بحسب السياق، مع إثبات screen ميكانيكياً |
| منع عبور الفيل | River limit |
| مواجهة الجنرالين | Flying General، وتظهر كحالة ممنوعة لا كنقلة تعليمية موجبة |

`Horse Eye` و`Blocked Eye` لا يُسمح بهما كالتسمية التعليمية الأساسية للحصان.

### 11.2 فحص النقلات

`xiangqi_rules.py` يعيد بناء الرقعة من FEN ثم يطبق كل ply. يفحص نوع القطعة، side، المصدر، الوجهة، المسار، القصر، النهر، الكش، ومواجهة الجنرالين. إذا كانت النقلة غير قانونية، يتوقف job.

### 11.3 فحص الادعاء السببي

`xiangqi_claims.py` يثبت أن كل claim يطابق الوضع بعد ply المحدد. مثلاً، `horse_leg_block` يحتاج subject.at للحصان، target للوجهة، blocker.at لموضع الـLeg، وstatement دقيقاً. لا يكفي أن تكون النقلة قانونية؛ يمكن لنقلة قانونية أن تحمل تفسيراً خاطئاً، ولذلك يتم رفضها إذا كان السبب المعلن غير صحيح.

الأمثلة التي يستطيع verifier إثباتها هي `legal_move` و`horse_leg_block` و`horse_leg_open` و`elephant_eye_block` و`elephant_eye_open` و`cannon_screen` و`river_limit` و`flying_general` و`legal_destinations`.

## 12. كيف يتحول claim إلى صورة؟

بعد نجاح claim proof، يستدعي `visual_director.py`. لا يختار primitive عشوائياً، بل يربط نوع الادعاء بالعنصر البصري:

| Claim | Primitive الإلزامي |
|---|---|
| `horse_leg_block` أو `horse_leg_open` | `horse_leg` |
| `elephant_eye_block` أو `elephant_eye_open` | `elephant_eye` |
| `cannon_screen` | `cannon_screen` |
| `river_limit` | `river_limit` |
| `legal_destinations` | `legal_destinations` |

إذا كان النص يقول إن Pawn أغلق Horse Leg، يجب أن يظهر Horse Leg بصرياً. إذا غاب primitive المطلوب، يفشل storyboard قبل الرندر.

تستطيع طبقة الأصول الاختيارية طلب establishing image من خدمة الصور، لكنها لا تستبدل رقعة Xiangqi الحتمية. أي صورة غير متاحة أو غير صحيحة تُستبعد، ولا تسمح للنظام بإخفاء board geometry خلف صورة زخرفية.

## 13. كيف يُنتج الصوت والكابشن؟

يستدعي `tts.py` Edge-TTS بالصوت المحدد للغة. الناتج ليس MP3 فقط، بل word boundaries أيضاً. بعد ذلك:

1. ينسخ MP3 إلى `public/generated/<job-id>/voice.mp3`.
2. يقيس مدة الصوت الفعلية بـword cues أو FFprobe.
3. يربط narration segments بالكلمات الفعلية.
4. يبني captions من `narrationSegments` أو word boundaries.
5. يضع captions القصيرة على beat المناسب.
6. يطبق سياسة English captions داخل الفيديو. في الإعداد الحالي، الكلام الصوتي والـmove labels هما الأساس، ويمكن تعطيل English caption track الطويل حتى لا يغطي board labels.

بذلك لا يبقى النص طويلاً على الشاشة طوال الفيديو ولا يسبق الصوت أو يتأخر عنه. المصدر الأساسي للتوقيت هو الصوت الفعلي، لا تخمين مدة الجملة.

## 14. كيف تُحسب مدة الفيديو؟

لا توجد مدة ثابتة لكل الفيديوهات. `timing.py` يوازن بين:

- طول narration.
- مدة الصوت الفعلية.
- عدد النقلات.
- عدد beats لكل نقلة.
- captions.
- `target_seconds` إن كان موجوداً كهدف تحريري.

يمكن أن يكون درس البداية حوالي 45–60 ثانية، ودرس قطعة أطول، ومباراة كاملة أطول بكثير. لا يجبر النظام كل المحتوى على قالب قصير واحد.

## 15. الناقد الإبداعي قبل الرندر

`creative_critic.py` يعمل قبل إنتاج thumbnail وقبل YouTube upload. يقوم بالفحص الحتمي أولاً:

- هل توجد `claimProof`؟
- هل claim types تطابق primitives؟
- هل كل move له beats؟
- هل scene presentation واضحة؟
- هل توجد عربية أو مصطلح ممنوع؟
- هل النتيجة تناسب نوع الحلقة؟

إذا وجد مشكلة، يستطيع تطبيق إصلاح محدود على حقول العرض فقط. لا يستطيع تغيير FEN أو النقلات أو claim proof بالحدس. بعد الإصلاح يعاد فحص storyboard. عدد التكرارات محدود بـ`PREPUBLISH_CRITIC_MAX_ITERATIONS=2` في production.

إذا طلب AI repair بلا sceneId أو scene_repairs قابلة للتطبيق، لا يُدخل النظام تغييرات عشوائية. إذا كان deterministic contract صالحاً، يسجل الطلب غير القابل للتنفيذ ويتابع بالـstoryboard الموثق؛ أما الخطأ الحتمي الحقيقي فيظل fail-closed.

## 16. الرندر بـRemotion

بعد اجتياز pre-render critic، يكتب النظام job JSON في:

```text
output/jobs/<job-id>/job.json
public/generated/<job-id>/job.json
```

ثم يشغل Remotion composition باسم `XiangqiComposition`. Remotion يقرأ job JSON ويرسم:

- رقعة 9×10 من نقاط التقاطع.
- river وpalaces.
- قطع SVG المرخصة.
- حركة كل نقلة.
- arrows وhighlight وpiece anchors.
- Horse Leg أو Elephant Eye أو Cannon Screen حسب claim.
- move labels وcaption timing.
- صوت MP3.

الناتج MP4 H.264 عمودي 1080×1920، ويُحفظ في مجلد job. في الفيديو الجديد `en-001` كان الناتج 48.49 ثانية.

## 17. الفحص البصري بعد الرندر

بعد إنتاج MP4، يستدعي `visual_qa.py` فحص frames فعلية، وليس فقط JSON. يبحث عن:

- ظهور الرقعة الصحيحة.
- river وpalaces في أماكنهما.
- تطابق الحركة مع narration segment.
- primitive المطلوب في المشهد.
- عدم وجود overlap بين caption وmove label.
- عدم وجود text عربي.
- عدم وجود frame فارغ أو أصول مفقودة.
- أن ملف الصوت والفيديو قابلان للقراءة.

بعد ذلك يستدعي النظام final creative critic مع `visualQA`. لا يعتبر MP4 صالحاً للنشر إلا إذا كان `visualQA.ok=true` وقرار critic هو approve والنتيجة فوق الحد الأدنى.

## 18. thumbnail قبل النشر

بعد نجاح الرندر والـvisual QA والـfinal critic، يستدعي النظام `thumbnail.py`. ينشئ thumbnail English، ويتحقق من أبعادها وحجمها وصيغتها، ثم يضعها داخل `prepublish_thumbnails`.

إذا فشلت thumbnail gate يتوقف النظام قبل YouTube upload. لا ينشر الفيديو أولاً ثم يحاول إصلاح الغلاف لاحقاً.

## 19. كيف يُبنى العنوان والوصف والـtags والـhashtags؟

الـdirector يعطي عنواناً أولياً، لكن `youtube_publisher.build_metadata()` يطبق سياسة القناة في `config/youtube_metadata_policy.json`:

1. يحدد اللغة.
2. يحدد `content_type`.
3. يحدد سلسلة القناة وplaylist المناسبة.
4. يضيف title prefix إذا لم يكن موجوداً.
5. يقطع العنوان إلى الحد الأقصى المسموح.
6. يبني tags من base tags وsecondary keywords وعنوان الدرس وtheme وsource kind.
7. يبني hashtags من السياسة، مع حد أقصى.
8. يبني description من template يشمل hook وseries name وlanguage label وplaylist CTA وchannel CTA وملاحظة أن التحليل تعليمي أصلي.
9. يحدد `categoryId` و`defaultAudioLanguage` و`privacyStatus`.

إذن الذكاء الاصطناعي يساعد في الفكرة والhook والعنوان، لكن السياسة الحتمية هي التي تضمن اتساق metadata وعدم خروج الوصف عن هوية القناة.

## 20. كيف يختار playlist؟

كل content type في السياسة مرتبط بـplaylist key. مثلاً `en-001` اختير له:

```text
en-start-here
```

يقوم publisher بالبحث عن playlist بالعنوان داخل قناة المستخدم. إذا وجدت يستخدمها. إذا لم توجد وكان `YOUTUBE_AUTO_CREATE_PLAYLISTS=1`، ينشئها تلقائياً. إذا وجد playlist ID قديماً لكنه أعاد `playlistNotFound`، يستبعد ID القديم وينشئ أو يحل playlist جديدة بدلاً من تكرار الفشل.

## 21. ماذا يحدث عند رفع الفيديو إلى YouTube؟

عند `YOUTUBE_PUBLISH_ENABLED=1` و`YOUTUBE_PUBLISH_MODE=public`، يعمل publisher بالترتيب التالي:

1. يقرأ OAuth token من `YOUTUBE_OAUTH_TOKEN_JSON`.
2. يتحقق من صلاحيات `youtube.upload` و`youtube.force-ssl`.
3. يجهز localization assets قبل الرفع إذا كانت localization مفعلة.
4. يجهز thumbnail ويفحصها.
5. يرفع MP4 بواسطة resumable upload.
6. يحصل على `video_id`.
7. يحل playlist أو ينشئها.
8. يضيف الفيديو إلى playlist.
9. يرفع caption tracks المطلوبة.
10. يحدّث العنوان والوصف المترجمين English/Chinese.
11. يرفع thumbnail English.
12. يسجل النتيجة في SQLite.
13. لا يعتبر الوظيفة مكتملة إلا عندما تصبح الحالة `published`.

المسار الصيني يجهز captions وmetadata الصينية، والصوت الصيني يمكن توليده كـlocalization asset. أما multi-audio track في YouTube فله قيود API خاصة؛ لذلك يظهر في metadata عند الحاجة كـ`generated_studio_upload_required` إذا كان يحتاج إدخالاً من YouTube Studio، ولا يُدّعى أنه أُضيف كمسار صوت متعدد إذا لم تؤكده API.

## 22. الحماية من duplicate upload

هناك ثلاث حمايات مستقلة:

1. **Stable job ID:** job ID يعتمد على candidate ID واللغة، وليس على وقت التشغيل.
2. **SQLite publication state:** إذا كانت الحالة `published` لا يعيد النظام الرندر أو الرفع.
3. **Resumable statuses:** إذا نجح upload وفشلت playlist أو localization أو thumbnail، يحفظ video ID ويعيد محاولة الجزء الفاشل فقط.

إذا كان الفيديو العام موجوداً، لا يستخدم النظام render جديداً في retry العادي. وإذا حدث deletion مقصود، يسجل old video ID في `publication_reset_history`. full-channel restart الموثق يسمح بإنتاج replacement، أما remediation الفردي فيبقى محمياً إلى أن تتم الموافقة الصريحة.

## 23. ماذا يحدث بعد النشر؟

بعد نجاح video upload وlocalization والthumbnail والplaylist، يكتب publisher:

- `youtube_publications.status = published`.
- video ID وURL.
- playlist ID وURL.
- metadata وlocalization result.
- attempts وtimestamps.

ثم يحدّث `youtube_videos` و`youtube_video_playlists`، ويحدّث candidate إلى `published`، ويحدّث curriculum episode إلى `published`. بعد ذلك يرفع workflow SQLite إلى artifact ويعمل commit إلى GitHub كي تبدأ الجولة التالية من الحالة الصحيحة.

## 24. حالات الفشل بالتفصيل

| نقطة الفشل | ما يفعله النظام |
|---|---|
| مصدر grounding غير متاح في production | يتوقف قبل script generation. |
| أقل من مصادر evidence المطلوبة | يتوقف قبل director. |
| AI Router فشل على مفتاح | ينتقل للمفتاح التالي حسب المشروع المستقل. |
| انتهت مفاتيح Gemini | ينتقل إلى النموذج التالي ثم Hugging Face حسب chain؛ إذا كانت كل السلسلة غير متاحة يفشل production ولا يخترع نصاً غير موثقاً. |
| director أعاد JSON غير صالح | يستخدم sanitizer أو fallback فقط في اختبار غير ناشر؛ production يظل محكوماً بعقد grounding. |
| move غير قانونية | job blocked قبل audio/render. |
| claim سببي خاطئ | job blocked قبل storyboard/render. |
| primitive غير مطابق للclaim | storyboard gate يفشل. |
| creative critic رفض | إصلاح محدود ثم إعادة الفحص، بحد أقصى iteration budget. |
| render فشل | job failed ولا upload. |
| visual QA فشل | لا thumbnail ولا upload. |
| thumbnail gate فشل | لا upload. |
| YouTube upload نجح وplaylist فشلت | status `uploaded_playlist_pending`، يعاد playlist فقط. |
| captions/localization فشلت بعد وجود video ID | status `published_localization_pending`، يحفظ video ID ولا يرفع duplicate. |
| thumbnail API quota | status `published_thumbnail_pending`، يعاد thumbnail لاحقاً. |
| YouTube quota | reconciliation يسجل cooldown ويعيد المحاولة لاحقاً وفق السياسة، ولا ينشئ فيديو مكرراً. |
| workflow انقطع بعد النشر | SQLite وcatalog يحفظان الهوية، والتشغيل التالي يبدأ reconciliation. |

## 25. مثال حقيقي: أول فيديو بعد إعادة البدء

بعد حذف كل الفيديوهات القديمة وإعادة ضبط catalog، اختار النظام:

```text
lesson: en-001-what-is-xiangqi
selection_mode: curriculum
content_type: definition
playlist: en-start-here
```

هذا درس بداية وليس لعبة كاملة. كان static board lesson؛ لذلك لم يلعب مباراة ولم يخترع نقلات. شرح:

- أن Xiangqi لعبة بين جيشين.
- الهدف checkmate للـGeneral.
- شبكة 9×10 من نقاط التقاطع.
- river.
- palace.
- بداية setup والقطع.
- خريطة طريق للدروس التالية.
- مثال تمهيدي على Cannon screen.

اجتاز البحث والـgrounding والـclaim proof والـstoryboard والـcritic والرندر والـvisual QA والthumbnail، ثم نُشر public بالهوية الجديدة:

```text
https://www.youtube.com/watch?v=GCgUvitq9lA
```

تحليل MP4 بعد إنتاجه أكد أن الرقعة 9×10 صحيحة، river وpalaces ظاهرة، الصوت والمشاهد متزامنان، لا توجد العربية، ولا توجد قراءة خام لأكواد الإحداثيات، وأن الفيديو درس Start Here وليس full game.

## 26. ما الذي يحتاجه المستخدم؟

بعد إعداد الأسرار مرة واحدة، لا يحتاج المستخدم إلى كتابة عنوان أو وصف أو سيناريو أو تحديد المشاهد. المطلوب عادة هو:

1. الحفاظ على OAuth صالح في `YOUTUBE_OAUTH_TOKEN_JSON`.
2. الحفاظ على key pools الخاصة بـAI Router.
3. التأكد من أن `YOUTUBE_PUBLISH_ENABLED=1` و`YOUTUBE_PUBLISH_MODE=public`.
4. ترك GitHub Actions يعمل.
5. مراجعة الفيديو عند الرغبة، وليس كشرط للتشغيل.

إذا أراد المستخدم تغيير ترتيب القناة، يعدل curriculum config. إذا أراد تغيير نماذج الذكاء الاصطناعي، يعدل مستودع AI Router المستقل. إذا أراد تغيير سياسة العناوين أو playlist، يعدل ملفات config الخاصة بـYouTube. لا يحتاج إلى تعديل كل الملفات.

## 27. ملخص المسؤولية في جملة واحدة

**الخطة تختار ماذا ننتج، قاعدة البيانات تتذكر أين وصلنا، الاكتشاف يوسّع الأفكار، grounding يثبت المعلومات العامة، AI director يصوغ الشرح، Xiangqi verifier يثبت النقلات والادعاءات، visual director يختار التعبير المرئي، TTS يضبط الصوت والكابشن، Remotion يرندر، critic وvisual QA يمنعان العيوب، YouTube publisher ينشر ويحافظ على الهوية، وGitHub Actions يعيد الدورة تلقائياً دون جلسة Manus مفتوحة.**

## المراجع البرمجية

[1]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/README.md "Chinese Cheese Video README"
[2]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/docs/grounded_script_generation_contract.md "Grounded Script Generation and Xiangqi Claim Contract"
[3]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/run_pipeline.py "End-to-end pipeline"
[4]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/director.py "Director and structured script contract"
[5]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/xiangqi_claims.py "Mechanical Xiangqi claims verifier"
[6]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/visual_director.py "Semantic visual director"
[7]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/creative_critic.py "Pre-publication creative critic"
[8]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/python/youtube_publisher.py "YouTube metadata and publication engine"
[9]: https://github.com/ysrg2003/chinese-cheese-video/blob/master/.github/workflows/render-video.yml "Autonomous GitHub Actions workflow"

## المراجع الخارجية للقواعد والـgrounding

[10]: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en "World Xiangqi Federation Rules"
[11]: https://www.xiangqi.com/help/pieces-and-moves "Xiangqi.com Pieces and Moves"
[12]: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess "Chess.com Chinese Chess Guide"
[13]: https://ai.google.dev/gemini-api/docs/google-search "Gemini Grounding with Google Search"
