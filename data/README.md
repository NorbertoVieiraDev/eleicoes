# Data by election / Dados por eleição

English: use `data/<year>/round-<number>/manifest.json`. Each resource includes its official HTTPS URL, source package name, SHA-512, byte size and ZIP members. Keep raw downloads in the ignored `raw/` subdirectory. Shared reference data, when acquired, belong under `data/reference/` with source date and license. Do not put credentials or infrastructure here.

Português: use `data/<ano>/round-<número>/manifest.json`. Cada recurso inclui URL HTTPS oficial, nome, SHA-512, tamanho e conteúdo do ZIP. Downloads originais ficam no subdiretório ignorado `raw/`. Referências compartilhadas, quando obtidas, ficam em `data/reference/`, com data da fonte e licença. Não guardar credenciais ou infraestrutura aqui.

## Historical elections / Eleições históricas

English: create folders only when their source catalogs have been inspected; an empty folder must not imply available data. Planned initial backfill: 2024, 2022, 2020 and 2018. These years are not downloaded or validated yet. For each year, verify available rounds, the source schema and any event-specific rules; add a schema adapter and synthetic regression tests before processing. Only 2026 has a reviewed manifest and current adapter.

Português: criar pastas somente após inspecionar o catálogo da fonte; pastas vazias não devem sugerir dados disponíveis. Carga histórica inicialmente planejada: 2024, 2022, 2020 e 2018. Esses anos ainda não foram baixados ou validados. Para cada ano, conferir turnos disponíveis, estrutura e regras de cada pleito; adicionar adaptador e testes sintéticos antes de processar. Somente 2026 tem manifesto revisado e adaptador atual.
