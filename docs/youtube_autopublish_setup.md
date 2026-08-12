# النشر التلقائي إلى قناة Xiangqi Lab

هذا الدليل يضيف خطوة نشر مستقلة إلى خط إنتاج **Chinese Cheese Video**. بعد اكتمال الرندر، يبني النظام metadata، يرفع MP4 إلى قناة Xiangqi Lab، يبحث عن قائمة التشغيل الملائمة أو ينشئها، يضيف الفيديو إليها، ويسجل النتيجة في SQLite. إذا انقطع الرفع أو فشلت إضافة قائمة التشغيل، يعيد المحاولة باستخدام الهوية نفسها ولا ينشئ فيديوًّا مكرراً.

> **مهم:** لا يعمل رفع الفيديو بمفتاح YouTube API العام وحده. يحتاج YouTube Data API إلى OAuth 2.0 نيابة عن مالك القناة. كما أن Service Account ليس بديلاً صالحاً لقناة YouTube شخصية؛ يذكر التوثيق الرسمي أن هذا المسار يؤدي إلى `NoLinkedYouTubeAccount`.[1]

## 1. ما الذي نُفّذ في المشروع

| المكوّن | الملف | الوظيفة |
| --- | --- | --- |
| الناشر | `python/youtube_publisher.py` | OAuth، metadata، resumable upload، إنشاء القائمة، الإدراج، backoff |
| سياسة metadata | `config/youtube_metadata_policy.json` | قواعد العناوين والوصف والكلمات والهاشتاقات لكل نوع ولغة |
| قوائم التشغيل | `config/youtube_playlists.json` | أسماء ووصف قوائم EN و中文 ومفتاح كل قائمة |
| حالة النشر | `python/local_store.py` | جدول `youtube_publications` مع video ID وplaylist ID والمحاولات |
| نقطة الربط | `python/run_pipeline.py` | يستدعي الناشر بعد نجاح الرندر |
| الهوية المستقرة | `python/automation_runner.py` | يجعل job ID ثابتاً لكل candidate واللغة حتى لا تتكرر الفيديوهات |
| سير العمل | `.github/workflows/render-video.yml` | يمرر OAuth ويشغل النشر بعد الإنتاج |
| البحث الرسمي | `docs/youtube_automation_research.md` | خلاصة توثيق Google وYouTube والسياسات |

## 2. تدفق التنفيذ بعد التفعيل

```text
GitHub Actions schedule
        ↓
content_discovery.py
        ↓
اختيار candidate جديد ببصمة SHA-256
        ↓
automation_runner.py — EN ثم 中文
        ↓
Director + TTS + Remotion render
        ↓
youtube_publisher.py
        ├─ يبني title / description / tags / hashtags
        ├─ videos.insert عبر resumable upload
        ├─ يحفظ video_id فور النجاح
        ├─ يجد playlist أو ينشئها
        ├─ playlistItems.insert
        └─ يتحقق ويسجل published في SQLite
```

إذا نجح الرفع وفشلت القائمة، تسجل الحالة `uploaded_playlist_pending` أو `failed` مع `video_id`. في التشغيل التالي يستخدم النظام video ID المحفوظ ويعيد محاولة الإضافة إلى القائمة بدلاً من رفع MP4 جديد.

## 3. إعداد Google Cloud مرة واحدة

