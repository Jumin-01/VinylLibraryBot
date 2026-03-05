from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from app.services.user_service import UserService
from aiogram_i18n import I18nContext

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message, i18n: I18nContext):
    await UserService.get_or_create_user(message.from_user)
    await message.answer(f"{i18n.get('start-welcome')}\n{i18n.get('start-find-prompt')}")

@router.message(Command("language"))
async def language_menu(message: Message, i18n: I18nContext):
    current_locale = i18n.locale
    
    uk_text = "Українська"
    en_text = "English"

    if current_locale == "uk":
        uk_text = f"✅ {uk_text}"
    elif current_locale == "en":
        en_text = f"✅ {en_text}"

    kb = [
        [KeyboardButton(text=uk_text)],
        [KeyboardButton(text=en_text)],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer(i18n.get('language-select'), reply_markup=keyboard)

# Словник для зіставлення тексту кнопки з кодом мови
LANG_MAP = {
    "English": "en",
    "Українська": "uk",
}

@router.message(F.text.func(lambda text: text.lstrip('✅ ').strip() in LANG_MAP))
async def language_selected(message: Message, i18n: I18nContext):
    clean_text = message.text.lstrip('✅ ').strip()
    lang_code = LANG_MAP[clean_text]
    # Встановлюємо локаль для наступних запитів (зберігаємо в БД).
    await i18n.manager.set_locale(locale=lang_code, event_from_user=message.from_user)
    # Встановлюємо локаль для поточної відповіді, щоб повідомлення було на правильній мові.
    await i18n.set_locale(locale=lang_code)
    # Відповідаємо, використовуючи оновлену локаль з контексту, та видаляємо клавіатуру.
    await message.answer(i18n.get('language-selected'), reply_markup=ReplyKeyboardRemove())

@router.message(Command("find"))
async def find_menu(message: Message, i18n: I18nContext):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('find-menu-artist'), callback_data="search_mode_artist"))
    builder.row(InlineKeyboardButton(text=i18n.get('find-menu-album'), callback_data="search_mode_title"))
    builder.row(InlineKeyboardButton(text=i18n.get('find-menu-barcode'), callback_data="search_mode_barcode"))
    builder.row(InlineKeyboardButton(text=i18n.get('find-menu-catno'), callback_data="search_mode_catno"))
    await message.answer(i18n.get('find-menu-prompt'), reply_markup=builder.as_markup())

# Callback handlers to set FSM state (as before)
from aiogram.fsm.context import FSMContext
from app.states.search_states import SearchVinyl

@router.callback_query(F.data == "search_mode_artist")
async def on_search_mode_artist(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get('search-prompt-artist'))
    await state.update_data(search_type="artist")
    await state.set_state(SearchVinyl.waiting_for_query)
    await callback.answer()

@router.callback_query(F.data == "search_mode_title")
async def on_search_mode_title(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get('search-prompt-album'))
    await state.update_data(search_type="release_title")
    await state.set_state(SearchVinyl.waiting_for_query)
    await callback.answer()

@router.callback_query(F.data == "search_mode_barcode")
async def on_search_mode_barcode(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.edit_text(i18n.get('search-prompt-barcode'))
    await state.set_state(SearchVinyl.waiting_for_barcode)
    await callback.answer()

@router.callback_query(F.data == "search_mode_catno")
async def on_search_mode_catno(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get('search-prompt-catno'))
    await state.set_state(SearchVinyl.waiting_for_catno)
    await callback.answer()