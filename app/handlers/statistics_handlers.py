from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from app.services.statistics_service import StatisticsService
from app.services.valuation_service import ValuationService
from aiogram_i18n import I18nContext

router = Router()

@router.message(Command("stats"))
async def cmd_stats(message: Message, i18n: I18nContext):
    await show_stats_menu(message, i18n)

async def show_stats_menu(message: Message, i18n: I18nContext, is_edit: bool = False):
    text = i18n.get('stats-menu-title')
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-general'), callback_data="stats_general"))
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-tops'), callback_data="stats_tops"))
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-market'), callback_data="stats_market"))
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-activity'), callback_data="stats_activity"))
    
    if is_edit:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_main")
async def on_stats_main(callback: CallbackQuery, i18n: I18nContext):
    await show_stats_menu(callback.message, i18n, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "stats_general")
async def on_stats_general(callback: CallbackQuery, i18n: I18nContext):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer(i18n.get('stats-collection-empty'), show_alert=True)
        return
    
    na = i18n.get('card-na')
    text = (
        f"<b>{i18n.get('stats-general-title')}</b>\n\n"
        f"{i18n.get('stats-general-total-releases')} {stats['total_releases']}\n"
        f"{i18n.get('stats-general-unique-artists')} {stats['unique_artists']}\n"
        f"{i18n.get('stats-general-unique-countries')} {stats['unique_countries']}\n"
        f"{i18n.get('stats-general-years-range')} {stats['oldest_release'] or na} - {stats['newest_release'] or na}\n"
        f"{i18n.get('stats-general-avg-year')} {stats['average_year'] or na}\n"
    )
    if stats['decades_distribution']:
        text += f"\n{i18n.get('stats-general-decades')}\n"
        for decade, count, perc in stats['decades_distribution']:
            text += i18n.get('stats-general-decades-line', decade=str(decade), count=str(count), perc=f"{perc:.1f}") + "\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-back'), callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_tops")
async def on_stats_tops(callback: CallbackQuery, i18n: I18nContext):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer(i18n.get('stats-collection-empty'), show_alert=True)
        return

    text = f"<b>{i18n.get('stats-tops-title')}</b>\n"
    if stats['top_artists']:
        text += f"\n<b>{i18n.get('stats-tops-artists')}</b>\n" + "\n".join([f"• {n}: {c}" for n, c in stats['top_artists']])
    if stats['top_genres']:
        text += f"\n\n<b>{i18n.get('stats-tops-genres')}</b>\n" + "\n".join([f"• {g}: {c}" for g, c in stats['top_genres']])
    if stats['top_styles']:
        text += f"\n\n<b>{i18n.get('stats-tops-styles')}</b>\n" + "\n".join([f"• {s}: {c}" for s, c in stats['top_styles']])
    if stats['top_countries']:
        text += f"\n\n<b>{i18n.get('stats-tops-countries')}</b>\n" + "\n".join([f"• {c}: {n}" for c, n in stats['top_countries']])

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-back'), callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_market")
async def on_stats_market(callback: CallbackQuery, i18n: I18nContext):
    stats = await StatisticsService.get_user_statistics(callback.from_user.id)
    if not stats:
        await callback.answer(i18n.get('stats-collection-empty'), show_alert=True)
        return

    text = f"<b>{i18n.get('stats-market-title')}</b>\n"
    if stats.get('total_collection_value', 0) > 0:
        text += f"\n{i18n.get('stats-market-total-value')} {ValuationService.CURRENCY_SYMBOL}{stats['total_collection_value']}\n"

    if stats['most_expensive_releases']:
        text += f"\n<b>{i18n.get('stats-market-most-valuable')}</b>\n"
        for item in stats['most_expensive_releases']:
            v = item['vinyl']
            val = item['value']
            artist = v.artists[0].name if v.artists else i18n.get('card-unknown')
            text += f"• {artist} - {v.title} (<b>{val['currency']}{val['min']}–{val['max']}</b>)\n"
    
    if stats['rarest_releases']:
        text += f"\n<b>{i18n.get('stats-market-rarest')}</b>\n"
        for v in stats['rarest_releases']:
            artist = v.artists[0].name if v.artists else i18n.get('card-unknown')
            text += f"• {artist} - {v.title} ({v.have_count})\n"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-back'), callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "stats_activity")
async def on_stats_activity(callback: CallbackQuery, i18n: I18nContext):
    activity = await StatisticsService.get_user_activity(callback.from_user.id)
    if not activity:
        await callback.answer(i18n.get('stats-user-not-found'), show_alert=True)
        return

    joined_date = activity['joined_at'].strftime("%d.%m.%Y")
    text = (
        f"<b>{i18n.get('stats-activity-title')}</b>\n\n"
        f"{i18n.get('stats-activity-joined')} {joined_date}\n"
        f"{i18n.get('stats-activity-days-active')} {activity['days_member']}\n"
        f"{i18n.get('stats-activity-total-collection')} {activity['total_items']}\n"
        f"{i18n.get('stats-activity-added-last-30')} {activity['added_last_30']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.get('stats-menu-back'), callback_data="stats_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