افتح [Google Cloud Console](https://console.cloud.google.com/) بحساب يملك قناة **Xiangqi Lab**.

### 3.1 إنشاء مشروع API

أنشئ مشروعاً منفصلاً، مثلاً `xiangqi-lab-youtube-publisher`. من **APIs & Services → Library** فعّل **YouTube Data API v3**.

### 3.2 إعداد شاشة الموافقة OAuth

من **APIs & Services → OAuth consent screen** أنشئ شاشة موافقة. استخدم اسماً واضحاً مثل **Xiangqi Lab Publisher**، وأضف البريد الذي يملك قناة YouTube. إذا اختير نوع **External** فيجب إضافة الحساب كـ Test user أثناء الإعداد الأولي.

للاستخدام اليومي المستمر، اجعل حالة التطبيق **In production** بعد إكمال متطلبات Google التي تظهر في لوحة التحكم. توثيق Google يذكر أن تطبيق External في وضع `Testing` يعطي refresh token ينتهي بعد سبعة أيام عندما لا تكون الصلاحيات مقتصرة على بيانات الملف الشخصي.[2] لذلك لا تترك التطبيق في Testing إذا كان المطلوب نشر يومي بلا تدخل.

بناءً على قرار مالك القناة، كل فيديو ينجح في التحقق النهائي سيُنشر **عاماً مباشرة**. لا يغيّر النظام الفيديو إلى `unlisted` أو `private` تلقائياً؛ لذلك يكون الاختبار الأول محلياً عبر `--dry-run`، ثم يُجرى أول تشغيل حقيقي بعد مراجعة metadata.

### 3.3 إنشاء OAuth Client

من **APIs & Services → Credentials → Create Credentials → OAuth client ID** اختر **Desktop app**. نزّل ملف JSON، وسمّه محلياً:

```text
client_secret.json
```

لا تضع هذا الملف داخل المشروع ولا ترفعه إلى GitHub. ملف client secret ليس هو refresh token؛ كلاهما يجب حمايتهما، ولا ينبغي إرسالهما في المحادثة.

## 4. إنشاء refresh token محلياً

من جذر المشروع نفّذ الخطوات التالية على جهازك الشخصي أو في بيئة محلية تفتح متصفحاً:

```bash
cd /path/to/chinese-cheese-video
python3 -m pip install -r python/requirements.txt
python3 python/youtube_publisher.py \
  --auth-client-secrets /path/to/client_secret.json \
  --auth-output /path/to/youtube-token.json
```

يفتح النظام صفحة Google. اختر الحساب الذي يملك قناة **Xiangqi Lab**، وافق على صلاحيات رفع وإدارة الفيديو وقوائم التشغيل، ثم ينتج:

```text
youtube-token.json
```

تحقق محلياً من أن الملف يحتوي على `refresh_token`، ثم خزّنه في GitHub Secret. لا تعرض محتواه في الطرفية ولا في هذه المحادثة.

## 5. إضافة Secret وVariables إلى GitHub Actions

في إعدادات مستودع المشروع افتح **Settings → Secrets and variables → Actions**.

### Secret المطلوب

أضف Secret باسم:

```text
YOUTUBE_OAUTH_TOKEN_JSON
```

وقيمته هي محتوى `youtube-token.json` كاملاً، بما في ذلك `refresh_token` و`client_id` و`client_secret` و`token_uri`.

### Variables المطلوبة

أضف Variables التالية:

| الاسم | اختبار أولي | التشغيل الفعلي |
| --- | --- | --- |
| `YOUTUBE_PUBLISH_ENABLED` | `0` | `1` |
| `YOUTUBE_PUBLISH_MODE` | `public` | `public` |
| `YOUTUBE_AUTO_CREATE_PLAYLISTS` | `1` | `1` |

لا تجعل `YOUTUBE_OAUTH_TOKEN_JSON` Variable عادية؛ يجب أن يكون Secret. لا تحتاج عملية النشر إلى `YOUTUBE_API_KEY`، لكن يمكن إبقاؤه اختيارياً لاكتشاف فيديوهات الاتجاهات العامة.

## 6. اختبار آمن قبل النشر العام

> **قرار النشر:** بعد إضافة OAuth وتفعيل الناشر، تكون الفيديوهات العامة هي السلوك المقصود دائماً. لا تستخدم اختباراً حقيقياً غير مدرج؛ استخدم الاختبارات المحلية الجافة أولاً.

### 6.1 اختبار metadata بلا OAuth

```bash
python3 python/youtube_publisher.py \
  --video output/sample.mp4 \
  --job-json output/jobs/<job-id>/job.json \
  --dry-run
```

يجب أن ترى `title` لا يتجاوز 100 حرف، ووصفاً طبيعياً، وعدداً محدوداً من tags وhashtags، و`playlist_key` صحيحاً. لا يرفع هذا الأمر أي ملف.

### 6.2 أول تشغيل عام بعد مراجعة metadata

بعد نجاح اختبار `--dry-run` وإضافة Secret، ضع:

```text
YOUTUBE_PUBLISH_ENABLED=1
YOUTUBE_PUBLISH_MODE=public
```

ثم شغّل workflow يدوياً. هذا التشغيل سينشر الفيديو **عاماً**؛ لذلك يجب مراجعته محلياً قبل التشغيل. تحقق من الآتي:

| الاختبار | النتيجة المطلوبة |
| --- | --- |
| upload | يظهر video ID في سجل workflow وSQLite |
| privacy | الفيديو عام مباشرة كما طلب مالك القناة |
| playlist | توجد قائمة التشغيل المناسبة للغة والنوع |
| duplicate retry | إعادة تشغيل workflow لا تنشئ video ID جديداً |
| language | النسخة الإنجليزية والصينية منفصلتان |
| metadata | لا توجد عربية أو voice female أو كلمات مضللة |

بعد التأكد من أول فيديو عام والقائمة والوصف والصورة المصغرة، لا يحتاج التشغيل اليومي إلى تدخل منك ما دام refresh token صالحاً وأسرار GitHub موجودة. ويظل مفتاح `YOUTUBE_PUBLISH_ENABLED=1` هو حاجز الإيقاف الوحيد إذا احتجت تعطيل النشر لاحقاً.

## 7. سياسة العناوين والوصف والكلمات والهاشتاقات

### العنوان

يولّد النظام عنواناً صادقاً، يضع موضوع Xiangqi الأساسي في البداية، ثم hook قصيراً مرتبطاً بالموقف. الحد الرسمي لعنوان YouTube هو 100 حرف.[3] لا يستخدم النظام عبارات مثل `guaranteed views` أو `viral secret` ولا يضع كلمات غير موجودة في الفيديو.

أمثلة إنجليزية:

```text
Solve This Xiangqi Puzzle | The Cannon Pin
Xiangqi Opening: The One Move Beginners Miss
Can a Beginner Beat an Expert? | Xiangqi Skill Match
```

أمثلة صينية:

```text
解开这道象棋谜题｜炮的牵制
象棋开局：初学者容易漏掉的一步
新手能战胜高手吗？｜象棋等级对局
```

### الوصف

يبدأ الوصف بجملة واضحة عن الموضوع والوعد، ثم اسم السلسلة واللغة وملاحظة الحقوق ودعوة متابعة القائمة والقناة. الحد الرسمي للوصف 5,000 حرف.[3] لا يضع النظام قائمة كلمات مكررة داخل الوصف؛ تُستخدم الكلمات داخل نص طبيعي.

### الكلمات الرئيسية

يستعمل النظام أربعة مستويات مستقلة:

| المستوى | عدد تقريبي | مثال إنجليزي | مثال صيني |
| --- | ---: | --- | --- |
| Primary | 1 | `xiangqi puzzle` | `象棋谜题` |
| Secondary | 3 | `Chinese chess tactics`, `xiangqi checkmate`, `find the best move` | `象棋战术`, `象棋杀法`, `最佳着法` |
| Supporting tags | حتى 15 إجمالاً | أخطاء spelling ومرادفات دقيقة | مرادفات صينية دقيقة |
| Hashtags | 3–5 | `#Xiangqi #ChineseChess #XiangqiPuzzle` | `#中国象棋 #象棋 #象棋谜题` |

تذكر إرشادات YouTube أن tags تفيد أساساً في تصحيح أخطاء البحث، وأن دورها في الاكتشاف محدود؛ لذلك لا نعتمد عليها لتعويض عنوان أو محتوى ضعيف.[3] أما الهاشتاقات فليست سحراً للانتشار: قد تربط الفيديو بموضوع مشابه، ويظهر حتى ثلاثة منها قرب العنوان، لكن الحشو أو الهاشتاقات غير المرتبطة قد يضرّان.[4]

### الصورة المصغرة والاحتفاظ

ينبغي أن تعرض الصورة المصغرة رقعة أو قطعة أو تهديداً واحداً، وأن يجيب أول مشهد في الفيديو عن وعدها بسرعة. توصي مواد YouTube الرسمية بتجربة صيغ وعناوين وصور مختلفة، وباستخدام Analytics لتحديد ما يجذب المشاهدة فعلياً.[5] لذلك يتعامل النظام مع الصورة المصغرة والعنوان بوصفهما وعداً واحداً، ولا يستخدم clickbait لا يفي به الفيديو.

## 8. متى تُضاف قائمة التشغيل؟

بعد الحصول على `video_id`، يستخرج النظام `content_type` من candidate و`language` من job، ثم يبحث عن مفتاح القائمة في `config/youtube_metadata_policy.json`:

| نوع المحتوى | English | 简体中文 |
| --- | --- | --- |
| definition / rules | Start Here / Piece Academy | 象棋入门 / 棋子学院 |
| opening | Opening Lab | 象棋开局 |
| tactics | Tactics 101 | 象棋战术 |
| endgame | Endgame Lab | 象棋残局 |
| advanced_puzzle | Puzzle Ladder | 象棋谜题 |
| full_game | Full Games | 完整棋局讲解 |
| comparison | Comparison Lab | 棋类对比 |
| trend_breakdown | Trending Xiangqi | 象棋热点 |
| skill_match | Skill Matches | 等级对局 |
| viewer_challenge | Viewer Challenges | 观众挑战 |

إذا لم توجد القائمة، ينشئها الناشر تلقائياً عندما يكون `YOUTUBE_AUTO_CREATE_PLAYLISTS=1`. وإذا كانت موجودة، يعثر عليها بالعنوان ويستخدم ID الموجود. لا يضع `position` حتى لا يصطدم بخطأ `manualSortRequired` في قوائم الترتيب غير اليدوي.[6]

## 9. حالات SQLite

الجدول `youtube_publications` يضمن أن الحالة قابلة للفحص بعد كل تشغيل:

| الحالة | المعنى | التصرف التالي |
| --- | --- | --- |
| `not_started` | لم تبدأ عملية النشر | ابدأ الرفع |
| `publishing` | عملية قيد التنفيذ | أعد المحاولة بنفس job ID إذا انقطع التشغيل |
| `uploaded_playlist_pending` | نجح الرفع وفشلت القائمة | استخدم video ID المحفوظ وأعد إدراج القائمة |
| `published` | نجح الرفع والقائمة | لا تعِد الرفع |
| `failed` | فشلت العملية قبل الاكتمال | افحص الخطأ وأعد المحاولة تلقائياً |

كما أن job ID أصبح ثابتاً لكل candidate واللغة، بدلاً من تضمين وقت التشغيل. هذا ضروري حتى لا يحوّل كل retry إلى فيديو جديد.

## 10. حدود الأتمتة

لا يمكن ضمان عدد مشاهدات أو ترتيب بحث أو انتشار؛ لا توجد صيغة metadata تضمن ذلك. ما يمكن ضمانه هو تنفيذ تقني متسق، وصف وعنوان صادقان، تصنيف صحيح، قائمة تشغيل مناسبة، عدم تكرار الرفع، واستعمال Analytics لاحقاً لتعديل القوالب. كما يجب عدم إعادة رفع footage مملوك للغير؛ الاكتشاف يستخدم metadata العامة كإلهام فقط، بينما الفيديو الناتج تحليل أصلي على رقعة Xiangqi.

## المراجع

[1]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API — Implementing OAuth 2.0 Authorization"
[2]: https://developers.google.com/identity/protocols/oauth2 "Google Identity — Using OAuth 2.0 to Access Google APIs"
[3]: https://support.google.com/youtube/answer/57404?hl=en&co=GENIE.Platform%3DDesktop "YouTube Help — Edit video settings"
[4]: https://support.google.com/youtube/answer/6390658 "YouTube Help — Find playlists & videos using hashtags"
[5]: https://www.youtube.com/creators/grow/optimize-your-content/ "YouTube Creators — Optimize & evolve your content"
[6]: https://developers.google.com/youtube/v3/docs/playlistItems/insert "YouTube Data API — PlaylistItems: insert"
[7]: https://developers.google.com/youtube/v3/guides/uploading_a_video "YouTube Data API — Upload a Video"
[8]: https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol "YouTube Data API — Resumable Uploads"
