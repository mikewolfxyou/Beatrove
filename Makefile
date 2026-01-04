default: test

.PHONY: test python-test

test:
	@npm test

python-test:
	@python -m unittest discover -s tests/python -p 'test_*.py'
