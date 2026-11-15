# Factory feed exporter

`export-factory-feed.py` writes the single JSON file the companion site reads for its Usage and KPIs modules.

It imports the advisor's own Python functions instead of recomputing any number. Set `ADVISOR_BIN` to the advisor's `bin` directory before running it.

```
ADVISOR_BIN=<advisor bin directory> python3 tools/export-factory-feed.py --out /tmp/factory-feed.json
```

It needs Python 3 and nothing else. Run it on the factory host, because the runners line reads live tmux state.

The file is written to a temp path and then renamed, so a crash never leaves half a feed. Two runs give the same file apart from `generatedAt`.

Before writing, the script checks the feed against the contract and refuses to write an invalid one. Missing input files give the feed's absent form and still exit 0. The script only reads the advisor's state; it never runs the advisor's writers.

The field contract is the `FactoryFeed` schema in `apps/web/src/content/feed.ts`.
