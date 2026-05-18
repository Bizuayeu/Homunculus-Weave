"""通常実行（pytest 非経由）での import 動作を検証する。

conftest.py は pytest 起動時のみ実行されるため、Skill として直接呼び出すケース
（Claude が `python -c '...'` で実行する等）では `__init__.py` 側の bootstrap が
担保となる。この経路を subprocess で外部 Python プロセスとして実行し検証する。
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

PRECOGNITIVE_ROOT = Path(__file__).parent.parent
EXPERTISES_DIR = PRECOGNITIVE_ROOT.parent


def _run_standalone(script: str) -> subprocess.CompletedProcess:
    """conftest.py を読み込まない外部 Python プロセスでスクリプトを実行する"""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8"},
    )


def test_standalone_seimei_usecase_import() -> None:
    """通常実行（pytest 非経由）で SeimeiAssessmentUseCase が動作する"""
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, r'{EXPERTISES_DIR}')
        from PrecognitiveViewer.Report.seimei_usecase import SeimeiAssessmentUseCase
        result = SeimeiAssessmentUseCase().assess('山田', '太郎', [3, 5], [4, 9])
        assert '七格' in result, '七格 missing'
        assert '人材4類型' in result, '人材4類型 missing'
        print('SEIMEI_OK')
    """)
    proc = _run_standalone(script)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "SEIMEI_OK" in proc.stdout


def test_standalone_iching_usecase_import() -> None:
    """通常実行で IChingDivinationUseCase が動作する"""
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, r'{EXPERTISES_DIR}')
        from PrecognitiveViewer.Report.iching_usecase import IChingDivinationUseCase
        result = IChingDivinationUseCase().divine('test', 'ctx')
        assert '得卦' in result, '得卦 missing'
        assert '得爻' in result, '得爻 missing'
        print('ICHING_OK')
    """)
    proc = _run_standalone(script)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "ICHING_OK" in proc.stdout


def test_standalone_full_pipeline() -> None:
    """通常実行で三占術 → 鑑定書生成の全工程が動作する"""
    script = textwrap.dedent(f"""
        import sys
        from datetime import datetime
        sys.path.insert(0, r'{EXPERTISES_DIR}')

        from PrecognitiveViewer.Report.composer_usecase import ReadingReportComposerUseCase
        from PrecognitiveViewer.Report.domain import Recipient
        from PrecognitiveViewer.Report.filename import ReportFilenameGenerator
        from PrecognitiveViewer.Report.iching_usecase import IChingDivinationUseCase
        from PrecognitiveViewer.Report.presenter import ReadingReportPresenter
        from PrecognitiveViewer.Report.seimei_usecase import SeimeiAssessmentUseCase
        from PrecognitiveViewer.Report.tarot_usecase import TarotReadingUseCase
        from PrecognitiveViewer.Report.triple_divination import TripleDivinationUseCase

        seimei = SeimeiAssessmentUseCase().assess('青羽', 'つむぐ', [8, 6], [1, 3, 4])
        iching = IChingDivinationUseCase().divine('本質を観たい', '人物リーディング')
        tarot = TarotReadingUseCase().read('', 'プロファイリング', 'person_reading')
        triplet = TripleDivinationUseCase().synthesize(seimei, iching, tarot)
        recipient = Recipient(full_name='青羽 つむぐ', reading='あおば つむぐ')
        ts = datetime(2026, 5, 18, 10, 47, 59)
        report = ReadingReportComposerUseCase().compose(triplet, recipient, ts)
        markdown = ReadingReportPresenter().render(report)
        filename = ReportFilenameGenerator.generate(ts)

        assert filename == 'ReadingReport_20260518_104759.md'
        assert '青羽 つむぐ' in markdown
        assert '第' in markdown  # 章節がレンダリングされている
        print('FULL_OK')
    """)
    proc = _run_standalone(script)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "FULL_OK" in proc.stdout


def test_init_is_idempotent() -> None:
    """__init__.py が複数回 import されても sys.path に重複追加されない"""
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, r'{EXPERTISES_DIR}')
        import PrecognitiveViewer
        # 重複 import
        import PrecognitiveViewer
        import PrecognitiveViewer

        # Seimei への path がちょうど 1 回だけ追加されている
        seimei_path = r'{PRECOGNITIVE_ROOT / "Seimei"}'
        count = sum(1 for p in sys.path if p == seimei_path)
        assert count == 1, f'Seimei が {{count}} 回追加されている'
        print('IDEMPOTENT_OK')
    """)
    proc = _run_standalone(script)
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "IDEMPOTENT_OK" in proc.stdout
