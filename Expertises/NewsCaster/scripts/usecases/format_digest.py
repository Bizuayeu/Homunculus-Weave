from __future__ import annotations

from typing import Iterable

from domain.digest import DailyDigest
from domain.models import NewsItem


class FormatDigestUseCase:
    def execute(
        self, *, target_date: str, items: Iterable[NewsItem]
    ) -> DailyDigest:
        items_tuple = tuple(items)
        count = len(items_tuple)
        subject = f"[ナルエビちゃんニュース] {target_date} のダイジェスト ({count}件)"

        if count == 0:
            body = (
                f"# {target_date} のナルエビちゃんニュース\n\n"
                "前日付の新着エントリはありませんでした。\n"
            )
        else:
            body_parts = [
                f"# {target_date} のナルエビちゃんニュース（{count}件）\n",
            ]
            for item in items_tuple:
                cats = " / ".join(item.categories) if item.categories else "-"
                body_parts.append(
                    f"## {item.title}\n"
                    f"- 公開: {item.pub_date_jst.strftime('%Y-%m-%d %H:%M')} JST\n"
                    f"- カテゴリ: {cats}\n"
                    f"- リンク: {item.link}\n\n"
                    f"{item.description}\n"
                )
            body = "\n".join(body_parts)

        return DailyDigest(
            target_date=target_date,
            items=items_tuple,
            formatted_subject=subject,
            formatted_body=body,
        )
