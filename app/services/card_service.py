from app.services.valuation_service import ValuationService
from aiogram_i18n import I18nContext

class CardService:
    @staticmethod
    def format_card(
        i18n: I18nContext,
        title: str,
        artist: str,
        year: str | int,
        country: str,
        cat_no: str,
        genres: str,
        styles: str,
        formats: str,
        added_at: str = None,
        tracklist: list[str] = None,
        rating_average: float = None,
        rating_count: int = None,
        lowest_price: float = None,
        num_for_sale: int = None,
        have_count: int = None,
        want_count: int = None,
        smart_valuation: dict = None
    ) -> str:
        lines = [
            f"<b>{i18n.get('card-album')}:</b> {title}",
            f"<b>{i18n.get('card-artist')}:</b> {artist}",
            f"<b>{i18n.get('card-year')}:</b> {year}"
        ]
        
        if added_at:
            lines.append(f"<b>{i18n.get('card-added')}:</b> {added_at}")
            
        lines.append(f"<b>{i18n.get('card-country')}:</b> {country}")
        lines.append(f"<b>{i18n.get('card-catno')}:</b> {cat_no}")
        lines.append(f"<b>{i18n.get('card-format')}:</b> {formats}")
        lines.append(f"<b>{i18n.get('card-genre')}:</b> {genres}")
        lines.append(f"<b>{i18n.get('card-style')}:</b> {styles}")

        if rating_average and rating_count:
            lines.append(f"<b>{i18n.get('card-rating')}:</b> {rating_average}/5 ({rating_count} {i18n.get('card-votes')})")

        # Smart Market Value
        if smart_valuation:
            v_min = smart_valuation['min']
            v_max = smart_valuation['max']
            d_ratio = smart_valuation['demand_ratio']
            demand_icon = "🔥" if d_ratio > 0.25 else "📉" if d_ratio < 0.1 else "📊"
            currency = smart_valuation.get('currency', ValuationService.CURRENCY_SYMBOL)
            lines.append(f"<b>{i18n.get('card-smart-value')}:</b> {currency}{v_min}–{v_max}")
        elif lowest_price is not None:
             lines.append(f"<b>{i18n.get('card-marketplace')}:</b> {i18n.get('card-from')} {ValuationService.CURRENCY_SYMBOL}{lowest_price} ({num_for_sale or 0} {i18n.get('card-for-sale')})")

        # if have_count is not None and want_count is not None:
        #     lines.append(f"<b>{i18n.get('card-community')}:</b> {i18n.get('card-have')}: {have_count} | {i18n.get('card-want')}: {want_count}")
            
        if tracklist:
            lines.append(f"\n<b>{i18n.get('card-tracklist')}:</b>")
            lines.extend(tracklist)
            
        return "\n".join(lines)

    @staticmethod
    def from_vinyl(vinyl, i18n: I18nContext):
        artist = vinyl.artists[0].name if vinyl.artists else i18n.get('card-unknown')
        
        cat_no = vinyl.catno or i18n.get('card-na')

        formats_list = []
        if vinyl.formats:
            for f in vinyl.formats:
                parts = [f.name]
                if f.descriptions:
                    parts.extend(f.descriptions)
                formats_list.append(", ".join(parts))
        formats = "; ".join(formats_list) if formats_list else "Vinyl"

        genres = ", ".join(vinyl.genres) if vinyl.genres else i18n.get('card-na')
        styles = ", ".join(vinyl.styles) if vinyl.styles else i18n.get('card-na')
        
        added_at = vinyl.created_at.strftime("%d.%m.%Y") if hasattr(vinyl, "created_at") and vinyl.created_at else i18n.get('card-na')
        
        tracks = []
        if vinyl.tracks:
            sorted_tracks = sorted(vinyl.tracks, key=lambda x: x.position)
            for t in sorted_tracks:
                dur = f" ({t.duration})" if t.duration else ""
                # Формат як у пошуку: "A1 Title" (без крапки)
                tracks.append(f"{t.position} {t.title}{dur}")
        
        smart_val = ValuationService.calculate_smart_value(
            vinyl.lowest_price,
            vinyl.median_price,
            vinyl.highest_price,
            vinyl.num_for_sale,
            vinyl.have_count,
            vinyl.want_count
        )

        return CardService.format_card(
            i18n=i18n,
            title=vinyl.title,
            artist=artist,
            year=vinyl.year,
            country=vinyl.country or i18n.get('card-na'),
            cat_no=cat_no,
            genres=genres,
            styles=styles,
            formats=formats,
            added_at=added_at,
            tracklist=tracks,
            rating_average=vinyl.rating_average,
            rating_count=vinyl.rating_count,
            lowest_price=vinyl.lowest_price,
            num_for_sale=vinyl.num_for_sale,
            have_count=vinyl.have_count,
            want_count=vinyl.want_count,
            smart_valuation=smart_val
        )

    @staticmethod
    def from_discogs(result, i18n: I18nContext, details=None, in_collection=False):
        full_title = result.get("title", f"{i18n.get('card-unknown')} - {i18n.get('card-unknown')}")
        if " - " in full_title:
            artist, title = full_title.split(" - ", 1)
        else:
            artist = i18n.get('card-unknown')
            title = full_title
            
        year = result.get("year", i18n.get('card-unknown'))
        country = result.get("country", i18n.get('card-unknown'))
        cat_no = result.get("catno", i18n.get('card-unknown'))
        
            
        fmt_list = result.get("format", [])
        formats = ", ".join(fmt_list) if fmt_list else "Vinyl"
        
        genres = ", ".join(result.get("genre", [])) or i18n.get('card-na')
        styles = ", ".join(result.get("style", [])) or "-"
        
        tracks = []
        rating_average, rating_count, lowest_price, num_for_sale, have_count, want_count, smart_val, median_price, highest_price = None, None, None, None, None, None, None, None, None

        if details:
            if "tracklist" in details:
                for t in details["tracklist"]:
                    pos = t.get('position', '')
                    t_title = t.get('title', '')
                    dur = t.get('duration', '')
                    line = f"{pos} {t_title}"
                    if dur:
                        line += f" ({dur})"
                    tracks.append(line)

            community_data = details.get("community", {})
            rating_data = community_data.get("rating", {})
            
            rating_average = rating_data.get("average")
            rating_count = rating_data.get("count")
            lowest_price = details.get("lowest_price")
            num_for_sale = details.get("num_for_sale")
            have_count = community_data.get("have")
            want_count = community_data.get("want")
            
            smart_val = ValuationService.calculate_smart_value(
                lowest_price,
                median_price, # Для пошуку ми поки не маємо цих даних, якщо не робити окремий запит
                highest_price,
                num_for_sale,
                have_count,
                want_count
            )
                
        return CardService.format_card(
            i18n=i18n,
            title=title,
            artist=artist,
            year=year,
            country=country,
            cat_no=cat_no,
            genres=genres,
            styles=styles,
            formats=formats,
            tracklist=tracks,
            rating_average=rating_average,
            rating_count=rating_count,
            lowest_price=lowest_price,
            num_for_sale=num_for_sale,
            have_count=have_count,
            want_count=want_count,
            smart_valuation=smart_val
        )