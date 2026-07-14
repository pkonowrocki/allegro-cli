# Graph Report - .  (2026-07-14)

## Corpus Check
- Corpus is ~12,740 words - fits in a single context window. You may not need a graph.

## Summary
- 283 nodes · 628 edges · 26 communities (18 shown, 8 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- API Client & Browser
- Mock Client & Test Infra
- CLI Entry & E2E Tests
- Cart Commands
- Argument Parser & CLI Tests
- Offer Page Scraper
- Search Scraper & Pagination
- Data Models
- LLM Agent Integration
- HTML Parsing Utilities
- Test Fixtures & Docs
- Lazy Parameter Extraction
- Auth & Bot Bypass
- CI Release Pipeline
- CI Workflow
- Allegro Smart
- Config Module
- Package Meta
- Cart Command Docs
- Offer Command Docs
- Packages Command Docs
- Search Command Docs

## God Nodes (most connected - your core abstractions)
1. `AllegroClient` - 41 edges
2. `main()` - 34 edges
3. `parse_offer_page()` - 27 edges
4. `create_parser()` - 26 edges
5. `parse_search_results()` - 23 edges
6. `Config` - 20 edges
7. `_run_cli()` - 14 edges
8. `MockAllegroClient` - 13 edges
9. `AllegroCliError` - 13 edges
10. `load_config()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Compact JSON Output Pattern for Agents` --semantically_similar_to--> `--compact Flag for Token Efficiency`  [INFERRED] [semantically similar]
  skills/allegro-cli/SKILL.md → AI_INTEGRATION.md
- `test_search_result_dataclass()` --calls--> `SearchResult`  [EXTRACTED]
  tests/test_scraper.py → allegro_cli/api/models.py
- `test_search_result_no_next()` --calls--> `SearchResult`  [EXTRACTED]
  tests/test_scraper.py → allegro_cli/api/models.py
- `test_parser_cart_add()` --calls--> `create_parser()`  [EXTRACTED]
  tests/test_cli.py → allegro_cli/main.py
- `test_parser_cart_list()` --calls--> `create_parser()`  [EXTRACTED]
  tests/test_cli.py → allegro_cli/main.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Agent-Friendly Output Pipeline: compact flag + JSON errors + tools.json schemas** — ai_integration_compactflag, ai_integration_stderrjsonerrors, ai_integration_toolsjson, skills_allegrocli_skill_compactoutput [INFERRED 0.85]
- **Scraper + HTML Fixtures + Mock Client form the offline testing infrastructure** — claude_scraper, claude_mockclient, tests_fixtures_offer_page_html_offerpage, tests_fixtures_search_results_html_searchresultsfixture, tests_fixtures_search_empty_html_emptyfixture [INFERRED 0.85]
- **CI + Bump & Release + PyPI Publish form the automated release pipeline** — _github_workflows_ci_ciworkflow, _github_workflows_bump_bumprelease, _github_workflows_bump_commitizen, _github_workflows_bump_pypi_publish [EXTRACTED 0.95]

## Communities (26 total, 8 thin omitted)

### Community 0 - "API Client & Browser"
Cohesion: 0.12
Nodes (14): AllegroClient, Fetch and parse a single offer page by ID., Fetch lazy-loaded parameter groups via the opbox API., Completely remove an item from the cart using its unique item ID., Fetch the detailed list of current packages., AllegroCliError, AuthenticationError, CartError (+6 more)

### Community 1 - "Mock Client & Test Infra"
Cohesion: 0.12
Nodes (22): MockAllegroClient, MockResponse, Any, A version of AllegroClient that reads responses from local JSON fixtures     ins, handle_login(), Config, ensure_dirs(), load_config() (+14 more)

### Community 2 - "CLI Entry & E2E Tests"
Cohesion: 0.11
Nodes (33): cli(), main(), _mock_config(), End-to-end tests exercising the full CLI pipeline with fixture HTML., URL should contain /kategoria/-{id} when --category is numeric., --category laptopy-491 extracts numeric ID., URL should contain order= param when --sort is set., URL should contain price_from and price_to params. (+25 more)

### Community 3 - "Cart Commands"
Cohesion: 0.17
Nodes (23): _flatten_cart_items(), handle_cart_add(), handle_cart_list(), handle_cart_remove(), _output_cart(), Flatten nested cart groups/items into flat rows for table display., handle_config_set(), handle_config_show() (+15 more)

### Community 4 - "Argument Parser & CLI Tests"
Cohesion: 0.14
Nodes (25): create_parser(), ArgumentParser, Flags like --format work after the subcommand., test_parser_cart_add(), test_parser_cart_list(), test_parser_config_set_cookies(), test_parser_config_show(), test_parser_login() (+17 more)

### Community 5 - "Offer Page Scraper"
Cohesion: 0.09
Nodes (23): _extract_offer_id(), _extract_parameters_from_html(), _extract_parameters_from_json(), _extract_parameters_from_serialized_json(), parse_offer_page(), Extract parameters from <script data-serialize-box-id> JSON blocks.      Allegro, Extract product parameters from __NEXT_DATA__ JSON., Fallback: extract parameters from HTML tables or definition lists.      Allegro (+15 more)

### Community 6 - "Search Scraper & Pagination"
Cohesion: 0.17
Nodes (19): SearchResult, extract_lazy_contexts(), parse_next_page_url(), parse_search_results(), Extract lazy-load context entries from the initial HTML.      Allegro embeds ``<, test_search_command_outputs_json(), test_extract_lazy_contexts(), test_extract_lazy_contexts_empty() (+11 more)

### Community 7 - "Data Models"
Cohesion: 0.41
Nodes (11): Category, DeliveryInfo, Image, Offer, Price, Seller, SellingMode, Stock (+3 more)

### Community 8 - "LLM Agent Integration"
Cohesion: 0.18
Nodes (12): --compact Flag for Token Efficiency, LLM Agent Integration Guide, MCP (Model Context Protocol) Server Wrapper, Structured JSON Errors on stderr for Agent Self-Correction, agent_specs/tools.json Function Schemas, Rich Tables & Custom Exception Hierarchy (v0.5.0), skill Command (v0.7.0), Output Module (allegro_cli/output.py) (+4 more)

### Community 9 - "HTML Parsing Utilities"
Cohesion: 0.18
Nodes (12): _clean_price(), _extract_image(), _extract_param_value(), _extract_params_from_table(), _extract_price(), _is_real_offer(), Filter out non-offer articles (category links, banners, etc.)., Normalise '1\xa0299,56\xa0zł' or '1 299.56 zł' → '1299.56'. (+4 more)

### Community 10 - "Test Fixtures & Docs"
Cohesion: 0.28
Nodes (9): Mock Client (allegro_cli/api/mock_client.py), Models & Exception Hierarchy (allegro_cli/api/models.py), Scraper (BeautifulSoup + lxml + __NEXT_DATA__), MockAllegroClient for Regression Prevention, __NEXT_DATA__ JSON Block in Offer Page, Offer Page HTML Fixture, Search Empty Results HTML Fixture, __NEXT_DATA__ JSON Block in Search Results (+1 more)

### Community 11 - "Lazy Parameter Extraction"
Cohesion: 0.25
Nodes (8): parse_opbox_parameters(), Recursively walk a JSON structure looking for parameter groups., Extract parameters from an opbox subtree JSON response., _walk_for_params(), Parameters buried deep in the opbox response tree., test_parse_opbox_parameters(), test_parse_opbox_parameters_empty(), test_parse_opbox_parameters_nested()

### Community 12 - "Auth & Bot Bypass"
Cohesion: 0.33
Nodes (6): CloakBrowser (Source-Patched Chromium), Cookie-Based Auth (no OAuth), Dual HTTP Stack (httpx + CloakBrowser), CLI Entry Point allegro_cli/main:cli, Bot Bypass via CloakBrowser (58+ C++ Fingerprint Patches), DataDome/Cloudflare Bot Detection Bypass

### Community 13 - "CI Release Pipeline"
Cohesion: 0.50
Nodes (4): Bump & Release Workflow, Commitizen Version Bumper, PyPI Publish Step, Conventional Commits + Commitizen Versioning

## Knowledge Gaps
- **17 isolated node(s):** `allegro-cli`, `PyPI Publish Step`, `CI Workflow`, `Python Version Matrix 3.10-3.13`, `Allegro Smart UX Feature (v0.7.0)` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AllegroClient` connect `API Client & Browser` to `Mock Client & Test Infra`, `CLI Entry & E2E Tests`, `Cart Commands`, `Search Scraper & Pagination`, `Data Models`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `main()` connect `CLI Entry & E2E Tests` to `API Client & Browser`, `Mock Client & Test Infra`, `Cart Commands`, `Argument Parser & CLI Tests`, `Search Scraper & Pagination`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `parse_opbox_parameters()` connect `Lazy Parameter Extraction` to `API Client & Browser`, `CLI Entry & E2E Tests`, `Search Scraper & Pagination`, `Data Models`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `AllegroClient` (e.g. with `AllegroCliError` and `AuthenticationError`) actually correct?**
  _`AllegroClient` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allegro-cli`, `PyPI Publish Step`, `CI Workflow` to the rest of the system?**
  _17 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `API Client & Browser` be split into smaller, more focused modules?**
  _Cohesion score 0.12063492063492064 - nodes in this community are weakly interconnected._
- **Should `Mock Client & Test Infra` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._