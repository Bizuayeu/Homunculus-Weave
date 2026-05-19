from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from domain.digest import DailyDigest
from domain.feed_policy import FeedPolicy
from domain.feed_source import FeedSource
from domain.models import NewsItem


WEAVE_COMPACT_PLACEHOLDER = "{{WEAVE_COMPACT:%s}}"


class FormatDigestUseCase:
    """フィード別セクション分け + ポリシー別本文選択でダイジェスト本文を構築する。

    WEAVE_COMPACT ポリシーの item には description を出力せず、
    `{{WEAVE_COMPACT:<guid>}}` プレースホルダを埋め込む。
    親プロセス Weave が dry-run 後にプレースホルダを書き換える前提。
    """

    def execute(
        self,
        *,
        target_date: str,
        items: Iterable[NewsItem],
        feed_sources: Sequence[FeedSource],
    ) -> DailyDigest:
        items_tuple = tuple(items)
        count = len(items_tuple)

        items_by_source: dict[str, list[NewsItem]] = defaultdict(list)
        for item in items_tuple:
            items_by_source[item.source_name].append(item)
        source_count = sum(
            1 for fs in feed_sources if items_by_source.get(fs.name)
        )

        subject = (
            f"[NewsCaster] {target_date} のダイジェスト "
            f"({count}件 / {source_count}ソース)"
        )

        if count == 0:
            body = (
                f"# {target_date} のニュースダイジェスト\n\n"
                "前日付の新着エントリはありませんでした。\n"
            )
            return DailyDigest(
                target_date=target_date,
                items=items_tuple,
                formatted_subject=subject,
                formatted_body=body,
            )

        body_parts: list[str] = [
            f"# {target_date} のニュースダイジェスト（{count}件 / {source_count}ソース）\n"
        ]
        for fs in feed_sources:
            section_items = items_by_source.get(fs.name, [])
            if not section_items:
                continue
            body_parts.append(f"## {fs.name}（{len(section_items)}件）\n")
            for item in section_items:
                cats = " / ".join(item.categories) if item.categories else "-"
                header = (
                    f"### {item.title}\n"
                    f"- 公開: {item.pub_date_jst.strftime('%Y-%m-%d %H:%M')} JST\n"
                    f"- カテゴリ: {cats}\n"
                    f"- リンク: {item.link}\n\n"
                )
                if fs.policy is FeedPolicy.WEAVE_COMPACT:
                    body_block = WEAVE_COMPACT_PLACEHOLDER % item.guid + "\n"
                else:
                    body_block = f"{item.description}\n"
                body_parts.append(header + body_block)

        body = "\n".join(body_parts)

        return DailyDigest(
            target_date=target_date,
            items=items_tuple,
            formatted_subject=subject,
            formatted_body=body,
        )
