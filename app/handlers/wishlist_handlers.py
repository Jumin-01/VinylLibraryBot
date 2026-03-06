from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.models import User
from app.services.vinyl_service import VinylService
from app.services.card_service import CardService
from app.services.analytics_service import AnalyticsService
from aiogram_i18n import I18nContext

router = Router()
ITEMS_PER_PAGE = 5

class WishlistSearch(StatesGroup):
    waiting_for_query = State()

@router.message(Command("wishlist"))
async def cmd_wishlist(message: Message, state: FSMContext, i18n: I18nContext):
    await state.clear()
    await show_wishlist(message, state, i18n, page=0, is_edit=False)

@router.message(Command("search_wishlist"))
async def cmd_search_wishlist(message: Message, state: FSMContext, i18n: I18nContext):
    await message.answer(i18n.get("wishlist-search-title"))
    await state.set_state(WishlistSearch.waiting_for_query)

@router.callback_query(F.data == "trigger_wish_search")
async def on_trigger_wish_search(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get("wishlist-search-title"))
    await state.set_state(WishlistSearch.waiting_for_query)
    await callback.answer()

@router.message(WishlistSearch.waiting_for_query)
async def process_wishlist_search(message: Message, state: FSMContext, i18n: I18nContext, user: User):
    query = message.text
    
    await AnalyticsService.log_action(
        user_id=user.id,
        event_type="search_wishlist",
        metadata={"query": query}
    )
    
    await state.update_data(query=query)
    await show_wishlist(message, state, i18n, user, page=0, is_edit=False)

@router.callback_query(F.data == "cancel_wish_search")
async def on_cancel_wish_search(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await state.clear()
    await callback.message.edit_text(i18n.get("wishlist-search-cancelled"), reply_markup=None)
    await callback.answer()

async def show_wishlist(message: Message, state: FSMContext, i18n: I18nContext, user: User, page: int = 0, is_edit: bool = False):
    limit = ITEMS_PER_PAGE

    data = await state.get_data()
    query = data.get("query")

    if query:
        vinyls, total = await VinylService.search_user_collection(user.telegram_id, query, page, limit, is_wishlist=True)
        title_prefix = i18n.get("wishlist-search-results-for", query=query)
    else:
        vinyls, total = await VinylService.get_user_collection(user.telegram_id, page, limit, is_wishlist=True)
        title_prefix = i18n.get("wishlist-title")

    text = f"<b>{title_prefix}</b>"

    if not vinyls:
        if is_edit:
            try:
                await message.edit_text(text + "\n\n" + i18n.get("wishlist-empty"), reply_markup=None, parse_mode="HTML")
            except TelegramBadRequest:
                await message.delete()
                await message.answer(text + "\n\n" + i18n.get("wishlist-empty"), parse_mode="HTML")
        else:
            await message.answer(text + "\n\n" + i18n.get("wishlist-empty"), parse_mode="HTML")
        return

    builder = InlineKeyboardBuilder()
    if not query:
        builder.row(InlineKeyboardButton(text=i18n.get("action-search-wishlist"), callback_data="trigger_wish_search"))
    for v in vinyls:
        artist_name = v.release.artists[0].name if v.release.artists else "Unknown"
        builder.row(InlineKeyboardButton(text=f"{artist_name} - {v.release.title}", callback_data=f"view_wish:{v.id}:{page}"))

    # Navigation
    if total > ITEMS_PER_PAGE:
        nav_row = []

        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"wish_nav:{page-1}"))
        
        max_page = (total - 1) // ITEMS_PER_PAGE
        nav_row.append(InlineKeyboardButton(text=f"{page+1}/{max_page+1}", callback_data="noop"))
        
        if (page + 1) * ITEMS_PER_PAGE < total:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"wish_nav:{page+1}"))
        
        builder.row(*nav_row)

    if query:
        builder.row(InlineKeyboardButton(text=i18n.get("action-cancel-search"), callback_data="cancel_wish_search"))

    if is_edit:
        try:
            await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            await message.delete()
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("view_wish:"))
async def on_view_wish_item(callback: CallbackQuery, state: FSMContext, i18n: I18nContext, user: User):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])

    vinyl = await VinylService.get_user_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer(i18n.get("wishlist-item-not-found"), show_alert=True)
        await show_wishlist(callback.message, state, i18n, user, page, is_edit=True)
        return

    text = CardService.from_vinyl(vinyl, i18n)
    if len(text) > 1024:
        text = text[:1021] + "..."

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
        builder.row(InlineKeyboardButton(text=i18n.get("action-listen-yt"), callback_data=f"wish_listen_yt:{vinyl_id}"))

    # Actions
    builder.row(InlineKeyboardButton(text=i18n.get("action-move-collection"), callback_data=f"wish_move:{vinyl.id}:{page}"))
    builder.row(InlineKeyboardButton(text=i18n.get("action-remove"), callback_data=f"wish_del_ask:{vinyl.id}:{page}"))
    
    # Back
    builder.row(InlineKeyboardButton(text=i18n.get("action-back-list"), callback_data=f"wish_nav:{page}"))

    if image_uri:
        try:
            media = InputMediaPhoto(media=image_uri, caption=text, parse_mode="HTML")
            await callback.message.edit_media(media=media, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer_photo(photo=image_uri, caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    await callback.answer()

@router.callback_query(F.data.startswith("wish_listen_yt:"))
async def on_wish_listen_yt(callback: CallbackQuery, i18n: I18nContext, user: User):
    vinyl_id = int(callback.data.split(":")[1])
    
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
                    if btn.callback_data and btn.callback_data.startswith(f"wish_listen_yt:{vinyl_id}"):
                        new_row.append(InlineKeyboardButton(text=i18n.get("action-open-yt"), url=url))
                    else:
                        new_row.append(btn)
                new_rows.append(new_row)
        
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows))
    else:
        # Якщо не знайдено, просто повідомляємо, не змінюючи повідомлення
        await callback.message.answer(i18n.get("alert-yt-not-found"), parse_mode="HTML")

