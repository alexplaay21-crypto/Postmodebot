# -*- coding: utf-8 -*-

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedGif,
    InlineQueryResultCachedDocument,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
)

from bot.keyboards import main_menu_kb
from bot.storage import (
    delete_post,
    get_post,
    get_user_language,
    get_user_posts,
)
from bot.texts import t

router = Router(name="saved_posts")


def _post_markup(buttons):
    if not buttons:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button.get("text", ""),
                    url=button.get("url"),
                )
                for button in row
            ]
            for row in buttons
        ]
    )


def _description(post: dict) -> str:
    text = post.get("caption") or ""
    text = text.replace("\n", " ").strip()

    if len(text) > 100:
        text = text[:97] + "..."

    return text or "-"


@router.callback_query(F.data == "menu:saved")
async def saved_posts_menu(call: CallbackQuery):
    user_id = call.from_user.id
    lang = get_user_language(user_id, "en")
    posts = get_user_posts(user_id)

    if not posts:
        await call.message.edit_text(
            t(lang, "saved_posts_title") + "\n\n" +
            t(lang, "saved_posts_empty"),
            reply_markup=main_menu_kb(lang),
        )
        await call.answer()
        return

    rows = [
        [
            InlineKeyboardButton(
                text=f"📄 {post['name'][:40]}",
                callback_data=f"saved:view:{post['code']}",
            )
        ]
        for post in posts
    ]

    rows.append([
        InlineKeyboardButton(
            text=t(lang, "btn_saved_back"),
            callback_data="saved:back",
        )
    ])

    await call.message.edit_text(
        t(lang, "saved_posts_title") + "\n\n" +
        t(lang, "saved_posts_choose"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@router.callback_query(F.data == "saved:back")
async def saved_posts_back(call: CallbackQuery):
    lang = get_user_language(call.from_user.id, "en")

    await call.message.edit_text(
        t(lang, "menu_title"),
        reply_markup=main_menu_kb(lang),
    )
    await call.answer()


@router.callback_query(F.data.startswith("saved:view:"))
async def saved_post_view(call: CallbackQuery):
    user_id = call.from_user.id
    lang = get_user_language(user_id, "en")
    code = call.data.split(":", 2)[2]

    post = get_post(user_id, code)

    if not post:
        await call.answer(
            t(lang, "saved_post_not_found"),
            show_alert=True,
        )
        return

    buttons = _post_markup(post.get("buttons"))

    text = (
        f"<b>{post['name']}</b>\n\n"
        f"<code>{post['code']}</code>"
    )

    if post.get("target"):
        text += f"\n{post['target']}"

    rows = [
        [
            InlineKeyboardButton(
                text=t(lang, "btn_saved_delete"),
                callback_data=f"saved:delete:{post['code']}",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_saved_back"),
                callback_data="menu:saved",
            )
        ],
    ]

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )

    media = post.get("media")

    if media:
        try:
            if media["type"] == "photo":
                await call.message.answer_photo(
                    media["file_id"],
                    caption=post.get("caption") or None,
                    parse_mode="HTML",
                    reply_markup=buttons,
                )
            elif media["type"] == "animation":
                await call.message.answer_animation(
                    media["file_id"],
                    caption=post.get("caption") or None,
                    parse_mode="HTML",
                    reply_markup=buttons,
                )
            elif media["type"] == "document":
                await call.message.answer_document(
                    media["file_id"],
                    caption=post.get("caption") or None,
                    parse_mode="HTML",
                    reply_markup=buttons,
                )
        except Exception:
            pass
    else:
        await call.message.answer(
            post.get("caption") or "-",
            parse_mode="HTML",
            reply_markup=buttons,
        )

    await call.answer()


@router.callback_query(F.data.startswith("saved:delete:"))
async def saved_post_delete(call: CallbackQuery):
    user_id = call.from_user.id
    lang = get_user_language(user_id, "en")
    code = call.data.split(":", 2)[2]

    deleted = delete_post(user_id, code)

    if not deleted:
        await call.answer(
            t(lang, "saved_post_not_found"),
            show_alert=True,
        )
        return

    await call.answer(t(lang, "saved_post_deleted"))

    posts = get_user_posts(user_id)

    if not posts:
        await call.message.edit_text(
            t(lang, "saved_posts_title") + "\n\n" +
            t(lang, "saved_posts_empty"),
            reply_markup=main_menu_kb(lang),
        )
        return

    rows = [
        [
            InlineKeyboardButton(
                text=f"📄 {post['name'][:40]}",
                callback_data=f"saved:view:{post['code']}",
            )
        ]
        for post in posts
    ]

    rows.append([
        InlineKeyboardButton(
            text=t(lang, "btn_saved_back"),
            callback_data="saved:back",
        )
    ])

    await call.message.edit_text(
        t(lang, "saved_posts_title") + "\n\n" +
        t(lang, "saved_posts_choose"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.inline_query()
async def inline_saved_posts(query: InlineQuery):
    user_id = query.from_user.id
    search = (query.query or "").strip().lower()

    posts = get_user_posts(user_id)

    if search:
        posts = [
            post
            for post in posts
            if search in post.get("name", "").lower()
            or search in post.get("code", "").lower()
        ]

    results = []

    for post in posts[:50]:
        code = post["code"]
        name = post["name"]
        caption = post.get("caption") or ""
        markup = _post_markup(post.get("buttons"))
        media = post.get("media")
        entities = post.get("entities")

        if media and media.get("type") == "photo":
            results.append(
                InlineQueryResultCachedPhoto(
                    id=code,
                    photo_file_id=media["file_id"],
                    title=name,
                    description=_description(post),
                    caption=caption or None,
                    parse_mode="HTML" if not entities else None,
                    caption_entities=entities,
                    reply_markup=markup,
                )
            )

        elif media and media.get("type") == "animation":
            results.append(
                InlineQueryResultCachedGif(
                    id=code,
                    animation_file_id=media["file_id"],
                    title=name,
                    description=_description(post),
                    caption=caption or None,
                    parse_mode="HTML" if not entities else None,
                    caption_entities=entities,
                    reply_markup=markup,
                )
            )

        elif media and media.get("type") == "document":
            results.append(
                InlineQueryResultCachedDocument(
                    id=code,
                    document_file_id=media["file_id"],
                    title=name,
                    description=_description(post),
                    caption=caption or None,
                    parse_mode="HTML" if not entities else None,
                    caption_entities=entities,
                    reply_markup=markup,
                )
            )

        else:
            results.append(
                InlineQueryResultArticle(
                    id=code,
                    title=name,
                    description=_description(post),
                    input_message_content=InputTextMessageContent(
                        message_text=caption or "-",
                        parse_mode="HTML" if not entities else None,
                        entities=entities,
                    ),
                    reply_markup=markup,
                )
            )

    await query.answer(
        results=results,
        cache_time=1,
        is_personal=True,
    )
