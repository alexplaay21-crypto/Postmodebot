import json, sys

D = sys.argv[1] if len(sys.argv) > 1 else "locales"

RU = {
"post_ask_text": "✍️ <b>Текст поста</b>\nОтправь текст — форматирование сохранится:\n• выдели текст средствами самого Telegram (жирный, курсив, ссылка, спойлер, цитата) — бот перенесёт всё как есть;\n• или впиши HTML-теги вручную: <code>&lt;b&gt;жирный&lt;/b&gt;</code>, <code>&lt;i&gt;курсив&lt;/i&gt;</code>, <code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code>, <code>&lt;s&gt;зачёркнутый&lt;/s&gt;</code>, <code>&lt;tg-spoiler&gt;спойлер&lt;/tg-spoiler&gt;</code>, <code>&lt;blockquote&gt;цитата&lt;/blockquote&gt;</code>, <code>&lt;a href=\"https://...\"&gt;ссылка&lt;/a&gt;</code> (не смешивай оба способа в одном тексте);\n• Premium-эмодзи можно вставлять прямо в текст.\n\nℹ️ Если к посту будет медиа, текст ограничен 1024 символами, без медиа — 4096.",
"post_ask_media": "🖼 Пришли фото, видео, GIF или файл для поста — или нажми «Пропустить», если медиа не нужно.",
"post_ask_buttons": "🔘 <b>Кнопки-ссылки</b>\nФормат: <code>Текст - ссылка</code>\n\n• Одна кнопка — одна строка:\n<code>Наш канал - https://t.me/example</code>\n\n• Несколько кнопок в одном ряду — через «|»:\n<code>Сайт - https://example.com | Чат - https://t.me/chat</code>\n\n• Каждая новая строка — новый ряд кнопок.\n\n• Цвет кнопки — третьим полем: <code>blue</code>, <code>green</code> или <code>red</code>:\n<code>Купить - https://example.com - green</code>\n\n• Ссылку можно писать без https:// (<code>t.me/example</code>, <code>example.com</code>) или как <code>@username</code>.\n\nИли нажми «Пропустить».",
"post_buttons_invalid": "⚠️ Не нашёл ни одной корректной кнопки. Формат: <code>Текст - https://ссылка</code> (несколько в ряд — через «|»). Попробуй ещё раз или нажми «Пропустить».",
}
EN = {
"post_ask_text": "✍️ <b>Post text</b>\nSend the text — formatting is kept:\n• format it with Telegram's own tools (bold, italic, link, spoiler, quote) and the bot copies it as is;\n• or type HTML tags by hand: <code>&lt;b&gt;bold&lt;/b&gt;</code>, <code>&lt;i&gt;italic&lt;/i&gt;</code>, <code>&lt;u&gt;underline&lt;/u&gt;</code>, <code>&lt;s&gt;strike&lt;/s&gt;</code>, <code>&lt;tg-spoiler&gt;spoiler&lt;/tg-spoiler&gt;</code>, <code>&lt;blockquote&gt;quote&lt;/blockquote&gt;</code>, <code>&lt;a href=\"https://...\"&gt;link&lt;/a&gt;</code> (don't mix both ways in one text);\n• Premium emoji can be pasted right into the text.\n\nℹ️ With media, the text is limited to 1024 characters; without media — 4096.",
"post_ask_media": "🖼 Send a photo, video, GIF or file for the post — or tap “Skip” if you don't need media.",
"post_ask_buttons": "🔘 <b>Link buttons</b>\nFormat: <code>Text - link</code>\n\n• One button per line:\n<code>Our channel - https://t.me/example</code>\n\n• Several buttons in one row — separate with “|”:\n<code>Website - https://example.com | Chat - https://t.me/chat</code>\n\n• Every new line starts a new row.\n\n• Button color — third field: <code>blue</code>, <code>green</code> or <code>red</code>:\n<code>Buy - https://example.com - green</code>\n\n• The link may be written without https:// (<code>t.me/example</code>, <code>example.com</code>) or as <code>@username</code>.\n\nOr tap “Skip”.",
"post_buttons_invalid": "⚠️ No valid buttons found. Format: <code>Text - https://link</code> (several in a row — separated by “|”). Try again or tap “Skip”.",
}
HELP = {
"ru": [
 ("2. Отправь текст поста. Поддерживается HTML-разметка.", "2. Отправь текст поста. Форматирование Telegram (жирный, курсив, спойлер, цитата, Premium-эмодзи) сохраняется; HTML-теги тоже работают."),
 ("3. Отправь фото, GIF или файл.", "3. Отправь фото, видео, GIF или файл."),
 ("4. Добавь кнопки-ссылки или пропусти этот шаг.", "4. Добавь кнопки-ссылки (несколько в ряд — через «|», цвет: blue / green / red) или пропусти этот шаг."),
 ("Можно добавлять кнопки-ссылки. 🔵🟢🔴 — это эмодзи перед текстом кнопки для визуального обозначения.\n\n⚠️ Telegram не поддерживает настоящие цветные inline-кнопки.",
  "Формат: Текст - ссылка. Несколько кнопок в одном ряду — через «|», новая строка — новый ряд. Цвет третьим полем: blue, green или red — кнопка станет по-настоящему синей, зелёной или красной."),
],
"en": [
 ("2. Send the post text. HTML formatting is supported.", "2. Send the post text. Telegram formatting (bold, italic, spoiler, quote, Premium emoji) is kept; HTML tags work too."),
 ("3. Send a photo, GIF or file.", "3. Send a photo, video, GIF or file."),
 ("4. Add link buttons or skip this step.", "4. Add link buttons (several in a row — separated by “|”, color: blue / green / red) or skip this step."),
 ("You can add link buttons. 🔵🟢🔴 are emojis placed before button text for visual indication.\n\n⚠️ Telegram does not support real colored inline buttons.",
  "Format: Text - link. Several buttons in one row — separated by “|”, a new line starts a new row. Color as the third field: blue, green or red — the button becomes really blue, green or red."),
],
}

for lang, new in (("ru", RU), ("en", EN)):
    path = f"{D}/{lang}.json"
    data = json.load(open(path, encoding="utf-8"))
    data.update(new)
    for old, repl in HELP[lang]:
        assert old in data["help_text"], (lang, old[:40])
        data["help_text"] = data["help_text"].replace(old, repl)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(lang, "ok", len(data))
