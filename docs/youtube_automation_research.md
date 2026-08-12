# YouTube Automation Research — Official API Findings

**تاريخ البحث:** 13 أغسطس 2026

## النتيجة المعمارية الأساسية

النشر التلقائي إلى قناة YouTube يتطلب **OAuth 2.0** نيابة عن مالك القناة. مفتاح `YOUTUBE_API_KEY` وحده مناسب للقراءات العامة المحدودة، لكنه لا يخول رفع فيديو أو تعديل قوائم تشغيل خاصة. كما أن YouTube Data API لا يدعم مسار Service Account لقناة شخصية؛ التوثيق الرسمي يذكر أن المحاولة تؤدي إلى `NoLinkedYouTubeAccount`.

## العمليات الرسمية المطلوبة

| العملية | API | الوظيفة | التفويض |
| --- | --- | --- | --- |
| رفع الفيديو | `videos.insert` | إنشاء الفيديو مع title وdescription وtags وcategoryId وprivacyStatus | OAuth، ويفضل scope `https://www.googleapis.com/auth/youtube.upload` |
| استئناف الرفع | Resumable Upload Protocol | استكمال الرفع بعد انقطاع الشبكة باستخدام session URI وHTTP 308 | نفس OAuth |
| إضافة إلى قائمة تشغيل | `playlistItems.insert` | إضافة `videoId` إلى `playlistId` بعد نجاح الرفع | scope أوسع مثل `https://www.googleapis.com/auth/youtube` أو `youtube.force-ssl` |
| التحقق | `videos.list` و`playlistItems.list` | تأكيد video ID وplaylist association والحالة | OAuth |

## القيود التي تؤثر على التنفيذ

عملية `playlistItems.insert` تكلف 50 وحدة من حصة API، وتحتاج `snippet.playlistId` و`snippet.resourceId`. لا يمكن إدراج الفيديو في قائمة Uploaded Videos الخاصة، ولا ينبغي تحديد `position` إلا إذا كانت القائمة مضبوطة على Manual ordering. يجب حفظ video ID وplaylist ID وحالة كل محاولة في SQLite حتى لا تعيد GitHub Actions الرفع أو الإدراج بعد نجاح جزئي.

## سياسة الرفع المقترحة

بناءً على قرار مالك القناة، يضبط التشغيل الفعلي `YOUTUBE_PUBLISH_MODE=public`، وتُجرى اختبارات metadata محلياً عبر `--dry-run` قبل أول رفع حقيقي. لا يجب أن يفشل الإنتاج كله إذا نجح الرفع وفشل إدراج قائمة التشغيل؛ يسجل النظام الحالة `uploaded_playlist_pending` ويعيد محاولة الإدراج باستخدام `videoId` الموجود بدلاً من إنشاء فيديو مكرر.

## البيانات الوصفية التي يدعمها الرفع

يمكن تحديد `title` و`description` و`tags` و`categoryId` و`privacyStatus` عند `videos.insert`. بالنسبة لقناة Xiangqi Lab، الفئة الافتراضية المقترحة هي `Games`، مع فصل اللغة في العنوان والوصف وقائمة التشغيل: الإنجليزية أولاً والصينية المبسطة ثانياً، بلا عربية أو صوت أنثوي أو خلط لغوي في الفيديو الواحد.

## استراتيجية الاعتمادية

يستخدم الرفع resumable upload، مع exponential backoff لأخطاء الشبكة و5xx، وحفظ حالة الجلسة والنتيجة. بعد `201 Created` يُحفظ `videoId` فوراً. لا يُعتبر job منشوراً إلا بعد نجاح الرفع والتحقق من الإضافة إلى قائمة التشغيل، أو يسجل حالة جزئية قابلة للاستئناف.

## المراجع الرسمية

[1]: https://developers.google.com/youtube/v3/guides/authentication — Implementing OAuth 2.0 Authorization
[2]: https://developers.google.com/youtube/v3/guides/uploading_a_video — Upload a Video
[3]: https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol — Resumable Uploads
[4]: https://developers.google.com/youtube/v3/docs/playlistItems/insert — PlaylistItems: insert

