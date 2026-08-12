from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit(f"PyYAML is required for workflow validation: {exc}")

workflow = yaml.safe_load(Path('.github/workflows/render-video.yml').read_text(encoding='utf-8'))
assert workflow.get('name')
assert 'schedule' in workflow.get(True, workflow.get('on', {})) or 'schedule' in workflow.get('on', {})
assert workflow.get('concurrency', {}).get('cancel-in-progress') is False
assert 'produce' in workflow.get('jobs', {})
steps = workflow['jobs']['produce']['steps']
step_text = '\n'.join(str(step) for step in steps)
assert 'actions/upload-artifact@v4' in step_text
assert 'python python/automation_runner.py' in step_text
assert 'GEMINI_KEYS_JSON' in str(workflow['jobs']['produce'].get('env', {}))
print('workflow validation passed')
