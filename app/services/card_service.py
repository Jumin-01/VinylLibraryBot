class CardService:
    @staticmethod
    def format_card(
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
        want_count: int = None
    ) -> str:
        lines = [
            f"💿 <b>Album:</b> {title}",
            f"👤 <b>Artist:</b> {artist}",
            f"📅 <b>Year:</b> {year}"
        ]
        
        if added_at:
            lines.append(f"📥 <b>Added:</b> {added_at}")
            
        lines.append(f"🌍 <b>Country:</b> {country}")
        lines.append(f"🔢 <b>Cat. No:</b> {cat_no}")
        lines.append(f"💽 <b>Format:</b> {formats}")
        lines.append(f"🎼 <b>Genre:</b> {genres}")
        lines.append(f"🎵 <b>Style:</b> {styles}")

        if rating_average and rating_count:
            lines.append(f"⭐ <b>Rating:</b> {rating_average}/5 ({rating_count} votes)")

        # Використовуємо lowest_price, якщо воно є. Discogs API може повертати 0.0
        if lowest_price is not None:
            # Валюта не вказується в API, тому просто показуємо ціну
            lines.append(f"💰 <b>Marketplace:</b> From ${lowest_price} ({num_for_sale or 0} for sale)")

        if have_count is not None and want_count is not None:
            lines.append(f"👥 <b>Community:</b> Have: {have_count} | Want: {want_count}")
            
        if tracklist:
            lines.append("\n🎶 <b>Tracklist:</b>")
            lines.extend(tracklist)
            
        return "\n".join(lines)

    @staticmethod
    def from_vinyl(vinyl):
        artist = vinyl.artists[0].name if vinyl.artists else "Unknown"
        
        cat_no = vinyl.catno or "N/A"

        formats_list = []
        if vinyl.formats:
            for f in vinyl.formats:
                parts = [f.name]
                if f.descriptions:
                    parts.extend(f.descriptions)
                formats_list.append(", ".join(parts))
        formats = "; ".join(formats_list) if formats_list else "Vinyl"

        genres = ", ".join(vinyl.genres) if vinyl.genres else "N/A"
        styles = ", ".join(vinyl.styles) if vinyl.styles else "N/A"
        
        added_at = vinyl.created_at.strftime("%d.%m.%Y") if hasattr(vinyl, "created_at") and vinyl.created_at else "N/A"
        
        tracks = []
        if vinyl.tracks:
            sorted_tracks = sorted(vinyl.tracks, key=lambda x: x.position)
            for t in sorted_tracks:
                dur = f" ({t.duration})" if t.duration else ""
                # Формат як у пошуку: "A1 Title" (без крапки)
                tracks.append(f"{t.position} {t.title}{dur}")
        
        return CardService.format_card(
            title=vinyl.title,
            artist=artist,
            year=vinyl.year,
            country=vinyl.country or 'N/A',
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
            want_count=vinyl.want_count
        )

    @staticmethod
    def from_discogs(result, details=None, in_collection=False):
        full_title = result.get("title", "Unknown - Unknown")
        if " - " in full_title:
            artist, title = full_title.split(" - ", 1)
        else:
            artist = "Unknown Artist"
            title = full_title
            
        year = result.get("year", "Unknown")
        country = result.get("country", "Unknown")
        cat_no = result.get("catno", "Unknown")
        
            
        fmt_list = result.get("format", [])
        formats = ", ".join(fmt_list) if fmt_list else "Vinyl"
        
        genres = ", ".join(result.get("genre", [])) or "Not specified"
        styles = ", ".join(result.get("style", [])) or "-"
        
        tracks = []
        rating_average, rating_count, lowest_price, num_for_sale, have_count, want_count = None, None, None, None, None, None

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
                
        return CardService.format_card(
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
            want_count=want_count
        )