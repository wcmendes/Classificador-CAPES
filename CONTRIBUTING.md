# Contributing to NoQualis

Thank you for your interest in improving NoQualis! This guide covers the two most
common contribution types: adding a new CAPES evaluation area and adding a new
data-source parser.

> **Nota em português:** contribuições em português são bem-vindas nos Issues e PRs.
> Código e documentação técnica devem seguir as convenções já existentes no repositório.

---

## 1. Contributing an Area

Each CAPES evaluation area is defined as a single JSON file in `areas/`. To add a
new area:

### Step-by-step

1. **Copy a reference file** — Use `areas/area02-computacao.json` or
   `areas/area27-administracao.json` as a starting template.

2. **Create your area file** — Name it `areas/area<NN>-<slug>.json` where `<NN>`
   is the two-digit CAPES area code and `<slug>` is a lowercase ASCII identifier
   (e.g., `area31-educacao.json`).

3. **Validate against the schema** — Run:
   ```bash
   python -m pipeline validate areas/area<NN>-<slug>.json
   ```
   The file must conform to `schema/area.schema.json`. Fix all errors before
   submitting.

4. **Test with `classify()`** — Run the classification engine against synthetic
   data to verify your rules produce the expected strata:
   ```bash
   pytest pipeline/tests/ -k "area<NN>"
   ```

5. **Submit a Pull Request** — One area per PR, never group multiple areas.
   Include in the PR description:
   - Link to the official CAPES ficha/documento de área used as source.
   - Any items marked `[INCERTO]` that require further verification.

### Conventions

- Metrics referenced in rules must exist in the `provides` field of at least one
  source in `sources.yml`.
- Use the exact metric canonical names already defined in the project.
- Set `status: "experimental"` until the area rules have been validated against
  the official ficha.

---

## 2. Contributing a Parser

Parsers extract data from bibliometric sources. Each parser implements the
`SourceParser` protocol defined in `pipeline/parsers/base.py`.

### Step-by-step

1. **Create a new file** — `pipeline/parsers/<source_id>.py`
   (e.g., `pipeline/parsers/sjr.py`).

2. **Implement the `SourceParser` interface**:
   ```python
   from pipeline.parsers.base import SourceParser, ParsedRecord
   from typing import Iterator

   class SjrParser:
       @property
       def source_id(self) -> str:
           return "sjr"

       @property
       def provides(self) -> list[str]:
           return ["sjr_quartil"]

       def parse(self, path: str) -> Iterator[ParsedRecord]:
           # Yield one ParsedRecord per journal/venue found in the file
           ...
   ```

3. **Test with synthetic data** — Create a minimal test fixture in
   `pipeline/tests/` and write tests confirming the parser yields correct
   `ParsedRecord` instances.

4. **Submit a Pull Request** — **One parser per PR, never group multiple
   parsers.** Include in the PR description:
   - The source this parser handles.
   - Whether the source is `livre` or `restrita` in `sources.yml`.
   - Sample output from running against test data.

### Rules

- Parsers MUST NOT normalize ISSNs — that is the pipeline's responsibility.
- Parsers MUST NOT access the network — they read local files only.
- One parser = one PR. This makes review manageable and keeps history clean.

---

## 3. Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Be respectful, constructive, and inclusive.

---

## 4. Reporting Issues

- **Bugs**: Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md).
  Include steps to reproduce, expected vs. actual behavior, and your environment.
- **Feature requests**: Use the
  [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md).
  Describe the use case and how it fits the project goals.
- **Classification discrepancies**: If a verdict differs from the official ficha,
  open an Issue with the ISSN, area, expected stratum, and the source document
  page/section.

---

## General Guidelines

- Run `pytest pipeline/tests/` before submitting any PR.
- Keep commits focused — one logical change per commit.
- Write commit messages in English, present tense, imperative mood.
- PRs that break existing tests will not be merged.