@router.callback_query(F.data.startswith("wish_nav:"))
async def on_wishlist_nav(callback: CallbackQuery, state: FSMContext, i18n: I18nContext, user: User):
    parts = callback.data.split(":")
    page = int(parts[1])
    await show_wishlist(callback.message, state, i18n, user, page, is_edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("wish_del_ask:"))
async def on_wishlist_delete_ask(callback: CallbackQuery, i18n: I18nContext):
    parts = callback.data.split(":")
    vinyl_id = parts[1]
    page = parts[2]
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=i18n.get("action-yes-delete"), callback_data=f"wish_del_yes:{vinyl_id}:{page}"),
        InlineKeyboardButton(text=i18n.get("action-no-cancel"), callback_data=f"view_wish:{vinyl_id}:{page}")
    )
    
    text = i18n.get("wishlist-remove-confirm")
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("wish_del_yes:"))
async def on_wishlist_delete_confirm(callback: CallbackQuery, state: FSMContext, i18n: I18nContext, user: User):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])
    
    success = await VinylService.delete_vinyl(vinyl_id)
    if success:
        await callback.answer(i18n.get("wishlist-deleted"))
        await show_wishlist(callback.message, state, i18n, user, page=page, is_edit=True)
    else:
        await callback.answer(i18n.get("wishlist-delete-error"), show_alert=True)

@router.callback_query(F.data.startswith("wish_move:"))
async def on_wishlist_move(callback: CallbackQuery, state: FSMContext, i18n: I18nContext, user: User):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])
    
    # Get vinyl to find discogs_id
    vinyl = await VinylService.get_user_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer(i18n.get("wishlist-item-not-found"), show_alert=True)
        await show_wishlist(callback.message, state, i18n, user, page=page, is_edit=True)
        return

    # Re-add with to_wishlist=False (Promote)
    updated = await VinylService.add_vinyl_from_discogs(callback.from_user.id, vinyl.release.discogs_id, to_wishlist=False)
    
    if updated:
        await callback.answer(i18n.get("wishlist-moved"))
        await show_wishlist(callback.message, state, i18n, user, page=page, is_edit=True)
    else:
        await callback.answer(i18n.get("wishlist-move-error"), show_alert=True)