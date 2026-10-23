# 5. Публичное демо на Cloudflare

`web/` — полностью статический сайт, без секретов, базы и серверных функций. Он показывает только вымышленные данные из `web/data.json`. Чтобы обновить цифры, снова выполните `seed`, `load`, `export` и зафиксируйте обновлённый JSON в репозитории.

## Workers Static Assets из GitHub

Cloudflare Workers & Pages → Create application → Continue with GitHub → `badahyousr-collab/Data-Lab`. В корне репозитория лежит `wrangler.jsonc`: он задаёт имя `pipisso-data-lab` и каталог статических файлов `./web`. Код Worker не нужен.

- Production branch: `main`.
- Build command: пусто, сборка не требуется.
- Deploy command (если показан): `npx wrangler deploy`.
- Preview builds: можно выключить для первой публикации; включить позже, когда понадобятся предварительные сборки веток.
- Protect with Cloudflare Access: **выключено**, чтобы заказчик открыл демо без входа.
- Advanced settings: значения по умолчанию, без переменных, секретов и привязок.

После публикации открыть выданный `*.workers.dev` адрес в приватном окне, проверить фильтры и сравнить «Все категории» с `python -m datalab.cli report`. Публичную ссылку добавлять в README только после реального размещения и проверки. Собственный домен можно добавить позже.

Для локального просмотра: `python -m http.server 8000 --directory web`. Сайт не должен получать доступ к исходным заказам реального магазина.
