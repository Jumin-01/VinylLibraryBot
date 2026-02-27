from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from app.services.user_service import UserService

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    await UserService.get_or_create_user(message.from_user)
    await message.answer("👋 Hi! I'm your record collection bot.\nUse /find to search for vinyl records.")

@router.message(Command("find"))
async def find_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Artist", callback_data="search_mode_artist"))
    builder.row(InlineKeyboardButton(text="💿 Album Title", callback_data="search_mode_title"))
    builder.row(InlineKeyboardButton(text="📦 Barcode", callback_data="search_mode_barcode"))
    builder.row(InlineKeyboardButton(text="🔢 Catalog Number", callback_data="search_mode_catno"))
    await message.answer("Select search method:", reply_markup=builder.as_markup())

# Callback handlers to set FSM state (as before)
from aiogram.fsm.context import FSMContext
from app.states.search_states import SearchVinyl

@router.callback_query(F.data == "search_mode_artist")
async def on_search_mode_artist(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the artist name:")
    await state.update_data(search_type="artist")
    await state.set_state(SearchVinyl.waiting_for_query)
    await callback.answer()

@router.callback_query(F.data == "search_mode_title")
async def on_search_mode_title(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the album title:")
    await state.update_data(search_type="release_title")
    await state.set_state(SearchVinyl.waiting_for_query)
    await callback.answer()

@router.callback_query(F.data == "search_mode_barcode")
async def on_search_mode_barcode(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Enter the barcode or send a photo of it:")
    await state.set_state(SearchVinyl.waiting_for_barcode)
    await callback.answer()

@router.callback_query(F.data == "search_mode_catno")
async def on_search_mode_catno(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the catalog number:")
    await state.set_state(SearchVinyl.waiting_for_catno)
    await callback.answer()