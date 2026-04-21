## Examples

Use the bundled demo fixture to evaluate autoshelf without customer data.

Generate the fixture:

```bash
python examples/fixtures/generate_demo.py /tmp/autoshelf-demo
```

Run a full local evaluation loop:

```bash
python -m autoshelf doctor /tmp/autoshelf-demo
python -m autoshelf plan /tmp/autoshelf-demo
python -m autoshelf preview /tmp/autoshelf-demo
python -m autoshelf apply /tmp/autoshelf-demo
python -m autoshelf verify /tmp/autoshelf-demo
```

The fixture includes:

- Mixed business, study, screenshot, and duplicate-content files.
- A sample `.autoshelfrc.yaml` with pinned folders, exclusions, and a finance mapping.
- `fixture-manifest.json` so support or QA can confirm the generated corpus shape.
