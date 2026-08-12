# تقرير إكمال النشر التلقائي إلى Xiangqi Lab

## الحالة

تم تنفيذ مسار النشر الآلي داخل مشروع **Chinese Cheese Video**. بعد تفعيل OAuth مرة واحدة وإضافة Secret المطلوب إلى GitHub، سيقوم التشغيل المجدول بعد كل رندر ناجح بإنشاء metadata، ورفع الفيديو إلى قناة **Xiangqi Lab | 中国象棋实验室**، ونشره **عاماً مباشرة**، ثم إضافته إلى قائمة التشغيل المطابقة للغة ونوع المحتوى.

القناة: https://www.youtube.com/@XiangqiLab

## ما تم تنفيذه

| الجزء | النتيجة |
| --- | --- |
| OAuth YouTube | دعم `YOUTUBE_OAUTH_TOKEN_JSON` باستخدام Google OAuth refresh token آمن |
| رفع الفيديو | `videos.insert` مع resumable upload وbackoff للأخطاء العابرة |
| النشر العام | `YOUTUBE_PUBLISH_MODE=public` في policy وworkflow و`.env.example` |
| metadata | title حتى 100 حرف، description حتى 5000 حرف، tags دقيقة، hashtags محدودة |
| اللغات | `en` و`zh` فقط؛ لا عربية ولا صوت أنثوي |
| التصنيف | `content_type` يحدد playlist key منفصلاً لكل لغة |
| قوائم التشغيل | إيجاد القائمة بالعنوان أو إنشاؤها تلقائياً ثم `playlistItems.insert` |
| منع التكرار | job ID ثابت لكل candidate واللغة، وجدول `youtube_publications` في SQLite |
| التعافي | حفظ video ID بعد الرفع؛ إعادة محاولة القائمة دون رفع فيديو ثانٍ |
| الجدولة | GitHub Actions الحالي ثلاث مرات يومياً مع متغيرات النشر الجديدة |
| Supabase | عند استخدام Supabase للمحتوى، يبقى سجل YouTube في SQLite المحلي لضمان التوافق |

## الاختبارات المنفذة

تم تشغيل الاختبارات التالية بنجاح:

```text
5 tests — OK
- English metadata maps to EN tactics playlist
- Chinese metadata maps to 中文 endgame playlist
- SQLite publication state is persistent and idempotent
- Fake YouTube API upload → playlist creation → playlist item insertion
- Retry reuses existing video ID and does not upload again

workflow validation passed
python compilation passed
JSON validation passed
Git diff check passed
public-publish-validation-ok
```

تم تثبيت والتحقق من مكتبات `google-api-python-client` و`google-auth` و`google-auth-oauthlib`. لم يُنفّذ رفع حقيقي أثناء الاختبار لأن ذلك يتطلب refresh token الخاص بمالك قناة YouTube.

## الملفات الرئيسية

```text
python/youtube_publisher.py
python/local_store.py
python/run_pipeline.py
python/automation_runner.py
python/test_youtube_publisher.py
python/test_youtube_publisher_fake_api.py
config/youtube_metadata_policy.json
config/youtube_playlists.json
.github/workflows/render-video.yml
docs/youtube_autopublish_setup.md
docs/youtube_automation_research.md
```

## الإجراء الوحيد المتبقي من المالك

1. في Google Cloud، أنشئ مشروعاً وفعّل **YouTube Data API v3**.
2. أنشئ OAuth consent screen واجعل التطبيق **In production** حتى لا ينتهي refresh token بعد سبعة أيام في حالة External Testing.[1]
3. أنشئ OAuth Client من نوع **Desktop app** ونزّل `client_secret.json`.
4. محلياً شغّل:

```bash
python3 -m pip install -r python/requirements.txt
python3 python/youtube_publisher.py \
  --auth-client-secrets /path/to/client_secret.json \
  --auth-output /path/to/youtube-token.json
```

5. خزّن محتوى `youtube-token.json` كاملاً في GitHub Secret باسم:

```text
YOUTUBE_OAUTH_TOKEN_JSON
```

6. أضف GitHub Variables التالية:

```text
YOUTUBE_PUBLISH_ENABLED=1
YOUTUBE_PUBLISH_MODE=public
YOUTUBE_AUTO_CREATE_PLAYLISTS=1
```

بعد هذه الخطوات، لا يحتاج التشغيل اليومي إلى تدخل منك. سيكون كل فيديو ناجح النشر عاماً مباشرة، وستُضاف النسخة الإنجليزية أو الصينية إلى قائمتها المناسبة تلقائياً.

## ملاحظة تشغيلية مهمة

لا تضع `client_secret.json` أو `youtube-token.json` أو محتوى `YOUTUBE_OAUTH_TOKEN_JSON` في Git أو هذه المحادثة. الملفات محمية في `.gitignore`، والـSecret يجب أن يبقى داخل GitHub Actions Secrets فقط.

## المراجع

[1]: https://developers.google.com/identity/protocols/oauth2 "Google Identity — Using OAuth 2.0 to Access Google APIs"
[2]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API — Implementing OAuth 2.0 Authorization"
[3]: https://developers.google.com/youtube/v3/guides/uploading_a_video "YouTube Data API — Upload a Video"
[4]: https://developers.google.com/youtube/v3/docs/playlistItems/insert "YouTube Data API — PlaylistItems: insert"
[5]: https://support.google.com/youtube/answer/57404?hl=en&co=GENIE.Platform%3DDesktop "YouTube Help — Edit video settings"
