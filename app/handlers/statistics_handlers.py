from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from app.services.statistics_service import StatisticsService

router = Router()

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await show_stats_menu(message)

async def show_stats_menu(message: Message, is_edit: bool = False):
    text = "📊 <b>Statistics Menu</b>\nSelect a category to view:"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📈 General Overview", callback_data="stats_general"))
    builder.row(InlineKeyboardButton(text="🏆 Top Lists", callback_data="stats_tops"))
    builder.row(InlineKeyboardButton(text="💎 Market & Rarity", callback_data="stats_market"))
    builder.row(InlineKeyboardButton(text="👤 User Activity", callback_data="stats_activity"))
    
    if is_edit:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_main")
async def on_stats_main(callback: CallbackQuery):
    await show_stats_menu(callback.message, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "stats_general")
async def on_stats_general(callback: CallbackQuery):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer("Collection is empty!", show_alert=True)
        return
    
    text = (
        " <b>General Overview</b>\n\n"
        f"💿 <b>Total Releases:</b> {stats['total_releases']}\n"
        f"👤 <b>Unique Artists:</b> {stats['unique_artists']}\n"
        f"🌍 <b>Unique Countries:</b> {stats['unique_countries']}\n"
        f"📅 <b>Years Range:</b> {stats['oldest_release'] or 'N/A'} - {stats['newest_release'] or 'N/A'}\n"
        f"📊 <b>Average Year:</b> {stats['average_year'] or 'N/A'}\n"
    )
    if stats['decades_distribution']:
        text += "\n<b>📅 Decades:</b>\n"
        for decade, count, perc in stats['decades_distribution']:
            text += f"• {decade}s: {count} ({perc:.1f}%)\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_tops")
async def on_stats_tops(callback: CallbackQuery):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer("Collection is empty!", show_alert=True)
        return

    text = "🏆 <b>Top Lists</b>\n"
    if stats['top_artists']:
        text += "\n<b>🎤 Top Artists:</b>\n" + "\n".join([f"• {n}: {c}" for n, c in stats['top_artists']])
    if stats['top_genres']:
        text += "\n\n<b>🎼 Top Genres:</b>\n" + "\n".join([f"• {g}: {c}" for g, c in stats['top_genres']])
    if stats['top_styles']:
        text += "\n\n<b>🎵 Top Styles:</b>\n" + "\n".join([f"• {s}: {c}" for s, c in stats['top_styles']])
    if stats['top_countries']:
        text += "\n\n<b>🌍 Top Countries:</b>\n" + "\n".join([f"• {c}: {n}" for c, n in stats['top_countries']])

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_market")
async def on_stats_market(callback: CallbackQuery):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer("Collection is empty!", show_alert=True)
        return

    text = "💎 <b>Market & Rarity</b>\n"
    if stats['most_expensive_releases']:
        text += "\n<b>💰 Most Valuable:</b>\n"
        for v in stats['most_expensive_releases']:
            artist = v.artists[0].name if v.artists else "Unknown"
            text += f"• {artist} - {v.title} (<b>${v.lowest_price}</b>)\n"
    
    if stats['rarest_releases']:
        text += "\n<b>🦄 Rarest (Fewest Owners):</b>\n"
        for v in stats['rarest_releases']:
            artist = v.artists[0].name if v.artists else "Unknown"
            text += f"• {artist} - {v.title} ({v.have_count})\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_activity")
async def on_stats_activity(callback: CallbackQuery):
    activity = await StatisticsService.get_user_activity(callback.from_user.id)
    if not activity:
        await callback.answer("User not found.", show_alert=True)
        return

    joined_date = activity['joined_at'].strftime("%d.%m.%Y")
    text = (
        "👤 <b>User Activity</b>\n\n"
        f"📅 <b>Joined:</b> {joined_date}\n"
        f"⏳ <b>Days Active:</b> {activity['days_member']}\n"
        f"💿 <b>Total Collection:</b> {activity['total_items']}\n"
        f"📈 <b>Added Last 30 Days:</b> {activity['added_last_30']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
