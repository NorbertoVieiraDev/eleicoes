# Sources and licensing

Primary dataset: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna

Catalog API: https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna

Retrieved 2026-11-01. Source catalog modification timestamp: 2026-10-27T19:22:03.090436. License metadata: `cc-by`, title `Creative Commons Atribuição`, URL http://www.opendefinition.org/licenses/cc-by. The catalog does not specify a Creative Commons version; do not invent one. Original data retain the source license and require appropriate TSE attribution. MIT applies only to this project's code and original documentation.

Official technical documentation: https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados

Known source issue: the RR second-round BU link pointed to its `.zip.sha512` resource instead of the ZIP. The ZIP URL was obtained by removing `.sha512`; it downloaded successfully and matched the official checksum. Both URLs and the correction are retained in the round manifest.

Each source package includes its own `_leiame-boletimurnaweb.pdf`. Consult the matching year's readme and specifications before interpreting or adapting its fields. Historical catalogs, candidate registers, official result snapshots, country crosswalks and map sources have not yet been incorporated.
