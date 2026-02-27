from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from app.services.collection_search_service import CollectionSearchService
from app.services.vinyl_service import VinylService
from app.services.ytmusic_service import YTMusicService
from app.services.card_service import CardService

router = Router()
ITEMS_PER_PAGE = 5

class CollectionSearch(StatesGroup):
    waiting_for_query = State()

@router.message(Command("search_collection"))
async def cmd_search_collection(message: Message, state: FSMContext):
    await message.answer("🔍 Enter search query (title or artist):")
    await state.set_state(CollectionSearch.waiting_for_query)

@router.message(CollectionSearch.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text
    await state.update_data(query=query)
    await show_collection_search_results(message, state, page=0, is_new=True)

async def show_collection_search_results(message: Message, state: FSMContext, page: int, is_new: bool = False):
    data = await state.get_data()
    query = data.get("query")
    user_id = message.chat.id

    vinyls, total = await CollectionSearchService.search_user_collection(user_id, query, page, ITEMS_PER_PAGE)

    if not vinyls:
        if is_new:
            await message.answer(f"❌ No results found for '<b>{query}</b>' in your collection.", parse_mode="HTML")
            # Не очищуємо стан, щоб користувач міг спробувати інший запит, або можна очистити
            await state.clear()
        else:
            await message.answer("No more results.")
        return

    text = f"🔍 Search results for '<b>{query}</b>':"

    builder = InlineKeyboardBuilder()
    for v in vinyls:
        artist_name = v.artists[0].name if v.artists else "Unknown"
        builder.row(InlineKeyboardButton(text=f"{artist_name} - {v.title}", callback_data=f"view_search_item:{v.id}:{page}"))

    # Pagination
    if total > ITEMS_PER_PAGE:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"coll_search_page:{page-1}"))
        
        max_page = (total - 1) // ITEMS_PER_PAGE
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{max_page+1}", callback_data="noop"))
        
        if (page + 1) * ITEMS_PER_PAGE < total:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"coll_search_page:{page+1}"))
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="❌ Cancel Search", callback_data="cancel_coll_search"))

    if is_new:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
             # Якщо попереднє повідомлення було з фото
            await message.delete()
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("coll_search_page:"))
async def on_coll_search_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    await show_collection_search_results(callback.message, state, page=page, is_new=False)
    await callback.answer()

@router.callback_query(F.data == "cancel_coll_search")
async def on_cancel_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Search cancelled.")
    await callback.answer()

@router.callback_query(F.data.startswith("view_search_item:"))
async def on_view_search_item(callback: CallbackQuery):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)

    vinyl = await VinylService.get_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer("Record not found!", show_alert=True)
        return

    artist_name = vinyl.artists[0].name if vinyl.artists else "Unknown"
    text = CardService.from_vinyl(vinyl)

    if len(text) > 1024:
        text = text[:1021] + "..."

    image_uri = None
    if vinyl.images:
        image_uri = vinyl.images[0].uri

    yt_url = await YTMusicService.get_album_url(artist_name, vinyl.title)

    builder = InlineKeyboardBuilder()
    if yt_url:
        builder.row(InlineKeyboardButton(text="🎧 Listen on YT Music", url=yt_url))
    
    builder.row(InlineKeyboardButton(text="🗑️ Delete", callback_data=f"coll_search_delete_confirm:{vinyl_id}:{page}"))
    # Кнопка "Назад" повертає до результатів пошуку
    builder.row(InlineKeyboardButton(text="⬅️ Back to results", callback_data=f"coll_search_page:{page}"))
    
    if image_uri:
        try:
            media = InputMediaPhoto(media=image_uri, caption=text, parse_mode="HTML")
            await callback.message.edit_media(media=media, reply_markup=builder.as_markup())
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer_photo(photo=image_uri, caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()

@router.callback_query(F.data.startswith("coll_search_delete_confirm:"))
async def on_coll_search_delete_confirm(callback: CallbackQuery):
    _, vinyl_id, page = callback.data.split(":")
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"coll_search_delete_execute:{vinyl_id}:{page}"),
        InlineKeyboardButton(text="❌ No, cancel", callback_data=f"view_search_item:{vinyl_id}:{page}")
    )
    
    text = "Are you sure you want to delete this record from your collection?"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("coll_search_delete_execute:"))
async def on_coll_search_delete_execute(callback: CallbackQuery, state: FSMContext):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)
    
    success = await VinylService.delete_vinyl(vinyl_id)
    if success:
        await callback.answer("Record deleted.", show_alert=True)
    else:
        await callback.answer("Error deleting record.", show_alert=True)
        
    await show_collection_search_results(callback.message, state, page=int(page), is_new=False)