"""Smoke tests — verificam que o esqueleto do projeto funciona."""

from pathlib import Path

from pipeline.parsers.base import ParsedRecord, SourceParser


def test_parsed_record_creation(sample_parsed_record: ParsedRecord) -> None:
    """ParsedRecord pode ser instanciado com dados sintéticos."""
    assert sample_parsed_record.issn == "1234-5678"
    assert sample_parsed_record.metricas["sjr_quartil"] == "Q1"


def test_parsed_record_minimal(sample_parsed_record_minimal: ParsedRecord) -> None:
    """ParsedRecord funciona com campos opcionais como None."""
    assert sample_parsed_record_minimal.issn_alt is None
    assert sample_parsed_record_minimal.doi is None
    assert sample_parsed_record_minimal.titulo is None


def test_sources_yml_exists(sources_yml_path: Path) -> None:
    """sources.yml existe na raiz do monorepo."""
    assert sources_yml_path.exists()


def test_areas_dir_has_json(areas_dir: Path) -> None:
    """Diretório areas/ contém pelo menos um arquivo JSON."""
    json_files = list(areas_dir.glob("*.json"))
    assert len(json_files) >= 2


def test_source_parser_protocol() -> None:
    """SourceParser é um Protocol — classes conformes são importáveis."""
    assert hasattr(SourceParser, "source_id")
    assert hasattr(SourceParser, "provides")
    assert hasattr(SourceParser, "parse")


def test_gitignore_covers_local_yml(repo_root: Path) -> None:
    """.gitignore deve conter regra para config/local.yml."""
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "config/local.yml" in gitignore


def test_config_example_exists(repo_root: Path) -> None:
    """config/local.yml.example deve existir como template."""
    assert (repo_root / "config" / "local.yml.example").exists()
