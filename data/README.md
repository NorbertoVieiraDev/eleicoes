# Data by election / Dados por eleição

English: use `data/<year>/round-<number>/manifest.json`. Each resource includes its official HTTPS URL, source package name, SHA-512, byte size and ZIP members. Keep raw downloads in the ignored `raw/` subdirectory. Shared reference data, when acquired, belong under `data/reference/` with source date and license. Do not put credentials or infrastructure here.

Português: use `data/<ano>/round-<número>/manifest.json`. Cada recurso inclui URL HTTPS oficial, nome, SHA-512, tamanho e conteúdo do ZIP. Downloads originais ficam no subdiretório ignorado `raw/`. Referências compartilhadas, quando obtidas, ficam em `data/reference/`, com data da fonte e licença. Não guardar credenciais ou infraestrutura aqui.

## Historical elections / Eleições históricas

English: official results from 2000 onward are now inventoried and harmonized where available. See `data/catalog/legacy-results-2000-2010.json` and `reports/history/` for source inventory, checksums, conversion counts and field-level coverage. Elections from 2000–2010 are section-level totalized results; they do not identify individual voting machines. BU (polling-machine bulletin) files are available from 2012 onward in this collection. Missing elections/fields remain absent or NULL; no values are inferred. Rebuild local Parquet outputs with `scripts/download_legacy_results.py` and `scripts/normalize_history.py`; generated bulk archives and Parquets are intentionally excluded from Git.

Português: os resultados oficiais disponíveis de 2000 em diante foram inventariados e harmonizados. Consulte `data/catalog/legacy-results-2000-2010.json` e `reports/history/` para o inventário das fontes, checksums, contagens da conversão e cobertura por campo. De 2000 a 2010, os arquivos trazem resultados totalizados por seção; não identificam urnas individuais. Nesta coleção, os arquivos de BU (boletim de urna) estão disponíveis a partir de 2012. Eleições/campos ausentes continuam ausentes ou NULL; nenhum valor é inferido. Recrie localmente os Parquet com `scripts/download_legacy_results.py` e `scripts/normalize_history.py`; os arquivos brutos e Parquet gerados ficam fora do Git.
