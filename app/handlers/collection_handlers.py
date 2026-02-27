from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from app.services.vinyl_service import VinylService
from app.services.ytmusic_service import YTMusicService
from app.services.card_service import CardService

router = Router()
ITEMS_PER_PAGE = 5

@router.message(Command("collection"))
async def view_collection(message: Message):
    await show_collection_page(message, page=0, user_id=message.from_user.id)

async def show_collection_page(message: Message, page: int, user_id: int, is_edit: bool = False):
    vinyls, total = await VinylService.get_user_collection(user_id, page=page, limit=ITEMS_PER_PAGE)
    
    text = "📂 Your collection:"
    
    if not vinyls:
        if is_edit:
            await message.edit_text(text + "\n\nYour collection is empty.", reply_markup=None)
        else:
            await message.answer(text + "\n\nYour collection is empty.")
        return

    builder = InlineKeyboardBuilder()
    for v in vinyls:
        artist_name = v.artists[0].name if v.artists else "Unknown"
        builder.row(InlineKeyboardButton(text=f"{artist_name} - {v.title}", callback_data=f"view_item:{v.id}:{page}"))

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
async def on_coll_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_collection_page(callback.message, page=page, user_id=callback.from_user.id, is_edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("view_item:"))
async def on_view_item(callback: CallbackQuery):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)

    vinyl = await VinylService.get_vinyl_by_id(vinyl_id)
    if not vinyl:
        await callback.answer("Record not found!", show_alert=True)
        return

    artist_name = vinyl.artists[0].name if vinyl.artists else "Unknown"
    text = CardService.from_vinyl(vinyl)

    # Обрізаємо, якщо занадто довгий для підпису фото (1024 символи)
    if len(text) > 1024:
        text = text[:1021] + "..."

    # Отримуємо фото
    image_uri = None
    if vinyl.images:
        for img in vinyl.images:
            if img.type == "primary":
                image_uri = img.uri
                break
        if not image_uri and vinyl.images:
            image_uri = vinyl.images[0].uri

    # Шукаємо посилання на YouTube Music
    yt_url = await YTMusicService.get_album_url(artist_name, vinyl.title)

    builder = InlineKeyboardBuilder()
    if yt_url:
        builder.row(InlineKeyboardButton(text="🎧 Listen on YT Music", url=yt_url))
    builder.row(InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete_confirm:{vinyl_id}:{page}"))
    builder.row(InlineKeyboardButton(text="⬅️ Back to list", callback_data=f"coll_page:{page}"))
    
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

@router.callback_query(F.data.startswith("delete_confirm:"))
async def on_delete_confirm(callback: CallbackQuery):
    _, vinyl_id, page = callback.data.split(":")
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"delete_execute:{vinyl_id}:{page}"),
        InlineKeyboardButton(text="❌ No, cancel", callback_data=f"view_item:{vinyl_id}:{page}")
    )
    
    text = "Are you sure you want to delete this record?"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("delete_execute:"))
async def on_delete_execute(callback: CallbackQuery):
    _, vinyl_id, page = callback.data.split(":")
    vinyl_id = int(vinyl_id)
    
    success = await VinylService.delete_vinyl(vinyl_id)
    if success:
        await callback.answer("Record deleted.", show_alert=True)
    else:
        await callback.answer("Error deleting record.", show_alert=True)
        
    await show_collection_page(callback.message, page=int(page), user_id=callback.from_user.id, is_edit=True)