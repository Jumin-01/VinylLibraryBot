import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy import select
from app.states.search_states import SearchVinyl
from app.services.search_service import SearchService
from app.services.vinyl_service import VinylService
from app.services.user_service import UserService
from app.database.db import AsyncSessionLocal
from app.database.models import Vinyl
from app.services.ytmusic_service import YTMusicService
from app.services.card_service import CardService
from app.services.analytics_service import AnalyticsService

router = Router()

# --- Generic text search ---
async def process_search(message: Message, query: str, search_type: str, state: FSMContext):
    if not query:
        await message.answer("Please enter a query after the command.")
        return

    await AnalyticsService.log_action(
        user_id=message.from_user.id,
        event_type="search_api",
        metadata={"query": query, "type": search_type}
    )

    results = await SearchService.search_discogs(query, search_type)
    if not results:
        await message.answer(f"No results found for '{query}'")
        return

    request_id = str(message.message_id)
    data = await state.get_data()
    search_results = data.get("search_results", {})
    search_results[request_id] = results
    await state.update_data(search_results=search_results)
    await show_search_result(message, state, request_id, 0, is_new=True)

@router.message(SearchVinyl.waiting_for_query, F.text)
async def search_query_input(message: Message, state: FSMContext):
    data = await state.get_data()
    search_type = data.get("search_type", "q")
    await state.set_state(None)
    await process_search(message, message.text, search_type, state)

@router.message(SearchVinyl.waiting_for_barcode, F.text)
async def search_barcode_input(message: Message, state: FSMContext):
    # Цей обробник тепер відповідає лише за текстове введення штрих-коду
    await state.set_state(None)
    await process_search(message, message.text, "barcode", state)

@router.message(SearchVinyl.waiting_for_barcode, F.photo)
async def search_barcode_photo_input(message: Message, state: FSMContext):
    status_msg = await message.answer("📷 Photo received. Looking for a barcode...")
    
    photo = message.photo[-1]
    bot = message.bot
    
    try:
        file_io = await bot.download(photo)

        # Делегуємо розпізнавання сервісу
        barcode_data = await SearchService.search_by_barcode_photo(file_io)

        if not barcode_data:
            await status_msg.edit_text("❌ No barcode found in the photo. Please try again or enter it manually.")
            # Не скидаємо стан, щоб користувач міг спробувати ще раз
            return
        
        await status_msg.edit_text(f"✅ Barcode found: {barcode_data}. Searching...")
        
        await state.set_state(None)
        await process_search(message, barcode_data, "barcode", state)
    except Exception as e:
        print(f"❌ Error in search_barcode_photo_input: {e}")
        await status_msg.edit_text("❌ An error occurred while processing the photo.")
        await state.clear()

@router.message(SearchVinyl.waiting_for_catno, F.text)
async def search_catno_input(message: Message, state: FSMContext):
    await state.set_state(None)
    await process_search(message, message.text, "catno", state)

@router.message(F.photo)
async def handle_photo_search(message: Message, state: FSMContext):
    status_msg = await message.answer("📸 Photo received. Analyzing the label...")
    photo = message.photo[-1]
    bot = message.bot

    try:
        file_io = await bot.download(photo)
        
        # Delegate recognition logic to service
        final_results = await SearchService.search_by_photo(file_io)
    except Exception as e:
        print(f"❌ Error in handle_photo_search: {e}")
        await status_msg.edit_text("❌ An error occurred while analyzing the photo.")
        return

    if not final_results:
        await status_msg.edit_text("❌ Release not found. Try taking a clearer photo of the vinyl label.")
        return

    request_id = str(message.message_id)
    data = await state.get_data()
    search_results = data.get("search_results", {})
    search_results[request_id] = final_results
    await state.update_data(search_results=search_results)

    await status_msg.edit_text("✅ Possible options found:")
    await show_search_result(message, state, request_id, 0, is_new=True)

