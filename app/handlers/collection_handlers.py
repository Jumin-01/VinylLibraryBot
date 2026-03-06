from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from app.database.models import User
from app.services.vinyl_service import VinylService
from app.services.ytmusic_service import YTMusicService
from app.services.card_service import CardService
from app.services.analytics_service import AnalyticsService
from aiogram_i18n import I18nContext

router = Router()
ITEMS_PER_PAGE = 5

@router.message(Command("collection"))
async def view_collection(message: Message, i18n: I18nContext, user: User):
    await show_collection_page(message, i18n, page=0, user=user)

async def show_collection_page(message: Message, i18n: I18nContext, page: int, user: User, is_edit: bool = False):
    vinyls, total = await VinylService.get_user_collection(user.telegram_id, page=page, limit=ITEMS_PER_PAGE)
    
    text = i18n.get("collection-title")
    
    if not vinyls:
        if is_edit:
            await message.edit_text(text + "\n\n" + i18n.get("collection-empty"), reply_markup=None)
        else:
            await message.answer(text + "\n\n" + i18n.get("collection-empty"))
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get("action-search-collection"), callback_data="trigger_coll_search"))
    for v in vinyls:
        artist_name = v.release.artists[0].name if v.release.artists else "Unknown"
        builder.row(InlineKeyboardButton(text=f"{artist_name} - {v.release.title}", callback_data=f"view_item:{v.id}:{page}"))

    if total > ITEMS_PER_PAGE:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"coll_page:{page-1}"))
        max_page = (total - 1) // ITEMS_PER_PAGE
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{max_page+1}", callback_data="noop"))
        if (page + 1) * ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"coll_page:{page+1}"))
        builder.row(*nav_buttons)

    if is_edit:
        try:
            await message.edit_text(text, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            # Якщо попереднє повідомлення було з фото, ми не можемо його редагувати в текст
            await message.delete()
            await message.answer(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("coll_page:"))
async def on_coll_page(callback: CallbackQuery, i18n: I18nContext, user: User):
    page = int(callback.data.split(":")[1])
    await show_collection_page(callback.message, i18n, page=page, user=user, is_edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("view_item:"))
async def on_view_item(callback: CallbackQuery, i18n: I18nContext, user: User):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)

    vinyl = await VinylService.get_user_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer(i18n.get("collection-record-not-found"), show_alert=True)
        return

    # --- ANALYTICS: Log View ---
    await AnalyticsService.log_vinyl_interaction(user.id, vinyl.release, "view_release", vinyl.id)

    text = CardService.from_vinyl(vinyl, i18n)

    # Обрізаємо, якщо занадто довгий для підпису фото (1024 символи)
    if len(text) > 1024:
        text = text[:1021] + "..."

    # Отримуємо фото
    image_uri = None
    if vinyl.release.images:
        for img in vinyl.release.images:
            if img.type == "primary":
                image_uri = img.uri
                break
        if not image_uri and vinyl.release.images:
            image_uri = vinyl.release.images[0].uri

    builder = InlineKeyboardBuilder()
    if vinyl.release.generated_playlist_url:
        builder.row(InlineKeyboardButton(text=i18n.get("action-open-yt"), url=vinyl.release.generated_playlist_url))
    else:
        builder.row(InlineKeyboardButton(text=i18n.get("action-listen-yt"), callback_data=f"listen_yt:{vinyl_id}"))
    
    builder.row(InlineKeyboardButton(text=i18n.get("action-delete"), callback_data=f"delete_confirm:{vinyl_id}:{page}"))
    builder.row(InlineKeyboardButton(text=i18n.get("action-back-list"), callback_data=f"coll_page:{page}"))
    
    if image_uri:
        try:
            # Спробуємо оновити медіа, якщо це вже було фото
            media = InputMediaPhoto(media=image_uri, caption=text, parse_mode="HTML")
            await callback.message.edit_media(media=media, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            # Якщо це був текст, видаляємо і шлемо фото
            await callback.message.delete()
            await callback.message.answer_photo(photo=image_uri, caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            # Якщо це було фото, видаляємо і шлемо текст
            await callback.message.delete()
            await callback.message.answer(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()

@router.callback_query(F.data.startswith("listen_yt:"))
async def on_listen_yt(callback: CallbackQuery, i18n: I18nContext, user: User):
    vinyl_id = int(callback.data.split(":")[1])
    
    # Відповідаємо одразу, щоб прибрати годинник завантаження, бо генерація може зайняти час
    await callback.answer(i18n.get("alert-yt-searching"), show_alert=False)

    # --- ANALYTICS: Log Listen ---
    await AnalyticsService.log_action(user.id, "listen_yt", entity_type="user_vinyl", entity_id=str(vinyl_id))
    
    url = await VinylService.get_or_create_playlist_url(vinyl_id)
    
    if url:
        # Отримуємо поточну клавіатуру і замінюємо кнопку
        current_markup = callback.message.reply_markup
        new_rows = []
        if current_markup and current_markup.inline_keyboard:
            for row in current_markup.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data and btn.callback_data.startswith(f"listen_yt:{vinyl_id}"):
                        new_row.append(InlineKeyboardButton(text=i18n.get("action-open-yt"), url=url))
                    else:
                        new_row.append(btn)
                new_rows.append(new_row)
        
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows))
    else:
        await callback.message.answer(i18n.get("alert-yt-not-found"), parse_mode="HTML")

@router.callback_query(F.data.startswith("delete_confirm:"))
async def on_delete_confirm(callback: CallbackQuery, i18n: I18nContext):
    _, vinyl_id, page = callback.data.split(":")
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=i18n.get("action-yes-delete"), callback_data=f"delete_execute:{vinyl_id}:{page}"),
        InlineKeyboardButton(text=i18n.get("action-no-cancel"), callback_data=f"view_item:{vinyl_id}:{page}")
    )
    
    text = i18n.get("collection-delete-confirm")
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("delete_execute:"))
async def on_delete_execute(callback: CallbackQuery, i18n: I18nContext, user: User):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)
    
    success = await VinylService.delete_vinyl(vinyl_id)
    if success:
        await callback.answer(i18n.get("collection-record-deleted"), show_alert=True)
    else:
        await callback.answer(i18n.get("collection-record-delete-error"), show_alert=True)
        
    await show_collection_page(callback.message, i18n, page=int(page), user=user, is_edit=True)