# حالة تفعيل OAuth وGitHub للنشر التلقائي

**تاريخ التحديث:** 13 أغسطس 2026

## ما اكتمل

تم التحقق من ملف OAuth المرفوع من مالك القناة: هو تطبيق Google OAuth من نوع `installed` ويحتوي الحقول المطلوبة. أُكملت موافقة الحساب الذي يملك قناة Xiangqi Lab، وتم إصدار refresh token في ملف محلي محمي ومستثنى من Git.

تم إنشاء مستودع خاص للمشروع ورفعه:

```text
https://github.com/ysrg2003/chinese-cheese-video
```

## إعداد GitHub Actions

فشلت إضافة Repository Secret من GitHub CLI بسبب أن تفويض CLI الحالي يفتقر إلى صلاحية إدارة Actions Secrets (`HTTP 403 Resource not accessible by integration`). لذلك فُتحت واجهة GitHub الرسمية في المتصفح الشخصي عند صفحة إنشاء secret.

**السر المحفوظ بنجاح:** `YOUTUBE_OAUTH_TOKEN_JSON`

لن تسجل هذه الوثيقة ولا أي ملف في المستودع قيمة OAuth أو refresh token أو client secret.

## الإعدادات المطلوبة بعد إضافة السر

| GitHub Variable | القيمة |
| --- | --- |
| `YOUTUBE_PUBLISH_ENABLED` | `1` — تم الحفظ |
| `YOUTUBE_PUBLISH_MODE` | `public` — تم الحفظ |
| `YOUTUBE_AUTO_CREATE_PLAYLISTS` | `1` |

تم التحقق من OAuth عبر YouTube Data API للقراءة فقط: الحساب المفوّض يعيد القناة `Xiangqi Lab | 中国象棋实验室` بالمعرّف `UCM7pTdgZRwDZ2gZDtC6SITg`. لم يُنفّذ أي upload أو write أثناء هذا الفحص. لا توجد قوائم تشغيل حالياً، وسيُنشئها الناشر تلقائياً عند أول فيديو لأن `YOUTUBE_AUTO_CREATE_PLAYLISTS=1`.

بعد حفظ السر والمتغيرات، سيكون كل فيديو ناجح النشر عاماً مباشرة، ويضاف تلقائياً إلى قائمة التشغيل التي يحددها `content_type` واللغة.
