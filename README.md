# eleicoes

[English documentation](docs/en/README.md) · [Documentação em português](docs/pt-BR/README.md)

Open, reproducible exploration of Brazilian election data published by the **Tribunal Superior Eleitoral (TSE)**. Independent project; not affiliated with the TSE or any political party.

Exploração aberta e reproduzível dos dados eleitorais brasileiros publicados pelo **Tribunal Superior Eleitoral (TSE)**. Projeto independente, sem vínculo com o TSE ou partidos políticos.

## CSV → Parquet: transparency / transparência

[How the conversion works and how to verify it](docs/en/parquet-transparency.md) · [Como a conversão funciona e como conferir](docs/pt-BR/parquet-transparency.md)

[Historical BU collection and schema differences](docs/en/historical-data.md) · [Coleta histórica e diferenças de formato](docs/pt-BR/historical-data.md)

## Current scope / Escopo atual

- **Historical BU files:** the TSE catalog snapshot contains 425 tabular ZIP packages across regular election cycles 2012–2026 and supplementary contests. All 425 were downloaded and converted locally into 466 Parquet member files (420,378,316 rows; approximately 5.66 GB). Original ZIPs and Parquets are excluded from Git; public package-level evidence is in [`reports/history/conversion-records.json`](reports/history/conversion-records.json).
- **Arquivos históricos de BU:** o retrato do catálogo do TSE contém 425 pacotes ZIP tabulares dos ciclos regulares de 2012 a 2026 e eleições suplementares. Os 425 foram baixados e convertidos localmente em 466 arquivos Parquet (420.378.316 linhas; cerca de 5,66 GB). Os ZIPs e Parquets originais ficam fora do Git; as evidências por pacote estão em [`reports/history/conversion-records.json`](reports/history/conversion-records.json).
- **Cross-election canonical data:** 170 TSE ZIP resources from 2000–2010 were integrity-checked and normalized alongside BU records for 2012, 2014, 2016, 2018, 2020, 2022, 2024 and 2026. This produced 637,673,681 vote rows and 16,849,380 section/urn summary rows in 28 canonical Parquet files (about 4.14 GB), now served by the [public election portal](https://estatisticasbrasil.com.br/eleicoes/). Results from 2000–2010 are only at section level and do not contain urn numbers. See [`reports/history/normalization-report.json`](reports/history/normalization-report.json) and the field-level [`coverage audit`](reports/history/canonical-coverage.json); its SHA-512 values were verified against each stored object. All downloaded source ZIPs and derived Parquets are excluded from Git.
- **Base histórica unificada:** 170 pacotes ZIP do TSE de 2000–2010 foram verificados e padronizados junto com os BUs de 2012, 2014, 2016, 2018, 2020, 2022, 2024 e 2026. O resultado tem 637.673.681 linhas de votos e 16.849.380 linhas de totais por seção/urna em 28 arquivos Parquet canônicos (cerca de 4,14 GB), agora servidos pelo [portal público de eleições](https://estatisticasbrasil.com.br/eleicoes/). Os resultados de 2000–2010 só chegam ao nível de seção e não incluem número da urna. Consulte [`reports/history/normalization-report.json`](reports/history/normalization-report.json) e a [auditoria de disponibilidade por campo](reports/history/canonical-coverage.json); os SHA-512 foram conferidos contra cada objeto armazenado. ZIPs e Parquets ficam fora do Git.
- The 2026 analytical query base is prepared. Independent expected-section and official-total reconciliation remain pending.
- A base analítica de consulta de 2026 está preparada. Ainda falta conciliar com cadastro independente de seções e totais oficiais.

## Layout / Organização

```text
data/
  <catalog-year>/
    round-1/       # manifests and local raw/ downloads
    round-2/
    supplementary/ # where published by the TSE catalog
  README.md        # rules for adding historical elections
derived/history/  # local source-layout Parquets; ignored by Git
derived/canonical/ # local cross-election BI tables and coverage audit; ignored by Git
docs/
  en/
  pt-BR/
scripts/      # public, reproducible download and preparation
reports/      # aggregate validation evidence; no private paths
tests/        # synthetic data tests
```

Election files use `data/<catalog-year>/round-<number>/` or `supplementary/`. Do not assume every election has two rounds or the same columns. Event/election identifiers distinguish simultaneous ordinary, supplementary and consultation contests.

Os arquivos usam `data/<ano-catalogo>/round-<número>/` ou `supplementary/`. Nem toda eleição tem dois turnos ou as mesmas colunas. Identificadores de pleito/eleição distinguem disputas ordinárias, suplementares e consultas simultâneas.

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

Publish source code, bilingual documentation, official source manifests and aggregate reports. Never commit passwords, tokens, connection strings, private hostnames, production configuration, infrastructure definitions, local execution logs or large datasets. The public portal is hosted separately and retrieves canonical files from private object storage; this repository publishes the reproducible processing method, source manifests, aggregate reports and checksums.

Publicar código, documentação bilíngue, manifestos das fontes oficiais e relatórios agregados. Nunca versionar senhas, tokens, conexões, endereços privados, configuração de produção, definições de infraestrutura, logs locais ou bases grandes. O portal público é hospedado separadamente e obtém os arquivos canônicos do armazenamento privado de objetos; este repositório publica o método reproduzível de processamento, manifestos das fontes, relatórios agregados e checksums.

License: code and original documentation use [MIT](LICENSE). TSE source data retain their own attribution license; see [data provenance](docs/en/sources.md) / [proveniência](docs/pt-BR/sources.md).
