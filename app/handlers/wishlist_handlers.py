from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services.vinyl_service import VinylService
from app.services.card_service import CardService
from app.services.analytics_service import AnalyticsService

router = Router()
ITEMS_PER_PAGE = 5

class WishlistSearch(StatesGroup):
    waiting_for_query = State()

@router.message(Command("wishlist"))
async def cmd_wishlist(message: Message, state: FSMContext):
    await state.clear()
    await show_wishlist(message, state, page=0, is_edit=False)

@router.message(Command("search_wishlist"))
async def cmd_search_wishlist(message: Message, state: FSMContext):
    await message.answer("🔍 Enter query to search in your Wishlist:")
    await state.set_state(WishlistSearch.waiting_for_query)

@router.callback_query(F.data == "trigger_wish_search")
async def on_trigger_wish_search(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Enter query to search in your Wishlist:")
    await state.set_state(WishlistSearch.waiting_for_query)
    await callback.answer()

@router.message(WishlistSearch.waiting_for_query)
async def process_wishlist_search(message: Message, state: FSMContext):
    query = message.text
    
    await AnalyticsService.log_action(
        user_id=message.from_user.id,
        event_type="search_wishlist",
        metadata={"query": query}
    )
    
    await state.update_data(query=query)
    await show_wishlist(message, state, page=0, is_edit=False)

@router.callback_query(F.data == "cancel_wish_search")
async def on_cancel_wish_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Wishlist search cancelled.")
    await callback.answer()

async def show_wishlist(message: Message, state: FSMContext, page: int = 0, is_edit: bool = False):
    limit = ITEMS_PER_PAGE
    user_id = message.chat.id

    data = await state.get_data()
    query = data.get("query")

    if query:
        vinyls, total = await VinylService.search_user_collection(user_id, query, page, limit, is_wishlist=True)
        title_prefix = f"🔍 Wishlist Search: '{query}'"
    else:
        vinyls, total = await VinylService.get_user_collection(user_id, page, limit, is_wishlist=True)
        title_prefix = "💫 Your Wishlist"

    text = f"<b>{title_prefix}</b>"

    if not vinyls:
        if is_edit:
            try:
                await message.edit_text(text + "\n\nEmpty.", reply_markup=None, parse_mode="HTML")
            except TelegramBadRequest:
                await message.delete()
                await message.answer(text + "\n\nEmpty.", parse_mode="HTML")
        else:
            await message.answer(text + "\n\nEmpty.", parse_mode="HTML")
        return

    builder = InlineKeyboardBuilder()
    if not query:
        builder.row(InlineKeyboardButton(text="🔍 Search Wishlist", callback_data="trigger_wish_search"))
    for v in vinyls:
        artist_name = v.artists[0].name if v.artists else "Unknown"
        builder.row(InlineKeyboardButton(text=f"{artist_name} - {v.title}", callback_data=f"view_wish:{v.id}:{page}"))

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
        builder.row(InlineKeyboardButton(text="❌ Cancel Search", callback_data="cancel_wish_search"))

    if is_edit:
        try:
            await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            await message.delete()
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("view_wish:"))
async def on_view_wish_item(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])

    vinyl = await VinylService.get_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer("Item not found", show_alert=True)
        await show_wishlist(callback.message, state, page, is_edit=True)
        return

    text = CardService.from_vinyl(vinyl)
    if len(text) > 1024:
        text = text[:1021] + "..."

    image_uri = None
    if vinyl.images:
        image_uri = vinyl.images[0].uri

    builder = InlineKeyboardBuilder()
    
    if vinyl.generated_playlist_url:
        builder.row(InlineKeyboardButton(text="🔗 Open in YT Music", url=vinyl.generated_playlist_url))
    else:
        builder.row(InlineKeyboardButton(text="🎧 Listen on YT Music", callback_data=f"wish_listen_yt:{vinyl.id}"))

    # Actions
    builder.row(InlineKeyboardButton(text="➕ Move to Collection", callback_data=f"wish_move:{vinyl.id}:{page}"))
    builder.row(InlineKeyboardButton(text="❌ Remove", callback_data=f"wish_del_ask:{vinyl.id}:{page}"))
    
    # Back
    builder.row(InlineKeyboardButton(text="⬅️ Back to list", callback_data=f"wish_nav:{page}"))

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
async def on_wish_listen_yt(callback: CallbackQuery):
    vinyl_id = int(callback.data.split(":")[1])
    
    await callback.answer("🎧 Searching tracks...", show_alert=False)
    
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
                        new_row.append(InlineKeyboardButton(text="🔗 Open in YT Music", url=url))
                    else:
                        new_row.append(btn)
                new_rows.append(new_row)
        
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows))
    else:
        # Якщо не знайдено, просто повідомляємо, не змінюючи повідомлення
        await callback.message.answer("❌ Could not find tracks on YouTube Music.", parse_mode="HTML")

@router.callback_query(F.data.startswith("wish_nav:"))
async def on_wishlist_nav(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    page = int(parts[1])
    await show_wishlist(callback.message, state, page, is_edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("wish_del_ask:"))
async def on_wishlist_delete_ask(callback: CallbackQuery):
    parts = callback.data.split(":")
    vinyl_id = parts[1]
    page = parts[2]
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Yes, delete", callback_data=f"wish_del_yes:{vinyl_id}:{page}"),
        InlineKeyboardButton(text="🔙 Cancel", callback_data=f"view_wish:{vinyl_id}:{page}")
    )
    
    text = "❓ <b>Remove this item from Wishlist?</b>"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("wish_del_yes:"))
async def on_wishlist_delete_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])
    
    success = await VinylService.delete_vinyl(vinyl_id)
    if success:
        await callback.answer("Deleted from Wishlist")
        await show_wishlist(callback.message, state, page=page, is_edit=True)
    else:
        await callback.answer("Error deleting", show_alert=True)

@router.callback_query(F.data.startswith("wish_move:"))
async def on_wishlist_move(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    vinyl_id = int(parts[1])
    page = int(parts[2])
    
    # Get vinyl to find discogs_id
    vinyl = await VinylService.get_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer("Error: Item not found", show_alert=True)
        await show_wishlist(callback.message, state, page=page, is_edit=True)
        return

    # Re-add with to_wishlist=False (Promote)
    updated = await VinylService.add_vinyl_from_discogs(callback.from_user.id, vinyl.discogs_id, to_wishlist=False)
    
    if updated:
        await callback.answer("🎉 Moved to Collection!")
        await show_wishlist(callback.message, state, page=page, is_edit=True)
    else:
        await callback.answer("Error moving item", show_alert=True)