# --- Show search results with navigation ---
async def show_search_result(message: Message, state: FSMContext, request_id: str, index: int, is_new: bool = False):
    data = await state.get_data()
    results = data.get("search_results", {}).get(request_id, [])
    if not results:
        if not is_new:
            await message.answer("⚠️ Search results expired.")
        return

    result = results[index]
    release_id = result.get("id")
    
    cover = result.get("cover_image") or result.get("thumb")

    # Check if in collection
    in_collection = await VinylService.is_vinyl_in_collection(message.chat.id, release_id)
    # This import is assumed to be added at the top: from app.services.vinyl_service import VinylService
    in_wishlist = await VinylService.is_vinyl_in_wishlist(message.chat.id, release_id)

    # Search YouTube Music using the service
    # Note: We need artist and title for YT search. Extracting them again for this purpose.
    full_title = result.get("title", "Unknown - Unknown")
    artist_name, album_title = full_title.split(" - ", 1) if " - " in full_title else ("Unknown Artist", full_title)
    yt_url = await YTMusicService.get_album_url(artist_name, album_title)

    details = await SearchService.get_release_details(release_id)

    # Зберігаємо деталі в кеші FSM, щоб не викликати API повторно при додаванні
    data = await state.get_data()
    release_details_cache = data.get("release_details_cache", {})
    release_details_cache[str(release_id)] = details
    await state.update_data(release_details_cache=release_details_cache)

    caption = CardService.from_discogs(result, details, in_collection)

    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    builder = InlineKeyboardBuilder()
    if in_collection:
        builder.row(InlineKeyboardButton(text="✅ In Collection", callback_data="already_in_collection"))
    elif in_wishlist:
        builder.row(InlineKeyboardButton(text="💫 In Wishlist", callback_data="noop"))
        builder.row(InlineKeyboardButton(text="💿 Move to Collection", callback_data=f"search_confirm:move:{request_id}:{index}"))
    else:
        builder.row(InlineKeyboardButton(text="➕ Add to Collection", callback_data=f"search_confirm:coll:{request_id}:{index}"))
        builder.row(InlineKeyboardButton(text="💫 Add to Wishlist", callback_data=f"search_confirm:wish:{request_id}:{index}"))

    if yt_url:
        builder.row(InlineKeyboardButton(text="🎧 Listen on YT Music", url=yt_url))

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"search_nav:{request_id}:{index-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{index+1}/{len(results)}", callback_data="noop"))
    if index < len(results) - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"search_nav:{request_id}:{index+1}"))
    builder.row(*nav_row)

    if is_new:
        if cover:
            try:
                await message.answer_photo(photo=cover, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
            except TelegramBadRequest:
                await message.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await message.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            if message.photo:
                if cover:
                    media = InputMediaPhoto(media=cover, caption=caption, parse_mode="HTML")
                    await message.edit_media(media=media, reply_markup=builder.as_markup())
                else:
                    await message.delete()
                    await message.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
            else:
                if cover:
                    await message.delete()
                    await message.answer_photo(photo=cover, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
                else:
                    await message.edit_text(text=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            pass

@router.callback_query(F.data.startswith("search_nav:"))
async def on_search_nav(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    request_id, index = parts[1], int(parts[2])
    await show_search_result(callback.message, state, request_id, index, is_new=False)
    await callback.answer()

@router.callback_query(F.data == "already_in_collection")
async def on_already_in_collection(callback: CallbackQuery):
    await callback.answer("💿 This record is already in your collection!", show_alert=True)

@router.callback_query(F.data.startswith("search_confirm:"))
async def on_search_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action, request_id, index_str = parts[1], parts[2], parts[3]
    index = int(index_str)
    data = await state.get_data()
    search_results = data.get("search_results", {})
    results = search_results.get(request_id, [])
    
    if not results:
        await callback.answer("Error: search results expired", show_alert=True)
        return

    release_id = results[index].get("id")
    
    # Отримуємо деталі релізу з кешу FSM, щоб не робити повторний запит
    release_details_cache = data.get("release_details_cache", {})
    release_data = release_details_cache.get(str(release_id))

    to_wishlist = (action == 'wish')

    # Use Service to add
    vinyl = await VinylService.add_vinyl_from_discogs(
        telegram_id=callback.from_user.id,
        release_id=release_id,
        to_wishlist=to_wishlist,
        release_data=release_data)
    
    if vinyl:
        if action == 'move':
            text = f"✅ <b>{vinyl.title}</b> moved to Collection!"
        else:
            destination = "Wishlist" if to_wishlist else "Collection"
            text = f"✅ <b>{vinyl.title}</b> added to {destination}!"
    else:
        text = "❌ Error adding vinyl."
        
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode="HTML")
    else:
        await callback.message.edit_text(text=text, reply_markup=None, parse_mode="HTML")
    
    await callback.answer()
    
    # Видаляємо тільки результати цього конкретного запиту
    if request_id in search_results:
        del search_results[request_id]
        await state.update_data(search_results=search_results)