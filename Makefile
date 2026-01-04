default: test

.PHONY: test python-test

test:
	@npm test

python-test:
	@PYTHONWARNINGS="ignore:::fastapi.routing,ignore:::starlette._utils,ignore:::anyio._backends._asyncio" python -m unittest discover -s tests/python -p 'test_*.py'