## ممارسات metadata والنمو من المصادر الرسمية

| العنصر | القاعدة القابلة للتطبيق |
| --- | --- |
| العنوان | واضح وصادق ومطابق للفيديو؛ الحد الرسمي 100 حرف. نضع الوعد الأساسي والعبارة القابلة للبحث في البداية ثم hook قصيراً. |
| الوصف | الحد الرسمي 5,000 حرف. نضع في أول سطرين تعريف الموضوع والوعد، ثم فهرساً زمنياً عندما تتوفر مدة الفيديو، ثم دعوة لمشاهدة السلسلة والرابط المناسب. |
| Tags | فائدتها الأساسية تصحيح أخطاء البحث الإملائية؛ YouTube يذكر أنها تلعب دوراً محدوداً في الاكتشاف بخلاف العنوان والوصف والمحتوى نفسه. لذلك نستخدم مجموعة صغيرة دقيقة لا حشواً طويلاً. |
| Hashtags | تربط الفيديوهات ذات الموضوع نفسه. تظهر حتى ثلاثة منها بجانب العنوان، ويجب أن تكون مرتبطة مباشرة بالمحتوى. لا نتجاوز العدد الكبير؛ إذا تجاوز الفيديو 60 hashtag يتجاهل YouTube الهاشتاقات، والحشو قد يخالف سياسة metadata المضللة. |
| الصور المصغرة | نستخدم رقعة وقطعة وتهديداً واحداً ووعداً بصرياً واضحاً. YouTube يوصي باختبار بدائل العنوان والصورة وترك بيانات المشاهدة تقود القرار عندما تتاح الميزة. |
| الاتجاه التحريري | نمزج الموضوعات الرائجة مع موضوعات evergreen، ونجرب سلاسل وصيغاً متعددة، ثم نضاعف ما تثبته Analytics بدلاً من افتراض أرقام نجاح ثابتة. |
| الجودة والسياسة | العنوان والوصف والصورة يجب أن تعكس المحتوى بدقة، مع الإفصاح عن المحتوى الاصطناعي أو المعدل إذا بدا واقعياً، وتجنب الكلمات المضللة والهاشتاقات غير ذات الصلة. |

## سياسة metadata لـ Xiangqi Lab

يولد النظام لكل فيديو أربعة مستويات من الكلمات: `primary_keyword` موضوع البحث الرئيس، `secondary_keywords` نوايا بحث مرتبطة، `supporting_keywords` مرادفات وأخطاء إملائية مفيدة للـ tags فقط، و`hashtags` عدد محدود من المصطلحات القابلة للنقر. لا تُنسخ جميع الكلمات داخل الوصف على شكل قائمة؛ الوصف يظل نصاً طبيعياً يخدم المشاهد.

القوالب تبدأ بعنوان مستقل لكل لغة. الإنجليزية تستخدم كلمات مثل `xiangqi`, `Chinese chess`, `xiangqi tactics`, `xiangqi puzzle`, `xiangqi opening` حسب الموضوع. الصينية تستخدم `中国象棋`, `象棋战术`, `象棋残局`, `象棋开局`, `象棋谜题` حسب الموضوع. لا يخلط النظام العنوان أو الصوت أو الكابشن بين اللغتين.

الهاشتاقات الافتراضية القصوى ثلاثة إلى خمسة عند الحاجة، مثل `#Xiangqi #ChineseChess #XiangqiTactics` للفيديو الإنجليزي، و`#中国象棋 #象棋 #象棋战术` للفيديو الصيني. إذا لم يضف الهاشتاق قيمة اكتشاف واضحة، يُترك فارغاً بدلاً من الحشو.

## المراجع الإضافية

[5]: https://www.youtube.com/creators/grow/optimize-your-content/ — Optimize & evolve your content
[6]: https://support.google.com/youtube/answer/57404?hl=en&co=GENIE.Platform%3DDesktop — Edit video settings
[7]: https://support.google.com/youtube/answer/6390658 — Find playlists & videos using hashtags
[8]: https://www.youtube.com/creators/resources/ — Resources for YouTube creators
