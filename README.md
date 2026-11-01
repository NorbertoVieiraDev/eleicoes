# eleicoes

[English documentation](docs/en/README.md) · [Documentação em português](docs/pt-BR/README.md)

Open, reproducible exploration of Brazilian election data published by the **Tribunal Superior Eleitoral (TSE)**. Independent project; not affiliated with the TSE or any political party.

Exploração aberta e reproduzível dos dados eleitorais brasileiros publicados pelo **Tribunal Superior Eleitoral (TSE)**. Projeto independente, sem vínculo com o TSE ou partidos políticos.

## CSV → Parquet: transparency / transparência

[How the conversion works and how to verify it](docs/en/parquet-transparency.md) · [Como a conversão funciona e como conferir](docs/pt-BR/parquet-transparency.md)

[Historical BU collection and schema differences](docs/en/historical-data.md) · [Coleta histórica e diferenças de formato](docs/pt-BR/historical-data.md)

## Current scope / Escopo atual

- **2026:** both rounds, 27 Brazilian UFs and overseas voting (ZZ); 56 published BU CSV ZIP packages downloaded and SHA-512 verified locally.
- **2026:** dois turnos, 27 UFs e exterior (ZZ); 56 pacotes ZIP de CSV de BU baixados e verificados localmente por SHA-512.
- The 2026 local query base is prepared; independent section-roster and official-total reconciliation remain pending. Historical elections and the interactive website are planned, not yet delivered.
- Base local de consulta de 2026 preparada; conciliação independente de seções e totais oficiais ainda pendente. Eleições históricas e site interativo estão planejados, ainda não entregues.

## Layout / Organização

```text
data/
  2026/
    round-1/   # manifests and local raw/ downloads
    round-2/
  README.md   # rules for adding historical elections
docs/
  en/
  pt-BR/
scripts/      # public, reproducible download and preparation
reports/      # aggregate validation evidence; no private paths
tests/        # synthetic data tests
```

Future elections use `data/<year>/round-<number>/`. Do not assume every election has two rounds or the same columns. Event/election identifiers distinguish simultaneous ordinary, supplementary and consultation contests.

Eleições futuras usam `data/<ano>/round-<número>/`. Nem toda eleição tem dois turnos ou as mesmas colunas. Identificadores de pleito/eleição distinguem disputas ordinárias, suplementares e consultas simultâneas.

## Quick start / Início rápido

Python 3.9+ and `curl` are required. / Requer Python 3.9+ e `curl`.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/download.py --year 2026
python scripts/prepare.py --year 2026
python -m unittest discover -s tests -v
```

The full 2026 download is approximately **5.22 GB**; source CSVs total **32.42 GB** uncompressed. Preparation temporarily expands one package at a time and produces additional Parquet files. Reserve at least 60 GB free for source, derived data and temporary work; actual requirements depend on the largest package and spill usage. Raw packages remain unchanged and excluded from Git. Download scripts do not require credentials.

O download completo de 2026 tem aproximadamente **5,22 GB**; os CSVs somam **32,42 GB** descompactados. A preparação expande temporariamente um pacote por vez e gera arquivos Parquet adicionais. Reserve pelo menos 60 GB livres para originais, derivados e trabalho temporário; a necessidade real depende do maior pacote e do uso de disco temporário. Pacotes originais ficam intactos e fora do Git. O download não exige credenciais.

## Sources and limits / Fontes e limites

- [Official BU data / Dados oficiais de BU](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna)
- [Official technical documentation / Documentação técnica oficial](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados)

Package checksums validate the downloaded bytes against the published hashes. They do not verify urn digital signatures, completeness of every expected electoral section, or legal totalization. See [methodology](docs/en/methodology.md) / [metodologia](docs/pt-BR/methodology.md).

Hashes conferem os bytes baixados contra os valores publicados. Não verificam assinaturas digitais da urna, presença de todas as seções esperadas ou totalização jurídica. Consulte os limites na metodologia.

## Public repository policy / Política do repositório público

Publish source code, bilingual documentation, official source manifests and aggregate reports. Never commit passwords, tokens, connection strings, private hostnames, production configuration, infrastructure definitions, local execution logs or large datasets. The repository is intended for public reuse; it does not yet provide a hosted dashboard or bundled national dataset.

Publicar código, documentação bilíngue, manifestos das fontes oficiais e relatórios agregados. Nunca versionar senhas, tokens, conexões, endereços privados, configuração de produção, definições de infraestrutura, logs locais ou bases grandes. O objetivo é permitir reutilização pública; ainda não há dashboard hospedado ou base nacional empacotada para download neste repositório.

License: code and original documentation use [MIT](LICENSE). TSE source data retain their own attribution license; see [data provenance](docs/en/sources.md) / [proveniência](docs/pt-BR/sources.md).
